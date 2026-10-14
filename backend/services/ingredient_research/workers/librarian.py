"""Ingredient librarian worker (catalog tools)."""

from __future__ import annotations

from typing import Any

from services.ingredient_research.prompts import LIBRARIAN_PROMPT
from services.ingredient_research.tools.catalog import (
    filter_ingredient_pool,
    get_ingredient_profile,
    list_ingredients,
)


def build_librarian_agent(model: Any) -> Any:
    """Build the catalog librarian ChatAgent.

    Args:
        model: Shared CAMEL model backend.

    Returns:
        Configured ``ChatAgent`` with catalog tools.
    """
    from camel.agents import ChatAgent
    from camel.toolkits import FunctionTool

    tools = [
        FunctionTool(list_ingredients),
        FunctionTool(filter_ingredient_pool),
        FunctionTool(get_ingredient_profile),
    ]
    return ChatAgent(
        system_message=LIBRARIAN_PROMPT,
        model=model,
        tools=tools,
    )
