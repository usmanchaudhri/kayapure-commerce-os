"""Evidence scout worker (PubMed tools)."""

from __future__ import annotations

from typing import Any

from services.ingredient_research.prompts import EVIDENCE_SCOUT_PROMPT
from services.ingredient_research.tools.catalog import get_ingredient_profile, list_ingredients
from services.ingredient_research.tools.pubmed import (
    search_ingredient_evidence,
    search_pubmed,
)


def build_evidence_scout_agent(model: Any) -> Any:
    """Build the PubMed evidence scout ChatAgent.

    Args:
        model: Shared CAMEL model backend.

    Returns:
        Configured ``ChatAgent`` with PubMed and catalog lookup tools.
    """
    from camel.agents import ChatAgent
    from camel.toolkits import FunctionTool

    tools = [
        FunctionTool(search_pubmed),
        FunctionTool(search_ingredient_evidence),
        FunctionTool(get_ingredient_profile),
        FunctionTool(list_ingredients),
    ]
    return ChatAgent(
        system_message=EVIDENCE_SCOUT_PROMPT,
        model=model,
        tools=tools,
    )
