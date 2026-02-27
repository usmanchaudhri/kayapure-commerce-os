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
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("kayapure.mcp_client")


class MCPToolError(Exception):
    """Raised when an MCP tool call fails."""
    pass


class MCPClient:
    """
    Lightweight MCP client that communicates with MCP servers over
    Streamable HTTP transport (JSON-RPC 2.0 over HTTP POST).

    This avoids the heavyweight langchain-mcp-adapters dependency for
    Approach B, where we only need to call specific tools directly.
    When upgrading to Approach A (tools injected into LangGraph), switch
    to MultiServerMCPClient from langchain-mcp-adapters.
    """

    def __init__(self, server_url: str, auth_token: Optional[str] = None):
        self._server_url = server_url.rstrip("/")
        self._auth_token = auth_token
        self._session_id: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._request_id = 0
        self._initialized = False
        self._available_tools: List[Dict[str, Any]] = []

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

        logger.debug(f"MCP request: {method} -> {json.dumps(params or {})[:200]}")

        response = await client.post(
            f"{self._server_url}/mcp",
            json=payload,
            headers=self._build_headers(),
        )

        # Capture session ID from response headers
        if "mcp-session-id" in response.headers:
            self._session_id = response.headers["mcp-session-id"]

        content_type = response.headers.get("content-type", "")

        if response.status_code >= 400:
            error_text = response.text[:500]
            logger.error(f"MCP server error {response.status_code}: {error_text}")
            raise MCPToolError(
                f"MCP server returned HTTP {response.status_code}: {error_text}"
            )

        # Handle SSE (text/event-stream) responses
        if "text/event-stream" in content_type:
            return self._parse_sse_response(response.text)

        # Handle direct JSON response
        result = response.json()
        if isinstance(result, list):
            # Batch response — return the last result
            result = result[-1] if result else {}

        if "error" in result:
            error = result["error"]
            raise MCPToolError(
                f"MCP tool error [{error.get('code', 'unknown')}]: {error.get('message', 'Unknown error')}"
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
                f"MCP tool error [{error.get('code', 'unknown')}]: {error.get('message', 'Unknown error')}"
            )

        return last_data.get("result", last_data)

    async def initialize(self) -> None:
        """
        Initialize the MCP session by sending the 'initialize' handshake
        followed by 'notifications/initialized'.
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
            logger.info(f"MCP session initialized: {json.dumps(init_result)[:200]}")

            # Step 2: Send initialized notification
            client = await self._get_client()
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            await client.post(
                f"{self._server_url}/mcp",
                json=notification,
                headers=self._build_headers(),
            )

            self._initialized = True
            logger.info("MCP client fully initialized and ready")

        except Exception as e:
            logger.error(f"MCP initialization failed: {e}")
            raise MCPToolError(f"Failed to initialize MCP session: {e}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Discover all available tools from the MCP server."""
        await self.initialize()
        result = await self._send_jsonrpc("tools/list")
        tools = result.get("tools", []) if isinstance(result, dict) else []
        self._available_tools = tools
        logger.info(f"Discovered {len(tools)} MCP tools")
        return tools

    async def call_tool(self, tool_name: str, arguments: Optional[Dict] = None) -> Any:
        """
        Call a specific MCP tool by name with the given arguments.
        Returns the tool's result content.
        """
        await self.initialize()

        logger.info(f"Calling MCP tool: {tool_name}({json.dumps(arguments or {})[:200]})")

        result = await self._send_jsonrpc("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })

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
                    return json.loads(combined)
                except json.JSONDecodeError:
                    return combined
            return content_items

        return result

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
        logger.info(f"Registered MCP server: {name} -> {server_url}")

    async def initialize_all(self) -> Dict[str, bool]:
        """Initialize all registered MCP servers. Returns status per server."""
        results = {}
        for name, client in self._clients.items():
            try:
                await client.initialize()
                results[name] = True
                logger.info(f"MCP server '{name}' initialized successfully")
            except Exception as e:
                results[name] = False
                logger.warning(f"MCP server '{name}' initialization failed: {e}")
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


# Singleton instance — configured during app startup in main.py
mcp_manager = MCPClientManager()
