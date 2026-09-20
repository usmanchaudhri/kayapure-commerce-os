"""
Apify REST client.

Used to start Store Actors and to pull dataset items from a run that was
started in this app or in Apify Console.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from utils.logging_config import get_logger

logger = get_logger("apify")

APIFY_API_BASE = "https://api.apify.com/v2"
_RUN_ID_RE = re.compile(r"[A-Za-z0-9]{8,}")


class ApifyError(Exception):
    """Raised when an Apify API call fails."""


def parse_run_id(value: str) -> str:
    """Accept a raw run id or an Apify Console run URL."""
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if "http" in cleaned.lower():
        parts = cleaned.split("?")[0].rstrip("/").split("/")
        if "runs" in parts:
            idx = len(parts) - 1
            for i, part in enumerate(parts):
                if part == "runs" and i + 1 < len(parts):
                    idx = i + 1
                    break
            cleaned = parts[idx]
    match = _RUN_ID_RE.fullmatch(cleaned)
    return match.group(0) if match else cleaned


class ApifyClient:
    def __init__(self, token: str) -> None:
        self._token = token

    @property
    def is_ready(self) -> bool:
        return bool(self._token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def start_run(self, actor_id: str, run_input: Dict[str, Any]) -> Dict[str, Any]:
        encoded = quote(actor_id, safe="~")
        url = f"{APIFY_API_BASE}/acts/{encoded}/runs"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=self._headers(), json=run_input)
        payload = _json(response)
        if response.status_code >= 400:
            raise ApifyError(_error_message(payload, response.status_code))
        return payload.get("data") or payload

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        url = f"{APIFY_API_BASE}/actor-runs/{run_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
        payload = _json(response)
        if response.status_code >= 400:
            raise ApifyError(_error_message(payload, response.status_code))
        return payload.get("data") or payload

    async def list_runs(self, *, limit: int = 20, status: str = "SUCCEEDED") -> List[Dict[str, Any]]:
        url = f"{APIFY_API_BASE}/actor-runs"
        params: Dict[str, str] = {"limit": str(limit), "desc": "1"}
        if status:
            params["status"] = status
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
        payload = _json(response)
        if response.status_code >= 400:
            raise ApifyError(_error_message(payload, response.status_code))
        data = payload.get("data") or payload
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    async def get_dataset_items(self, dataset_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items"
        params = {"clean": "true", "limit": str(limit)}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
        if response.status_code >= 400:
            raise ApifyError(_error_message(_json(response), response.status_code))
        items = response.json()
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    async def wait_for_run(
        self,
        run_id: str,
        *,
        timeout_sec: float = 90.0,
        interval_sec: float = 4.0,
    ) -> Dict[str, Any]:
        deadline = asyncio.get_event_loop().time() + timeout_sec
        run = await self.get_run(run_id)
        while run.get("status") in {"READY", "RUNNING"} and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval_sec)
            run = await self.get_run(run_id)
        return run

    async def fetch_run_items(self, run_id: str, limit: int = 500) -> Dict[str, Any]:
        run = await self.get_run(run_id)
        dataset_id = run.get("defaultDatasetId") or ""
        items: List[Dict[str, Any]] = []
        if dataset_id and run.get("status") in {"SUCCEEDED", "RUNNING", "READY"}:
            try:
                items = await self.get_dataset_items(dataset_id, limit=limit)
            except ApifyError:
                if run.get("status") == "SUCCEEDED":
                    raise
        return {
            "run_id": run.get("id") or run_id,
            "status": run.get("status") or "UNKNOWN",
            "dataset_id": dataset_id,
            "actor_id": run.get("actId") or "",
            "items": items,
        }


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {}


def _error_message(payload: Any, status: int) -> str:
    if isinstance(payload, dict):
        err = payload.get("error") or {}
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if payload.get("message"):
            return str(payload["message"])
    return f"Apify API error ({status})."
