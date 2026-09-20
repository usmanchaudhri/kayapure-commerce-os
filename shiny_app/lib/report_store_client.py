"""Load and save persisted AI reports."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc

from models.database import SessionLocal
from models.schemas import AdsAnalysisReport
from services import report_store


def get_latest_report(
    account_id: str,
    report_type: str,
    days: int,
) -> Optional[Dict[str, Any]]:
    """Most recent report regardless of age (e.g. for PDF download)."""
    db = SessionLocal()
    try:
        report = (
            db.query(AdsAnalysisReport)
            .filter(
                AdsAnalysisReport.account_id == account_id,
                AdsAnalysisReport.report_type == report_type,
                AdsAnalysisReport.days == days,
            )
            .order_by(desc(AdsAnalysisReport.created_at))
            .first()
        )
        if not report:
            return None
        result = report_store.report_to_result(report)
        result["cache_age_min"] = _age_minutes(report)
        return result
    finally:
        db.close()


def get_cached_report(
    account_id: str,
    report_type: str,
    days: int,
    max_age_hours: int = 24,
) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        report = report_store.get_recent_report(
            db,
            account_id=account_id,
            report_type=report_type,
            days=days,
            max_age_hours=max_age_hours,
        )
        if not report:
            return None
        result = report_store.report_to_result(report)
        result["cache_age_min"] = _age_minutes(report)
        return result
    finally:
        db.close()


def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        report = report_store.get_report_by_id(db, report_id)
        if not report:
            return None
        result = report_store.report_to_result(report)
        result["cache_age_min"] = _age_minutes(report)
        result["account_id"] = report.account_id
        result["account_name"] = report.account_name
        result["report_type"] = report.report_type
        result["days"] = report.days
        return result
    finally:
        db.close()


def list_latest_reports_by_account(
    account_ids: Optional[List[str]] = None,
    limit_per_account: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    db = SessionLocal()
    try:
        grouped = report_store.list_latest_reports_by_account(
            db,
            account_ids=account_ids,
            limit_per_account=limit_per_account,
        )
        serialized: Dict[str, List[Dict[str, Any]]] = {}
        for account_id, reports in grouped.items():
            serialized[account_id] = [
                {
                    "id": report.id,
                    "account_id": report.account_id,
                    "account_name": report.account_name,
                    "report_type": report.report_type,
                    "days": report.days,
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                    "created_label": report.created_at.strftime("%b %d, %Y %H:%M") if report.created_at else "Unknown date",
                }
                for report in reports
            ]
        return serialized
    finally:
        db.close()


def save_report(
    account_id: str,
    account_name: str,
    report_type: str,
    days: int,
    question: Optional[str],
    result: Dict[str, Any],
) -> int:
    db = SessionLocal()
    try:
        report = report_store.save_report(
            db,
            account_id=account_id,
            account_name=account_name,
            report_type=report_type,
            days=days,
            question=question,
            result=result,
        )
        return report.id
    finally:
        db.close()


def _age_minutes(report) -> int:
    if not report.created_at:
        return 0
    delta = datetime.utcnow() - report.created_at.replace(tzinfo=None)
    return max(0, int(delta.total_seconds() / 60))
