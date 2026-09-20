"""
Execute approved channel actions (Meta Ads, WhatsApp).
Legacy LangGraph actions still route through Firecracker mock.
"""

from typing import Any, Dict

from models.schemas import ActionProposal
from services.marketing import marketing_service
from services.whatsapp_service import whatsapp_service
from utils.logging_config import get_logger

logger = get_logger("action_executor")

CHANNEL_ACTION_TYPES = {
    "meta_pause_campaign",
    "meta_activate_campaign",
    "meta_delete_campaign",
    "meta_update_budget",
    "whatsapp_send_text",
    "whatsapp_send_template",
}


def is_channel_action(action_type: str) -> bool:
    return action_type in CHANNEL_ACTION_TYPES


async def execute_channel_action(action: ActionProposal) -> Dict[str, Any]:
    """Run a single approved channel action against external APIs."""
    action_type = action.action_type
    params = action.parameters or {}

    if action_type == "meta_pause_campaign":
        return await _meta_update_campaign(params, status="PAUSED", action="paused")

    if action_type == "meta_activate_campaign":
        return await _meta_update_campaign(params, status="ACTIVE", action="activated")

    if action_type == "meta_delete_campaign":
        return await _meta_delete_campaign(params)

    if action_type == "meta_update_budget":
        return await _meta_update_budget(params)

    if action_type == "whatsapp_send_text":
        return await _whatsapp_send_text(params)

    if action_type == "whatsapp_send_template":
        return await _whatsapp_send_template(params)

    return {"success": False, "error": f"Unsupported channel action: {action_type}"}


async def _meta_update_campaign(params: Dict[str, Any], status: str, action: str) -> Dict[str, Any]:
    campaign_id = params.get("campaign_id")
    if not campaign_id:
        return {"success": False, "error": "campaign_id is required"}

    if not marketing_service._fb_client:
        return {"success": False, "error": "Facebook Ads client not configured"}

    result = await marketing_service._fb_client.update_campaign(campaign_id, status=status)
    return {
        "success": True,
        "channel": "meta",
        "action": action,
        "campaign_id": campaign_id,
        "api_result": result,
    }


async def _meta_delete_campaign(params: Dict[str, Any]) -> Dict[str, Any]:
    campaign_id = params.get("campaign_id")
    if not campaign_id:
        return {"success": False, "error": "campaign_id is required"}

    if not marketing_service._fb_client:
        return {"success": False, "error": "Facebook Ads client not configured"}

    result = await marketing_service._fb_client.delete_campaign(campaign_id)
    return {
        "success": True,
        "channel": "meta",
        "action": "deleted",
        "campaign_id": campaign_id,
        "api_result": result,
    }


async def _meta_update_budget(params: Dict[str, Any]) -> Dict[str, Any]:
    campaign_id = params.get("campaign_id")
    daily_budget_cents = params.get("daily_budget_cents")
    if not campaign_id or daily_budget_cents is None:
        return {"success": False, "error": "campaign_id and daily_budget_cents are required"}

    if not marketing_service._fb_client:
        return {"success": False, "error": "Facebook Ads client not configured"}

    result = await marketing_service._fb_client.update_campaign(
        campaign_id,
        daily_budget=int(daily_budget_cents),
    )
    return {
        "success": True,
        "channel": "meta",
        "action": "budget_updated",
        "campaign_id": campaign_id,
        "daily_budget_cents": daily_budget_cents,
        "api_result": result,
    }


async def _whatsapp_send_text(params: Dict[str, Any]) -> Dict[str, Any]:
    to = params.get("to")
    message = params.get("message")
    if not to or not message:
        return {"success": False, "error": "to and message are required"}

    result = await whatsapp_service.send_text(to=to, message=message)
    return {
        "success": result.get("success", False),
        "channel": "whatsapp",
        "action": "send_text",
        "to": to,
        "api_result": result,
        "error": result.get("error"),
    }


async def _whatsapp_send_template(params: Dict[str, Any]) -> Dict[str, Any]:
    to = params.get("to")
    template_name = params.get("template_name")
    if not to or not template_name:
        return {"success": False, "error": "to and template_name are required"}

    result = await whatsapp_service.send_template(
        to=to,
        template_name=template_name,
        language_code=params.get("language_code", "en_US"),
        components=params.get("components"),
    )
    return {
        "success": result.get("success", False),
        "channel": "whatsapp",
        "action": "send_template",
        "to": to,
        "template_name": template_name,
        "api_result": result,
        "error": result.get("error"),
    }
