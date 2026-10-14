"""Deterministic safety flags used by Phase-1 claim/safety guidance."""

from __future__ import annotations

from typing import Dict, List

from services.ingredient_research.tools.catalog import load_priority_tags


HIGH_RISK_INGREDIENTS = {
    "yohimbine": "Stimulant / cardiovascular risk — hard exclude for consumer stacks.",
    "senna leaf": "Stimulant laxative — not suitable for daily wellness stacks.",
    "st john wort": "CYP3A4 inducer — major drug interaction risk.",
    "st. john wort": "CYP3A4 inducer — major drug interaction risk.",
}


def check_ingredients(names: List[str]) -> Dict[str, object]:
    """Apply hard-rule safety checks to a list of ingredient names.

    Args:
        names: Candidate ingredient names.

    Returns:
        Dict with ``flags``, ``blocked``, and ``allowed`` lists.
    """
    names = names or []
    priority = load_priority_tags()
    default_excludes = {
        n.lower() for n in (priority.get("default_hard_excludes") or [])
    }

    flags: List[str] = []
    blocked: List[str] = []
    allowed: List[str] = []

    for name in names:
        key = name.strip().lower()
        risk = HIGH_RISK_INGREDIENTS.get(key)
        if risk or key in default_excludes:
            blocked.append(name)
            flags.append(f"{name}: {risk or 'listed in default hard excludes'}")
        else:
            allowed.append(name)

    return {"flags": flags, "blocked": blocked, "allowed": allowed}
