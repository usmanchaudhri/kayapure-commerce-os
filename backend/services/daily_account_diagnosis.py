"""
Daily plain-English account diagnosis for supplement Meta ad accounts.

Summarizes traffic quality, creative strength, landing conversion, checkout
conversion, and repeat-purchase economics in five sentences.
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

logger = get_logger("daily_account_diagnosis")


def _pct_change(current: float, previous: float) -> Optional[float]:
    if previous <= 0:
        return None
    return round((current / previous - 1) * 100, 1)


def _traffic_sentence(totals: Dict[str, Any], prev: Dict[str, Any]) -> Dict[str, Any]:
    ctr = totals.get("ctr", 0)
    cpm = totals.get("cpm", 0)
    ctr_chg = _pct_change(ctr, prev.get("ctr", 0))
    trend = ""
    if ctr_chg is not None:
        trend = f" ({ctr_chg:+.0f}% vs prior period)"
    if ctr >= 1.5:
        quality = "Traffic quality looks healthy"
        detail = f"link CTR is {ctr:.2f}%{trend}, suggesting your ads are earning attention."
    elif ctr >= 0.8:
        quality = "Traffic quality is mixed"
        detail = (
            f"link CTR is {ctr:.2f}%{trend} — acceptable but not strong for supplement prospecting."
        )
    else:
        quality = "Traffic quality is weak"
        detail = (
            f"link CTR is {ctr:.2f}%{trend}. Creative hooks or audience-message fit likely need work "
            "before scaling spend."
        )
    return {
        "key": "traffic_quality",
        "label": "Traffic quality",
        "sentence": f"{quality}: {detail} CPM is {cpm:.2f}.",
        "metrics": {"ctr": ctr, "cpm": cpm, "ctr_change_pct": ctr_chg},
    }


def _creative_sentence(totals: Dict[str, Any], prev: Dict[str, Any], campaigns: List[Dict]) -> Dict[str, Any]:
    freq = totals.get("frequency", 0)
    freq_prev = prev.get("frequency", 0)
    ctr_chg = _pct_change(totals.get("ctr", 0), prev.get("ctr", 0))
    fatigue_count = 0
    for camp in campaigns:
        perf = camp["performance"]
        prev_perf = camp["previous_performance"]
        if perf["spend"] < 75:
            continue
        if (
            prev_perf.get("ctr", 0) > 0
            and perf["ctr"] <= prev_perf["ctr"] * 0.88
            and perf.get("frequency", 0) >= prev_perf.get("frequency", 0) * 1.1
        ):
            fatigue_count += 1

    if fatigue_count >= 2:
        strength = "Creative strength is fading"
        detail = (
            f"{fatigue_count} campaigns show fatigue signals (rising frequency, softer CTR). "
            "Refresh hooks before changing audiences."
        )
    elif ctr_chg is not None and ctr_chg >= 5:
        strength = "Creative strength is improving"
        detail = f"Account CTR rose {ctr_chg:+.0f}% vs the prior period while frequency held near {freq:.1f}."
    else:
        strength = "Creative strength is stable"
        detail = (
            f"Frequency is {freq:.1f} (was {freq_prev:.1f}). No broad fatigue pattern yet, "
            "but monitor top-spend ads weekly."
        )
    return {
        "key": "creative_strength",
        "label": "Creative strength",
        "sentence": f"{strength}: {detail}",
        "metrics": {"frequency": freq, "fatigue_campaigns": fatigue_count},
    }


def _landing_sentence(totals: Dict[str, Any]) -> Dict[str, Any]:
    rate = totals.get("lpv_to_atc_rate", 0)
    lpv = totals.get("landing_page_views", 0)
    if lpv < 10:
        return {
            "key": "landing_conversion",
            "label": "Landing-page conversion",
            "sentence": (
                "Landing-page conversion: insufficient landing-page view volume to judge reliably — "
                "confirm pixel events are firing."
            ),
            "metrics": {"lpv_to_atc_rate": rate, "landing_page_views": lpv},
        }
    if rate >= 8:
        verdict = "Landing-page conversion is solid"
        detail = f"{rate:.1f}% of landing views add to cart — product clarity and trust signals appear adequate."
    elif rate >= 4:
        verdict = "Landing-page conversion is moderate"
        detail = (
            f"only {rate:.1f}% of landing views add to cart. Test dosage clarity, reviews, and mobile speed."
        )
    else:
        verdict = "Landing-page conversion is weak"
        detail = (
            f"just {rate:.1f}% of landing views add to cart. Likely offer, page, or message-match bottleneck."
        )
    return {
        "key": "landing_conversion",
        "label": "Landing-page conversion",
        "sentence": f"{verdict}: {detail}",
        "metrics": {"lpv_to_atc_rate": rate},
    }


def _checkout_sentence(totals: Dict[str, Any]) -> Dict[str, Any]:
    atc_rate = totals.get("atc_to_checkout_rate", 0)
    checkout_purchase = totals.get("checkout_to_purchase_rate", 0)
    atc = totals.get("add_to_carts", 0)
    if atc < 5:
        return {
            "key": "checkout_conversion",
            "label": "Checkout conversion",
            "sentence": (
                "Checkout conversion: not enough cart events to assess checkout friction confidently."
            ),
            "metrics": {"atc_to_checkout_rate": atc_rate},
        }
    if atc_rate >= 50 and checkout_purchase >= 60:
        verdict = "Checkout conversion is healthy"
        detail = f"{atc_rate:.0f}% of carts reach checkout and {checkout_purchase:.0f}% complete purchase."
    elif atc_rate < 35:
        verdict = "Checkout conversion is leaking"
        detail = (
            f"only {atc_rate:.0f}% of add-to-carts reach checkout — check shipping disclosure, "
            "payment options, and subscription hesitation."
        )
    else:
        verdict = "Checkout conversion is mixed"
        detail = (
            f"{atc_rate:.0f}% cart-to-checkout and {checkout_purchase:.0f}% checkout-to-purchase — "
            "some friction remains after the product page."
        )
    return {
        "key": "checkout_conversion",
        "label": "Checkout conversion",
        "sentence": f"{verdict}: {detail}",
        "metrics": {"atc_to_checkout_rate": atc_rate, "checkout_to_purchase_rate": checkout_purchase},
    }


def _repeat_economics_sentence(totals: Dict[str, Any], economics) -> Dict[str, Any]:
    cpa = totals.get("cpa")
    if not economics.has_data:
        return {
            "key": "repeat_economics",
            "label": "Repeat-purchase economics",
            "sentence": (
                "Repeat-purchase economics: connect store P&L data to judge whether first-order CPA "
                "is acceptable for your supplement margin and subscription model."
            ),
            "metrics": {},
        }
    be = economics.break_even_cpa
    margin = economics.margin_percent
    if cpa is None:
        detail = "No attributed purchases in period — cannot assess acquisition economics."
    elif cpa <= be * 0.9:
        detail = (
            f"Meta CPA {cpa:.2f} is below estimated break-even {be:.2f} with {margin:.0f}% contribution margin — "
            "first-order economics look workable if repeat behavior holds."
        )
    elif cpa <= be * 1.15:
        detail = (
            f"Meta CPA {cpa:.2f} is near break-even {be:.2f}. Acceptable only if 60–90 day repeat "
            "or subscription retention is strong."
        )
    else:
        detail = (
            f"Meta CPA {cpa:.2f} exceeds break-even {be:.2f} on first-order contribution — "
            "paid media may be harvesting demand rather than building profitable new customers."
        )
    return {
        "key": "repeat_economics",
        "label": "Repeat-purchase economics",
        "sentence": f"Repeat-purchase economics: {detail}",
        "metrics": {
            "cpa": cpa,
            "break_even_cpa": round(be, 2),
            "margin_percent": round(margin, 1),
        },
    }


class DailyAccountDiagnosisService:
    async def diagnose_account(
        self,
        account_id: str,
        *,
        since: str,
        until: str,
        account_name: str = "",
        currency: str = "USD",
        explain: bool = True,
    ) -> Dict[str, Any]:
        fb = await resolve_fb_client()
        if not fb:
            return {"error": "Facebook Ads client is not configured.", "account_id": account_id}

        payload = await fetch_account_insights(fb, account_id, since=since, until=until)
        economics = load_store_economics(since, until)
        totals = payload["totals"]
        prev = payload["previous_totals"]
        campaigns = payload["campaigns"]

        sections = [
            _traffic_sentence(totals, prev),
            _creative_sentence(totals, prev, campaigns),
            _landing_sentence(totals),
            _checkout_sentence(totals),
            _repeat_economics_sentence(totals, economics),
        ]
        sentences = [s["sentence"] for s in sections]
        paragraph = " ".join(sentences)

        result = {
            "account_id": account_id,
            "account_name": account_name or account_id,
            "currency": currency,
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "comparison_period": payload["comparison_period"],
            "sections": sections,
            "sentences": sentences,
            "diagnosis": paragraph,
            "totals": totals,
            "store_economics": economics.__dict__ if economics.has_data else None,
            "campaigns_analyzed": len(campaigns),
        }

        if explain:
            result = await self._maybe_polish(result)
        return result

    async def diagnose_all(
        self,
        *,
        since: str,
        until: str,
        account_id: Optional[str] = None,
        explain: bool = True,
    ) -> Dict[str, Any]:
        fb = await resolve_fb_client()
        if not fb:
            return {"error": "Facebook Ads client is not configured.", "accounts": []}

        accounts = await fb.get_all_ad_accounts()
        if account_id:
            accounts = [a for a in accounts if a.get("id") == account_id]

        account_results = []
        for acc in accounts:
            acc_id = acc.get("id", "")
            account_results.append(
                await self.diagnose_account(
                    acc_id,
                    since=since,
                    until=until,
                    account_name=acc.get("name", ""),
                    currency=acc.get("currency", "USD"),
                    explain=explain,
                )
            )

        primary = account_results[0] if len(account_results) == 1 else None
        combined_sections: List[Dict[str, Any]] = []
        if primary and not primary.get("error"):
            combined_sections = primary.get("sections", [])
        elif account_results:
            for ar in account_results:
                if not ar.get("error"):
                    combined_sections = ar.get("sections", [])
                    primary = ar
                    break

        return {
            "period": {"since": since, "until": until, "label": period_label(since, until)},
            "accounts": account_results,
            "diagnosis": primary.get("diagnosis", "") if primary else "",
            "sections": combined_sections,
            "sentences": primary.get("sentences", []) if primary else [],
            "account_id": account_id or "",
        }

    async def _maybe_polish(self, result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from config import settings
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_google_genai import ChatGoogleGenerativeAI
            from pydantic import BaseModel, Field

            class PolishedDiagnosis(BaseModel):
                diagnosis: str = Field(..., description="Five plain-English sentences for a supplement founder.")
                sentences: List[str] = Field(..., min_length=5, max_length=5)

            llm = ChatGoogleGenerativeAI(
                model=settings.LLM_BASE_MODEL,
                temperature=0.35,
                api_key=settings.LLM_BASE_MODEL_API_KEY,
                max_retries=0,
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You polish supplement-brand Meta ad diagnoses. Use only facts from the input. "
                        "Return exactly five sentences covering traffic, creative, landing, checkout, "
                        "and repeat economics. Calm advisor tone — no shame language.",
                    ),
                    (
                        "human",
                        "Period: {period}\nDraft sentences:\n{draft}\n\nReturn polished diagnosis.",
                    ),
                ]
            )
            chain = prompt | llm.with_structured_output(PolishedDiagnosis)
            polished = await chain.ainvoke(
                {
                    "period": result["period"]["label"],
                    "draft": "\n".join(result.get("sentences", [])),
                }
            )
            result["diagnosis"] = polished.diagnosis
            result["sentences"] = polished.sentences
            for idx, section in enumerate(result.get("sections", [])):
                if idx < len(polished.sentences):
                    section["sentence"] = polished.sentences[idx]
            result["explain_meta"] = {"model_name": settings.LLM_BASE_MODEL, "polished": True}
        except Exception as exc:
            logger.warning(f"Daily diagnosis LLM polish skipped: {exc}")
            result["explain_meta"] = {"polished": False, "error": str(exc)}
        return result


daily_account_diagnosis_service = DailyAccountDiagnosisService()
