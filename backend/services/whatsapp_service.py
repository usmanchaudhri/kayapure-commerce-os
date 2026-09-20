"""
WhatsApp Cloud API client (Meta Graph API).
https://developers.facebook.com/docs/whatsapp/cloud-api
"""

from typing import Any, Dict, List, Optional

import httpx

from config import settings
from utils.logging_config import get_logger

logger = get_logger("whatsapp")

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppService:
    def __init__(self):
        self._access_token: str = ""
        self._phone_number_id: str = ""
        self._enabled: bool = False

    def configure(self) -> None:
        self._access_token = settings.WHATSAPP_ACCESS_TOKEN
        self._phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self._enabled = settings.whatsapp_ready
        mode = "live" if self._enabled else "disabled"
        logger.info(f"WhatsApp service configured: {mode}")

    @property
    def is_ready(self) -> bool:
        return self._enabled

    async def send_text(self, to: str, message: str) -> Dict[str, Any]:
        if not self.is_ready:
            return {"success": False, "error": "WhatsApp Cloud API is not configured"}

        payload = {
            "messaging_product": "whatsapp",
            "to": _normalize_phone(to),
            "type": "text",
            "text": {"body": message},
        }
        return await self._post_message(payload)

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "en_US",
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not self.is_ready:
            return {"success": False, "error": "WhatsApp Cloud API is not configured"}

        template: Dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "to": _normalize_phone(to),
            "type": "template",
            "template": template,
        }
        return await self._post_message(payload)

    async def _post_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{GRAPH_API_BASE}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            error_msg = data.get("error", {}).get("message", response.text)
            logger.error(f"WhatsApp API error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": response.status_code,
                "response": data,
            }

        logger.info(f"WhatsApp message sent to {payload.get('to')}")
        return {"success": True, "response": data}


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


whatsapp_service = WhatsAppService()
