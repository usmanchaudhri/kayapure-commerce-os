"""
Action proposal queue — create, approve, deny, and record outcomes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from graph.workflow import CommerceState, firecracker_executor_node
from models.schemas import ActionOutcome, ActionProposal, ActionStatus
from services.action_executor import execute_channel_action, is_channel_action
from utils.logging_config import get_logger

logger = get_logger("action_queue")


def propose_action(
    db: Session,
    *,
    action_type: str,
    title: str,
    description: str,
    parameters: Optional[Dict[str, Any]] = None,
    reasoning: Optional[str] = None,
    priority: str = "medium",
    source: str = "api",
) -> ActionProposal:
    params = dict(parameters or {})
    params["source"] = source

    action = ActionProposal(
        action_type=action_type,
        title=title,
        description=description,
        reasoning=reasoning,
        parameters=params,
        priority=priority,
        status=ActionStatus.PENDING,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    logger.info(f"Proposed action {action.id}: {action_type}")
    return action


def propose_meta_pause(db: Session, campaign_id: str, campaign_name: str) -> ActionProposal:
    return propose_action(
        db,
        action_type="meta_pause_campaign",
        title=f"Pause campaign: {campaign_name}",
        description=f"Pause Meta campaign {campaign_name} ({campaign_id}).",
        parameters={"campaign_id": campaign_id, "campaign_name": campaign_name},
        priority="medium",
        source="meta",
    )


def propose_meta_activate(db: Session, campaign_id: str, campaign_name: str) -> ActionProposal:
    return propose_action(
        db,
        action_type="meta_activate_campaign",
        title=f"Activate campaign: {campaign_name}",
        description=f"Activate Meta campaign {campaign_name} ({campaign_id}).",
        parameters={"campaign_id": campaign_id, "campaign_name": campaign_name},
        priority="medium",
        source="meta",
    )


def propose_meta_delete(db: Session, campaign_id: str, campaign_name: str) -> ActionProposal:
    return propose_action(
        db,
        action_type="meta_delete_campaign",
        title=f"Archive campaign: {campaign_name}",
        description=f"Archive Meta campaign {campaign_name} ({campaign_id}).",
        parameters={"campaign_id": campaign_id, "campaign_name": campaign_name},
        priority="high",
        source="meta",
    )


def propose_meta_budget(
    db: Session,
    campaign_id: str,
    campaign_name: str,
    daily_budget_cents: int,
) -> ActionProposal:
    return propose_action(
        db,
        action_type="meta_update_budget",
        title=f"Update budget: {campaign_name}",
        description=f"Set daily budget to {daily_budget_cents / 100:.2f} for {campaign_name}.",
        parameters={
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "daily_budget_cents": daily_budget_cents,
        },
        priority="medium",
        source="meta",
    )


def propose_whatsapp_text(db: Session, to: str, message: str) -> ActionProposal:
    preview = message[:80] + ("…" if len(message) > 80 else "")
    return propose_action(
        db,
        action_type="whatsapp_send_text",
        title=f"WhatsApp message to {to}",
        description=preview,
        parameters={"to": to, "message": message},
        priority="medium",
        source="whatsapp",
    )


def propose_whatsapp_template(
    db: Session,
    to: str,
    template_name: str,
    language_code: str = "en_US",
) -> ActionProposal:
    return propose_action(
        db,
        action_type="whatsapp_send_template",
        title=f"WhatsApp template to {to}",
        description=f"Send template '{template_name}' ({language_code}).",
        parameters={
            "to": to,
            "template_name": template_name,
            "language_code": language_code,
        },
        priority="medium",
        source="whatsapp",
    )


def list_pending_actions(db: Session, limit: int = 50) -> List[ActionProposal]:
    return (
        db.query(ActionProposal)
        .filter(ActionProposal.status == ActionStatus.PENDING)
        .order_by(ActionProposal.created_at.desc())
        .limit(limit)
        .all()
    )


def _record_outcome(
    db: Session,
    action: ActionProposal,
    execution_result: Dict[str, Any],
    *,
    outcome_type: str = "execution",
) -> ActionOutcome:
    outcome = ActionOutcome(
        action_proposal_id=action.id,
        outcome_type=outcome_type,
        success=bool(execution_result.get("success")),
        metrics_json={
            "action_type": action.action_type,
            "parameters": action.parameters,
            "result": execution_result,
            "recorded_at": datetime.utcnow().isoformat(),
        },
        notes=execution_result.get("error"),
    )
    db.add(outcome)
    return outcome


async def approve_action(db: Session, action_id: int, comment: Optional[str] = None) -> Dict[str, Any]:
    action = db.query(ActionProposal).filter(ActionProposal.id == action_id).first()
    if not action:
        raise ValueError("Action not found")
    if action.status != ActionStatus.PENDING:
        raise ValueError(f"Action is already {action.status}")

    action.status = ActionStatus.EXECUTING
    db.commit()

    try:
        if is_channel_action(action.action_type):
            execution_result = await execute_channel_action(action)
        else:
            execution_result = await _execute_legacy_action(action)

        if comment:
            execution_result["approval_comment"] = comment

        action.status = ActionStatus.COMPLETED if execution_result.get("success") else ActionStatus.FAILED
        action.result = execution_result
        _record_outcome(db, action, execution_result)
        db.commit()
        db.refresh(action)

        return {
            "status": action.status.value,
            "action_id": action.id,
            "execution_result": execution_result,
        }
    except Exception as exc:
        execution_result = {"success": False, "error": str(exc)}
        action.status = ActionStatus.FAILED
        action.result = execution_result
        _record_outcome(db, action, execution_result)
        db.commit()
        raise


async def deny_action(db: Session, action_id: int, comment: Optional[str] = None) -> Dict[str, Any]:
    action = db.query(ActionProposal).filter(ActionProposal.id == action_id).first()
    if not action:
        raise ValueError("Action not found")
    if action.status != ActionStatus.PENDING:
        raise ValueError(f"Action is already {action.status}")

    action.status = ActionStatus.DENIED
    action.result = {"denied": True, "comment": comment}
    db.commit()
    return {"status": "denied", "action_id": action.id, "comment": comment}


async def _execute_legacy_action(action: ActionProposal) -> Dict[str, Any]:
    """Firecracker mock path for LangGraph-era action types."""
    import uuid

    state: CommerceState = {
        "current_action": {
            "action_type": action.action_type,
            "parameters": action.parameters or {},
        },
        "sales_data": None,
        "ad_spend_data": None,
        "inventory_data": None,
        "pnl_summary": None,
        "sku_analysis": None,
        "proposed_actions": [],
        "agent_reasoning": None,
        "approval_status": "approved",
        "execution_result": None,
        "thread_id": str(uuid.uuid4()),
        "cycle_count": 0,
        "agent_logs": [],
        "errors": [],
    }
    result_state = await firecracker_executor_node(state)
    return result_state.get("execution_result", {"success": False, "error": "No execution result"})
