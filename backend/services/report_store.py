"""
Persisted ad analysis reports (Postgres).
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.schemas import AdsAnalysisReport


def save_report(
    db: Session,
    *,
    account_id: str,
    account_name: str,
    report_type: str,
    days: int,
    question: Optional[str],
    result: Dict[str, Any],
) -> AdsAnalysisReport:
    report = AdsAnalysisReport(
        account_id=account_id,
        account_name=account_name,
        report_type=report_type,
        days=days,
        question=question,
        analysis_json=result.get("analysis", result),
        data_snapshot_json=result.get("data_snapshot"),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_recent_report(
    db: Session,
    account_id: str,
    report_type: str,
    days: int,
    max_age_hours: int = 24,
) -> Optional[AdsAnalysisReport]:
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    return (
        db.query(AdsAnalysisReport)
        .filter(
            AdsAnalysisReport.account_id == account_id,
            AdsAnalysisReport.report_type == report_type,
            AdsAnalysisReport.days == days,
            AdsAnalysisReport.created_at >= cutoff,
        )
        .order_by(desc(AdsAnalysisReport.created_at))
        .first()
    )


def list_reports_for_account(
    db: Session,
    account_id: str,
    limit: int = 10,
) -> List[AdsAnalysisReport]:
    return (
        db.query(AdsAnalysisReport)
        .filter(AdsAnalysisReport.account_id == account_id)
        .order_by(desc(AdsAnalysisReport.created_at))
        .limit(limit)
        .all()
    )


def get_report_by_id(db: Session, report_id: int) -> Optional[AdsAnalysisReport]:
    return db.query(AdsAnalysisReport).filter(AdsAnalysisReport.id == report_id).first()


def list_latest_reports_by_account(
    db: Session,
    account_ids: Optional[List[str]] = None,
    limit_per_account: int = 3,
) -> Dict[str, List[AdsAnalysisReport]]:
    """Most recent reports grouped by account, newest first."""
    query = db.query(AdsAnalysisReport).order_by(desc(AdsAnalysisReport.created_at))
    if account_ids:
        query = query.filter(AdsAnalysisReport.account_id.in_(account_ids))
    reports = query.all()
    grouped: Dict[str, List[AdsAnalysisReport]] = {}
    for report in reports:
        bucket = grouped.setdefault(report.account_id, [])
        if len(bucket) >= limit_per_account:
            continue
        bucket.append(report)
    return grouped


def report_to_result(report: AdsAnalysisReport) -> Dict[str, Any]:
    analysis_payload = report.analysis_json or {}
    return {
        "analysis": analysis_payload,
        "data_snapshot": report.data_snapshot_json or {},
        "report_id": report.id,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "from_cache": True,
        "source": "database",
    }
