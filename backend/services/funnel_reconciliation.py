"""
Funnel and measurement reconciliation — Meta vs store outcomes.

Shows stage-by-stage funnel drop-off and purchase count discrepancies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.growth_insights_common import (
    fetch_account_insights,
    load_store_economics,
    period_label,
    resolve_fb_client,
)
from utils.logging_config import get_logger

logger = get_logger("funnel_reconciliation")


def _stage(
    name: str,
    label: str,
    count: int,
    prior_count: int,
    spend: float,
) -> Dict[str, Any]:
    rate_from_prior = round(count / prior_count * 100, 2) if prior_count > 0 else None
    return {
        "stage": name,
        "label": label,
        "count": count,
        "prior_stage_count": prior_count,
        "conversion_rate_pct": rate_from_prior,
        "spend_at_stage": round(spend, 2),
    }


class FunnelReconciliationService:
    async def reconcile_account(
        self,
        account_id: str,
        *,
        since: str,
        until: str,
        account_name: str = "",
        currency: str = "USD",
    ) -> Dict[str, Any]:
        fb = await resolve_fb_client()
        if not fb:
            return {"error": "Facebook Ads client is not configured.", "account_id": account_id}

        payload = await fetch_account_insights(fb, account_id, since=since, until=until)
        economics = load_store_economics(since, until)
        totals = payload["totals"]

        funnel = self._build_funnel_stages(totals)
        measurement = self._measurement_reconciliation(totals, economics)
        campaign_gaps = self._campaign_funnel_flags(payload["campaigns"])

        health_score = self._health_score(funnel, measurement)

        return {
            "account_id": account_id,
            "account_name": account_name or account_id,
            "currency": currency,
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "funnel_stages": funnel,
            "measurement": measurement,
            "campaign_flags": campaign_gaps,
            "health_score": health_score,
            "summary": self._summary(funnel, measurement),
            "totals": totals,
            "store_economics": economics.__dict__ if economics.has_data else None,
        }

    async def reconcile_all(
        self,
        *,
        since: str,
        until: str,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        fb = await resolve_fb_client()
        if not fb:
            return {"error": "Facebook Ads client is not configured."}

        accounts = await fb.get_all_ad_accounts()
        if account_id:
            accounts = [a for a in accounts if a.get("id") == account_id]

        results = []
        for acc in accounts:
            results.append(
                await self.reconcile_account(
                    acc.get("id", ""),
                    since=since,
                    until=until,
                    account_name=acc.get("name", ""),
                    currency=acc.get("currency", "USD"),
                )
            )

        primary = results[0] if results else {}
        return {
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "accounts": results,
            "funnel_stages": primary.get("funnel_stages", []),
            "measurement": primary.get("measurement", {}),
            "campaign_flags": primary.get("campaign_flags", []),
            "health_score": primary.get("health_score", 0),
            "summary": primary.get("summary", ""),
            "account_id": account_id or "",
        }

    def _build_funnel_stages(self, totals: Dict[str, Any]) -> List[Dict[str, Any]]:
        spend = totals.get("spend", 0)
        impressions = totals.get("impressions", 0)
        clicks = totals.get("link_clicks", 0)
        lpv = totals.get("landing_page_views", 0)
        atc = totals.get("add_to_carts", 0)
        checkout = totals.get("checkouts_initiated", 0)
        purchases = totals.get("conversions", 0)

        return [
            _stage("impressions", "Impressions", impressions, impressions, spend),
            _stage("link_clicks", "Link clicks", clicks, impressions, spend),
            _stage("landing_page_views", "Landing page views", lpv, clicks, spend),
            _stage("add_to_cart", "Add to cart", atc, lpv, spend),
            _stage("initiate_checkout", "Checkout started", checkout, atc, spend),
            _stage("purchase", "Meta purchases", purchases, checkout, spend),
        ]

    def _measurement_reconciliation(self, totals: Dict[str, Any], economics) -> Dict[str, Any]:
        meta_purchases = totals.get("conversions", 0)
        store_orders = economics.orders if economics.has_data else 0
        gap = meta_purchases - store_orders
        base = max(meta_purchases, store_orders, 1)
        gap_pct = round(abs(gap) / base * 100, 1)

        status = "aligned"
        if gap_pct >= 25:
            status = "major_gap"
        elif gap_pct >= 12:
            status = "moderate_gap"

        explanation = ""
        if not economics.has_data:
            explanation = (
                "Store order data is not available for this period. Connect daily_metrics "
                "to reconcile Meta purchases with paid orders."
            )
        elif gap > 0:
            explanation = (
                f"Meta reports {meta_purchases} purchases while the store recorded {store_orders} paid orders "
                f"({gap_pct:.0f}% gap). {abs(gap)} event(s) may be duplicated, outside the attribution window, "
                "or counted before payment completion."
            )
        elif gap < 0:
            explanation = (
                f"Store recorded {store_orders} paid orders while Meta reports {meta_purchases} purchases "
                f"({gap_pct:.0f}% gap). Platform may be under-attributing — avoid cutting spend on Meta CPA alone."
            )
        else:
            explanation = "Meta purchases and store orders align for this period."

        return {
            "meta_purchases": meta_purchases,
            "store_orders": store_orders,
            "gap": gap,
            "gap_pct": gap_pct,
            "status": status,
            "explanation": explanation,
            "revenue": round(economics.revenue, 2) if economics.has_data else None,
            "store_ad_spend": round(economics.ad_spend, 2) if economics.has_data else None,
        }

    def _campaign_funnel_flags(self, campaigns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flags = []
        for camp in campaigns:
            perf = camp["performance"]
            if perf["spend"] < 50:
                continue
            issues = []
            if perf["link_clicks"] >= 20 and perf["click_to_purchase_rate"] < 1.5:
                issues.append("weak_click_to_purchase")
            if perf["landing_page_views"] >= 15 and perf["lpv_to_atc_rate"] < 5:
                issues.append("weak_lpv_to_atc")
            if perf["add_to_carts"] >= 8 and perf["atc_to_checkout_rate"] < 40:
                issues.append("weak_cart_to_checkout")
            if not issues:
                continue
            flags.append(
                {
                    "campaign_id": camp["id"],
                    "campaign_name": camp["name"],
                    "spend": perf["spend"],
                    "issues": issues,
                    "click_to_purchase_rate": perf["click_to_purchase_rate"],
                    "lpv_to_atc_rate": perf["lpv_to_atc_rate"],
                    "atc_to_checkout_rate": perf["atc_to_checkout_rate"],
                }
            )
        flags.sort(key=lambda f: f["spend"], reverse=True)
        return flags[:10]

    def _health_score(self, funnel: List[Dict[str, Any]], measurement: Dict[str, Any]) -> int:
        score = 100
        rates = [s.get("conversion_rate_pct") for s in funnel[1:] if s.get("conversion_rate_pct") is not None]
        for rate in rates:
            if rate < 15:
                score -= 12
            elif rate < 30:
                score -= 6
        if measurement.get("status") == "major_gap":
            score -= 25
        elif measurement.get("status") == "moderate_gap":
            score -= 12
        return max(0, min(100, score))

    def _summary(self, funnel: List[Dict[str, Any]], measurement: Dict[str, Any]) -> str:
        parts = []
        purchase_stage = next((s for s in funnel if s["stage"] == "purchase"), None)
        if purchase_stage and purchase_stage.get("conversion_rate_pct") is not None:
            parts.append(
                f"Checkout-to-purchase rate is {purchase_stage['conversion_rate_pct']:.1f}%."
            )
        parts.append(measurement.get("explanation", ""))
        return " ".join(p for p in parts if p)


funnel_reconciliation_service = FunnelReconciliationService()
