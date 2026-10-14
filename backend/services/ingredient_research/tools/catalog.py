"""Local ingredient catalog tools backed by master_list.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from config import settings

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "ingredients"
MASTER_LIST_PATH = DATA_DIR / "master_list.json"
PRIORITY_TAGS_PATH = DATA_DIR / "priority_tags.json"


@lru_cache(maxsize=1)
def load_master_list() -> Dict[str, Any]:
    """Load and cache the ingredient master list JSON.

    Returns:
        Parsed master list document.

    Raises:
        FileNotFoundError: If the catalog file is missing.
    """
    if not MASTER_LIST_PATH.exists():
        raise FileNotFoundError(f"Missing ingredient catalog: {MASTER_LIST_PATH}")
    return json.loads(MASTER_LIST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_priority_tags() -> Dict[str, Any]:
    """Load and cache priority tag definitions.

    Returns:
        Parsed priority tags document.
    """
    if not PRIORITY_TAGS_PATH.exists():
        return {
            "highlighted": [],
            "seven_in_one_family": [],
            "default_hard_excludes": [],
        }
    return json.loads(PRIORITY_TAGS_PATH.read_text(encoding="utf-8"))


def list_ingredients(
    tags: List[str] = None,
    category: str = "",
    limit: int = 0,
) -> List[Dict[str, Any]]:
    """List ingredients from the local catalog with optional filters.

    Args:
        tags: Keep ingredients that contain any of these tags.
        category: Exact category filter when provided (empty = no filter).
        limit: Maximum rows to return (0 = no limit).

    Returns:
        List of ingredient dicts (name, canonical, category, tags).
    """
    ingredients = list(load_master_list().get("ingredients") or [])
    if tags:
        tag_set = {t.lower() for t in tags}
        ingredients = [
            item
            for item in ingredients
            if tag_set.intersection({t.lower() for t in (item.get("tags") or [])})
        ]
    if category:
        ingredients = [
            item
            for item in ingredients
            if str(item.get("category", "")).lower() == category.lower()
        ]
    if limit and limit > 0:
        ingredients = ingredients[: max(0, int(limit))]
    return ingredients


def filter_ingredient_pool(
    include_tags: List[str] = None,
    exclude: List[str] = None,
    explicit_ingredients: List[str] = None,
    ingredient_limit: int = 0,
) -> List[str]:
    """Build a research pool of ingredient names for a Workforce run.

    Args:
        include_tags: Catalog tags that should be included.
        exclude: Ingredient names to drop (case-insensitive).
        explicit_ingredients: Names forced into the pool when present in catalog.
        ingredient_limit: Cap on pool size (0 = settings default).

    Returns:
        Ordered unique ingredient name list.
    """
    limit = ingredient_limit or settings.INGREDIENT_RESEARCH_DEFAULT_LIMIT
    priority = load_priority_tags()
    hard_excludes = {
        n.lower() for n in (priority.get("default_hard_excludes") or [])
    }
    hard_excludes.update(n.lower() for n in (exclude or []))

    selected: List[str] = []
    seen = set()

    def _add(name: str) -> None:
        key = name.lower().strip()
        if not key or key in seen or key in hard_excludes:
            return
        seen.add(key)
        selected.append(name)

    for name in explicit_ingredients or []:
        _add(name)

    tags = list(include_tags or ["highlighted", "seven_in_one_family"])
    for item in list_ingredients(tags=tags, limit=0):
        _add(str(item.get("name") or ""))

    # If tags yielded too few items, top up from full catalog.
    if len(selected) < min(10, limit):
        for item in list_ingredients(limit=0):
            _add(str(item.get("name") or ""))
            if len(selected) >= limit:
                break

    return selected[:limit]


def get_ingredient_profile(name: str) -> Dict[str, Any]:
    """Return a single catalog profile by exact or case-insensitive name.

    Args:
        name: Ingredient name to look up.

    Returns:
        Ingredient dict, or ``{"error": ...}`` when missing.
    """
    needle = name.strip().lower()
    for item in load_master_list().get("ingredients") or []:
        if str(item.get("name", "")).lower() == needle:
            return item
        if str(item.get("canonical", "")).lower() == needle:
            return item
    return {"error": f"Ingredient not found in catalog: {name}"}
