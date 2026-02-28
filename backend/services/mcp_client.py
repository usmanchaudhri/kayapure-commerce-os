"""
KayaPure Commerce OS - MCP Client Manager
Manages connections to external MCP servers via Streamable HTTP transport.

This module provides a singleton MCP client that connects to the Pipeboard-hosted
Meta Ads MCP server at https://mcp.pipeboard.co/meta-ads-mcp and exposes its tools
for use by the MarketingService and other service layers.

Architecture: Approach B — MCP as a Service Layer
The MCP client wraps tool calls behind the existing service interfaces, so the
LangGraph workflow and API routes require zero changes.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import httpx

from utils.logging_config import get_logger, log_timing

logger = get_logger("mcp_client")


class MCPToolError(Exception):
    """Raised when an MCP tool call fails."""
    pass


class MCPClient:
    """
    Lightweight MCP client that communicates with MCP servers over
    Streamable HTTP transport (JSON-RPC 2.0 over HTTP POST).

    The server_url is used directly as the POST endpoint — no path suffix
    is appended. For example:
        server_url = "https://mcp.pipeboard.co/meta-ads-mcp"
        POST → https://mcp.pipeboard.co/meta-ads-mcp

    This avoids the heavyweight langchain-mcp-adapters dependency for
    Approach B, where we only need to call specific tools directly.
    When upgrading to Approach A (tools injected into LangGraph), switch
    to MultiServerMCPClient from langchain-mcp-adapters.
    """

    def __init__(self, server_url: str, auth_token: Optional[str] = None):
        # Use the server_url as-is — it IS the endpoint. Do NOT append /mcp.
        self._server_url = server_url.rstrip("/")
        self._auth_token = auth_token
        self._session_id: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._request_id = 0
        self._initialized = False
        self._available_tools: List[Dict[str, Any]] = []
        self._server_info: Optional[Dict[str, Any]] = None

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for MCP requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _next_id(self) -> int:
        """Generate the next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def _send_jsonrpc(self, method: str, params: Optional[Dict] = None) -> Any:
        """
        Send a JSON-RPC 2.0 request to the MCP server.
        Posts directly to self._server_url (no path suffix appended).
        Handles both direct JSON responses and SSE (Server-Sent Events) streams.
        """
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        start_time = time.perf_counter()
        logger.info(
            f"MCP request: {method} → {self._server_url}",
            extra={"mcp_method": method, "server_url": self._server_url},
        )
        logger.debug(
            f"MCP payload: {json.dumps(payload)[:500]}",
            extra={"mcp_method": method, "payload_preview": json.dumps(payload)[:500]},
        )

        response = await client.post(
            self._server_url,
            json=payload,
            headers=self._build_headers(),
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"MCP response: status={response.status_code}, "
            f"content-type={response.headers.get('content-type', 'unknown')}, "
            f"latency={elapsed_ms:.1f}ms, body={response.text[:500]}",
            extra={
                "mcp_method": method,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", "unknown"),
                "latency_ms": round(elapsed_ms, 1),
                "response_preview": response.text[:500],
            },
        )

        # Capture session ID from response headers if provided
        if "mcp-session-id" in response.headers:
            self._session_id = response.headers["mcp-session-id"]
            logger.debug(f"MCP session ID captured: {self._session_id}")

        content_type = response.headers.get("content-type", "")

        if response.status_code >= 400:
            error_text = response.text[:500]
            logger.error(
                f"MCP server error {response.status_code}: {error_text}",
                extra={
                    "mcp_method": method,
                    "status_code": response.status_code,
                    "error_body": error_text,
                    "latency_ms": round(elapsed_ms, 1),
                },
            )
            raise MCPToolError(
                f"MCP server returned HTTP {response.status_code}: {error_text}"
            )

        # Handle SSE (text/event-stream) responses
        if "text/event-stream" in content_type:
            return self._parse_sse_response(response.text)

        # Handle direct JSON response
        if not response.text.strip():
            logger.warning(
                f"MCP server returned empty body for method '{method}'",
                extra={"mcp_method": method, "latency_ms": round(elapsed_ms, 1)},
            )
            return {}

        result = response.json()

        # Handle batch responses (array of JSON-RPC results)
        if isinstance(result, list):
            result = result[-1] if result else {}

        if isinstance(result, dict) and "error" in result:
            error = result["error"]
            logger.error(
                f"MCP tool error [{error.get('code', 'unknown')}]: {error.get('message', 'Unknown error')}",
                extra={
                    "mcp_method": method,
                    "error_code": error.get("code"),
                    "error_message": error.get("message"),
                    "latency_ms": round(elapsed_ms, 1),
                },
            )
            raise MCPToolError(
                f"MCP tool error [{error.get('code', 'unknown')}]: "
                f"{error.get('message', 'Unknown error')}"
            )

        return result.get("result", result)

    def _parse_sse_response(self, sse_text: str) -> Any:
        """Parse Server-Sent Events response and extract the JSON-RPC result."""
        last_data = None
        for line in sse_text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str:
                    try:
                        last_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

        if last_data is None:
            raise MCPToolError("No valid data found in SSE response")

        if "error" in last_data:
            error = last_data["error"]
            raise MCPToolError(
                f"MCP tool error [{error.get('code', 'unknown')}]: "
                f"{error.get('message', 'Unknown error')}"
            )

        return last_data.get("result", last_data)

    async def initialize(self) -> None:
        """
        Initialize the MCP session by sending the 'initialize' handshake
        followed by 'notifications/initialized'.

        Some MCP servers (like Pipeboard) are stateless and don't strictly
        require initialization, but we send it anyway for protocol compliance.
        If the server returns an empty result, we log a warning and proceed.
        """
        if self._initialized:
            return

        try:
            # Step 1: Send initialize request
            init_result = await self._send_jsonrpc("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "KayaPure Commerce OS",
                    "version": "1.0.0",
                },
            })

            if init_result:
                self._server_info = init_result
                server_name = init_result.get("serverInfo", {}).get("name", "unknown")
                server_version = init_result.get("serverInfo", {}).get("version", "unknown")
                protocol = init_result.get("protocolVersion", "unknown")
                logger.info(
                    f"MCP handshake success: server={server_name} v{server_version}, protocol={protocol}",
                    extra={
                        "server_name": server_name,
                        "server_version": server_version,
                        "protocol_version": protocol,
                    },
                )
            else:
                logger.warning(
                    "MCP initialize returned empty result — server may be stateless. "
                    "Proceeding without session."
                )

            # Step 2: Send initialized notification (fire-and-forget)
            try:
                client = await self._get_client()
                notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }
                await client.post(
                    self._server_url,
                    json=notification,
                    headers=self._build_headers(),
                )
                logger.debug("Sent notifications/initialized")
            except Exception as e:
                # Non-fatal — some servers don't handle this notification
                logger.debug(f"notifications/initialized failed (non-fatal): {e}")

            self._initialized = True
            logger.info("MCP client fully initialized and ready")

        except Exception as e:
            logger.error(
                f"MCP initialization failed: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise MCPToolError(f"Failed to initialize MCP session: {e}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Discover all available tools from the MCP server."""
        await self.initialize()
        result = await self._send_jsonrpc("tools/list")
        tools = result.get("tools", []) if isinstance(result, dict) else []
        self._available_tools = tools
        tool_names = [t.get("name", "?") for t in tools[:10]]
        logger.info(
            f"Discovered {len(tools)} MCP tools",
            extra={"tool_count": len(tools), "sample_tools": tool_names},
        )
        return tools

    async def call_tool(self, tool_name: str, arguments: Optional[Dict] = None) -> Any:
        """
        Call a specific MCP tool by name with the given arguments.
        Returns the tool's result content, parsed as JSON if possible.
        """
        await self.initialize()

        start_time = time.perf_counter()
        logger.info(
            f"Calling MCP tool: {tool_name}",
            extra={
                "tool_name": tool_name,
                "arguments": json.dumps(arguments or {})[:300],
            },
        )

        try:
            result = await self._send_jsonrpc("tools/call", {
                "name": tool_name,
                "arguments": arguments or {},
            })

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Extract content from MCP tool response
            if isinstance(result, dict) and "content" in result:
                content_items = result["content"]
                if isinstance(content_items, list):
                    # Concatenate all text content items
                    texts = []
                    for item in content_items:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(item.get("text", ""))
                    combined = "\n".join(texts)
                    # Try to parse as JSON
                    try:
                        parsed = json.loads(combined)
                        logger.info(
                            f"MCP tool {tool_name} completed in {elapsed_ms:.1f}ms (JSON response)",
                            extra={
                                "tool_name": tool_name,
                                "duration_ms": round(elapsed_ms, 1),
                                "response_type": "json",
                                "response_preview": json.dumps(parsed)[:300],
                            },
                        )
                        return parsed
                    except json.JSONDecodeError:
                        logger.info(
                            f"MCP tool {tool_name} completed in {elapsed_ms:.1f}ms (text response)",
                            extra={
                                "tool_name": tool_name,
                                "duration_ms": round(elapsed_ms, 1),
                                "response_type": "text",
                                "response_preview": combined[:300],
                            },
                        )
                        return combined
                return content_items

            logger.info(
                f"MCP tool {tool_name} completed in {elapsed_ms:.1f}ms",
                extra={
                    "tool_name": tool_name,
                    "duration_ms": round(elapsed_ms, 1),
                    "response_type": "raw",
                },
            )
            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"MCP tool {tool_name} FAILED after {elapsed_ms:.1f}ms: {e}",
                extra={
                    "tool_name": tool_name,
                    "duration_ms": round(elapsed_ms, 1),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    async def close(self) -> None:
        """Close the MCP client and HTTP session."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        self._initialized = False
        self._session_id = None
        logger.info("MCP client closed")


class MCPClientManager:
    """
    Manages multiple MCP server connections as a singleton.
    Currently supports Meta Ads MCP; designed to be extended with
    additional MCP servers (Shopify, Google Ads, Stripe, etc.).
    """

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._initialized = False

    def register_server(
        self,
        name: str,
        server_url: str,
        auth_token: Optional[str] = None,
    ) -> None:
        """Register an MCP server for later use."""
        self._clients[name] = MCPClient(
            server_url=server_url,
            auth_token=auth_token,
        )
        logger.info(
            f"Registered MCP server: {name} → {server_url}",
            extra={"server_name": name, "server_url": server_url},
        )

    async def initialize_all(self) -> Dict[str, bool]:
        """Initialize all registered MCP servers. Returns status per server."""
        results = {}
        for name, client in self._clients.items():
            try:
                await client.initialize()
                tools = await client.list_tools()
                results[name] = True
                logger.info(
                    f"MCP server '{name}' initialized: {len(tools)} tools available",
                    extra={"server_name": name, "tool_count": len(tools), "status": "connected"},
                )
            except Exception as e:
                results[name] = False
                logger.warning(
                    f"MCP server '{name}' initialization failed: {e}",
                    extra={"server_name": name, "error": str(e), "status": "failed"},
                )
        self._initialized = True
        return results

    def get_client(self, name: str) -> MCPClient:
        """Get a specific MCP client by server name."""
        if name not in self._clients:
            raise MCPToolError(f"MCP server '{name}' not registered")
        return self._clients[name]

    @property
    def meta_ads(self) -> MCPClient:
        """Convenience accessor for the Meta Ads MCP client."""
        return self.get_client("meta-ads")

    async def close_all(self) -> None:
        """Close all MCP client connections."""
        for name, client in self._clients.items():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"Error closing MCP client '{name}': {e}")
        self._clients.clear()
        self._initialized = False
        logger.info("All MCP clients closed")


# Singleton instance — configured during app startup in main.py
mcp_manager = MCPClientManager()
