"""CAMEL model factory helpers for the ingredient research workforce."""

from __future__ import annotations

import os
from typing import Any, Optional

from config import settings
from utils.logging_config import get_logger

logger = get_logger("ingredient_research")


def ensure_google_api_key() -> None:
    """Export Gemini/Google API keys for CAMEL model backends when missing.

    CAMEL's Gemini platform expects ``GEMINI_API_KEY``. We also set
    ``GOOGLE_API_KEY`` for compatibility with other Google clients.

    Returns:
        None
    """
    api_key = settings.GOOGLE_API_KEY or settings.LLM_BASE_MODEL_API_KEY
    if not api_key:
        return
    if not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = api_key
    if not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = api_key


def resolve_model_type_name(raw: str) -> str:
    """Map a Commerce OS model string to a CAMEL ModelType-like name.

    Args:
        raw: Model id from settings (e.g. ``gemini-2.0-flash``).

    Returns:
        Uppercase underscored candidate name (e.g. ``GEMINI_2_0_FLASH``).
    """
    cleaned = raw.strip().lower().replace("-", "_").replace(".", "_")
    # Drop common preview/experimental suffixes that break enum lookup.
    for suffix in ("_preview", "_exp", "_thinking", "_lite_preview"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    if not cleaned.startswith("gemini") and "gemini" in cleaned:
        cleaned = "gemini" + cleaned.split("gemini", 1)[1]
    return cleaned.upper()


def create_research_model() -> Any:
    """Create the shared CAMEL model backend for research workers.

    Returns:
        A CAMEL model backend instance.

    Raises:
        RuntimeError: If CAMEL is unavailable or no API key is configured.
        ImportError: If camel-ai is not installed.
    """
    if not settings.ingredient_research_ready:
        raise RuntimeError(
            "Ingredient research requires GOOGLE_API_KEY or LLM_BASE_MODEL_API_KEY."
        )

    ensure_google_api_key()

    from camel.models import ModelFactory
    from camel.types import ModelPlatformType, ModelType

    platform_raw = (settings.INGREDIENT_RESEARCH_MODEL_PLATFORM or "gemini").lower()
    if platform_raw in {"gemini", "google", "google_genai"}:
        platform = ModelPlatformType.GEMINI
    else:
        try:
            platform = ModelPlatformType[platform_raw.upper()]
        except KeyError as exc:
            raise RuntimeError(
                f"Unsupported INGREDIENT_RESEARCH_MODEL_PLATFORM={platform_raw}"
            ) from exc

    model_raw = settings.INGREDIENT_RESEARCH_MODEL_TYPE
    candidate = resolve_model_type_name(model_raw)
    model_type: Optional[ModelType] = None
    for name in (
        candidate,
        candidate.replace("GEMINI_3_1", "GEMINI_3_1"),
        "GEMINI_2_0_FLASH",
        "GEMINI_2_5_FLASH",
    ):
        try:
            model_type = ModelType[name]
            break
        except KeyError:
            continue

    if model_type is None:
        # Fall back to string model id supported by ModelFactory.
        logger.warning(
            "CAMEL ModelType enum miss for %s; using string model id", model_raw
        )
        return ModelFactory.create(
            model_platform=platform,
            model_type=model_raw,
        )

    logger.info(
        "Creating CAMEL research model platform=%s type=%s",
        platform.name,
        model_type.name,
    )
    return ModelFactory.create(
        model_platform=platform,
        model_type=model_type,
    )
