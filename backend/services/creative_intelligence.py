"""
Creative intelligence for supplement Meta ads.

Identifies winning message patterns, fatigue, and a structured test backlog.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from services.growth_insights_common import (
    fetch_account_insights,
    period_label,
    resolve_fb_client,
)
from utils.logging_config import get_logger

logger = get_logger("creative_intelligence")

DISCOUNT_RE = re.compile(r"\b(\d+%\s*off|sale|discount|bogo|coupon|promo)\b", re.I)
ROUTINE_RE = re.compile(r"\b(morning|routine|daily|regimen|habit|every day)\b", re.I)
INGREDIENT_RE = re.compile(
    r"\b(organic|third[- ]party|tested|pure|sourced|ingredient|mg|capsule|vegan|non[- ]gmo)\b",
    re.I,
)
TESTIMONIAL_RE = re.compile(r"\b(review|testimonial|customer|real results|loved)\b", re.I)
URGENCY_RE = re.compile(r"\b(limited|today only|last chance|hurry)\b", re.I)


def _classify_copy(text: str) -> List[str]:
    tags: List[str] = []
    if DISCOUNT_RE.search(text):
        tags.append("discount_led")
    if ROUTINE_RE.search(text):
        tags.append("routine_education")
    if INGREDIENT_RE.search(text):
        tags.append("ingredient_transparency")
    if TESTIMONIAL_RE.search(text):
        tags.append("social_proof")
    if URGENCY_RE.search(text):
        tags.append("urgency")
    if not tags:
        tags.append("general_offer")
    return tags


def _efficiency_score(perf: Dict[str, Any]) -> float:
    ctr = perf.get("ctr", 0)
    impressions = perf.get("impressions", 0)
    link_clicks = perf.get("link_clicks", 0)
    if impressions <= 0:
        return ctr
    return ctr * 10 + (link_clicks / impressions) * 1000


class CreativeIntelligenceService:
    async def analyze_account(
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

        creative_payload = await fb.get_creatives_for_account(
            account_id,
            include_engagement=True,
            engagement_days=30,
        )
        creatives = creative_payload.get("creatives") or []

        insights = await fetch_account_insights(fb, account_id, since=since, until=until)

        enriched_creatives: List[Dict[str, Any]] = []
        for c in creatives:
            body = (c.get("body") or c.get("title") or c.get("name") or "").strip()
            tags = _classify_copy(body)
            engagement = c.get("engagement") or {}
            perf = {
                "spend": 0.0,
                "impressions": int(engagement.get("impressions", 0) or 0),
                "ctr": float(engagement.get("ctr", 0) or 0),
                "link_clicks": int(engagement.get("link_clicks", 0) or 0),
                "roas": 0.0,
                "cpa": None,
                "conversions": 0,
            }
            enriched_creatives.append(
                {
                    "creative_id": c.get("creative_id") or c.get("id", ""),
                    "name": c.get("name", "Creative"),
                    "type": c.get("type", "unknown"),
                    "body": body[:500],
                    "thumbnail_url": c.get("thumbnail_url", ""),
                    "tags": tags,
                    "performance": perf,
                    "efficiency_score": _efficiency_score(perf),
                    "age_days": c.get("age_days", 0),
                }
            )

        enriched_creatives.sort(key=lambda x: x["efficiency_score"], reverse=True)
        with_traction = [c for c in enriched_creatives if c["performance"]["impressions"] >= 500]
        winners = with_traction[:5]
        fatigued = self._detect_fatigue(insights["campaigns"])
        patterns = self._pattern_summary(with_traction)
        test_backlog = self._build_test_backlog(patterns, winners, fatigued)

        return {
            "account_id": account_id,
            "account_name": account_name or account_id,
            "currency": currency,
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "creatives_analyzed": len(enriched_creatives),
            "creatives_with_traction": len(with_traction),
            "winners": winners,
            "fatigued_campaigns": fatigued,
            "patterns": patterns,
            "pattern_insight": self._pattern_insight(patterns),
            "test_backlog": test_backlog,
        }

    async def analyze_all(
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
                await self.analyze_account(
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
            "pattern_insight": primary.get("pattern_insight", ""),
            "test_backlog": primary.get("test_backlog", []),
            "winners": primary.get("winners", []),
            "fatigued_campaigns": primary.get("fatigued_campaigns", []),
            "patterns": primary.get("patterns", []),
            "account_id": account_id or "",
        }

    def _detect_fatigue(self, campaigns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        fatigued = []
        for camp in campaigns:
            perf = camp["performance"]
            prev = camp["previous_performance"]
            if perf["spend"] < 75:
                continue
            freq_up = prev.get("frequency", 0) > 0 and perf["frequency"] >= prev["frequency"] * 1.12
            ctr_down = prev.get("ctr", 0) > 0 and perf["ctr"] <= prev["ctr"] * 0.88
            cpa_up = (
                perf.get("cpa")
                and prev.get("cpa")
                and perf["cpa"] >= prev["cpa"] * 1.15
            )
            if sum([freq_up, ctr_down, bool(cpa_up)]) >= 2:
                fatigued.append(
                    {
                        "campaign_id": camp["id"],
                        "campaign_name": camp["name"],
                        "frequency": perf["frequency"],
                        "ctr": perf["ctr"],
                        "cpa": perf.get("cpa"),
                        "spend": perf["spend"],
                        "creative_age_days": camp.get("creative_age_days", 0),
                    }
                )
        return fatigued[:8]

    def _pattern_summary(self, creatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = {}
        for c in creatives:
            for tag in c["tags"]:
                bucket = buckets.setdefault(
                    tag,
                    {"tag": tag, "count": 0, "spend": 0.0, "conversions": 0, "ctr_sum": 0.0},
                )
                bucket["count"] += 1
                bucket["spend"] += c["performance"]["spend"]
                bucket["conversions"] += c["performance"]["conversions"]
                bucket["ctr_sum"] += c["performance"]["ctr"]
        patterns = []
        for tag, b in buckets.items():
            patterns.append(
                {
                    "tag": tag,
                    "label": tag.replace("_", " ").title(),
                    "creative_count": b["count"],
                    "spend": round(b["spend"], 2),
                    "conversions": b["conversions"],
                    "avg_ctr": round(b["ctr_sum"] / max(b["count"], 1), 2),
                    "cpa": round(b["spend"] / b["conversions"], 2) if b["conversions"] else None,
                }
            )
        patterns.sort(key=lambda p: p["spend"], reverse=True)
        return patterns

    def _pattern_insight(self, patterns: List[Dict[str, Any]]) -> str:
        if not patterns:
            return "Not enough creative spend to identify message patterns yet."
        top = patterns[0]
        discount = next((p for p in patterns if p["tag"] == "discount_led"), None)
        routine = next((p for p in patterns if p["tag"] == "routine_education"), None)
        ingredient = next((p for p in patterns if p["tag"] == "ingredient_transparency"), None)

        parts = [f"Most spend ({top['label']}) consumed {top['spend']:.0f} in the period."]
        if discount and routine:
            if (discount.get("cpa") or 999) > (routine.get("cpa") or 0) and routine.get("cpa"):
                parts.append(
                    "Discount-led copy appears to attract cheaper clicks but weaker purchase efficiency "
                    "than routine-education angles."
                )
        if ingredient and ingredient.get("conversions", 0) > 0:
            parts.append(
                "Ingredient-transparency messaging shows purchase signal — lean into sourcing and dosage clarity."
            )
        parts.append(
            "Test three variants: morning-routine education, sourcing proof, and a 30-day habit challenge "
            "(wellness framing, not medical claims)."
        )
        return " ".join(parts)

    def _build_test_backlog(
        self,
        patterns: List[Dict[str, Any]],
        winners: List[Dict[str, Any]],
        fatigued: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        backlog: List[Dict[str, Any]] = []
        winner_tags = set()
        for w in winners[:3]:
            winner_tags.update(w.get("tags", []))

        tests = [
            {
                "hypothesis": "Routine-based education attracts higher-quality supplement buyers than discount hooks.",
                "variable": "Primary hook — morning regimen vs % off",
                "audience": "Prospecting (broad wellness interest)",
                "budget": "$30–50/day per variant",
                "duration_days": 10,
                "success_metric": "purchase_cpa",
                "decision_rule": "Scale variant if CPA beats account median by 15%+ with ≥15 purchases.",
            },
            {
                "hypothesis": "Ingredient transparency improves trust and LPV-to-cart rate.",
                "variable": "Visual — label macro / third-party testing callout",
                "audience": "Same as top winner",
                "budget": "$25–40/day",
                "duration_days": 14,
                "success_metric": "lpv_to_atc_rate",
                "decision_rule": "Adopt if LPV→ATC improves ≥20% vs control.",
            },
            {
                "hypothesis": "Bundle/subscription incentive protects margin vs straight discount.",
                "variable": "Offer — subscribe & save vs one-time % off",
                "audience": "Warm / engaged audiences",
                "budget": "$20–35/day",
                "duration_days": 21,
                "success_metric": "60_day_contribution_margin",
                "decision_rule": "Prefer offer with higher contribution per new customer.",
            },
        ]

        if fatigued:
            tests.insert(
                0,
                {
                    "hypothesis": "Refreshing fatigued creative restores CTR without audience changes.",
                    "variable": "First-3-second hook on fatigued campaigns",
                    "audience": f"Existing — {fatigued[0]['campaign_name'][:40]}",
                    "budget": "$40–60/day",
                    "duration_days": 10,
                    "success_metric": "purchase_cpa",
                    "decision_rule": "Replace incumbent if CPA improves ≥10% after 5k impressions each.",
                },
            )

        for idx, test in enumerate(tests[:4], start=1):
            backlog.append({"id": f"test_{idx}", "priority": idx, **test})
        return backlog


creative_intelligence_service = CreativeIntelligenceService()
