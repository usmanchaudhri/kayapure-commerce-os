"""FastAPI-facing façade for the CAMEL ingredient research Workforce."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from config import settings
from services.ingredient_research.progress import build_streaming_callback, make_event
from services.ingredient_research.schemas import (
    IngredientCatalogItem,
    IngredientCatalogResponse,
    IngredientComboRequest,
    ResearchReport,
    ResearchRunListResponse,
    ResearchRunSummary,
    RunMetadata,
)
from services.ingredient_research.store import ingredient_research_store
from services.ingredient_research.tools.catalog import filter_ingredient_pool, list_ingredients
from services.ingredient_research.tools.report_parse import parse_research_report
from services.ingredient_research.workforce import build_task_content, build_workforce
from utils.logging_config import get_logger

logger = get_logger("ingredient_research")

EventCallback = Callable[[Dict[str, Any]], None]


class IngredientResearchService:
    """Orchestrates Phase-1 CAMEL Workforce ingredient research runs."""

    def __init__(self) -> None:
        """Initialize the service façade."""
        self.store = ingredient_research_store

    @property
    def is_ready(self) -> bool:
        """Return True when API keys required for CAMEL Gemini are present.

        Returns:
            Readiness flag.
        """
        return settings.ingredient_research_ready

    def get_catalog(
        self,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> IngredientCatalogResponse:
        """Return the local ingredient catalog.

        Args:
            tags: Optional tag filters.
            limit: Optional max rows.

        Returns:
            IngredientCatalogResponse with matching ingredients.
        """
        rows = list_ingredients(tags=tags or [], limit=limit or 0)
        ingredients = [
            IngredientCatalogItem(
                name=str(r.get("name") or ""),
                canonical=str(r.get("canonical") or r.get("name") or ""),
                category=str(r.get("category") or "herbal_extract"),
                tags=list(r.get("tags") or []),
            )
            for r in rows
            if r.get("name")
        ]
        return IngredientCatalogResponse(count=len(ingredients), ingredients=ingredients)

    def list_runs(self, limit: int = 50) -> ResearchRunListResponse:
        """List persisted research runs.

        Args:
            limit: Max runs to return.

        Returns:
            ResearchRunListResponse.
        """
        runs = self.store.list_runs(limit=limit)
        return ResearchRunListResponse(count=len(runs), runs=runs)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a persisted research run payload.

        Args:
            run_id: Run identifier.

        Returns:
            Stored JSON dict, or None.
        """
        return self.store.get_report(run_id)

    async def research_combos(
        self,
        request: IngredientComboRequest,
        *,
        on_event: Optional[EventCallback] = None,
    ) -> ResearchReport:
        """Run the CAMEL Workforce and return a structured ResearchReport.

        Args:
            request: Combo research request parameters.
            on_event: Optional live progress callback for UI streaming.

        Returns:
            Validated ResearchReport (also persisted to disk).

        Raises:
            RuntimeError: If the service is not configured or CAMEL fails hard.
        """
        if not self.is_ready:
            raise RuntimeError(
                "Ingredient research is not configured. "
                "Set GOOGLE_API_KEY or LLM_BASE_MODEL_API_KEY."
            )

        def _emit(event: Dict[str, Any]) -> None:
            if on_event is not None:
                on_event(event)

        run_id = str(uuid.uuid4())
        _emit(
            make_event(
                "run_started",
                "Research run started",
                f"Goal: {request.goal}",
                task_id=run_id,
            )
        )

        pool = filter_ingredient_pool(
            include_tags=request.include_tags or [],
            exclude=request.exclude or [],
            explicit_ingredients=request.explicit_ingredients or [],
            ingredient_limit=request.ingredient_limit
            or settings.INGREDIENT_RESEARCH_DEFAULT_LIMIT,
        )
        if len(pool) < 2:
            raise RuntimeError(
                "Ingredient pool too small after filters. "
                "Relax include_tags/exclude or add explicit_ingredients."
            )

        _emit(
            make_event(
                "pool_selected",
                f"Ingredient pool selected ({len(pool)})",
                ", ".join(pool),
            )
        )

        logger.info(
            "Starting ingredient research run_id=%s goal=%r pool_size=%s",
            run_id,
            request.goal,
            len(pool),
        )

        progress_cb = build_streaming_callback(on_event)

        def _stream_callback(
            worker_id: Any = None,
            task_id: Any = None,
            text: Any = None,
            mode: Any = None,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            """Forward CAMEL worker stream chunks into the progress sink."""
            chunk = text if text is not None else kwargs.get("text", "")
            if not chunk:
                return
            _emit(
                make_event(
                    "stream",
                    "Worker stream",
                    str(chunk)[:600],
                    worker=str(worker_id or ""),
                    task_id=str(task_id or ""),
                )
            )

        started = time.time()
        workforce = build_workforce(
            task_timeout_seconds=settings.INGREDIENT_RESEARCH_TIMEOUT_SEC,
            callbacks=[progress_cb],
            stream_callback=_stream_callback,
        )
        from camel.tasks import Task

        task = Task(
            content=build_task_content(
                goal=request.goal,
                pool=pool,
                max_ingredients=request.max_ingredients,
                format_name=request.format,
                market=request.market,
                max_combos=settings.INGREDIENT_RESEARCH_MAX_COMBOS,
            ),
            additional_info={
                "goal": request.goal,
                "pool": pool,
                "format": request.format,
                "market": request.market,
                "max_ingredients": request.max_ingredients,
                "run_id": run_id,
            },
            id=run_id,
        )

        _emit(
            make_event(
                "workforce_running",
                "Workforce executing",
                "Librarian → Evidence scout → Synergy analyst → Claim guard",
            )
        )

        result = await workforce.process_task_async(task)
        duration = time.time() - started
        raw_text = self._extract_result_text(result)

        metadata = RunMetadata(
            run_id=run_id,
            model=settings.INGREDIENT_RESEARCH_MODEL_TYPE,
            duration_seconds=round(duration, 2),
            pool_size=len(pool),
            pool=pool,
            mode=request.mode or "auto_decompose",
            camel_available=True,
        )
        report = parse_research_report(
            raw_text,
            goal=request.goal,
            metadata=metadata,
            fallback_pool=pool,
        )
        # Cap combos defensively.
        report.combo_candidates = report.combo_candidates[
            : settings.INGREDIENT_RESEARCH_MAX_COMBOS
        ]
        path = self.store.save_report(report)
        report.run_metadata.artifact_path = path
        _emit(
            make_event(
                "run_completed",
                "Research run completed",
                f"{len(report.combo_candidates)} combo(s) in {duration:.1f}s → {path}",
                task_id=run_id,
            )
        )
        logger.info(
            "Completed ingredient research run_id=%s combos=%s duration=%.1fs path=%s",
            run_id,
            len(report.combo_candidates),
            duration,
            path,
        )
        return report

    def _extract_result_text(self, result: Any) -> str:
        """Normalize CAMEL task/workforce result objects into text.

        Args:
            result: Return value from ``process_task_async``.

        Returns:
            Best-effort string content for JSON parsing.
        """
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        for attr in ("result", "content", "msg", "message"):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value.strip():
                return value
            if value is not None and hasattr(value, "content"):
                content = getattr(value, "content", None)
                if isinstance(content, str):
                    return content
        # Task objects often store the final answer on `.result`.
        if hasattr(result, "model_dump"):
            dumped = result.model_dump()
            for key in ("result", "content"):
                if isinstance(dumped.get(key), str):
                    return dumped[key]
            return str(dumped)
        return str(result)


ingredient_research_service = IngredientResearchService()
