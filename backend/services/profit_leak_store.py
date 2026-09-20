"""
Persist profit leak scan runs, findings, and evidence to PostgreSQL.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from models.schemas import (
    ProfitLeakAnalysisRun,
    ProfitLeakFinding,
    ProfitLeakFindingEvidence,
)

PROMPT_VERSION = "profit_leak_explain_v1"


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _scan_input_hash(scan_result: Dict[str, Any]) -> str:
    period = scan_result.get("period") or {}
    payload = {
        "since": period.get("since"),
        "until": period.get("until"),
        "account_id": scan_result.get("account_id", ""),
        "finding_ids": [f.get("id") for f in scan_result.get("findings", [])],
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def save_profit_leak_scan(
    db: Session,
    scan_result: Dict[str, Any],
    *,
    account_id: str = "",
    account_name: str = "",
    model_name: Optional[str] = None,
    prompt_version: str = PROMPT_VERSION,
) -> ProfitLeakAnalysisRun:
    """Persist a completed scan with findings and evidence rows."""
    period = scan_result.get("period") or {}
    since = period.get("since", "")
    until = period.get("until", "")
    summary = scan_result.get("summary") or {}

    scoped_account = account_id or scan_result.get("account_id", "")
    scoped_name = account_name or scan_result.get("account_name", "")
    if not scoped_account and scan_result.get("accounts"):
        first = scan_result["accounts"][0]
        scoped_account = first.get("account_id", "")
        scoped_name = first.get("account_name", "")

    run = ProfitLeakAnalysisRun(
        account_id=scoped_account,
        account_name=scoped_name,
        period_start=_parse_date(since),
        period_end=_parse_date(until),
        analysis_type="profit_leak_scan",
        prompt_version=prompt_version,
        model_name=model_name,
        input_data_hash=_scan_input_hash(scan_result),
        status="completed",
        summary_json=summary,
        executive_summary=scan_result.get("executive_summary"),
        scan_params_json={
            "accounts_scanned": summary.get("accounts_scanned"),
            "explain": scan_result.get("explain", True),
        },
    )
    db.add(run)
    db.flush()

    for finding_data in scan_result.get("findings", []):
        finding = ProfitLeakFinding(
            id=finding_data["id"],
            analysis_run_id=run.id,
            account_id=finding_data.get("account_id", scoped_account),
            account_name=finding_data.get("account_name", scoped_name),
            category=finding_data.get("category", ""),
            severity=finding_data.get("severity", "medium"),
            title=finding_data.get("title", ""),
            diagnosis=finding_data.get("diagnosis", ""),
            recommendation=finding_data.get("recommendation", ""),
            llm_explanation=finding_data.get("llm_explanation"),
            confidence=float(finding_data.get("confidence", 0)),
            estimated_impact_min=float(finding_data.get("estimated_impact_min", 0)),
            estimated_impact_max=float(finding_data.get("estimated_impact_max", 0)),
            entity_type=finding_data.get("entity_type", ""),
            entity_id=finding_data.get("entity_id", ""),
            entity_name=finding_data.get("entity_name", ""),
            status=finding_data.get("status", "open"),
            structured_output={
                "llm_observed_facts": finding_data.get("llm_observed_facts", []),
                "llm_hypotheses": finding_data.get("llm_hypotheses", []),
                "llm_caveats": finding_data.get("llm_caveats", []),
                "llm_recommended_action": finding_data.get("llm_recommended_action"),
                "caveats": finding_data.get("caveats", []),
            },
            experiment_json=finding_data.get("experiment") or {},
        )
        db.add(finding)
        db.flush()

        for ev in finding_data.get("evidence", []):
            db.add(
                ProfitLeakFindingEvidence(
                    finding_id=finding.id,
                    evidence_type="metric",
                    metric_name=ev.get("metric_name", ""),
                    observed_value=str(ev.get("observed_value", "")),
                    comparison_value=str(ev.get("comparison_value", ""))
                    if ev.get("comparison_value") not in (None, "")
                    else None,
                    comparison_label=ev.get("comparison_label"),
                    entity_type=ev.get("entity_type"),
                    entity_id=ev.get("entity_id"),
                    evidence_json=ev,
                )
            )

    db.commit()
    db.refresh(run)
    return run


def get_profit_leak_run(db: Session, run_id: int) -> Optional[ProfitLeakAnalysisRun]:
    return (
        db.query(ProfitLeakAnalysisRun)
        .options(
            joinedload(ProfitLeakAnalysisRun.findings).joinedload(
                ProfitLeakFinding.evidence_rows
            )
        )
        .filter(ProfitLeakAnalysisRun.id == run_id)
        .first()
    )


def list_profit_leak_runs(
    db: Session,
    *,
    account_id: Optional[str] = None,
    limit: int = 20,
) -> List[ProfitLeakAnalysisRun]:
    query = db.query(ProfitLeakAnalysisRun).order_by(desc(ProfitLeakAnalysisRun.created_at))
    if account_id:
        query = query.filter(ProfitLeakAnalysisRun.account_id == account_id)
    return query.limit(limit).all()


def update_finding_status(
    db: Session,
    finding_id: str,
    status: str,
) -> Optional[ProfitLeakFinding]:
    finding = db.query(ProfitLeakFinding).filter(ProfitLeakFinding.id == finding_id).first()
    if not finding:
        return None
    finding.status = status
    db.commit()
    db.refresh(finding)
    return finding


def run_to_result(run: ProfitLeakAnalysisRun) -> Dict[str, Any]:
    """Serialize a persisted run back to API/Shiny shape."""
    findings = []
    for f in sorted(run.findings, key=lambda x: x.estimated_impact_max, reverse=True):
        structured = f.structured_output or {}
        findings.append(
            {
                "id": f.id,
                "account_id": f.account_id,
                "account_name": f.account_name,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "diagnosis": f.diagnosis,
                "recommendation": f.recommendation,
                "llm_explanation": f.llm_explanation,
                "llm_observed_facts": structured.get("llm_observed_facts", []),
                "llm_hypotheses": structured.get("llm_hypotheses", []),
                "llm_caveats": structured.get("llm_caveats", []),
                "llm_recommended_action": structured.get("llm_recommended_action"),
                "confidence": f.confidence,
                "estimated_impact_min": f.estimated_impact_min,
                "estimated_impact_max": f.estimated_impact_max,
                "entity_type": f.entity_type,
                "entity_id": f.entity_id,
                "entity_name": f.entity_name,
                "status": f.status,
                "experiment": f.experiment_json or {},
                "caveats": structured.get("caveats", []),
                "evidence": [
                    {
                        "metric_name": e.metric_name,
                        "observed_value": e.observed_value,
                        "comparison_value": e.comparison_value,
                        "comparison_label": e.comparison_label or "",
                        "entity_type": e.entity_type or "",
                        "entity_id": e.entity_id or "",
                    }
                    for e in f.evidence_rows
                ],
            }
        )

    summary = run.summary_json or {}
    return {
        "analysis_run_id": run.id,
        "period": {
            "since": run.period_start.strftime("%Y-%m-%d"),
            "until": run.period_end.strftime("%Y-%m-%d"),
            "label": summary.get("period_label", ""),
        },
        "summary": summary,
        "executive_summary": run.executive_summary,
        "findings": findings,
        "from_cache": True,
        "source": "database",
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
