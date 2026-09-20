"""HTTP client for the Saleor MCP server (Streamable HTTP).

Talks to a local or hosted Saleor MCP endpoint and calls read-only tools
(products, orders, customers, channels, stocks, etc.).

Docs: https://mcp.saleor.app/
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Tools exposed by saleor/saleor-mcp (read-only GraphQL wrappers)
SALEOR_MCP_TOOLS: dict[str, str] = {
    "products": "List products (name, slug, category, pricing)",
    "orders": "List recent orders with lines and totals",
    "order_count": "Total order count (optional filters)",
    "customers": "List customers",
    "channels": "List sales channels and warehouses",
    "stocks": "List stock levels by warehouse / variant",
    "warehouse_details": "Warehouse details by ID",
    "current_domain": "Connected Saleor API URL",
}


class SaleorMcpError(RuntimeError):
    """Raised when the MCP server returns an error or is unreachable."""


def _parse_sse_jsonrpc(body: str) -> dict[str, Any]:
    """Extract the first JSON-RPC payload from an SSE or plain JSON body."""
    text = (body or "").strip()
    if not text:
        raise SaleorMcpError("Empty response from Saleor MCP server")

    if text.startswith("{"):
        return json.loads(text)

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                return json.loads(payload)

    raise SaleorMcpError(f"Could not parse MCP response: {text[:300]}")


class SaleorMcpClient:
    """Minimal Streamable-HTTP MCP client for Saleor tools."""

    def __init__(
        self,
        *,
        mcp_url: str,
        saleor_api_url: str,
        auth_token: str,
        timeout: float = 60.0,
    ) -> None:
        self.mcp_url = mcp_url.rstrip("/")
        self.saleor_api_url = saleor_api_url
        self.auth_token = auth_token
        self.timeout = timeout
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-Saleor-API-URL": self.saleor_api_url,
            "X-Saleor-Auth-Token": self.auth_token,
        }

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.mcp_url,
                headers=self._headers(),
                json=payload,
            )

        # notifications/initialized often returns 202 with empty body
        if response.status_code == 202 and not (response.text or "").strip():
            return None

        if response.status_code >= 400:
            raise SaleorMcpError(
                f"MCP HTTP {response.status_code}: {response.text[:500]}"
            )

        data = _parse_sse_jsonrpc(response.text)
        if "error" in data:
            err = data["error"]
            message = err.get("message") if isinstance(err, dict) else str(err)
            raise SaleorMcpError(message or "Unknown MCP error")
        return data

    async def initialize(self) -> dict[str, Any]:
        result = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "kayapure-commerce-os",
                        "version": "1.0.0",
                    },
                },
            }
        )
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return (result or {}).get("result") or {}

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.initialize()
        data = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
            }
        )
        return ((data or {}).get("result") or {}).get("tools") or []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call an MCP tool and return parsed content (usually JSON/dict)."""
        await self.initialize()
        data = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments or {},
                },
            }
        )
        result = (data or {}).get("result") or {}
        if result.get("isError"):
            raise SaleorMcpError(_tool_error_text(result))

        return _extract_tool_payload(result)


def _tool_error_text(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return " ".join(parts).strip() or "Saleor MCP tool returned an error"


def _extract_tool_payload(result: dict[str, Any]) -> Any:
    """Prefer structuredContent; fall back to JSON/text content blocks."""
    if "structuredContent" in result and result["structuredContent"] is not None:
        return result["structuredContent"]

    content = result.get("content") or []
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            texts.append(str(item.get("text") or ""))
    if not texts:
        return result

    joined = "\n".join(texts).strip()
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return joined


def get_configured_client() -> SaleorMcpClient:
    """Build a client from backend settings."""
    from config import settings

    mcp_url = (settings.SALEOR_MCP_URL or "").strip()
    api_url = (settings.SALEOR_API_URL or "").strip()
    token = (settings.SALEOR_AUTH_TOKEN or "").strip()

    if not mcp_url:
        raise SaleorMcpError(
            "SALEOR_MCP_URL is not set (e.g. http://127.0.0.1:6000/mcp)"
        )
    if not api_url:
        raise SaleorMcpError(
            "SALEOR_API_URL is not set (e.g. https://api.kayapure.com/graphql/)"
        )
    if not token:
        raise SaleorMcpError(
            "SALEOR_AUTH_TOKEN is not set "
            "(Saleor app token with MANAGE_PRODUCTS + MANAGE_ORDERS)"
        )

    return SaleorMcpClient(
        mcp_url=mcp_url,
        saleor_api_url=api_url,
        auth_token=token,
    )
