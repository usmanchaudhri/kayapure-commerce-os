"""Claim guard worker (structure/function language)."""

from __future__ import annotations

from typing import Any

from services.ingredient_research.claim_policy import (
    CLAIM_GUARD_SYSTEM_PROMPT,
    scan_claim_text,
)
from services.ingredient_research.prompts import CLAIM_GUARD_PROMPT


def build_claim_guard_agent(model: Any) -> Any:
    """Build the claims compliance ChatAgent.

    Args:
        model: Shared CAMEL model backend.

    Returns:
        Configured ``ChatAgent`` with claim scanner tool.
    """
    from camel.agents import ChatAgent
    from camel.toolkits import FunctionTool

    tools = [FunctionTool(scan_claim_text)]
    return ChatAgent(
        system_message=f"{CLAIM_GUARD_PROMPT}\n\n{CLAIM_GUARD_SYSTEM_PROMPT}",
        model=model,
        tools=tools,
    )
