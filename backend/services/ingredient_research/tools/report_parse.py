"""Parse and validate Workforce free-text into ResearchReport models."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from services.ingredient_research.schemas import (
    Citation,
    ComboCandidate,
    EvidenceGrade,
    IngredientDossier,
    RejectedOrDeferred,
    ResearchReport,
    RunMetadata,
)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from an LLM/workforce string.

    Args:
        text: Raw model or task result text.

    Returns:
        Parsed dict, or None if parsing fails.
    """
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _grade(value: Any) -> EvidenceGrade:
    """Coerce an evidence grade string into the EvidenceGrade enum.

    Args:
        value: Raw grade value.

    Returns:
        EvidenceGrade member (defaults to insufficient).
    """
    try:
        return EvidenceGrade(str(value or "insufficient").lower())
    except ValueError:
        return EvidenceGrade.INSUFFICIENT


def parse_research_report(
    raw_text: str,
    *,
    goal: str,
    metadata: RunMetadata,
    fallback_pool: Optional[List[str]] = None,
) -> ResearchReport:
    """Validate workforce output into a ResearchReport.

    Args:
        raw_text: Raw textual result from the CAMEL Workforce task.
        goal: Original research goal.
        metadata: Run metadata to attach.
        fallback_pool: Ingredient pool used if dossiers are missing.

    Returns:
        A validated ResearchReport (best-effort if JSON is incomplete).
    """
    data = _extract_json_object(raw_text) or {}

    dossiers: List[IngredientDossier] = []
    for item in data.get("ingredient_dossiers") or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        citations = [
            Citation(**c) if isinstance(c, dict) else Citation(title=str(c))
            for c in (item.get("citations") or [])
            if isinstance(c, (dict, str))
        ]
        dossiers.append(
            IngredientDossier(
                name=str(item["name"]),
                evidence_grade=_grade(item.get("evidence_grade")),
                key_findings=list(item.get("key_findings") or []),
                typical_uses=list(item.get("typical_uses") or []),
                citations=citations,
                notes=str(item.get("notes") or ""),
            )
        )

    combos: List[ComboCandidate] = []
    for item in data.get("combo_candidates") or []:
        if not isinstance(item, dict):
            continue
        ingredients = [str(x) for x in (item.get("ingredients") or []) if x]
        if len(ingredients) < 2:
            continue
        combos.append(
            ComboCandidate(
                name=str(item.get("name") or "Untitled combo"),
                ingredients=ingredients,
                rationale=str(item.get("rationale") or ""),
                synergy_type=str(item.get("synergy_type") or "hypothesis"),
                evidence_grade=_grade(item.get("evidence_grade")),
                safety_flags=list(item.get("safety_flags") or []),
                confidence=float(item.get("confidence") or 0.3),
                claim_safe_positioning=str(item.get("claim_safe_positioning") or ""),
            )
        )

    rejected = [
        RejectedOrDeferred(item=str(r.get("item") or ""), reason=str(r.get("reason") or ""))
        for r in (data.get("rejected_or_deferred") or [])
        if isinstance(r, dict)
    ]

    citations: List[Citation] = []
    for c in data.get("citations") or []:
        if isinstance(c, dict):
            citations.append(Citation(**{k: c.get(k, "") for k in Citation.model_fields}))
        elif isinstance(c, str):
            citations.append(Citation(title=c))

    summary = str(data.get("summary") or "").strip()
    if not summary:
        summary = (
            f"Research run for goal '{goal}' produced "
            f"{len(combos)} combo candidate(s) across {len(dossiers) or len(fallback_pool or [])} ingredients. "
            "Human formulator review required."
        )

    if not dossiers and fallback_pool:
        dossiers = [
            IngredientDossier(
                name=name,
                evidence_grade=EvidenceGrade.INSUFFICIENT,
                key_findings=["Dossier details were not returned in structured form."],
            )
            for name in fallback_pool
        ]

    open_questions = [str(q) for q in (data.get("open_questions") or [])]

    return ResearchReport(
        summary=summary,
        goal=goal,
        ingredient_dossiers=dossiers,
        combo_candidates=combos,
        rejected_or_deferred=rejected,
        open_questions=open_questions,
        citations=citations,
        disclaimer=str(
            data.get("disclaimer")
            or ResearchReport.model_fields["disclaimer"].default
        ),
        run_metadata=metadata,
    )
