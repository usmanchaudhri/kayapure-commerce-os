"""
Deterministic Profit Leak Scanner for supplement Meta ad accounts.

Computes metrics and comparisons first, then produces ranked findings with
evidence, confidence, and estimated monthly impact ranges. Optional LLM layer
explains findings; results persist to profit_leak_* tables.
"""

from __future__ import annotations

import re
import statistics
import uuid
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from utils.logging_config import get_logger

logger = get_logger("profit_leak_scanner")

CAMPAIGN_SCAN_INSIGHT_FIELDS = (
    "campaign_id,spend,impressions,clicks,cpc,ctr,cpm,reach,frequency,"
    "inline_link_clicks,actions,purchase_roas"
)

MIN_CAMPAIGN_SPEND = 50.0
MIN_AD_SPEND = 40.0
MIN_LINK_CLICKS_FUNNEL = 15
MIN_FUNNEL_EVENTS = 10
MIN_SPEND_FATIGUE = 75.0
MIN_CREATIVE_AGE_DAYS = 14

DISCOUNT_PATTERN = re.compile(
    r"\b(discount|sale|promo|coupon|bogo|%\s*off|percent\s*off|clearance)\b",
    re.IGNORECASE,
)
RETARGET_PATTERN = re.compile(
    r"\b(retarget|remarketing|existing|returning|warm|engaged|loyal)\b",
    re.IGNORECASE,
)
PROSPECT_PATTERN = re.compile(
    r"\b(prospect|acquisition|cold|tof|top[\s-]?of[\s-]?funnel|new[\s-]?customer)\b",
    re.IGNORECASE,
)

FUNNEL_ACTION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "landing_page_views": ("landing_page_view", "omni_landing_page_view"),
    "add_to_carts": ("add_to_cart", "omni_add_to_cart"),
    "checkouts_initiated": ("initiate_checkout", "omni_initiated_checkout"),
    "purchases": ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"),
}


@dataclass
class StoreEconomics:
    orders: int = 0
    revenue: float = 0.0
    ad_spend: float = 0.0
    cogs: float = 0.0
    shipping: float = 0.0
    net_profit: float = 0.0
    margin_percent: float = 0.0
    contribution_per_order: float = 0.0
    break_even_cpa: float = 0.0
    has_data: bool = False


@dataclass
class FindingEvidence:
    metric_name: str
    observed_value: float | int | str
    comparison_value: float | int | str | None = None
    comparison_label: str = ""
    entity_type: str = ""
    entity_id: str = ""
    entity_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "comparison_value": self.comparison_value,
            "comparison_label": self.comparison_label,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
        }


@dataclass
class ProfitLeakFinding:
    id: str
    category: str
    severity: str
    title: str
    diagnosis: str
    recommendation: str
    confidence: float
    estimated_impact_min: float
    estimated_impact_max: float
    entity_type: str
    entity_id: str
    entity_name: str
    evidence: List[FindingEvidence] = dc_field(default_factory=list)
    experiment: Dict[str, Any] = dc_field(default_factory=dict)
    caveats: List[str] = dc_field(default_factory=list)
    llm_explanation: str = ""
    llm_observed_facts: List[str] = dc_field(default_factory=list)
    llm_hypotheses: List[Dict[str, Any]] = dc_field(default_factory=list)
    llm_caveats: List[str] = dc_field(default_factory=list)
    llm_recommended_action: str = ""
    status: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "diagnosis": self.diagnosis,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 2),
            "estimated_impact_min": round(self.estimated_impact_min, 2),
            "estimated_impact_max": round(self.estimated_impact_max, 2),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "evidence": [e.to_dict() for e in self.evidence],
            "experiment": self.experiment,
            "caveats": self.caveats,
            "llm_explanation": self.llm_explanation,
            "llm_observed_facts": self.llm_observed_facts,
            "llm_hypotheses": self.llm_hypotheses,
            "llm_caveats": self.llm_caveats,
            "llm_recommended_action": self.llm_recommended_action,
            "status": self.status,
        }


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _extract_conversions(actions: Any) -> int:
    return _extract_actions_sum(actions, *FUNNEL_ACTION_ALIASES["purchases"])


def _extract_roas(purchase_roas: Any) -> float:
    if isinstance(purchase_roas, list) and purchase_roas:
        return _safe_float(purchase_roas[0].get("value", 0))
    return 0.0


def _extract_actions_sum(actions: Any, *action_types: str) -> int:
    if not isinstance(actions, list):
        return 0
    wanted = set(action_types)
    total = 0
    for action in actions:
        action_type = action.get("action_type", "")
        if action_type in wanted:
            total += _safe_int(action.get("value", 0))
        elif any(action_type.endswith(suffix) for suffix in wanted if "." in suffix):
            total += _safe_int(action.get("value", 0))
    return total


def _extract_funnel_counts(actions: Any) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for key, aliases in FUNNEL_ACTION_ALIASES.items():
        counts[key] = _extract_actions_sum(actions, *aliases)
    return counts


def _rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _parse_campaign_performance(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return _empty_performance()

    spend = _safe_float(row.get("spend"))
    impressions = _safe_int(row.get("impressions"))
    clicks = _safe_int(row.get("clicks"))
    link_clicks = _safe_int(row.get("inline_link_clicks"))
    funnel = _extract_funnel_counts(row.get("actions"))
    conversions = funnel["purchases"] or _extract_conversions(row.get("actions"))
    roas = _extract_roas(row.get("purchase_roas"))
    lpv = funnel["landing_page_views"]
    atc = funnel["add_to_carts"]
    checkout = funnel["checkouts_initiated"]

    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "cpc": _safe_float(row.get("cpc")),
        "ctr": _safe_float(row.get("ctr")),
        "cpm": _safe_float(row.get("cpm")),
        "reach": _safe_int(row.get("reach")),
        "frequency": _safe_float(row.get("frequency")),
        "link_clicks": link_clicks,
        "landing_page_views": lpv,
        "add_to_carts": atc,
        "checkouts_initiated": checkout,
        "conversions": conversions,
        "roas": round(roas, 2),
        "cpa": round(spend / max(conversions, 1), 2) if conversions > 0 else None,
        "click_to_purchase_rate": _rate(conversions, link_clicks),
        "lpv_to_atc_rate": _rate(atc, lpv),
        "atc_to_checkout_rate": _rate(checkout, atc),
        "checkout_to_purchase_rate": _rate(conversions, checkout),
        "link_click_to_lpv_rate": _rate(lpv, link_clicks),
    }


def _empty_performance() -> Dict[str, Any]:
    return {
        "spend": 0.0,
        "impressions": 0,
        "clicks": 0,
        "cpc": 0.0,
        "ctr": 0.0,
        "cpm": 0.0,
        "reach": 0,
        "frequency": 0.0,
        "link_clicks": 0,
        "landing_page_views": 0,
        "add_to_carts": 0,
        "checkouts_initiated": 0,
        "conversions": 0,
        "roas": 0.0,
        "cpa": None,
        "click_to_purchase_rate": 0.0,
        "lpv_to_atc_rate": 0.0,
        "atc_to_checkout_rate": 0.0,
        "checkout_to_purchase_rate": 0.0,
        "link_click_to_lpv_rate": 0.0,
    }


def _period_days(since: str, until: str) -> int:
    start = datetime.strptime(since, "%Y-%m-%d").date()
    end = datetime.strptime(until, "%Y-%m-%d").date()
    return max(1, (end - start).days + 1)


def _previous_period(since: str, until: str) -> Tuple[str, str]:
    start = datetime.strptime(since, "%Y-%m-%d").date()
    end = datetime.strptime(until, "%Y-%m-%d").date()
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")


def _monthly_factor(since: str, until: str) -> float:
    return 30.0 / _period_days(since, until)


def _impact_range(monthly_waste: float, *, low_ratio: float = 0.55, high_ratio: float = 1.0) -> Tuple[float, float]:
    waste = max(0.0, monthly_waste)
    return waste * low_ratio, waste * high_ratio


def _severity_from_impact(monthly_max: float) -> str:
    if monthly_max >= 1000:
        return "critical"
    if monthly_max >= 500:
        return "high"
    if monthly_max >= 200:
        return "medium"
    return "low"


def _median(values: List[float]) -> float:
    cleaned = [v for v in values if v is not None and v > 0]
    if not cleaned:
        return 0.0
    return float(statistics.median(cleaned))


def _campaign_age_days(campaign: Dict[str, Any], until: str) -> int:
    raw = campaign.get("start_time") or campaign.get("created_time") or ""
    if not raw:
        return 0
    try:
        start = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        end = datetime.strptime(until, "%Y-%m-%d").date()
        return max(0, (end - start).days)
    except Exception:
        return 0


def _supplement_creative_brief(campaign_name: str) -> Dict[str, Any]:
    return {
        "hooks": [
            "Morning routine / daily regimen education (habit-first, not hype)",
            "Ingredient transparency — sourcing, purity, or third-party testing",
            "Founder or customer routine story with realistic timeframe",
        ],
        "visual_openings": [
            "First 3 seconds: product in real morning routine context",
            "Macro label / ingredient callout on clean background",
            "Before-after energy or focus (wellness framing, not medical claims)",
        ],
        "offer_variation": (
            "Test subscription or bundle incentive vs straight percentage discount "
            "to protect contribution margin"
        ),
    }


def _is_discount_campaign(name: str) -> bool:
    return bool(DISCOUNT_PATTERN.search(name or ""))


def _is_retarget_campaign(name: str) -> bool:
    return bool(RETARGET_PATTERN.search(name or ""))


def _is_prospect_campaign(name: str) -> bool:
    return bool(PROSPECT_PATTERN.search(name or ""))


class ProfitLeakScannerService:
    """Runs deterministic leak detection against Meta campaign insights."""

    async def scan_account(
        self,
        account_id: str,
        *,
        since: str,
        until: str,
        account_name: str = "",
        currency: str = "USD",
        store_economics: Optional[StoreEconomics] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return {
                "account_id": account_id,
                "account_name": account_name or account_id,
                "currency": currency,
                "period": {"since": since, "until": until},
                "findings": [],
                "summary": _empty_summary(currency),
                "error": "Facebook Ads client is not configured.",
            }

        time_range = {"since": since, "until": until}
        campaigns = await fb.get_campaigns_detailed(account_id)
        camp_rows = await fb.get_insights_raw_batch(
            account_id,
            time_range=time_range,
            level="campaign",
            fields=CAMPAIGN_SCAN_INSIGHT_FIELDS,
            id_field="campaign_id",
        )
        ad_rows = await fb.get_ad_insights_batch(account_id, time_range=time_range)

        prev_since, prev_until = _previous_period(since, until)
        prev_camp_rows = await fb.get_insights_raw_batch(
            account_id,
            time_range={"since": prev_since, "until": prev_until},
            level="campaign",
            fields=CAMPAIGN_SCAN_INSIGHT_FIELDS,
            id_field="campaign_id",
        )

        enriched: List[Dict[str, Any]] = []
        for camp in campaigns:
            cid = camp.get("id", "")
            perf = _parse_campaign_performance(camp_rows.get(cid, {}))
            prev_perf = _parse_campaign_performance(prev_camp_rows.get(cid, {}))
            if perf["spend"] <= 0 and prev_perf["spend"] <= 0:
                continue
            enriched.append(
                {
                    "id": cid,
                    "name": camp.get("name", "Untitled"),
                    "status": (camp.get("status") or "").upper(),
                    "start_time": camp.get("start_time") or camp.get("created_time"),
                    "performance": perf,
                    "previous_performance": prev_perf,
                    "creative_age_days": _campaign_age_days(camp, until),
                }
            )

        ads_enriched: List[Dict[str, Any]] = []
        for ad_id, row in ad_rows.items():
            perf = _parse_campaign_performance(row)
            if perf["spend"] < MIN_AD_SPEND:
                continue
            ads_enriched.append(
                {
                    "id": ad_id,
                    "name": row.get("ad_name") or f"Ad {ad_id}",
                    "campaign_id": row.get("campaign_id") or "",
                    "performance": perf,
                }
            )

        economics = store_economics or StoreEconomics()

        findings: List[ProfitLeakFinding] = []
        findings.extend(self._detect_spend_concentration(enriched, since, until, economics))
        findings.extend(self._detect_ad_spend_concentration(ads_enriched, since, until, economics))
        findings.extend(self._detect_funnel_leakage(enriched, since, until))
        findings.extend(self._detect_creative_fatigue(enriched, since, until))
        findings.extend(self._detect_discount_margin_leak(enriched, since, until, economics))
        findings.extend(self._detect_new_customer_distortion(enriched, since, until))

        if economics.has_data and economics.orders > 0:
            meta_purchases = sum(c["performance"]["conversions"] for c in enriched)
            gap = self._detect_measurement_gap(
                account_id,
                account_name or account_id,
                since,
                until,
                meta_purchases,
                economics.orders,
            )
            if gap:
                findings.append(gap)

        findings.sort(
            key=lambda f: (f.estimated_impact_max, f.confidence),
            reverse=True,
        )
        for finding in findings:
            finding.id = finding.id or str(uuid.uuid4())

        summary = self._build_summary(findings, enriched, currency, since, until)
        if economics.has_data:
            summary["store_economics"] = {
                "orders": economics.orders,
                "contribution_per_order": round(economics.contribution_per_order, 2),
                "break_even_cpa": round(economics.break_even_cpa, 2),
                "margin_percent": round(economics.margin_percent, 2),
            }
        return {
            "account_id": account_id,
            "account_name": account_name or account_id,
            "currency": currency,
            "period": {"since": since, "until": until, "label": summary["period_label"]},
            "comparison_period": {"since": prev_since, "until": prev_until},
            "campaigns_analyzed": len(enriched),
            "ads_analyzed": len(ads_enriched),
            "findings": [f.to_dict() for f in findings],
            "summary": summary,
        }

    async def scan_all_accounts(
        self,
        *,
        since: str,
        until: str,
        account_id: Optional[str] = None,
        store_orders: Optional[int] = None,
        force_refresh: bool = False,
        explain: bool = True,
        persist: bool = False,
        db: Any = None,
    ) -> Dict[str, Any]:
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return {
                "period": {"since": since, "until": until},
                "accounts": [],
                "findings": [],
                "summary": _empty_summary("USD"),
                "error": "Facebook Ads client is not configured.",
            }

        accounts = await fb.get_all_ad_accounts()
        if account_id:
            accounts = [a for a in accounts if a.get("id") == account_id]

        store_economics = _load_store_economics(since, until)

        all_findings: List[Dict[str, Any]] = []
        account_payloads: List[Dict[str, Any]] = []

        for acc in accounts:
            acc_id = acc.get("id", "")
            result = await self.scan_account(
                acc_id,
                since=since,
                until=until,
                account_name=acc.get("name", ""),
                currency=acc.get("currency", "USD"),
                store_economics=store_economics,
                force_refresh=force_refresh,
            )
            account_payloads.append(result)
            for finding in result.get("findings", []):
                finding["account_id"] = acc_id
                finding["account_name"] = result.get("account_name", "")
                finding["currency"] = result.get("currency", "USD")
                all_findings.append(finding)

        all_findings.sort(
            key=lambda f: (f.get("estimated_impact_max", 0), f.get("confidence", 0)),
            reverse=True,
        )

        total_min = sum(f.get("estimated_impact_min", 0) for f in all_findings)
        total_max = sum(f.get("estimated_impact_max", 0) for f in all_findings)
        currency = account_payloads[0].get("currency", "USD") if account_payloads else "USD"

        result = {
            "period": {"since": since, "until": until},
            "accounts": account_payloads,
            "findings": all_findings,
            "summary": {
                "total_opportunity_min": round(total_min, 2),
                "total_opportunity_max": round(total_max, 2),
                "finding_count": len(all_findings),
                "accounts_scanned": len(account_payloads),
                "currency": currency,
                "period_label": _period_label(since, until),
            },
            "account_id": account_id or "",
        }

        if explain and all_findings:
            from services.profit_leak_explainer import (
                merge_explanations,
                profit_leak_explainer_service,
            )

            explanation = await profit_leak_explainer_service.explain_scan(result)
            result = merge_explanations(result, explanation)
        result["explain"] = bool(explain)

        if persist and db is not None:
            from services.profit_leak_store import save_profit_leak_scan

            model_name = (result.get("explain_meta") or {}).get("model_name")
            run = save_profit_leak_scan(
                db,
                result,
                account_id=account_id or "",
                model_name=model_name,
            )
            result["analysis_run_id"] = run.id

        return result


    def _detect_spend_concentration(
        self,
        campaigns: List[Dict[str, Any]],
        since: str,
        until: str,
        economics: StoreEconomics,
    ) -> List[ProfitLeakFinding]:
        findings: List[ProfitLeakFinding] = []
        total_spend = sum(c["performance"]["spend"] for c in campaigns)
        if total_spend <= 0:
            return findings

        cpas = [
            c["performance"]["cpa"]
            for c in campaigns
            if c["performance"]["cpa"] is not None and c["performance"]["spend"] >= MIN_CAMPAIGN_SPEND
        ]
        median_cpa = _median([float(v) for v in cpas if v])
        monthly = _monthly_factor(since, until)
        break_even = economics.break_even_cpa if economics.has_data else 0.0

        for camp in campaigns:
            perf = camp["performance"]
            spend = perf["spend"]
            name = camp["name"]

            # Zero-conversion spend (MVP type 1 extension)
            if spend >= MIN_CAMPAIGN_SPEND and perf["conversions"] == 0:
                monthly_waste = spend * 0.85 * monthly
                impact_min, impact_max = _impact_range(monthly_waste, low_ratio=0.7, high_ratio=1.0)
                findings.append(
                    ProfitLeakFinding(
                        id=str(uuid.uuid4()),
                        category="spend_concentration",
                        severity=_severity_from_impact(impact_max),
                        title=f"Spend with no purchases — {name}",
                        diagnosis=(
                            f"Campaign spent {spend:.2f} with zero attributed purchases "
                            f"({perf['link_clicks']} link clicks). Sufficient spend for a pause/review decision."
                        ),
                        recommendation=(
                            "Pause or reduce budget until tracking, offer fit, and post-click experience are verified."
                        ),
                        confidence=0.88 if spend >= 150 else 0.76,
                        estimated_impact_min=impact_min,
                        estimated_impact_max=impact_max,
                        entity_type="campaign",
                        entity_id=camp["id"],
                        entity_name=name,
                        evidence=[
                            FindingEvidence("spend", round(spend, 2)),
                            FindingEvidence("conversions", 0),
                            FindingEvidence("link_clicks", perf["link_clicks"]),
                        ],
                        experiment={
                            "hypothesis": "Stopping zero-conversion spend reduces waste immediately.",
                            "action_type": "pause_or_reduce",
                            "success_metric": "purchase_count",
                            "duration_days": 7,
                        },
                    )
                )
                continue

            if spend < MIN_CAMPAIGN_SPEND or perf["cpa"] is None:
                continue

            spend_share = spend / total_spend * 100
            weak_vs_median = median_cpa > 0 and perf["cpa"] > median_cpa * 1.25
            weak_vs_margin = break_even > 0 and perf["cpa"] > break_even * 1.1
            if spend_share < 8 or not (weak_vs_median or weak_vs_margin):
                continue

            excess_ratio = (perf["cpa"] / median_cpa - 1) if median_cpa > 0 else 0.4
            monthly_waste = spend * min(max(excess_ratio, 0.15), 0.5) * monthly
            impact_min, impact_max = _impact_range(monthly_waste)

            margin_note = ""
            if weak_vs_margin and economics.has_data:
                margin_note = (
                    f" CPA {perf['cpa']:.2f} exceeds estimated break-even CPA "
                    f"{break_even:.2f} (contribution per order from store data)."
                )

            findings.append(
                ProfitLeakFinding(
                    id=str(uuid.uuid4()),
                    category="spend_concentration",
                    severity=_severity_from_impact(impact_max),
                    title=f"High spend with weak purchase efficiency — {name}",
                    diagnosis=(
                        f"Campaign consumed {spend_share:.0f}% of account spend "
                        f"({perf['cpa']:.2f} CPA vs account median {median_cpa:.2f}).{margin_note} "
                        f"Sufficient spend for a reallocation decision."
                    ),
                    recommendation=(
                        "Reduce spend on this campaign and reallocate to campaigns with stronger "
                        "purchase CPA and contribution margin."
                    ),
                    confidence=0.84 if weak_vs_margin else 0.76,
                    estimated_impact_min=impact_min,
                    estimated_impact_max=impact_max,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=name,
                    evidence=[
                        FindingEvidence("spend", round(spend, 2), round(total_spend, 2), "account total"),
                        FindingEvidence("spend_share_pct", round(spend_share, 1)),
                        FindingEvidence("cpa", perf["cpa"], median_cpa, "account median CPA"),
                        FindingEvidence(
                            "break_even_cpa",
                            perf["cpa"],
                            round(break_even, 2) if break_even else "n/a",
                            "store contribution",
                        ),
                        FindingEvidence("conversions", perf["conversions"]),
                    ],
                    experiment={
                        "hypothesis": "Reallocating from high-CPA spend improves account-level efficiency.",
                        "action_type": "budget_reallocation",
                        "success_metric": "purchase_cpa",
                        "duration_days": 14,
                    },
                    caveats=["Uses account median and store contribution estimates, not industry benchmarks."],
                )
            )
        return findings

    def _detect_ad_spend_concentration(
        self,
        ads: List[Dict[str, Any]],
        since: str,
        until: str,
        economics: StoreEconomics,
    ) -> List[ProfitLeakFinding]:
        findings: List[ProfitLeakFinding] = []
        total_spend = sum(a["performance"]["spend"] for a in ads)
        if total_spend <= 0:
            return findings

        cpas = [
            a["performance"]["cpa"]
            for a in ads
            if a["performance"]["cpa"] is not None and a["performance"]["spend"] >= MIN_AD_SPEND
        ]
        median_cpa = _median([float(v) for v in cpas if v])
        if median_cpa <= 0:
            return findings

        monthly = _monthly_factor(since, until)
        break_even = economics.break_even_cpa if economics.has_data else 0.0

        for ad in ads:
            perf = ad["performance"]
            spend = perf["spend"]
            if spend < MIN_AD_SPEND or perf["cpa"] is None:
                continue
            spend_share = spend / total_spend * 100
            if spend_share < 10:
                continue
            if perf["cpa"] <= median_cpa * 1.3 and (break_even <= 0 or perf["cpa"] <= break_even * 1.15):
                continue

            monthly_waste = spend * min(perf["cpa"] / median_cpa - 1, 0.45) * monthly
            impact_min, impact_max = _impact_range(monthly_waste)
            findings.append(
                ProfitLeakFinding(
                    id=str(uuid.uuid4()),
                    category="ad_spend_concentration",
                    severity=_severity_from_impact(impact_max),
                    title=f"Ad consuming spend above account-average CPA — {ad['name']}",
                    diagnosis=(
                        f"Ad consumed {spend_share:.0f}% of measured ad-level spend ({perf['cpa']:.2f} CPA "
                        f"vs account median {median_cpa:.2f}). It has sufficient spend for a decision."
                    ),
                    recommendation=(
                        "Review this ad in Ads Manager. Consider reducing budget and reallocating to ads "
                        "with stronger purchase efficiency."
                    ),
                    confidence=0.8,
                    estimated_impact_min=impact_min,
                    estimated_impact_max=impact_max,
                    entity_type="ad",
                    entity_id=ad["id"],
                    entity_name=ad["name"],
                    evidence=[
                        FindingEvidence("spend", round(spend, 2)),
                        FindingEvidence("spend_share_pct", round(spend_share, 1)),
                        FindingEvidence("cpa", perf["cpa"], median_cpa, "account median"),
                        FindingEvidence("conversions", perf["conversions"]),
                    ],
                    experiment={
                        "hypothesis": "Pausing or refreshing weak ads improves account CPA.",
                        "action_type": "ad_refresh",
                        "success_metric": "purchase_cpa",
                        "duration_days": 10,
                    },
                )
            )
        return findings

    def _detect_funnel_leakage(
        self,
        campaigns: List[Dict[str, Any]],
        since: str,
        until: str,
    ) -> List[ProfitLeakFinding]:
        findings: List[ProfitLeakFinding] = []
        monthly = _monthly_factor(since, until)

        def _median_metric(key: str, min_denominator: int = 0, denom_key: str = "") -> float:
            values = []
            for c in campaigns:
                perf = c["performance"]
                denom = perf.get(denom_key or key, 0) if denom_key else perf.get(key, 0)
                if denom >= min_denominator:
                    values.append(perf[key])
            return _median(values)

        median_ctr = _median_metric("ctr", min_denominator=500, denom_key="impressions")
        median_click_purchase = _median_metric(
            "click_to_purchase_rate", min_denominator=MIN_LINK_CLICKS_FUNNEL, denom_key="link_clicks"
        )
        median_lpv_atc = _median_metric(
            "lpv_to_atc_rate", min_denominator=MIN_FUNNEL_EVENTS, denom_key="landing_page_views"
        )
        median_atc_checkout = _median_metric(
            "atc_to_checkout_rate", min_denominator=MIN_FUNNEL_EVENTS, denom_key="add_to_carts"
        )

        for camp in campaigns:
            perf = camp["performance"]
            spend = perf["spend"]
            if spend < MIN_CAMPAIGN_SPEND:
                continue

            # Pattern: strong CTR, weak click → purchase
            if (
                perf["link_clicks"] >= MIN_LINK_CLICKS_FUNNEL
                and median_ctr > 0
                and perf["ctr"] >= median_ctr * 0.85
                and median_click_purchase > 0
                and perf["click_to_purchase_rate"] < median_click_purchase * 0.55
            ):
                gap_ratio = 1 - perf["click_to_purchase_rate"] / max(median_click_purchase, 0.01)
                impact_min, impact_max = _impact_range(spend * min(gap_ratio, 0.65) * monthly)
                findings.append(
                    self._funnel_finding(
                        camp,
                        category="post_click_leak",
                        title=f"Strong clicks, weak purchases — {camp['name']}",
                        diagnosis=(
                            f"Link CTR ({perf['ctr']:.2f}%) is near/above baseline but click-to-purchase "
                            f"({perf['click_to_purchase_rate']:.2f}%) is below account median "
                            f"({median_click_purchase:.2f}%). Likely post-click bottleneck."
                        ),
                        recommendation=(
                            "Audit landing page, offer clarity, mobile checkout, and message match before changing targeting."
                        ),
                        evidence=[
                            FindingEvidence("ctr", perf["ctr"], median_ctr, "account median"),
                            FindingEvidence(
                                "click_to_purchase_rate",
                                perf["click_to_purchase_rate"],
                                median_click_purchase,
                                "account median",
                            ),
                            FindingEvidence("link_clicks", perf["link_clicks"]),
                            FindingEvidence("landing_page_views", perf["landing_page_views"]),
                        ],
                        impact_min=impact_min,
                        impact_max=impact_max,
                        experiment_type="landing_page_test",
                        metric="click_to_purchase_rate",
                    )
                )

            # Pattern: LPV → ATC weak
            if (
                perf["landing_page_views"] >= MIN_FUNNEL_EVENTS
                and perf["add_to_carts"] >= 3
                and median_lpv_atc > 0
                and perf["lpv_to_atc_rate"] < median_lpv_atc * 0.5
            ):
                gap_ratio = 1 - perf["lpv_to_atc_rate"] / max(median_lpv_atc, 0.01)
                impact_min, impact_max = _impact_range(spend * min(gap_ratio, 0.5) * monthly)
                findings.append(
                    self._funnel_finding(
                        camp,
                        category="funnel_lpv_to_atc",
                        title=f"Landing views not adding to cart — {camp['name']}",
                        diagnosis=(
                            f"Landing-page-to-add-to-cart rate ({perf['lpv_to_atc_rate']:.2f}%) is "
                            f"materially below account median ({median_lpv_atc:.2f}%). "
                            f"Many visitors see the page but do not add to cart."
                        ),
                        recommendation=(
                            "Improve product clarity, pricing/trust signals, and mobile page speed on the landing experience."
                        ),
                        evidence=[
                            FindingEvidence("landing_page_views", perf["landing_page_views"]),
                            FindingEvidence("add_to_carts", perf["add_to_carts"]),
                            FindingEvidence(
                                "lpv_to_atc_rate",
                                perf["lpv_to_atc_rate"],
                                median_lpv_atc,
                                "account median",
                            ),
                        ],
                        impact_min=impact_min,
                        impact_max=impact_max,
                        experiment_type="lp_optimization",
                        metric="lpv_to_atc_rate",
                    )
                )

            # Pattern: ATC → checkout weak
            if (
                perf["add_to_carts"] >= MIN_FUNNEL_EVENTS
                and perf["checkouts_initiated"] >= 3
                and median_atc_checkout > 0
                and perf["atc_to_checkout_rate"] < median_atc_checkout * 0.5
            ):
                gap_ratio = 1 - perf["atc_to_checkout_rate"] / max(median_atc_checkout, 0.01)
                impact_min, impact_max = _impact_range(spend * min(gap_ratio, 0.45) * monthly)
                findings.append(
                    self._funnel_finding(
                        camp,
                        category="funnel_atc_to_checkout",
                        title=f"Cart abandonment before checkout — {camp['name']}",
                        diagnosis=(
                            f"Add-to-cart to checkout rate ({perf['atc_to_checkout_rate']:.2f}%) is below "
                            f"account median ({median_atc_checkout:.2f}%). Checkout friction is a likely bottleneck."
                        ),
                        recommendation=(
                            "Check shipping cost disclosure, payment options, discount application, and mobile checkout errors."
                        ),
                        evidence=[
                            FindingEvidence("add_to_carts", perf["add_to_carts"]),
                            FindingEvidence("checkouts_initiated", perf["checkouts_initiated"]),
                            FindingEvidence(
                                "atc_to_checkout_rate",
                                perf["atc_to_checkout_rate"],
                                median_atc_checkout,
                                "account median",
                            ),
                        ],
                        impact_min=impact_min,
                        impact_max=impact_max,
                        experiment_type="checkout_test",
                        metric="atc_to_checkout_rate",
                    )
                )

        return findings

    def _funnel_finding(
        self,
        camp: Dict[str, Any],
        *,
        category: str,
        title: str,
        diagnosis: str,
        recommendation: str,
        evidence: List[FindingEvidence],
        impact_min: float,
        impact_max: float,
        experiment_type: str,
        metric: str,
    ) -> ProfitLeakFinding:
        return ProfitLeakFinding(
            id=str(uuid.uuid4()),
            category=category,
            severity=_severity_from_impact(impact_max),
            title=title,
            diagnosis=diagnosis,
            recommendation=recommendation,
            confidence=0.78,
            estimated_impact_min=impact_min,
            estimated_impact_max=impact_max,
            entity_type="campaign",
            entity_id=camp["id"],
            entity_name=camp["name"],
            evidence=evidence,
            experiment={
                "hypothesis": f"Fixing this funnel step improves {metric}.",
                "action_type": experiment_type,
                "success_metric": metric,
                "duration_days": 14,
            },
            caveats=["Funnel metrics depend on Meta pixel/CAPI event quality."],
        )

    def _detect_creative_fatigue(
        self,
        campaigns: List[Dict[str, Any]],
        since: str,
        until: str,
    ) -> List[ProfitLeakFinding]:
        findings: List[ProfitLeakFinding] = []
        monthly = _monthly_factor(since, until)

        for camp in campaigns:
            perf = camp["performance"]
            prev = camp["previous_performance"]
            if perf["spend"] < MIN_SPEND_FATIGUE or prev["spend"] < 30:
                continue

            freq_up = prev["frequency"] > 0 and perf["frequency"] >= prev["frequency"] * 1.12
            ctr_down = prev["ctr"] > 0 and perf["ctr"] <= prev["ctr"] * 0.88
            cpa_up = (
                perf["cpa"] is not None
                and prev["cpa"] is not None
                and perf["cpa"] >= prev["cpa"] * 1.15
            )
            cpm_up = prev["cpm"] > 0 and perf["cpm"] >= prev["cpm"] * 1.12
            age_days = camp.get("creative_age_days") or 0
            age_signal = age_days >= MIN_CREATIVE_AGE_DAYS

            signals = sum([freq_up, ctr_down, cpa_up, cpm_up, age_signal])
            if signals < 3:
                continue

            monthly_waste = perf["spend"] * 0.35 * monthly
            impact_min, impact_max = _impact_range(monthly_waste)
            brief = _supplement_creative_brief(camp["name"])

            freq_change = (
                ((perf["frequency"] - prev["frequency"]) / max(prev["frequency"], 0.01)) * 100
                if prev["frequency"] > 0
                else 0
            )
            ctr_change = (
                ((perf["ctr"] - prev["ctr"]) / max(prev["ctr"], 0.01)) * 100
                if prev["ctr"] > 0
                else 0
            )
            cpa_change = 0.0
            if perf["cpa"] and prev["cpa"]:
                cpa_change = (perf["cpa"] / prev["cpa"] - 1) * 100

            findings.append(
                ProfitLeakFinding(
                    id=str(uuid.uuid4()),
                    category="creative_fatigue",
                    severity=_severity_from_impact(impact_max),
                    title=f"Creative fatigue signals — {camp['name']}",
                    diagnosis=(
                        f"Over the period, frequency moved {freq_change:+.0f}%, CTR {ctr_change:+.0f}%, "
                        f"and CPA {cpa_change:+.0f}% vs the prior period while spend continued "
                        f"({perf['spend']:.2f}). Creative age ~{age_days} days. Fatigue is plausible."
                    ),
                    recommendation=(
                        "Launch the creative brief below before changing audience. "
                        "Refresh first-three-second hooks and primary visuals, not just the offer."
                    ),
                    confidence=0.72 if signals == 3 else 0.82,
                    estimated_impact_min=impact_min,
                    estimated_impact_max=impact_max,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=camp["name"],
                    evidence=[
                        FindingEvidence("frequency", perf["frequency"], prev["frequency"], "prior period"),
                        FindingEvidence("ctr", perf["ctr"], prev["ctr"], "prior period"),
                        FindingEvidence("cpm", perf["cpm"], prev["cpm"], "prior period"),
                        FindingEvidence("creative_age_days", age_days),
                    ],
                    experiment={
                        "hypothesis": "New hooks and openings restore CTR and purchase efficiency.",
                        "action_type": "creative_test",
                        "success_metric": "purchase_cpa",
                        "duration_days": 10,
                        "creative_brief": brief,
                    },
                )
            )
        return findings

    def _detect_discount_margin_leak(
        self,
        campaigns: List[Dict[str, Any]],
        since: str,
        until: str,
        economics: StoreEconomics,
    ) -> List[ProfitLeakFinding]:
        findings: List[ProfitLeakFinding] = []
        discount_camps = [c for c in campaigns if _is_discount_campaign(c["name"])]
        if not discount_camps:
            return findings

        monthly = _monthly_factor(since, until)
        roas_vals = [c["performance"]["roas"] for c in campaigns if c["performance"]["roas"] > 0]
        median_roas = _median(roas_vals)

        for camp in discount_camps:
            perf = camp["performance"]
            if perf["spend"] < MIN_CAMPAIGN_SPEND:
                continue

            weak_roas = median_roas > 0 and perf["roas"] < median_roas * 0.8
            weak_margin = economics.has_data and economics.margin_percent < 25
            if not weak_roas and not weak_margin:
                continue

            monthly_waste = perf["spend"] * 0.3 * monthly
            impact_min, impact_max = _impact_range(monthly_waste)

            margin_line = ""
            if economics.has_data:
                margin_line = (
                    f" Store contribution margin is {economics.margin_percent:.1f}% for the period — "
                    f"discount-led volume may not be economically valuable."
                )

            findings.append(
                ProfitLeakFinding(
                    id=str(uuid.uuid4()),
                    category="discount_margin_leak",
                    severity=_severity_from_impact(impact_max),
                    title=f"Discount campaign with weak margin profile — {camp['name']}",
                    diagnosis=(
                        f"Discount/promo campaign ROAS {perf['roas']:.2f}x "
                        f"{'below' if weak_roas else 'near'} account median.{margin_line}"
                    ),
                    recommendation=(
                        "Test bundle or subscription incentive instead of deep discounts. "
                        "Evaluate 60-day repeat value before scaling."
                    ),
                    confidence=0.8 if weak_margin else 0.7,
                    estimated_impact_min=impact_min,
                    estimated_impact_max=impact_max,
                    entity_type="campaign",
                    entity_id=camp["id"],
                    entity_name=camp["name"],
                    evidence=[
                        FindingEvidence("roas", perf["roas"], median_roas, "account median"),
                        FindingEvidence("spend", round(perf["spend"], 2)),
                        FindingEvidence(
                            "margin_percent",
                            round(economics.margin_percent, 1) if economics.has_data else "n/a",
                        ),
                    ],
                    experiment={
                        "hypothesis": "Bundle/subscription offer improves contribution margin vs % discount.",
                        "action_type": "offer_test",
                        "success_metric": "contribution_margin",
                        "duration_days": 21,
                    },
                    caveats=["Uses campaign naming heuristics for discount detection."],
                )
            )
        return findings

    def _detect_new_customer_distortion(
        self,
        campaigns: List[Dict[str, Any]],
        since: str,
        until: str,
    ) -> List[ProfitLeakFinding]:
        findings: List[ProfitLeakFinding] = []
        total_spend = sum(c["performance"]["spend"] for c in campaigns)
        if total_spend <= 0:
            return findings

        retarget = [c for c in campaigns if _is_retarget_campaign(c["name"])]
        prospect = [c for c in campaigns if _is_prospect_campaign(c["name"])]

        retarget_spend = sum(c["performance"]["spend"] for c in retarget)
        retarget_share = retarget_spend / total_spend * 100
        retarget_conv = sum(c["performance"]["conversions"] for c in retarget)
        total_conv = sum(c["performance"]["conversions"] for c in campaigns)

        if retarget_share >= 35 and total_conv > 0:
            retarget_conv_share = retarget_conv / total_conv * 100
            if retarget_conv_share >= 40:
                monthly = _monthly_factor(since, until)
                impact_min, impact_max = _impact_range(retarget_spend * 0.25 * monthly)
                findings.append(
                    ProfitLeakFinding(
                        id=str(uuid.uuid4()),
                        category="new_customer_distortion",
                        severity=_severity_from_impact(impact_max),
                        title="High returning-customer share on retargeting campaigns",
                        diagnosis=(
                            f"Retargeting campaigns consume {retarget_share:.0f}% of spend and "
                            f"~{retarget_conv_share:.0f}% of attributed purchases. "
                            f"Reported efficiency may reflect harvesting existing demand, not new acquisition."
                        ),
                        recommendation=(
                            "Evaluate retargeting using new-customer CPA and new-customer contribution margin "
                            "before increasing spend. Separate prospecting performance in reporting."
                        ),
                        confidence=0.75,
                        estimated_impact_min=impact_min,
                        estimated_impact_max=impact_max,
                        entity_type="account",
                        entity_id="account",
                        entity_name="Account mix",
                        evidence=[
                            FindingEvidence("retarget_spend_share_pct", round(retarget_share, 1)),
                            FindingEvidence("retarget_conversion_share_pct", round(retarget_conv_share, 1)),
                        ],
                        experiment={
                            "hypothesis": "Prospecting-only reporting reveals true acquisition cost.",
                            "action_type": "reporting_segmentation",
                            "success_metric": "new_customer_cpa",
                            "duration_days": 14,
                        },
                        caveats=["Uses campaign name heuristics for retargeting vs prospecting."],
                    )
                )

        # Prospect campaigns with high CPA vs account
        cpas = [c["performance"]["cpa"] for c in campaigns if c["performance"]["cpa"]]
        median_cpa = _median([float(v) for v in cpas if v])
        for camp in prospect:
            perf = camp["performance"]
            if perf["cpa"] and median_cpa > 0 and perf["cpa"] > median_cpa * 1.4 and perf["spend"] >= MIN_CAMPAIGN_SPEND:
                monthly = _monthly_factor(since, until)
                impact_min, impact_max = _impact_range(perf["spend"] * 0.2 * monthly)
                findings.append(
                    ProfitLeakFinding(
                        id=str(uuid.uuid4()),
                        category="new_customer_distortion",
                        severity=_severity_from_impact(impact_max),
                        title=f"Prospecting CPA elevated — {camp['name']}",
                        diagnosis=(
                            f"Prospecting campaign CPA {perf['cpa']:.2f} is well above account median "
                            f"{median_cpa:.2f}. New-customer acquisition may be uneconomical at current spend."
                        ),
                        recommendation=(
                            "Improve creative-message fit and offer for cold audiences, or narrow targeting "
                            "before scaling prospecting spend."
                        ),
                        confidence=0.74,
                        estimated_impact_min=impact_min,
                        estimated_impact_max=impact_max,
                        entity_type="campaign",
                        entity_id=camp["id"],
                        entity_name=camp["name"],
                        evidence=[
                            FindingEvidence("cpa", perf["cpa"], median_cpa, "account median"),
                            FindingEvidence("spend", round(perf["spend"], 2)),
                        ],
                        experiment={
                            "hypothesis": "Better cold-audience creative lowers new-customer CPA.",
                            "action_type": "prospecting_creative_test",
                            "success_metric": "new_customer_cpa",
                            "duration_days": 14,
                        },
                    )
                )
        return findings

    def _detect_measurement_gap(
        self,
        account_id: str,
        account_name: str,
        since: str,
        until: str,
        meta_purchases: int,
        store_orders: int,
    ) -> Optional[ProfitLeakFinding]:
        if meta_purchases <= 0 and store_orders <= 0:
            return None
        if store_orders <= 0:
            return None

        gap = meta_purchases - store_orders
        base = max(store_orders, meta_purchases, 1)
        gap_pct = abs(gap) / base * 100
        if gap_pct < 12:
            return None

        monthly = _monthly_factor(since, until)
        impact_min, impact_max = _impact_range(abs(gap) * 25 * monthly, low_ratio=0.3, high_ratio=0.6)

        if gap > 0:
            title = "Meta purchases exceed store orders"
            diagnosis = (
                f"Meta reports {meta_purchases} purchases while the store recorded {store_orders} paid orders "
                f"({gap_pct:.0f}% gap). Some events may be duplicated or outside the reporting window. "
                f"Treat ROAS as low-confidence until tracking is reconciled."
            )
        else:
            title = "Store orders exceed Meta purchases"
            diagnosis = (
                f"Store recorded {store_orders} paid orders while Meta reports {meta_purchases} purchases "
                f"({gap_pct:.0f}% gap). Platform may be under-attributing conversions — "
                f"avoid over-cutting spend based on Meta CPA alone."
            )

        return ProfitLeakFinding(
            id=str(uuid.uuid4()),
            category="measurement_gap",
            severity="high" if gap_pct >= 25 else "medium",
            title=title,
            diagnosis=diagnosis,
            recommendation=(
                "Reconcile pixel/CAPI events, attribution windows, and duplicate counting. "
                "Align date ranges and order status filters between Meta and your store."
            ),
            confidence=0.86,
            estimated_impact_min=impact_min,
            estimated_impact_max=impact_max,
            entity_type="account",
            entity_id=account_id,
            entity_name=account_name,
            evidence=[
                FindingEvidence("meta_purchases", meta_purchases, store_orders, "store orders"),
                FindingEvidence("gap", gap),
                FindingEvidence("gap_pct", round(gap_pct, 1)),
            ],
            experiment={
                "hypothesis": "Aligned tracking improves decision quality.",
                "action_type": "tracking_audit",
                "success_metric": "attribution_match_rate",
                "duration_days": 7,
            },
            caveats=["Store data may use a different attribution window than Meta."],
        )

    def _build_summary(
        self,
        findings: List[ProfitLeakFinding],
        campaigns: List[Dict[str, Any]],
        currency: str,
        since: str,
        until: str,
    ) -> Dict[str, Any]:
        total_min = sum(f.estimated_impact_min for f in findings)
        total_max = sum(f.estimated_impact_max for f in findings)
        total_spend = sum(c["performance"]["spend"] for c in campaigns)
        return {
            "total_opportunity_min": round(total_min, 2),
            "total_opportunity_max": round(total_max, 2),
            "finding_count": len(findings),
            "total_spend": round(total_spend, 2),
            "currency": currency,
            "period_label": _period_label(since, until),
        }


def _period_label(since: str, until: str) -> str:
    days = _period_days(since, until)
    return f"{since} to {until} ({days} days)"


def _empty_summary(currency: str) -> Dict[str, Any]:
    return {
        "total_opportunity_min": 0.0,
        "total_opportunity_max": 0.0,
        "finding_count": 0,
        "total_spend": 0.0,
        "currency": currency,
        "period_label": "",
    }


def _load_store_economics(since: str, until: str) -> StoreEconomics:
    """Aggregate store P&L from daily_metrics for contribution margin and measurement checks."""
    try:
        from datetime import datetime as dt

        from models.database import SessionLocal
        from models.schemas import DailyMetric

        start = dt.strptime(since, "%Y-%m-%d")
        end = dt.strptime(until, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        db = SessionLocal()
        try:
            rows = (
                db.query(DailyMetric)
                .filter(DailyMetric.timestamp >= start, DailyMetric.timestamp <= end)
                .all()
            )
            if not rows:
                return StoreEconomics()

            orders = sum(int(r.orders_count or 0) for r in rows)
            revenue = sum(_safe_float(r.revenue) for r in rows)
            ad_spend = sum(_safe_float(r.ad_spend) for r in rows)
            cogs = sum(_safe_float(r.cogs_total) for r in rows)
            shipping = sum(_safe_float(r.shipping_cost) for r in rows)
            net_profit = sum(_safe_float(r.net_profit) for r in rows)

            contribution = revenue - cogs - shipping
            margin_percent = (contribution / revenue * 100) if revenue > 0 else 0.0
            contribution_per_order = (contribution / orders) if orders > 0 else 0.0
            break_even_cpa = max(contribution_per_order, 0.0)

            return StoreEconomics(
                orders=orders,
                revenue=revenue,
                ad_spend=ad_spend,
                cogs=cogs,
                shipping=shipping,
                net_profit=net_profit,
                margin_percent=margin_percent,
                contribution_per_order=contribution_per_order,
                break_even_cpa=break_even_cpa,
                has_data=True,
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"Could not load store economics for profit leak scan: {exc}")
        return StoreEconomics()


profit_leak_scanner_service = ProfitLeakScannerService()
