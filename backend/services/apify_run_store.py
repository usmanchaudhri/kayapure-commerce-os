"""Persisted Apify Actor runs (Postgres)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.schemas import ApifyActorRun


def upsert_run(
    db: Session,
    *,
    run_id: str,
    actor_id: str,
    dataset_id: str,
    status: str,
    source: str,
    mode: str,
    label: str,
    product_title: Optional[str],
    product_asin: Optional[str],
    product_url: Optional[str],
    raw_json: Dict[str, Any],
    snapshot_json: Optional[Dict[str, Any]],
    reset_analysis: bool = False,
) -> ApifyActorRun:
    row = db.query(ApifyActorRun).filter(ApifyActorRun.run_id == run_id).first()
    if row is None:
        row = ApifyActorRun(run_id=run_id)
        db.add(row)
    row.actor_id = actor_id or ""
    row.dataset_id = dataset_id or ""
    row.status = status or ""
    row.source = source or "manual"
    row.mode = mode or "reviews"
    row.label = label or run_id
    row.product_title = product_title
    row.product_asin = product_asin
    row.product_url = product_url
    row.raw_json = raw_json
    row.snapshot_json = snapshot_json
    if reset_analysis:
        row.analysis_json = None
        row.analysis_error = None
    db.commit()
    db.refresh(row)
    return row


def save_analysis(
    db: Session,
    run_id: str,
    *,
    analysis_json: Optional[Dict[str, Any]] = None,
    analysis_error: Optional[str] = None,
) -> Optional[ApifyActorRun]:
    row = get_by_run_id(db, run_id)
    if row is None:
        return None
    row.analysis_json = analysis_json
    row.analysis_error = analysis_error
    db.commit()
    db.refresh(row)
    return row


def list_runs(db: Session, limit: int = 50) -> List[ApifyActorRun]:
    return (
        db.query(ApifyActorRun)
        .order_by(desc(ApifyActorRun.updated_at), desc(ApifyActorRun.id))
        .limit(limit)
        .all()
    )


def get_by_run_id(db: Session, run_id: str) -> Optional[ApifyActorRun]:
    if not run_id:
        return None
    return db.query(ApifyActorRun).filter(ApifyActorRun.run_id == run_id).first()


def run_to_view(row: ApifyActorRun, *, analyzing: bool = False) -> Dict[str, Any]:
    payload = dict(row.raw_json or {})
    payload.update(
        {
            "db_id": row.id,
            "loaded_run_id": row.run_id,
            "label": row.label,
            "mode": row.mode,
            "source": row.source,
            "analysis": row.analysis_json,
            "analysis_error": row.analysis_error,
            "analyzing": analyzing,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


def run_choices(rows: List[ApifyActorRun]) -> Dict[str, str]:
    return {row.run_id: row.label or row.run_id for row in rows}
