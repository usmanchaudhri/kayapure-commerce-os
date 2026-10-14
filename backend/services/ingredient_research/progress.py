"""Live progress events for the ingredient research Workforce."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger("ingredient_research")

EventSink = Callable[[Dict[str, Any]], None]


def _now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string.

    Returns:
        ISO timestamp string.
    """
    return datetime.now(timezone.utc).isoformat()


def make_event(
    kind: str,
    title: str,
    detail: str = "",
    *,
    worker: str = "",
    task_id: str = "",
) -> Dict[str, Any]:
    """Build a normalized progress event dictionary.

    Args:
        kind: Event category (e.g. ``task_started``, ``log``, ``stream``).
        title: Short human-readable headline.
        detail: Optional longer detail text.
        worker: Optional worker id / role label.
        task_id: Optional CAMEL task id.

    Returns:
        Event dict suitable for Shiny live logs.
    """
    return {
        "ts": _now_iso(),
        "kind": kind,
        "title": title,
        "detail": (detail or "")[:2000],
        "worker": worker or "",
        "task_id": task_id or "",
    }


def build_streaming_callback(sink: Optional[EventSink] = None) -> Any:
    """Create a CAMEL WorkforceCallback that forwards events to ``sink``.

    Args:
        sink: Callable that receives event dicts for live UI updates.

    Returns:
        Instance of a WorkforceCallback subclass with ``emit`` / ``events``.
    """
    from camel.societies.workforce.workforce_callback import WorkforceCallback

    class _StreamingWorkforceCallback(WorkforceCallback):
        """CAMEL WorkforceCallback that forwards lifecycle events to a sink."""

        def __init__(self, event_sink: Optional[EventSink] = None) -> None:
            """Initialize the callback.

            Args:
                event_sink: Callable that receives event dicts.
            """
            self._sink = event_sink
            self.events: List[Dict[str, Any]] = []

        def set_sink(self, event_sink: EventSink) -> None:
            """Replace the event sink.

            Args:
                event_sink: New sink callable.
            """
            self._sink = event_sink

        def emit(self, event: Dict[str, Any]) -> None:
            """Append and forward an event.

            Args:
                event: Normalized event dict.
            """
            self.events.append(event)
            if self._sink is not None:
                try:
                    self._sink(event)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Progress sink failed: %s", exc)

        def _forward(
            self, kind: str, title: str, detail: str = "", **kwargs: Any
        ) -> None:
            """Helper to emit a typed event."""
            self.emit(make_event(kind, title, detail, **kwargs))

        def log_message(self, event: Any) -> None:
            """Handle a CAMEL log event."""
            level = getattr(event, "level", "info")
            message = getattr(event, "message", str(event))
            self._forward("log", f"Log ({level})", str(message))

        def log_task_created(self, event: Any) -> None:
            """Handle task created."""
            desc = getattr(event, "description", "") or ""
            self._forward(
                "task_created",
                "Task created",
                desc[:500],
                task_id=str(getattr(event, "task_id", "")),
            )

        def log_task_decomposed(self, event: Any) -> None:
            """Handle task decomposition."""
            subtasks = getattr(event, "subtask_ids", []) or []
            self._forward(
                "task_decomposed",
                "Task decomposed",
                f"{len(subtasks)} subtask(s): {', '.join(map(str, subtasks[:8]))}",
                task_id=str(getattr(event, "parent_task_id", "")),
            )

        def log_task_assigned(self, event: Any) -> None:
            """Handle task assignment to a worker."""
            self._forward(
                "task_assigned",
                "Task assigned",
                f"Worker {getattr(event, 'worker_id', '')}",
                worker=str(getattr(event, "worker_id", "")),
                task_id=str(getattr(event, "task_id", "")),
            )

        def log_task_started(self, event: Any) -> None:
            """Handle task start."""
            self._forward(
                "task_started",
                "Worker started",
                f"Worker {getattr(event, 'worker_id', '')} began work",
                worker=str(getattr(event, "worker_id", "")),
                task_id=str(getattr(event, "task_id", "")),
            )

        def log_task_updated(self, event: Any) -> None:
            """Handle task update / replan."""
            update_type = getattr(event, "update_type", "update")
            self._forward(
                "task_updated",
                f"Task {update_type}",
                str(getattr(event, "new_value", "") or getattr(event, "old_value", "")),
                worker=str(getattr(event, "worker_id", "") or ""),
                task_id=str(getattr(event, "task_id", "")),
            )

        def log_task_completed(self, event: Any) -> None:
            """Handle task completion."""
            summary = getattr(event, "result_summary", None) or "Completed"
            elapsed = getattr(event, "processing_time_seconds", None)
            detail = str(summary)[:800]
            if elapsed is not None:
                detail = f"{detail}\n(time: {elapsed:.1f}s)"
            self._forward(
                "task_completed",
                "Task completed",
                detail,
                worker=str(getattr(event, "worker_id", "")),
                task_id=str(getattr(event, "task_id", "")),
            )

        def log_task_failed(self, event: Any) -> None:
            """Handle task failure."""
            self._forward(
                "task_failed",
                "Task failed",
                str(getattr(event, "error_message", event)),
                worker=str(getattr(event, "worker_id", "") or ""),
                task_id=str(getattr(event, "task_id", "")),
            )

        def log_worker_created(self, event: Any) -> None:
            """Handle worker creation."""
            role = getattr(event, "role", "") or getattr(event, "worker_type", "")
            self._forward(
                "worker_created",
                "Worker ready",
                str(role),
                worker=str(getattr(event, "worker_id", "")),
            )

        def log_worker_deleted(self, event: Any) -> None:
            """Handle worker deletion."""
            self._forward(
                "worker_deleted",
                "Worker removed",
                str(getattr(event, "reason", "") or ""),
                worker=str(getattr(event, "worker_id", "")),
            )

        def log_all_tasks_completed(self, event: Any) -> None:
            """Handle workforce completion."""
            self._forward("all_tasks_completed", "All workforce tasks completed", "")

    return _StreamingWorkforceCallback(sink)
