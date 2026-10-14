"""Filesystem persistence for ingredient research runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.ingredient_research.schemas import ResearchReport, ResearchRunSummary

RUNS_DIR = Path(__file__).resolve().parents[2] / "data" / "ingredient_research_runs"


class IngredientResearchStore:
    """Persist and load research run artifacts as JSON files."""

    def __init__(self, runs_dir: Optional[Path] = None) -> None:
        """Initialize the store.

        Args:
            runs_dir: Optional override for the runs directory.
        """
        self.runs_dir = runs_dir or RUNS_DIR
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: ResearchReport) -> str:
        """Write a research report to disk.

        Args:
            report: Validated research report.

        Returns:
            Absolute path string of the written artifact.
        """
        created_at = datetime.now(timezone.utc).isoformat()
        payload: Dict[str, Any] = {
            "created_at": created_at,
            "report": report.model_dump(mode="json"),
        }
        path = self.runs_dir / f"{report.run_metadata.run_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        report.run_metadata.artifact_path = str(path)
        # Rewrite with artifact path filled in.
        payload["report"] = report.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(path)

    def get_report(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load a persisted run by id.

        Args:
            run_id: Research run identifier.

        Returns:
            Parsed JSON document, or None if missing.
        """
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 50) -> List[ResearchRunSummary]:
        """List recent research runs newest-first.

        Args:
            limit: Maximum number of summaries to return.

        Returns:
            List of ResearchRunSummary rows.
        """
        files = sorted(
            self.runs_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        summaries: List[ResearchRunSummary] = []
        for path in files[: max(0, limit)]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                report = payload.get("report") or {}
                meta = report.get("run_metadata") or {}
                summaries.append(
                    ResearchRunSummary(
                        run_id=str(meta.get("run_id") or path.stem),
                        goal=str(report.get("goal") or ""),
                        created_at=str(payload.get("created_at") or ""),
                        pool_size=int(meta.get("pool_size") or 0),
                        combo_count=len(report.get("combo_candidates") or []),
                        artifact_path=str(path),
                    )
                )
            except Exception:  # noqa: BLE001
                continue
        return summaries


ingredient_research_store = IngredientResearchStore()
