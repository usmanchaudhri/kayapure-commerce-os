"""In-process helpers for the action approval queue (shared by Shiny handlers)."""

from typing import Any, Dict, List, Optional

from models.database import SessionLocal
from services import action_queue


def _with_db(fn):
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


def propose_meta_pause(campaign_id: str, campaign_name: str) -> int:
    def _run(db):
        action = action_queue.propose_meta_pause(db, campaign_id, campaign_name)
        return action.id

    return _with_db(_run)


def propose_meta_activate(campaign_id: str, campaign_name: str) -> int:
    def _run(db):
        action = action_queue.propose_meta_activate(db, campaign_id, campaign_name)
        return action.id

    return _with_db(_run)


def propose_meta_delete(campaign_id: str, campaign_name: str) -> int:
    def _run(db):
        action = action_queue.propose_meta_delete(db, campaign_id, campaign_name)
        return action.id

    return _with_db(_run)


def propose_meta_budget(campaign_id: str, campaign_name: str, daily_budget_cents: int) -> int:
    def _run(db):
        action = action_queue.propose_meta_budget(
            db, campaign_id, campaign_name, daily_budget_cents
        )
        return action.id

    return _with_db(_run)


def propose_whatsapp_text(to: str, message: str) -> int:
    def _run(db):
        action = action_queue.propose_whatsapp_text(db, to, message)
        return action.id

    return _with_db(_run)


def list_pending_actions(limit: int = 20) -> List[Dict[str, Any]]:
    def _run(db):
        actions = action_queue.list_pending_actions(db, limit=limit)
        return [
            {
                "id": a.id,
                "action_type": a.action_type,
                "title": a.title,
                "description": a.description,
                "priority": a.priority,
                "parameters": a.parameters or {},
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ]

    return _with_db(_run)


async def approve_action(action_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        return await action_queue.approve_action(db, action_id)
    finally:
        db.close()


async def deny_action(action_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        return await action_queue.deny_action(db, action_id)
    finally:
        db.close()
