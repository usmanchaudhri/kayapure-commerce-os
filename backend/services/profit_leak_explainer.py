"""
LLM explanations for profit leak findings.

The model receives pre-computed evidence packages and must not invent metrics.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import settings

PROMPT_VERSION = "profit_leak_explain_v1"
MAX_EXPLAINED_FINDINGS = 12


class FindingHypothesis(BaseModel):
    text: str = Field(..., description="Plausible cause stated in plain language.")
    confidence: float = Field(..., ge=0, le=1)


class FindingExplanation(BaseModel):
    finding_id: str
    explanation: str = Field(
        ...,
        description="2-4 sentences in plain English for a supplement brand founder.",
    )
    observed_facts: List[str] = Field(
        default_factory=list,
        description="Facts restated from evidence only.",
    )
    hypotheses: List[FindingHypothesis] = Field(default_factory=list)
    recommended_action: str = Field(
        ...,
        description="Concrete next step the founder can take this week.",
    )
    caveats: List[str] = Field(default_factory=list)


class ScanExplanationResult(BaseModel):
    executive_summary: str = Field(
        ...,
        description="3-5 sentence account-level summary of where money is leaking.",
    )
    finding_explanations: List[FindingExplanation]


class ProfitLeakExplainerService:
    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model=settings.LLM_BASE_MODEL,
            temperature=0.4,
            api_key=settings.LLM_BASE_MODEL_API_KEY,
            max_retries=0,
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a calm senior growth advisor for supplement DTC brands on Meta Ads. "
                    "You receive deterministic profit-leak findings with pre-computed evidence. "
                    "Your job is to explain each finding in plain language for a founder — not to "
                    "recalculate metrics or invent numbers. "
                    "Distinguish observed facts from plausible diagnoses. "
                    "Use neutral language: 'underperforming relative to account baseline' not 'bad'. "
                    "For supplement context, consider post-click trust, dosage clarity, regimen messaging, "
                    "and first-order vs repeat economics when relevant. "
                    "Never claim perfect causality. Include caveats when sample size or attribution is weak.",
                ),
                (
                    "human",
                    "Explain these profit leak findings for a supplement brand.\n"
                    "Period: {period_label}\n"
                    "Currency: {currency}\n"
                    "Total estimated monthly opportunity: {opportunity_range}\n\n"
                    "Findings with evidence packages (JSON):\n{findings_json}\n\n"
                    "Return an executive_summary plus one finding_explanation per finding id.",
                ),
            ]
        )
        self.chain = self.prompt | self.llm.with_structured_output(ScanExplanationResult)

    async def explain_scan(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        findings = list(scan_result.get("findings") or [])
        if not findings:
            return {
                "executive_summary": "",
                "finding_explanations": {},
                "prompt_version": PROMPT_VERSION,
                "model_name": settings.LLM_BASE_MODEL,
                "explained_count": 0,
            }

        to_explain = findings[:MAX_EXPLAINED_FINDINGS]
        packages = [_evidence_package(f) for f in to_explain]
        summary = scan_result.get("summary") or {}
        currency = summary.get("currency", "USD")
        opp_min = summary.get("total_opportunity_min", 0)
        opp_max = summary.get("total_opportunity_max", 0)
        period_label = summary.get("period_label", "")

        try:
            result = await self.chain.ainvoke(
                {
                    "period_label": period_label,
                    "currency": currency,
                    "opportunity_range": f"{currency} {opp_min:,.0f} – {opp_max:,.0f} / month",
                    "findings_json": json.dumps(packages, default=str),
                }
            )
            by_id = {ex.finding_id: ex.model_dump() for ex in result.finding_explanations}
            return {
                "executive_summary": result.executive_summary,
                "finding_explanations": by_id,
                "prompt_version": PROMPT_VERSION,
                "model_name": settings.LLM_BASE_MODEL,
                "explained_count": len(by_id),
            }
        except Exception as exc:
            return {
                "executive_summary": "",
                "finding_explanations": {},
                "prompt_version": PROMPT_VERSION,
                "model_name": settings.LLM_BASE_MODEL,
                "explained_count": 0,
                "error": str(exc),
            }


def _evidence_package(finding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": finding.get("id"),
        "category": finding.get("category"),
        "severity": finding.get("severity"),
        "title": finding.get("title"),
        "deterministic_diagnosis": finding.get("diagnosis"),
        "deterministic_recommendation": finding.get("recommendation"),
        "confidence": finding.get("confidence"),
        "estimated_impact_min": finding.get("estimated_impact_min"),
        "estimated_impact_max": finding.get("estimated_impact_max"),
        "entity_type": finding.get("entity_type"),
        "entity_id": finding.get("entity_id"),
        "entity_name": finding.get("entity_name"),
        "account_name": finding.get("account_name"),
        "evidence": finding.get("evidence", []),
        "experiment": finding.get("experiment", {}),
        "caveats": finding.get("caveats", []),
    }


def merge_explanations(
    scan_result: Dict[str, Any],
    explanation_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach LLM explanations onto finding dicts in-place."""
    by_id = explanation_payload.get("finding_explanations") or {}
    enriched: List[Dict[str, Any]] = []
    for finding in scan_result.get("findings", []):
        merged = dict(finding)
        ex = by_id.get(finding.get("id", ""))
        if ex:
            merged["llm_explanation"] = ex.get("explanation", "")
            merged["llm_observed_facts"] = ex.get("observed_facts", [])
            merged["llm_hypotheses"] = ex.get("hypotheses", [])
            merged["llm_caveats"] = ex.get("caveats", [])
            merged["llm_recommended_action"] = ex.get("recommended_action", "")
        enriched.append(merged)

    scan_result["findings"] = enriched
    scan_result["executive_summary"] = explanation_payload.get("executive_summary", "")
    scan_result["explain_meta"] = {
        "prompt_version": explanation_payload.get("prompt_version"),
        "model_name": explanation_payload.get("model_name"),
        "explained_count": explanation_payload.get("explained_count", 0),
        "error": explanation_payload.get("error"),
    }
    return scan_result


profit_leak_explainer_service = ProfitLeakExplainerService()
