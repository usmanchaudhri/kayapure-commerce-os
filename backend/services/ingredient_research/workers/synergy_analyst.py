"""Synergy analyst worker (combination proposals)."""

from __future__ import annotations

from typing import Any

from services.ingredient_research.prompts import SYNERGY_ANALYST_PROMPT
from services.ingredient_research.tools.safety_rules import check_ingredients


def build_synergy_analyst_agent(model: Any) -> Any:
    """Build the synergy / combination ChatAgent.

    Args:
        model: Shared CAMEL model backend.

    Returns:
        Configured ``ChatAgent`` with safety_rules helper tool.
    """
    from camel.agents import ChatAgent
    from camel.toolkits import FunctionTool

    tools = [FunctionTool(check_ingredients)]
    return ChatAgent(
        system_message=SYNERGY_ANALYST_PROMPT,
        model=model,
        tools=tools,
    )
