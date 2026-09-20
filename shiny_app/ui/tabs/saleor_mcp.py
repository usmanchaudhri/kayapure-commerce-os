"""Saleor MCP nav panel — query products/orders/customers via Saleor MCP."""

from shiny import ui

from shiny_app.lib.saleor_mcp_client import SALEOR_MCP_TOOLS


def nav_panel():
    tool_choices = {key: f"{key} — {desc}" for key, desc in SALEOR_MCP_TOOLS.items()}
    return ui.nav_panel(
        "Saleor MCP",
        ui.div(
            ui.div(
                ui.span("Commerce", class_="pls-featured-badge"),
                ui.tags.h3("Saleor MCP"),
                ui.div(
                    "Query your Saleor store through the Saleor MCP server — "
                    "products, orders, customers, channels, and stock "
                    "(read-only). Requires a running MCP endpoint and "
                    "SALEOR_* env vars.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.input_select(
                "saleor_mcp_tool",
                "Tool",
                choices=tool_choices,
                selected="products",
                width="100%",
            ),
            ui.input_numeric(
                "saleor_mcp_first",
                "Limit (first)",
                value=20,
                min=1,
                max=100,
                width="140px",
            ),
            ui.input_text(
                "saleor_mcp_search",
                "Product search",
                placeholder="Optional full-text search (products tool)",
                width="100%",
            ),
            ui.input_text(
                "saleor_mcp_channel",
                "Channel slug (not display name)",
                placeholder="e.g. default-channel — not Channel-USD",
                width="100%",
            ),
            ui.input_text(
                "saleor_mcp_warehouse_id",
                "Warehouse ID",
                placeholder="Global ID for warehouse_details",
                width="100%",
            ),
            ui.input_action_button(
                "saleor_mcp_run",
                "Run query",
                class_="btn-primary pls-scan-btn",
            ),
            class_="pls-controls saleor-mcp-controls",
        ),
        ui.output_ui("saleor_mcp_status"),
        ui.output_ui("saleor_mcp_content"),
        value="saleor_mcp",
    )
