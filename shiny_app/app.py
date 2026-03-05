"""
KayaPure Commerce OS — Shiny Dashboard (Meta Ads)
Embedded in FastAPI via ASGI mount at /dashboard.

Tabs:
  - Dashboard: KPIs, spend trends, campaign insights, all-account totals
  - Creatives: Creative management — grid view, detail modal, upload
"""

from shiny import App, Inputs, Outputs, Session, reactive, render, ui
import plotly.graph_objects as go
from shinywidgets import output_widget, render_widget
import json

# Currency symbol lookup
CURRENCY_SYMBOLS = {
    "PKR": "Rs", "USD": "$", "GBP": "£", "EUR": "€",
    "AED": "AED", "SAR": "SAR", "INR": "₹", "CAD": "C$", "AUD": "A$",
}


def fmt_currency(value, currency="USD"):
    """Format a number with the correct currency symbol."""
    sym = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{sym}{value:,.2f}"


def fmt_number(value):
    """Format a number with commas."""
    return f"{value:,}"


# ============================================
# UI
# ============================================
app_ui = ui.page_fluid(
    ui.tags.style("""
        body { background: #0f1117; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; }
        .card { background: #1a1d27; border: 1px solid #2d3348; border-radius: 10px; }
        .card-header { border-bottom: 1px solid #2d3348; padding: 12px 16px; font-weight: 600; font-size: 14px; color: #94a3b8; }
        .card-body { padding: 16px; }
        .kpi-value { font-size: 28px; font-weight: 700; color: #f1f5f9; letter-spacing: -0.5px; }
        .kpi-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
        .kpi-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }
        .kpi-card { background: #1a1d27; border: 1px solid #2d3348; border-radius: 10px; padding: 20px; }
        .badge-active { background: #065f46; color: #6ee7b7; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .badge-paused { background: #78350f; color: #fcd34d; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .badge-archived { background: #7f1d1d; color: #fca5a5; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; padding: 10px 12px; color: #64748b; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #2d3348; }
        td { padding: 10px 12px; border-bottom: 1px solid #1e2235; color: #cbd5e1; }
        tr:hover td { background: #1e2235; }
        .header-bar { background: linear-gradient(135deg, #1a1d27 0%, #0f1117 100%); border-bottom: 1px solid #2d3348; padding: 20px 24px; margin: -16px -16px 24px -16px; border-radius: 0; }
        .header-title { font-size: 20px; font-weight: 700; color: #f1f5f9; }
        .header-sub { font-size: 13px; color: #64748b; margin-top: 4px; }
        .source-badge { background: #1e3a5f; color: #7dd3fc; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .refresh-btn { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
        .refresh-btn:hover { background: #1d4ed8; }
        .period-info { font-size: 12px; color: #64748b; }
        /* Tab styling */
        .nav-tabs { border-bottom: 1px solid #2d3348; }
        .nav-tabs .nav-link { color: #64748b; border: none; padding: 12px 20px; font-weight: 600; font-size: 14px; }
        .nav-tabs .nav-link:hover { color: #e2e8f0; border: none; background: #1a1d27; }
        .nav-tabs .nav-link.active { color: #22d3ee; border: none; border-bottom: 2px solid #22d3ee; background: transparent; }
        .tab-content { padding-top: 24px; }
        /* Creative grid */
        .creative-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .creative-card {
            background: #1a1d27; border: 1px solid #2d3348; border-radius: 12px;
            overflow: hidden; cursor: pointer; transition: all 0.2s ease;
        }
        .creative-card:hover { border-color: #22d3ee; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .creative-thumb {
            width: 100%; height: 200px; object-fit: cover; display: block;
            background: #0f1117;
        }
        .creative-thumb-placeholder {
            width: 100%; height: 200px; display: flex; align-items: center; justify-content: center;
            background: #0f1117; color: #374151; font-size: 48px;
        }
        .creative-info { padding: 14px; }
        .creative-name { font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .creative-id { font-size: 11px; color: #475569; font-family: monospace; margin-bottom: 8px; }
        .creative-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .type-badge-video { background: #1e3a5f; color: #7dd3fc; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .type-badge-image { background: #1a3a2a; color: #6ee7b7; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .type-badge-carousel { background: #3b1f5e; color: #c4b5fd; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .type-badge-unknown { background: #374151; color: #9ca3af; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        /* Account selector bar */
        .creatives-toolbar {
            display: flex; align-items: center; gap: 16px; margin-bottom: 24px;
            padding: 16px; background: #1a1d27; border: 1px solid #2d3348; border-radius: 10px;
        }
        .creatives-toolbar label { color: #94a3b8; font-size: 13px; font-weight: 600; }
        .creatives-toolbar select {
            background: #0f1117; color: #e2e8f0; border: 1px solid #2d3348;
            border-radius: 6px; padding: 8px 12px; font-size: 13px; min-width: 300px;
        }
        .creatives-toolbar select:focus { border-color: #22d3ee; outline: none; }
        /* Upload area */
        .upload-area {
            border: 2px dashed #2d3348; border-radius: 12px; padding: 32px;
            text-align: center; background: #0f1117; margin-bottom: 24px;
            transition: border-color 0.2s;
        }
        .upload-area:hover { border-color: #22d3ee; }
        .upload-icon { font-size: 36px; color: #374151; margin-bottom: 8px; }
        .upload-text { color: #64748b; font-size: 13px; }
        /* Modal overrides */
        .modal-content { background: #1a1d27 !important; border: 1px solid #2d3348 !important; color: #e2e8f0 !important; }
        .modal-header { border-bottom: 1px solid #2d3348 !important; }
        .modal-footer { border-top: 1px solid #2d3348 !important; }
        .modal-title { color: #f1f5f9 !important; }
        .btn-close { filter: invert(1); }
        /* Action buttons in modal */
        .action-btn {
            padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600;
            border: none; cursor: pointer; transition: background 0.2s;
        }
        .action-btn-primary { background: #2563eb; color: white; }
        .action-btn-primary:hover { background: #1d4ed8; }
        .action-btn-danger { background: #dc2626; color: white; }
        .action-btn-danger:hover { background: #b91c1c; }
        .action-btn-secondary { background: #374151; color: #e2e8f0; }
        .action-btn-secondary:hover { background: #4b5563; }
        /* Detail grid in modal */
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
        .detail-item label { display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
        .detail-item span { font-size: 14px; color: #e2e8f0; }
    """),

    # Header
    ui.div(
        ui.div(
            ui.div(
                ui.span("KayaPure", style="color: #22d3ee;"),
                " Commerce OS — Meta Ads Dashboard",
                class_="header-title",
            ),
            ui.div("Real-time Facebook Marketing API data", class_="header-sub"),
            style="flex: 1;",
        ),
        ui.div(
            ui.input_action_button("refresh", "↻ Refresh Data", class_="refresh-btn"),
            style="display: flex; align-items: center;",
        ),
        class_="header-bar",
        style="display: flex; align-items: center; justify-content: space-between;",
    ),

    # ============================================
    # Tabbed Layout
    # ============================================
    ui.navset_tab(
        # ---- Tab 1: Dashboard ----
        ui.nav_panel(
            "Dashboard",

            # Total Spend (All Accounts)
            ui.div(
                ui.div(
                    ui.div("Total Ad Spend — All Accounts (Jan 2025 – Today)", class_="card-header"),
                    ui.div(ui.output_ui("total_spend_section"), class_="card-body"),
                    class_="card",
                ),
                style="margin-bottom: 24px;",
            ),

            # 7-Day View
            ui.div(
                ui.tags.h3("Last 7 Days — Primary Account", style="color: #94a3b8; font-size: 15px; font-weight: 600; margin-bottom: 8px;"),
            ),
            ui.output_ui("period_info"),

            ui.div(
                ui.output_ui("kpi_cards"),
                style="margin-bottom: 24px;",
            ),

            ui.layout_columns(
                ui.div(
                    ui.div(
                        ui.div("Daily Ad Spend Trend", class_="card-header"),
                        ui.div(output_widget("spend_chart"), class_="card-body"),
                        class_="card",
                    ),
                ),
                ui.div(
                    ui.div(
                        ui.div("Campaign Insights", class_="card-header"),
                        ui.div(ui.output_ui("campaign_table"), class_="card-body"),
                        class_="card",
                    ),
                ),
                col_widths=[7, 5],
            ),
        ),

        # ---- Tab 2: Creatives ----
        ui.nav_panel(
            "Creatives",

            # Toolbar: Account selector + Upload button
            ui.div(
                ui.div(
                    ui.tags.label("Ad Account:", **{"for": "account_select"}),
                    ui.output_ui("account_selector"),
                    style="display: flex; align-items: center; gap: 12px; flex: 1;",
                ),
                ui.div(
                    ui.input_action_button("show_upload", "⬆ Upload New Creative", class_="refresh-btn"),
                    style="display: flex; align-items: center;",
                ),
                class_="creatives-toolbar",
            ),

            # KPI summary row
            ui.div(
                ui.output_ui("creatives_kpi"),
                style="margin-bottom: 20px;",
            ),

            # Creative grid
            ui.div(
                ui.output_ui("creatives_grid"),
            ),
        ),
    ),
)


# ============================================
# Server
# ============================================
def server(input: Inputs, output: Outputs, session: Session):

    # ---- Shared reactive state ----
    selected_creative = reactive.value(None)

    # ---- Dashboard tab reactives ----

    @reactive.calc
    async def ad_data():
        input.refresh()
        from services.marketing import marketing_service
        data = await marketing_service.get_ad_spend_history(days=7)
        return data

    @reactive.calc
    async def total_spend_data():
        input.refresh()
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        data = await marketing_service._fb_client.get_total_spend_all_accounts(since="2025-01-01")
        return data

    @render.ui
    async def total_spend_section():
        data = await total_spend_data()
        if data is None or "error" in data:
            return ui.div("Facebook Ads client not configured or error occurred.", style="color: #64748b; text-align: center; padding: 24px;")

        period = data.get("period", {})
        accounts = data.get("accounts", [])
        currency_totals = data.get("currency_totals", {})

        kpi_items = []
        for cur, total in currency_totals.items():
            kpi_items.append(
                ui.div(
                    ui.div(f"Total Spend ({cur})", class_="kpi-label"),
                    ui.div(fmt_currency(total, cur), class_="kpi-value"),
                    ui.div(f"{period.get('since', '?')} → {period.get('until', '?')}", class_="kpi-sub"),
                    class_="kpi-card", style="flex: 1; min-width: 200px;",
                )
            )
        kpi_items.append(
            ui.div(
                ui.div("Total Impressions", class_="kpi-label"),
                ui.div(fmt_number(data.get("grand_total_impressions", 0)), class_="kpi-value"),
                ui.div(f"{data.get('total_accounts', 0)} accounts", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 200px;",
            )
        )
        kpi_items.append(
            ui.div(
                ui.div("Total Clicks", class_="kpi-label"),
                ui.div(fmt_number(data.get("grand_total_clicks", 0)), class_="kpi-value"),
                ui.div(f"{data.get('accounts_with_data', 0)} accounts with data", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 200px;",
            )
        )

        kpi_row = ui.div(*kpi_items, style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px;")

        if not accounts:
            return ui.div(kpi_row, ui.div("No accounts found", style="color: #64748b;"))

        rows = []
        for acc in accounts:
            status = acc.get("status", "UNKNOWN")
            badge_class = "badge-active" if status == "ACTIVE" else ("badge-archived" if status == "DISABLED" else "badge-paused")
            badge_label = "Active" if status == "ACTIVE" else ("Disabled" if status == "DISABLED" else status.title())
            acc_currency = acc.get("currency", "USD")
            rows.append(
                ui.tags.tr(
                    ui.tags.td(acc.get("account_name", "—")),
                    ui.tags.td(acc.get("account_id", "—"), style="font-size: 11px; color: #64748b;"),
                    ui.tags.td(ui.span(badge_label, class_=badge_class)),
                    ui.tags.td(acc_currency),
                    ui.tags.td(fmt_currency(acc.get("spend", 0), acc_currency)),
                    ui.tags.td(fmt_number(acc.get("impressions", 0))),
                    ui.tags.td(fmt_number(acc.get("clicks", 0))),
                )
            )

        account_table = ui.tags.table(
            ui.tags.thead(ui.tags.tr(
                ui.tags.th("Account Name"), ui.tags.th("Account ID"), ui.tags.th("Status"),
                ui.tags.th("Currency"), ui.tags.th("Total Spend"), ui.tags.th("Impressions"), ui.tags.th("Clicks"),
            )),
            ui.tags.tbody(*rows),
        )
        return ui.div(kpi_row, account_table)

    @render.ui
    async def period_info():
        data = await ad_data()
        period = data.get("period", {})
        source = data.get("source", "unknown")
        currency = data.get("currency", "USD")
        source_label = "LIVE API" if source == "facebook_api" else "MOCK"
        return ui.div(
            ui.span(f"Period: {period.get('start', '?')} → {period.get('end', '?')} ({period.get('days', '?')} days)", class_="period-info"),
            ui.span(" | "), ui.span(f"Currency: {currency}", class_="period-info"),
            ui.span(" | "), ui.span("Source: ", class_="period-info"), ui.span(source_label, class_="source-badge"),
            style="margin-bottom: 16px; display: flex; align-items: center; gap: 6px;",
        )

    @render.ui
    async def kpi_cards():
        data = await ad_data()
        currency = data.get("currency", "USD")
        cards = [
            ("Total Spend", fmt_currency(data.get("total_spend", 0), currency), f"Avg {fmt_currency(data.get('avg_daily_spend', 0), currency)}/day"),
            ("Total Impressions", fmt_number(data.get("total_impressions", 0)), f"{len(data.get('campaigns', []))} campaigns"),
            ("Total Clicks", fmt_number(data.get("total_clicks", 0)), "Across all campaigns"),
            ("Avg CPC", fmt_currency(data.get("avg_cpc", 0), currency), "Cost per click"),
            ("Avg CTR", f"{data.get('avg_ctr', 0):.2f}%", "Click-through rate"),
        ]
        card_divs = [
            ui.div(
                ui.div(label, class_="kpi-label"), ui.div(value, class_="kpi-value"), ui.div(sub, class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ) for label, value, sub in cards
        ]
        return ui.div(*card_divs, style="display: flex; gap: 16px; flex-wrap: wrap;")

    @render_widget
    async def spend_chart():
        data = await ad_data()
        daily = data.get("daily_breakdown", [])
        currency = data.get("currency", "USD")
        sym = CURRENCY_SYMBOLS.get(currency, currency)
        dates = [d["date"] for d in daily]
        spends = [d["spend"] for d in daily]
        clicks = [d.get("clicks", 0) for d in daily]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=dates, y=spends, name="Spend", marker_color="#2563eb", hovertemplate=f"{sym}%{{y:,.2f}}<extra>Spend</extra>"))
        fig.add_trace(go.Scatter(x=dates, y=clicks, name="Clicks", yaxis="y2", line=dict(color="#22d3ee", width=2), mode="lines+markers", hovertemplate="%{y:,}<extra>Clicks</extra>"))
        fig.update_layout(
            plot_bgcolor="#1a1d27", paper_bgcolor="#1a1d27", font=dict(color="#94a3b8", size=11),
            margin=dict(l=50, r=50, t=20, b=40), height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
            yaxis=dict(title=f"Spend ({sym})", gridcolor="#2d3348", zeroline=False),
            yaxis2=dict(title="Clicks", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)", zeroline=False),
            xaxis=dict(gridcolor="#2d3348"), bargap=0.3,
        )
        return fig

    @render.ui
    async def campaign_table():
        data = await ad_data()
        campaigns = data.get("campaigns", [])
        currency = data.get("currency", "USD")
        if not campaigns:
            return ui.div("No campaign data available", style="color: #64748b; text-align: center; padding: 40px;")
        rows = []
        for c in campaigns:
            status = c.get("status", "UNKNOWN").upper()
            badge_class = "badge-active" if status == "ACTIVE" else ("badge-paused" if status == "PAUSED" else "badge-archived")
            badge_label = "Active" if status == "ACTIVE" else ("Paused" if status == "PAUSED" else status.title())
            rows.append(
                ui.tags.tr(
                    ui.tags.td(c.get("name", "—")), ui.tags.td(ui.span(badge_label, class_=badge_class)),
                    ui.tags.td(fmt_currency(c.get("spend", 0), currency)), ui.tags.td(fmt_number(c.get("impressions", 0))),
                    ui.tags.td(fmt_number(c.get("clicks", 0))), ui.tags.td(fmt_currency(c.get("cpc", 0), currency)),
                    ui.tags.td(f"{c.get('ctr', 0):.2f}%"), ui.tags.td(f"{c.get('roas', 0):.2f}x"),
                )
            )
        return ui.tags.table(
            ui.tags.thead(ui.tags.tr(
                ui.tags.th("Campaign"), ui.tags.th("Status"), ui.tags.th("Spend"),
                ui.tags.th("Impressions"), ui.tags.th("Clicks"), ui.tags.th("CPC"), ui.tags.th("CTR"), ui.tags.th("ROAS"),
            )),
            ui.tags.tbody(*rows),
        )

    # ---- Creatives tab reactives ----

    @reactive.calc
    async def all_creatives_data():
        """Fetch all creatives across all accounts."""
        input.refresh()
        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        data = await marketing_service._fb_client.get_all_creatives()
        return data

    @render.ui
    async def account_selector():
        """Render the account dropdown based on fetched data."""
        data = await all_creatives_data()
        if data is None:
            return ui.div("Loading...", style="color: #64748b;")

        accounts = data.get("accounts", [])
        choices = {"__all__": f"All Accounts ({data.get('total_creatives', 0)} creatives)"}
        for acc in accounts:
            count = acc.get("creative_count", 0)
            label = f"{acc.get('account_name', 'Unknown')} ({acc.get('account_id', '')}) — {count} creatives"
            choices[acc.get("account_id", "")] = label

        return ui.input_select("account_select", None, choices=choices, width="100%")

    @render.ui
    async def creatives_kpi():
        """KPI summary for the selected account."""
        data = await all_creatives_data()
        if data is None:
            return ui.div()

        selected = input.account_select() if hasattr(input, "account_select") else "__all__"
        if not selected:
            selected = "__all__"

        if selected == "__all__":
            total = data.get("total_creatives", 0)
            accounts_count = data.get("accounts_with_creatives", 0)
            total_accounts = data.get("total_accounts", 0)
            # Count by type
            type_counts = {"video": 0, "image": 0, "carousel": 0, "unknown": 0}
            for acc in data.get("accounts", []):
                for c in acc.get("creatives", []):
                    ctype = c.get("type", "unknown")
                    type_counts[ctype] = type_counts.get(ctype, 0) + 1
        else:
            acc_data = next((a for a in data.get("accounts", []) if a.get("account_id") == selected), None)
            if not acc_data:
                return ui.div("Account not found", style="color: #64748b;")
            total = acc_data.get("creative_count", 0)
            accounts_count = 1
            total_accounts = 1
            type_counts = {"video": 0, "image": 0, "carousel": 0, "unknown": 0}
            for c in acc_data.get("creatives", []):
                ctype = c.get("type", "unknown")
                type_counts[ctype] = type_counts.get(ctype, 0) + 1

        kpi_items = [
            ui.div(
                ui.div("Total Creatives", class_="kpi-label"),
                ui.div(fmt_number(total), class_="kpi-value"),
                ui.div(f"{accounts_count} of {total_accounts} accounts", class_="kpi-sub"),
                class_="kpi-card", style="flex: 1; min-width: 160px;",
            ),
            ui.div(
                ui.div("Videos", class_="kpi-label"),
                ui.div(fmt_number(type_counts.get("video", 0)), class_="kpi-value", style="color: #7dd3fc;"),
                class_="kpi-card", style="flex: 1; min-width: 120px;",
            ),
            ui.div(
                ui.div("Images", class_="kpi-label"),
                ui.div(fmt_number(type_counts.get("image", 0)), class_="kpi-value", style="color: #6ee7b7;"),
                class_="kpi-card", style="flex: 1; min-width: 120px;",
            ),
            ui.div(
                ui.div("Carousels", class_="kpi-label"),
                ui.div(fmt_number(type_counts.get("carousel", 0)), class_="kpi-value", style="color: #c4b5fd;"),
                class_="kpi-card", style="flex: 1; min-width: 120px;",
            ),
        ]
        return ui.div(*kpi_items, style="display: flex; gap: 16px; flex-wrap: wrap;")

    @render.ui
    async def creatives_grid():
        """Render the creative grid for the selected account."""
        data = await all_creatives_data()
        if data is None or "error" in (data or {}):
            return ui.div("Facebook Ads client not configured or error occurred.", style="color: #64748b; text-align: center; padding: 40px;")

        selected = input.account_select() if hasattr(input, "account_select") else "__all__"
        if not selected:
            selected = "__all__"

        # Collect creatives based on selection
        creatives_list = []
        if selected == "__all__":
            for acc in data.get("accounts", []):
                acc_name = acc.get("account_name", "Unknown")
                acc_id = acc.get("account_id", "")
                for c in acc.get("creatives", []):
                    c["_account_name"] = acc_name
                    c["_account_id"] = acc_id
                    creatives_list.append(c)
        else:
            acc_data = next((a for a in data.get("accounts", []) if a.get("account_id") == selected), None)
            if acc_data:
                for c in acc_data.get("creatives", []):
                    c["_account_name"] = acc_data.get("account_name", "Unknown")
                    c["_account_id"] = acc_data.get("account_id", "")
                    creatives_list.append(c)

        if not creatives_list:
            return ui.div("No creatives found for the selected account.", style="color: #64748b; text-align: center; padding: 40px;")

        # Build grid cards
        cards = []
        for idx, c in enumerate(creatives_list):
            creative_id = c.get("creative_id", "")
            name = c.get("name", "Untitled")
            ctype = c.get("type", "unknown")
            status = c.get("status", "UNKNOWN").upper()
            thumb_url = c.get("preview_url") or c.get("thumbnail_url") or c.get("image_url") or ""

            # Type badge class
            type_class = f"type-badge-{ctype}" if ctype in ("video", "image", "carousel") else "type-badge-unknown"

            # Status badge
            status_class = "badge-active" if status == "ACTIVE" else ("badge-paused" if status == "PAUSED" else "badge-archived")
            status_label = "Active" if status == "ACTIVE" else ("Paused" if status == "PAUSED" else status.title())

            # Thumbnail
            if thumb_url:
                thumb = ui.tags.img(src=thumb_url, class_="creative-thumb", alt=name)
            else:
                icon = "🎬" if ctype == "video" else ("🖼" if ctype == "image" else ("📑" if ctype == "carousel" else "📄"))
                thumb = ui.div(icon, class_="creative-thumb-placeholder")

            # Short hash for display
            short_id = creative_id[-8:] if len(creative_id) > 8 else creative_id

            # Build the card as a button that triggers the modal
            card = ui.div(
                thumb,
                ui.div(
                    ui.div(name, class_="creative-name", title=name),
                    ui.div(f"ID: {creative_id}  #{short_id}", class_="creative-id"),
                    ui.div(
                        ui.span(ctype.title(), class_=type_class),
                        ui.span(status_label, class_=status_class),
                        class_="creative-meta",
                    ),
                    class_="creative-info",
                ),
                class_="creative-card",
                # Use onclick to set the selected creative via JS → Shiny input
                onclick=f"Shiny.setInputValue('clicked_creative', {json.dumps(json.dumps(c))}, {{priority: 'event'}});",
            )
            cards.append(card)

        return ui.div(*cards, class_="creative-grid")

    # ---- Creative detail modal ----

    @reactive.effect
    @reactive.event(input.clicked_creative)
    async def _show_creative_modal():
        """Show detail modal when a creative card is clicked."""
        raw = input.clicked_creative()
        if not raw:
            return

        try:
            c = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        creative_id = c.get("creative_id", "Unknown")
        name = c.get("name", "Untitled")
        ctype = c.get("type", "unknown")
        status = c.get("status", "UNKNOWN").upper()
        title = c.get("title", "") or "—"
        body = c.get("body", "") or "—"
        image_url = c.get("image_url", "") or "—"
        thumb_url = c.get("preview_url") or c.get("thumbnail_url") or ""
        account_name = c.get("_account_name", "—")
        account_id = c.get("_account_id", "—")

        type_class = f"type-badge-{ctype}" if ctype in ("video", "image", "carousel") else "type-badge-unknown"
        status_class = "badge-active" if status == "ACTIVE" else ("badge-paused" if status == "PAUSED" else "badge-archived")
        status_label = "Active" if status == "ACTIVE" else ("Paused" if status == "PAUSED" else status.title())

        # Preview image
        if thumb_url:
            preview = ui.tags.img(
                src=thumb_url,
                style="width: 100%; max-height: 360px; object-fit: contain; border-radius: 8px; background: #0f1117; margin-bottom: 16px;",
            )
        else:
            preview = ui.div(
                "No preview available",
                style="width: 100%; height: 200px; display: flex; align-items: center; justify-content: center; background: #0f1117; border-radius: 8px; color: #374151; margin-bottom: 16px;",
            )

        modal = ui.modal(
            preview,

            # Detail grid
            ui.div(
                ui.div(ui.tags.label("Creative ID"), ui.span(creative_id, style="font-family: monospace; font-size: 12px;"), class_="detail-item"),
                ui.div(ui.tags.label("Type"), ui.span(ctype.title(), class_=type_class), class_="detail-item"),
                ui.div(ui.tags.label("Status"), ui.span(status_label, class_=status_class), class_="detail-item"),
                ui.div(ui.tags.label("Account"), ui.span(f"{account_name}", style="font-size: 13px;"), class_="detail-item"),
                ui.div(ui.tags.label("Account ID"), ui.span(account_id, style="font-family: monospace; font-size: 12px;"), class_="detail-item"),
                ui.div(ui.tags.label("Ad Title"), ui.span(title), class_="detail-item"),
                class_="detail-grid",
            ),

            # Body text (full width)
            ui.div(
                ui.tags.label("Body Text", style="display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 16px; margin-bottom: 4px;"),
                ui.div(body, style="font-size: 13px; color: #cbd5e1; line-height: 1.6; padding: 12px; background: #0f1117; border-radius: 8px; max-height: 120px; overflow-y: auto;"),
            ),

            # Image URL
            ui.div(
                ui.tags.label("Image URL", style="display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 12px; margin-bottom: 4px;"),
                ui.div(image_url, style="font-size: 11px; color: #475569; font-family: monospace; word-break: break-all; padding: 8px; background: #0f1117; border-radius: 6px;"),
            ),

            # Action buttons
            ui.div(
                ui.tags.button("Create Ad from Creative", class_="action-btn action-btn-primary", onclick=f"alert('Create Ad flow for creative {creative_id} — coming soon');"),
                ui.tags.button("Delete Creative", class_="action-btn action-btn-danger", onclick=f"alert('Delete creative {creative_id} — coming soon');"),
                ui.tags.button("Copy ID", class_="action-btn action-btn-secondary", onclick=f"navigator.clipboard.writeText('{creative_id}'); alert('Creative ID copied to clipboard');"),
                style="display: flex; gap: 12px; margin-top: 20px; flex-wrap: wrap;",
            ),

            title=name,
            size="l",
            easy_close=True,
        )
        ui.modal_show(modal)

    # ---- Upload modal ----

    @reactive.effect
    @reactive.event(input.show_upload)
    async def _show_upload_modal():
        """Show the upload modal for new creatives."""
        # Get accounts for the dropdown
        data = await all_creatives_data()
        accounts = data.get("accounts", []) if data else []

        account_choices = {}
        for acc in accounts:
            account_choices[acc.get("account_id", "")] = f"{acc.get('account_name', 'Unknown')} ({acc.get('account_id', '')})"

        modal = ui.modal(
            # Account selector for upload target
            ui.div(
                ui.input_select("upload_account", "Target Ad Account", choices=account_choices, width="100%"),
                style="margin-bottom: 16px;",
            ),

            # Creative name
            ui.div(
                ui.input_text("upload_name", "Creative Name", placeholder="e.g., Summer Sale Banner v2", width="100%"),
                style="margin-bottom: 16px;",
            ),

            # Creative title
            ui.div(
                ui.input_text("upload_title", "Ad Title", placeholder="e.g., 50% Off All Gummies", width="100%"),
                style="margin-bottom: 16px;",
            ),

            # Body text
            ui.div(
                ui.input_text_area("upload_body", "Ad Body Text", placeholder="Write your ad copy here...", width="100%", rows=3),
                style="margin-bottom: 16px;",
            ),

            # File upload
            ui.div(
                ui.input_file("upload_file", "Upload Image or Video", accept=[".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov"], multiple=False),
                style="margin-bottom: 16px;",
            ),

            # Link URL
            ui.div(
                ui.input_text("upload_link", "Destination URL", placeholder="https://kayapure.com/product/...", width="100%"),
                style="margin-bottom: 20px;",
            ),

            # Submit button
            ui.div(
                ui.input_action_button("submit_upload", "Upload Creative to Meta", class_="action-btn action-btn-primary", style="width: 100%; padding: 12px;"),
            ),

            title="Upload New Creative",
            size="l",
            easy_close=True,
        )
        ui.modal_show(modal)

    @reactive.effect
    @reactive.event(input.submit_upload)
    async def _handle_upload():
        """Handle the creative upload submission."""
        account_id = input.upload_account()
        name = input.upload_name()
        title = input.upload_title()
        body = input.upload_body()
        link = input.upload_link()
        file_info = input.upload_file()

        if not account_id or not name:
            ui.notification_show("Please fill in at least the account and creative name.", type="error", duration=4)
            return

        if not file_info:
            ui.notification_show("Please select an image or video file to upload.", type="error", duration=4)
            return

        ui.notification_show(
            f"Upload creative '{name}' to {account_id} — This feature requires the Facebook Marketing API "
            f"'ads_management' permission. The upload endpoint will be wired once the permission is approved. "
            f"File: {file_info[0]['name']}",
            type="warning",
            duration=8,
        )
        ui.modal_remove()


# ============================================
# App instance (mounted by FastAPI)
# ============================================
shiny_app = App(app_ui, server)
