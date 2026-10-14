"""CAMEL Workforce factory for Kayapure ingredient research (Phase 1)."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from config import settings
from services.ingredient_research.models_camel import create_research_model
from services.ingredient_research.progress import make_event
from services.ingredient_research.prompts import COORDINATOR_PROMPT, TASK_PLANNER_PROMPT
from services.ingredient_research.workers import (
    build_claim_guard_agent,
    build_evidence_scout_agent,
    build_librarian_agent,
    build_synergy_analyst_agent,
)
from utils.logging_config import get_logger

logger = get_logger("ingredient_research")


def build_workforce(
    *,
    task_timeout_seconds: Optional[int] = None,
    callbacks: Optional[List[Any]] = None,
    stream_callback: Optional[Callable[..., Any]] = None,
) -> Any:
    """Construct the Phase-1 CAMEL Workforce with four specialist workers.

    Workers:
        - ingredient_librarian
        - evidence_scout
        - synergy_analyst
        - claim_guard

    Args:
        task_timeout_seconds: Optional per-workforce timeout override.
        callbacks: Optional CAMEL WorkforceCallback instances (e.g. streaming).
        stream_callback: Optional real-time token/chunk callback from workers.

    Returns:
        Configured CAMEL ``Workforce`` instance.

    Raises:
        ImportError: If camel-ai cannot be imported.
        RuntimeError: If model credentials are missing.
    """
    from camel.agents import ChatAgent
    from camel.societies.workforce import Workforce, WorkforceMode

    model = create_research_model()
    timeout = task_timeout_seconds or settings.INGREDIENT_RESEARCH_TIMEOUT_SEC

    coordinator = ChatAgent(system_message=COORDINATOR_PROMPT, model=model)
    task_agent = ChatAgent(system_message=TASK_PLANNER_PROMPT, model=model)

    workforce = Workforce(
        description=(
            "Kayapure Ingredient Research Team — researches approved catalog "
            "ingredients and proposes claim-safe combination candidates."
        ),
        coordinator_agent=coordinator,
        task_agent=task_agent,
        default_model=model,
        task_timeout_seconds=float(timeout),
        use_structured_output_handler=True,
        mode=WorkforceMode.AUTO_DECOMPOSE,
        callbacks=callbacks or None,
        stream_callback=stream_callback,
    )

    workforce.add_single_agent_worker(
        description=(
            "ingredient_librarian: filters the approved Kayapure catalog, "
            "returns ingredient profiles and the research pool."
        ),
        worker=build_librarian_agent(model),
    )
    workforce.add_single_agent_worker(
        description=(
            "evidence_scout: searches PubMed for ingredient evidence and "
            "returns only tool-backed citations (never invent PMIDs)."
        ),
        worker=build_evidence_scout_agent(model),
    )
    workforce.add_single_agent_worker(
        description=(
            "synergy_analyst: proposes effective ingredient combinations for "
            "the stated health goal within format and max_ingredients limits."
        ),
        worker=build_synergy_analyst_agent(model),
    )
    workforce.add_single_agent_worker(
        description=(
            "claim_guard: rewrites disease claims into structure/function "
            "language and emits the final ResearchReport JSON."
        ),
        worker=build_claim_guard_agent(model),
    )

    logger.info(
        "Built ingredient research Workforce (timeout=%ss, mode=auto_decompose)",
        timeout,
    )
    return workforce


def build_task_content(
    *,
    goal: str,
    pool: List[str],
    max_ingredients: int,
    format_name: str,
    market: str,
    max_combos: int,
) -> str:
    """Compose the Workforce Task content string for a research run.

    Args:
        goal: Health outcome goal.
        pool: Ingredient names in the research pool.
        max_ingredients: Max ingredients per combo.
        format_name: Delivery format (gummy, powder, etc.).
        market: Market / claims locale hint.
        max_combos: Maximum combo candidates to propose.

    Returns:
        Detailed task instruction for CAMEL Task(content=...).
    """
    pool_lines = "\n".join(f"- {name}" for name in pool)
    return f"""
Run Kayapure ingredient combination research.

Goal: {goal}
Delivery format: {format_name}
Market / claims context: {market}
Max ingredients per combo: {max_ingredients}
Max combo candidates: {max_combos}

Approved research pool ({len(pool)} ingredients):
{pool_lines}

Required workflow:
1) Librarian: confirm pool profiles from catalog tools only.
2) Evidence scout: gather PubMed evidence for the most relevant pool items (not necessarily all if pool is large; prioritize best fits). Never invent citations.
3) Synergy analyst: propose up to {max_combos} combinations using only pool ingredients. Label synergy_type. Run safety check tool on each combo.
4) Claim guard: finalize ONE JSON object with keys:
   summary, ingredient_dossiers, combo_candidates, rejected_or_deferred,
   open_questions, citations, disclaimer.

Hard rules:
- Only use ingredients from the approved pool.
- Citations must come from PubMed tools (include pmid/url).
- No disease claims (cure/treat/diagnose/prevent).
- Evidence grades: strong | mixed | weak | traditional_only | insufficient.
- This is internal R&D decision support, not medical advice.
""".strip()
