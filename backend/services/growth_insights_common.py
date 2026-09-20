"""Shared Meta + store data loading for growth insight features."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.profit_leak_scanner import (
    CAMPAIGN_SCAN_INSIGHT_FIELDS,
    MIN_AD_SPEND,
    StoreEconomics,
    _campaign_age_days,
    _load_store_economics,
    _parse_campaign_performance,
    _previous_period,
)
from utils.logging_config import get_logger

logger = get_logger("growth_insights_common")


async def fetch_account_insights(
    fb: Any,
    account_id: str,
    *,
    since: str,
    until: str,
) -> Dict[str, Any]:
    """Load enriched campaign and ad rows for an account."""
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

    totals = _aggregate_performance(enriched)
    prev_totals = _aggregate_performance(
        [
            {
                "performance": _parse_campaign_performance(prev_camp_rows.get(c["id"], {})),
                "previous_performance": {},
            }
            for c in enriched
        ]
    )

    return {
        "campaigns": enriched,
        "ads": ads_enriched,
        "totals": totals,
        "previous_totals": prev_totals,
        "comparison_period": {"since": prev_since, "until": prev_until},
    }


def _aggregate_performance(campaigns: List[Dict[str, Any]]) -> Dict[str, Any]:
    spend = sum(c["performance"]["spend"] for c in campaigns)
    impressions = sum(c["performance"]["impressions"] for c in campaigns)
    link_clicks = sum(c["performance"]["link_clicks"] for c in campaigns)
    lpv = sum(c["performance"]["landing_page_views"] for c in campaigns)
    atc = sum(c["performance"]["add_to_carts"] for c in campaigns)
    checkout = sum(c["performance"]["checkouts_initiated"] for c in campaigns)
    conversions = sum(c["performance"]["conversions"] for c in campaigns)
    ctr = (link_clicks / impressions * 100) if impressions > 0 else 0.0
    cpm = (spend / impressions * 1000) if impressions > 0 else 0.0
    cpa = (spend / conversions) if conversions > 0 else None
    roas_weighted = 0.0
    if spend > 0:
        roas_weighted = sum(
            c["performance"]["roas"] * c["performance"]["spend"] for c in campaigns
        ) / spend

    freq_vals = [c["performance"]["frequency"] for c in campaigns if c["performance"]["frequency"] > 0]
    frequency = sum(freq_vals) / len(freq_vals) if freq_vals else 0.0

    return {
        "spend": round(spend, 2),
        "impressions": impressions,
        "link_clicks": link_clicks,
        "landing_page_views": lpv,
        "add_to_carts": atc,
        "checkouts_initiated": checkout,
        "conversions": conversions,
        "ctr": round(ctr, 2),
        "cpm": round(cpm, 2),
        "cpa": round(cpa, 2) if cpa is not None else None,
        "roas": round(roas_weighted, 2),
        "frequency": round(frequency, 2),
        "click_to_purchase_rate": round(conversions / link_clicks * 100, 2) if link_clicks else 0.0,
        "lpv_to_atc_rate": round(atc / lpv * 100, 2) if lpv else 0.0,
        "atc_to_checkout_rate": round(checkout / atc * 100, 2) if atc else 0.0,
        "checkout_to_purchase_rate": round(conversions / checkout * 100, 2) if checkout else 0.0,
    }


def load_store_economics(since: str, until: str) -> StoreEconomics:
    return _load_store_economics(since, until)


async def resolve_fb_client():
    from services.marketing import marketing_service

    return marketing_service._fb_client


def period_label(since: str, until: str) -> str:
    return f"{since} to {until}"
