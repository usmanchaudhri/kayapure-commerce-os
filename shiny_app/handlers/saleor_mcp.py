"""Saleor MCP tab — call local/hosted Saleor MCP tools from the Shiny dashboard."""

from __future__ import annotations

import json
from typing import Any

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.growth_feature_common import error_block, loading_block
from shiny_app.lib.saleor_mcp_client import (
    SALEOR_MCP_TOOLS,
    SaleorMcpError,
    get_configured_client,
)


def _build_arguments(input: Inputs, tool: str) -> dict[str, Any]:
    args: dict[str, Any] = {}

    try:
        first = int(input.saleor_mcp_first() or 20)
    except Exception:
        first = 20
    first = max(1, min(first, 100))

    if tool in {"products", "orders", "customers", "stocks"}:
        args["first"] = first

    if tool == "products":
        try:
            search = (input.saleor_mcp_search() or "").strip()
        except Exception:
            search = ""
        if search:
            args["search"] = search
        try:
            channel = (input.saleor_mcp_channel() or "").strip()
        except Exception:
            channel = ""
        if channel:
            args["channel"] = channel

    if tool == "warehouse_details":
        try:
            wid = (input.saleor_mcp_warehouse_id() or "").strip()
        except Exception:
            wid = ""
        if wid:
            args["id"] = wid

    return args


def _flatten_edges(block: Any) -> list[dict[str, Any]] | None:
    """Turn Saleor/MCP edge lists into node rows. Returns None if shape unknown."""
    if isinstance(block, dict) and "edges" in block:
        rows: list[dict[str, Any]] = []
        for edge in block.get("edges") or []:
            node = edge.get("node") if isinstance(edge, dict) else None
            if isinstance(node, dict):
                rows.append(node)
            elif isinstance(edge, dict):
                rows.append(edge)
        return rows
    if isinstance(block, list):
        rows = []
        for item in block:
            if not isinstance(item, dict):
                continue
            # MCP tools often return edges: [{ node: {...} }, ...]
            node = item.get("node")
            rows.append(node if isinstance(node, dict) else item)
        return rows
    return None


def _rows_from_payload(tool: str, payload: Any) -> list[dict[str, Any]]:
    """Best-effort flatten of common Saleor MCP list responses into table rows."""
    if payload is None:
        return []
    if isinstance(payload, str):
        return [{"value": payload}]
    if not isinstance(payload, dict):
        return [{"value": str(payload)}]

    # saleor-mcp wraps lists as { "data": { "products": [edges...] } }
    root = payload
    data_block = payload.get("data")
    if isinstance(data_block, dict):
        root = data_block

    for key in ("products", "orders", "customers", "stocks", "channels"):
        flattened = _flatten_edges(root.get(key))
        if flattened is not None:
            return flattened

    if "channels" in root and isinstance(root["channels"], list):
        return [c for c in root["channels"] if isinstance(c, dict)]

    if tool == "order_count":
        return [root if isinstance(root, dict) else payload]
    if tool == "warehouse_details":
        wh = root.get("warehouse") if isinstance(root.get("warehouse"), dict) else root
        return [wh] if isinstance(wh, dict) else [{"value": str(payload)}]
    if tool == "current_domain":
        return [{"api_url": payload if isinstance(payload, str) else str(payload)}]

    # Fallback: single-row dump of top-level scalars / short lists
    return [root if isinstance(root, dict) else payload]


def _table_from_rows(rows: list[dict[str, Any]]) -> ui.Tag:
    if not rows:
        return ui.div("No rows returned.", class_="gf-card-sub")

    # Prefer a stable set of useful columns when present
    preferred = [
        "id",
        "name",
        "slug",
        "number",
        "status",
        "email",
        "quantity",
        "quantityAllocated",
        "isActive",
        "currencyCode",
        "created",
        "updatedAt",
        "api_url",
        "value",
        "totalCount",
    ]
    keys: list[str] = []
    for row in rows[:20]:
        for k in row.keys():
            if k not in keys and not isinstance(row.get(k), (dict, list)):
                keys.append(k)
    ordered = [k for k in preferred if k in keys] + [k for k in keys if k not in preferred]
    ordered = ordered[:10]

    header = ui.tags.tr(*[ui.tags.th(k) for k in ordered])
    body_rows = []
    for row in rows[:100]:
        cells = []
        for k in ordered:
            val = row.get(k, "")
            if val is None:
                val = ""
            cells.append(ui.tags.td(str(val)))
        body_rows.append(ui.tags.tr(*cells))

    return ui.div(
        ui.tags.table(
            ui.tags.thead(header),
            ui.tags.tbody(*body_rows),
        ),
        class_="table-scroll-wrap saleor-mcp-table",
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    result_val = reactive.Value(None)
    loading = reactive.Value(False)
    error_val = reactive.Value("")
    meta_val = reactive.Value({})

    async def _run():
        loading.set(True)
        error_val.set("")
        try:
            tool = (input.saleor_mcp_tool() or "products").strip()
            if tool not in SALEOR_MCP_TOOLS:
                raise SaleorMcpError(f"Unknown tool: {tool}")

            args = _build_arguments(input, tool)
            client = get_configured_client()
            payload = await client.call_tool(tool, args)
            result_val.set(payload)
            meta_val.set({"tool": tool, "arguments": args})
        except SaleorMcpError as exc:
            error_val.set(str(exc))
            result_val.set(None)
        except Exception as exc:
            error_val.set(str(exc))
            result_val.set(None)
        finally:
            loading.set(False)

    @reactive.effect
    @reactive.event(input.saleor_mcp_run)
    async def _on_run():
        await _run()

    @reactive.effect
    @reactive.event(input.refresh)
    async def _on_refresh():
        if result_val.get() is not None or error_val.get():
            await _run()

    @render.ui
    def saleor_mcp_status():
        if loading.get():
            return loading_block("Querying Saleor MCP…")
        err = error_val.get()
        if err:
            return error_block("Saleor MCP error", err)
        meta = meta_val.get() or {}
        if not meta:
            return ui.div(
                "Select a tool and click Run query. "
                "Configure SALEOR_MCP_URL, SALEOR_API_URL, and SALEOR_AUTH_TOKEN "
                "in backend/.env.",
                class_="gf-card-sub",
            )
        return ui.div(
            ui.span(f"Tool: {meta.get('tool')}", class_="saleor-mcp-chip"),
            ui.span(
                f"Args: {json.dumps(meta.get('arguments') or {}, separators=(',', ':'))}",
                class_="saleor-mcp-chip muted",
            ),
            class_="saleor-mcp-status-row",
        )

    @render.ui
    def saleor_mcp_content():
        if loading.get():
            return ui.div()
        if error_val.get():
            return ui.div()
        payload = result_val.get()
        if payload is None:
            return ui.div()

        tool = (meta_val.get() or {}).get("tool") or "products"
        rows = _rows_from_payload(tool, payload)
        pretty = json.dumps(payload, indent=2, default=str)

        return ui.div(
            ui.div(
                ui.div("Results", class_="gf-card-title"),
                _table_from_rows(rows),
                class_="gf-card saleor-mcp-card",
            ),
            ui.div(
                ui.div("Raw MCP payload", class_="gf-card-title"),
                ui.tags.pre(pretty, class_="saleor-mcp-raw"),
                class_="gf-card saleor-mcp-card",
            ),
            class_="saleor-mcp-results",
        )
