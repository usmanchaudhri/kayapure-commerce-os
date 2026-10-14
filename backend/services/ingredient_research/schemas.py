"""Pydantic contracts for the ingredient research Agent #1 API and reports."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceGrade(str, Enum):
    """Strength of supporting evidence for an ingredient or combination."""

    STRONG = "strong"
    MIXED = "mixed"
    WEAK = "weak"
    TRADITIONAL_ONLY = "traditional_only"
    INSUFFICIENT = "insufficient"


class Citation(BaseModel):
    """A single literature or web citation returned by research tools."""

    title: str = Field(..., description="Publication or page title.")
    url: str = Field(default="", description="Canonical URL when available.")
    pmid: str = Field(default="", description="PubMed ID when available.")
    source: str = Field(default="pubmed", description="Origin system, e.g. pubmed.")
    year: Optional[str] = Field(default=None, description="Publication year if known.")
    snippet: str = Field(default="", description="Short excerpt or abstract snippet.")


class IngredientDossier(BaseModel):
    """Structured profile for one researched ingredient."""

    name: str
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT
    key_findings: List[str] = Field(default_factory=list)
    typical_uses: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    notes: str = Field(default="")


class ComboCandidate(BaseModel):
    """A proposed multi-ingredient combination for a health goal."""

    name: str = Field(..., description="Short marketing-safe combo name.")
    ingredients: List[str] = Field(..., min_length=2)
    rationale: str
    synergy_type: str = Field(
        default="hypothesis",
        description="hypothesis | cited | traditional_pairing",
    )
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT
    safety_flags: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)
    claim_safe_positioning: str = Field(
        default="",
        description="Structure/function style positioning copy.",
    )


class RejectedOrDeferred(BaseModel):
    """An ingredient or idea deferred with an explicit reason."""

    item: str
    reason: str


class RunMetadata(BaseModel):
    """Operational metadata for a single research run."""

    run_id: str
    model: str = ""
    duration_seconds: float = 0.0
    pool_size: int = 0
    pool: List[str] = Field(default_factory=list)
    mode: str = "auto_decompose"
    camel_available: bool = True
    artifact_path: str = ""


class ResearchReport(BaseModel):
    """Final structured output of the ingredient research workforce."""

    summary: str
    goal: str
    ingredient_dossiers: List[IngredientDossier] = Field(default_factory=list)
    combo_candidates: List[ComboCandidate] = Field(default_factory=list)
    rejected_or_deferred: List[RejectedOrDeferred] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "For internal product R&D only. Not medical advice. "
            "Does not diagnose, treat, cure, or prevent any disease. "
            "Human formulator review required before any SKU or marketing use."
        )
    )
    run_metadata: RunMetadata


class IngredientComboRequest(BaseModel):
    """HTTP request body for POST /api/research/ingredient-combos."""

    goal: str = Field(
        ...,
        min_length=3,
        description="Health outcome to optimize for, e.g. adult vitality.",
    )
    max_ingredients: int = Field(default=7, ge=2, le=12)
    format: str = Field(default="gummy", description="Delivery format constraint.")
    include_tags: List[str] = Field(
        default_factory=lambda: ["highlighted", "seven_in_one_family"],
        description="Catalog tags used to build the research pool.",
    )
    exclude: List[str] = Field(default_factory=list)
    market: str = Field(default="PK", description="Market / claims locale hint.")
    ingredient_limit: Optional[int] = Field(
        default=None,
        ge=5,
        le=60,
        description="Max ingredients in the research pool.",
    )
    mode: str = Field(
        default="auto_decompose",
        description="Workforce mode: auto_decompose (Phase 1).",
    )
    explicit_ingredients: List[str] = Field(
        default_factory=list,
        description="Optional explicit ingredient names to force into the pool.",
    )


class IngredientCatalogItem(BaseModel):
    """One row from the local ingredient master list."""

    name: str
    canonical: str
    category: str = "herbal_extract"
    tags: List[str] = Field(default_factory=list)


class IngredientCatalogResponse(BaseModel):
    """Response for GET /api/research/ingredients."""

    count: int
    ingredients: List[IngredientCatalogItem]


class ResearchRunSummary(BaseModel):
    """Lightweight listing row for persisted research runs."""

    run_id: str
    goal: str
    created_at: str
    pool_size: int
    combo_count: int
    artifact_path: str


class ResearchRunListResponse(BaseModel):
    """Response for GET /api/research/runs."""

    count: int
    runs: List[ResearchRunSummary]
