"""
Supplement-specific unit economics for Meta ad accounts.

Computes first-order CAC, break-even CAC, and LTV-adjusted contribution using
user-supplied cost assumptions and store data.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.growth_insights_common import (
    fetch_account_insights,
    load_store_economics,
    period_label,
    resolve_fb_client,
)
from services.profit_leak_scanner import (
    _is_prospect_campaign,
    _is_retarget_campaign,
)
from utils.logging_config import get_logger

logger = get_logger("supplement_economics")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "supplement_economics_config.json"


@dataclass
class SupplementEconomicsInputs:
    product_cost: float = 12.0
    shipping_cost: float = 5.0
    payment_fee_pct: float = 2.9
    payment_fee_fixed: float = 0.30
    avg_discount_pct: float = 15.0
    refund_rate_pct: float = 5.0
    subscription_share_pct: float = 25.0
    subscription_retention_60d_pct: float = 70.0
    repeat_purchase_rate_90d_pct: float = 35.0
    avg_order_value: float = 48.0
    gross_margin_pct: float = 55.0
    ltv_multiplier_60d: float = 1.35
    ltv_multiplier_90d: float = 1.55

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SupplementEconomicsInputs":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def load_economics_config(account_id: str = "") -> SupplementEconomicsInputs:
    try:
        if _CONFIG_PATH.exists():
            raw = json.loads(_CONFIG_PATH.read_text())
            key = account_id or "default"
            block = raw.get(key) or raw.get("default") or {}
            return SupplementEconomicsInputs.from_dict(block)
    except Exception as exc:
        logger.warning(f"Could not load supplement economics config: {exc}")
    return SupplementEconomicsInputs()


def save_economics_config(inputs: SupplementEconomicsInputs, account_id: str = "") -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {}
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text())
        except Exception:
            data = {}
    key = account_id or "default"
    data[key] = inputs.to_dict()
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))


def _contribution_per_order(inputs: SupplementEconomicsInputs) -> float:
    discount_factor = 1 - inputs.avg_discount_pct / 100
    revenue = inputs.avg_order_value * discount_factor
    payment_fees = revenue * inputs.payment_fee_pct / 100 + inputs.payment_fee_fixed
    cogs = inputs.product_cost + inputs.shipping_cost + payment_fees
    net = revenue - cogs
    return net * (1 - inputs.refund_rate_pct / 100)


def _ltv_contribution(inputs: SupplementEconomicsInputs, days: int) -> float:
    first = _contribution_per_order(inputs)
    if days >= 90:
        return first * inputs.ltv_multiplier_90d
    return first * inputs.ltv_multiplier_60d


class SupplementEconomicsService:
    async def analyze_account(
        self,
        account_id: str,
        *,
        since: str,
        until: str,
        account_name: str = "",
        currency: str = "USD",
        inputs: Optional[SupplementEconomicsInputs] = None,
    ) -> Dict[str, Any]:
        fb = await resolve_fb_client()
        if not fb:
            return {"error": "Facebook Ads client is not configured.", "account_id": account_id}

        config = inputs or load_economics_config(account_id)
        payload = await fetch_account_insights(fb, account_id, since=since, until=until)
        store = load_store_economics(since, until)
        totals = payload["totals"]

        first_order_contribution = _contribution_per_order(config)
        contribution_60d = _ltv_contribution(config, 60)
        contribution_90d = _ltv_contribution(config, 90)
        break_even_cpa = first_order_contribution
        break_even_cpa_60d = contribution_60d
        break_even_cpa_90d = contribution_90d

        meta_cac = totals.get("cpa")
        store_cac = None
        if store.has_data and store.orders > 0 and totals.get("spend", 0) > 0:
            store_cac = round(totals["spend"] / store.orders, 2)

        campaign_rows = self._campaign_economics(
            payload["campaigns"],
            break_even_cpa,
            break_even_cpa_60d,
            break_even_cpa_90d,
        )
        mix = self._customer_mix(payload["campaigns"], totals)

        verdict = self._verdict(meta_cac, break_even_cpa, break_even_cpa_60d, break_even_cpa_90d)

        return {
            "account_id": account_id,
            "account_name": account_name or account_id,
            "currency": currency,
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "inputs": config.to_dict(),
            "metrics": {
                "ad_spend": totals.get("spend", 0),
                "meta_purchases": totals.get("conversions", 0),
                "first_order_cac": meta_cac,
                "store_blended_cac": store_cac,
                "first_order_contribution": round(first_order_contribution, 2),
                "break_even_cpa": round(break_even_cpa, 2),
                "break_even_cpa_60d": round(break_even_cpa_60d, 2),
                "break_even_cpa_90d": round(break_even_cpa_90d, 2),
                "contribution_margin_pct": round(
                    first_order_contribution / max(config.avg_order_value, 1) * 100, 1
                ),
                "refund_adjusted": True,
                "subscription_share_pct": config.subscription_share_pct,
            },
            "customer_mix": mix,
            "campaign_economics": campaign_rows,
            "verdict": verdict,
            "store_actuals": store.__dict__ if store.has_data else None,
        }

    async def analyze_all(
        self,
        *,
        since: str,
        until: str,
        account_id: Optional[str] = None,
        inputs: Optional[SupplementEconomicsInputs] = None,
    ) -> Dict[str, Any]:
        fb = await resolve_fb_client()
        if not fb:
            return {"error": "Facebook Ads client is not configured."}

        accounts = await fb.get_all_ad_accounts()
        if account_id:
            accounts = [a for a in accounts if a.get("id") == account_id]

        results = []
        for acc in accounts:
            acc_id = acc.get("id", "")
            cfg = inputs or load_economics_config(acc_id)
            results.append(
                await self.analyze_account(
                    acc_id,
                    since=since,
                    until=until,
                    account_name=acc.get("name", ""),
                    currency=acc.get("currency", "USD"),
                    inputs=cfg,
                )
            )

        primary = results[0] if results else {}
        return {
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "accounts": results,
            "metrics": primary.get("metrics", {}),
            "customer_mix": primary.get("customer_mix", {}),
            "campaign_economics": primary.get("campaign_economics", []),
            "verdict": primary.get("verdict", ""),
            "inputs": primary.get("inputs", {}),
            "account_id": account_id or "",
        }

    def _campaign_economics(
        self,
        campaigns: List[Dict[str, Any]],
        be_first: float,
        be_60: float,
        be_90: float,
    ) -> List[Dict[str, Any]]:
        rows = []
        for camp in campaigns:
            perf = camp["performance"]
            if perf["spend"] < 30:
                continue
            cpa = perf.get("cpa")
            if not cpa:
                continue
            rows.append(
                {
                    "campaign_id": camp["id"],
                    "campaign_name": camp["name"],
                    "spend": perf["spend"],
                    "conversions": perf["conversions"],
                    "cpa": cpa,
                    "roas": perf.get("roas", 0),
                    "vs_break_even": round(cpa - be_first, 2),
                    "vs_break_even_60d": round(cpa - be_60, 2),
                    "vs_break_even_90d": round(cpa - be_90, 2),
                    "status": self._cpa_status(cpa, be_first, be_60, be_90),
                    "segment": self._segment(camp["name"]),
                }
            )
        rows.sort(key=lambda r: r["spend"], reverse=True)
        return rows[:15]

    def _segment(self, name: str) -> str:
        if _is_retarget_campaign(name):
            return "retargeting"
        if _is_prospect_campaign(name):
            return "prospecting"
        return "other"

    def _cpa_status(self, cpa: float, be_first: float, be_60: float, be_90: float) -> str:
        if cpa <= be_first:
            return "profitable_first_order"
        if cpa <= be_60:
            return "acceptable_with_60d_ltv"
        if cpa <= be_90:
            return "acceptable_with_90d_ltv"
        return "uneconomical"

    def _customer_mix(self, campaigns: List[Dict[str, Any]], totals: Dict[str, Any]) -> Dict[str, Any]:
        retarget_spend = sum(
            c["performance"]["spend"] for c in campaigns if _is_retarget_campaign(c["name"])
        )
        prospect_spend = sum(
            c["performance"]["spend"] for c in campaigns if _is_prospect_campaign(c["name"])
        )
        total_spend = totals.get("spend", 0) or 1
        retarget_conv = sum(
            c["performance"]["conversions"] for c in campaigns if _is_retarget_campaign(c["name"])
        )
        total_conv = totals.get("conversions", 0) or 1
        return {
            "retargeting_spend_share_pct": round(retarget_spend / total_spend * 100, 1),
            "prospecting_spend_share_pct": round(prospect_spend / total_spend * 100, 1),
            "retargeting_conversion_share_pct": round(retarget_conv / total_conv * 100, 1),
            "note": (
                "High retargeting share may inflate reported efficiency — evaluate new-customer CPA separately."
                if retarget_spend / total_spend > 0.35
                else "Spend mix appears balanced between prospecting and retargeting heuristics."
            ),
        }

    def _verdict(
        self,
        cac: Optional[float],
        be_first: float,
        be_60: float,
        be_90: float,
    ) -> str:
        if cac is None:
            return "No attributed purchases in period — cannot judge acquisition economics."
        if cac <= be_first:
            return (
                f"First-order CAC ({cac:.2f}) is at or below break-even contribution ({be_first:.2f}). "
                "Scaling is reasonable if repeat/subscription assumptions hold."
            )
        if cac <= be_60:
            return (
                f"First-order CAC ({cac:.2f}) exceeds immediate break-even ({be_first:.2f}) but fits "
                f"60-day LTV contribution ({be_60:.2f}). Monitor subscription activation."
            )
        if cac <= be_90:
            return (
                f"CAC ({cac:.2f}) requires strong 90-day repeat behavior (break-even {be_90:.2f}). "
                "Do not scale without retention data."
            )
        return (
            f"CAC ({cac:.2f}) exceeds 90-day break-even ({be_90:.2f}). "
            "Paid media is likely uneconomical at current offer and creative mix."
        )


supplement_economics_service = SupplementEconomicsService()
