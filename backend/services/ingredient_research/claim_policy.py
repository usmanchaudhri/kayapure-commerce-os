"""Deterministic claim-language guards for nutraceutical research outputs."""

from __future__ import annotations

import re
from typing import Dict, List


BANNED_CLAIM_PATTERNS: List[str] = [
    r"\bcure(s|d)?\b",
    r"\btreat(s|ed|ing|ment)?\b",
    r"\bdiagnose(s|d)?\b",
    r"\bprevent(s|ed|ing)?\b",
    r"\bheal(s|ed|ing)?\b",
    r"\bclinically proven\b",
    r"\bguaranteed\b",
    r"\bmiracle\b",
]


def scan_claim_text(text: str) -> Dict[str, object]:
    """Scan copy for high-risk disease/claim language.

    Args:
        text: Free-text positioning or rationale to inspect.

    Returns:
        Dict with ``ok`` bool, ``flags`` list, and ``guidance`` string.
    """
    flags: List[str] = []
    lowered = text or ""
    for pattern in BANNED_CLAIM_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            flags.append(pattern)

    ok = len(flags) == 0
    guidance = (
        "Use structure/function language only "
        "(e.g. 'supports energy', 'may help maintain'). "
        "Avoid disease claims."
        if not ok
        else "No high-risk claim phrases detected by deterministic scanner."
    )
    return {"ok": ok, "flags": flags, "guidance": guidance}


CLAIM_GUARD_SYSTEM_PROMPT = """You are Kayapure's claims compliance reviewer for dietary supplements.
Rewrite or reject disease claims. Prefer structure/function language.
Never invent clinical proof. Flag banned phrasing (cure/treat/diagnose/prevent).
Market context may be PK or US — stay conservative for both.
Return only the cleaned research report JSON when asked to finalize.
"""
