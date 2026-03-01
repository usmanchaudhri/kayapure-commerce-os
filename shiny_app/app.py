"""
KayaPure Commerce OS — Shiny Dashboard (Meta Ads)
Embedded in FastAPI via ASGI mount at /dashboard.

Displays:
  - Aggregated KPI cards (total spend, clicks, impressions, avg CPC, avg CTR)
  - Campaign insights table with status badges
  - Daily spend breakdown chart
"""

from shiny import App, Inputs, Outputs, Session, reactive, render, ui
import plotly.graph_objects as go
from shinywidgets import output_widget, render_widget

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

    # ---- Total Spend (All Accounts, Jan 2025 – Today) ----
    ui.div(
        ui.div(
            ui.div("Total Ad Spend — All Accounts (Jan 2025 – Today)", class_="card-header"),
            ui.div(ui.output_ui("total_spend_section"), class_="card-body"),
            class_="card",
        ),
        style="margin-bottom: 24px;",
    ),

    # ---- 7-Day View: Period info ----
    ui.div(
        ui.tags.h3("Last 7 Days — Primary Account", style="color: #94a3b8; font-size: 15px; font-weight: 600; margin-bottom: 8px;"),
    ),
    ui.output_ui("period_info"),

    # KPI Cards Row
    ui.div(
        ui.output_ui("kpi_cards"),
        style="margin-bottom: 24px;",
    ),

    # Two-column layout: Chart + Campaign Table
    ui.layout_columns(
        # Daily Spend Chart
        ui.div(
            ui.div(
                ui.div("Daily Ad Spend Trend", class_="card-header"),
                ui.div(output_widget("spend_chart"), class_="card-body"),
                class_="card",
            ),
        ),
        # Campaign Table
        ui.div(
            ui.div(
                ui.div("Campaign Insights", class_="card-header"),
                ui.div(ui.output_ui("campaign_table"), class_="card-body"),
                class_="card",
            ),
        ),
        col_widths=[7, 5],
    ),

    # ---- Ad Creatives (All Accounts) ----
    ui.div(
        ui.div(
            ui.div("Ad Creatives — All Accounts", class_="card-header"),
            ui.div(ui.output_ui("creatives_section"), class_="card-body"),
            class_="card",
        ),
        style="margin-top: 24px; margin-bottom: 24px;",
    ),
)


# ============================================
# Server
# ============================================
def server(input: Inputs, output: Outputs, session: Session):

    @reactive.calc
    async def ad_data():
        """Fetch ad spend history from marketing_service. Re-runs on refresh."""
        input.refresh()  # Reactive dependency on refresh button

        from services.marketing import marketing_service
        data = await marketing_service.get_ad_spend_history(days=7)
        return data

    @reactive.calc
    async def total_spend_data():
        """Fetch total spend across all accounts from Jan 2025 to today."""
        input.refresh()  # Reactive dependency on refresh button

        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        data = await marketing_service._fb_client.get_total_spend_all_accounts(
            since="2025-01-01"
        )
        return data

    @render.ui
    async def total_spend_section():
        data = await total_spend_data()
        if data is None or "error" in data:
            return ui.div(
                "Facebook Ads client not configured or error occurred.",
                style="color: #64748b; text-align: center; padding: 24px;",
            )

        period = data.get("period", {})
        accounts = data.get("accounts", [])
        currency_totals = data.get("currency_totals", {})

        # Grand total KPI row
        kpi_items = []
        for cur, total in currency_totals.items():
            kpi_items.append(
                ui.div(
                    ui.div(f"Total Spend ({cur})", class_="kpi-label"),
                    ui.div(fmt_currency(total, cur), class_="kpi-value"),
                    ui.div(f"{period.get('since', '?')} → {period.get('until', '?')}", class_="kpi-sub"),
                    class_="kpi-card",
                    style="flex: 1; min-width: 200px;",
                )
            )

        kpi_items.append(
            ui.div(
                ui.div("Total Impressions", class_="kpi-label"),
                ui.div(fmt_number(data.get("grand_total_impressions", 0)), class_="kpi-value"),
                ui.div(f"{data.get('total_accounts', 0)} accounts", class_="kpi-sub"),
                class_="kpi-card",
                style="flex: 1; min-width: 200px;",
            )
        )
        kpi_items.append(
            ui.div(
                ui.div("Total Clicks", class_="kpi-label"),
                ui.div(fmt_number(data.get("grand_total_clicks", 0)), class_="kpi-value"),
                ui.div(f"{data.get('accounts_with_data', 0)} accounts with data", class_="kpi-sub"),
                class_="kpi-card",
                style="flex: 1; min-width: 200px;",
            )
        )

        kpi_row = ui.div(*kpi_items, style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px;")

        # Per-account breakdown table
        if not accounts:
            return ui.div(kpi_row, ui.div("No accounts found", style="color: #64748b;"))

        rows = []
        for acc in accounts:
            status = acc.get("status", "UNKNOWN")
            if status == "ACTIVE":
                badge = ui.span("Active", class_="badge-active")
            elif status == "DISABLED":
                badge = ui.span("Disabled", class_="badge-archived")
            else:
                badge = ui.span(status.title(), class_="badge-paused")

            acc_currency = acc.get("currency", "USD")
            rows.append(
                ui.tags.tr(
                    ui.tags.td(acc.get("account_name", "—")),
                    ui.tags.td(acc.get("account_id", "—"), style="font-size: 11px; color: #64748b;"),
                    ui.tags.td(badge),
                    ui.tags.td(acc_currency),
                    ui.tags.td(fmt_currency(acc.get("spend", 0), acc_currency)),
                    ui.tags.td(fmt_number(acc.get("impressions", 0))),
                    ui.tags.td(fmt_number(acc.get("clicks", 0))),
                )
            )

        account_table = ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Account Name"),
                    ui.tags.th("Account ID"),
                    ui.tags.th("Status"),
                    ui.tags.th("Currency"),
                    ui.tags.th("Total Spend"),
                    ui.tags.th("Impressions"),
                    ui.tags.th("Clicks"),
                )
            ),
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
        source_class = "source-badge"
        return ui.div(
            ui.span(f"Period: {period.get('start', '?')} → {period.get('end', '?')} ({period.get('days', '?')} days)", class_="period-info"),
            ui.span(" | "),
            ui.span(f"Currency: {currency}", class_="period-info"),
            ui.span(" | "),
            ui.span(f"Source: ", class_="period-info"),
            ui.span(source_label, class_=source_class),
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

        card_divs = []
        for label, value, sub in cards:
            card_divs.append(
                ui.div(
                    ui.div(label, class_="kpi-label"),
                    ui.div(value, class_="kpi-value"),
                    ui.div(sub, class_="kpi-sub"),
                    class_="kpi-card",
                    style="flex: 1; min-width: 160px;",
                )
            )

        return ui.div(
            *card_divs,
            style="display: flex; gap: 16px; flex-wrap: wrap;",
        )

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
        fig.add_trace(go.Bar(
            x=dates, y=spends, name="Spend",
            marker_color="#2563eb",
            hovertemplate=f"{sym}%{{y:,.2f}}<extra>Spend</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=clicks, name="Clicks",
            yaxis="y2",
            line=dict(color="#22d3ee", width=2),
            mode="lines+markers",
            hovertemplate="%{y:,}<extra>Clicks</extra>",
        ))

        fig.update_layout(
            plot_bgcolor="#1a1d27",
            paper_bgcolor="#1a1d27",
            font=dict(color="#94a3b8", size=11),
            margin=dict(l=50, r=50, t=20, b=40),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
            yaxis=dict(title=f"Spend ({sym})", gridcolor="#2d3348", zeroline=False),
            yaxis2=dict(title="Clicks", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)", zeroline=False),
            xaxis=dict(gridcolor="#2d3348"),
            bargap=0.3,
        )
        return fig

    @reactive.calc
    async def creatives_data():
        """Fetch all creatives across all accounts."""
        input.refresh()  # Reactive dependency on refresh button

        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None
        data = await marketing_service._fb_client.get_all_creatives()
        return data

    @render.ui
    async def creatives_section():
        data = await creatives_data()
        if data is None or "error" in data:
            return ui.div(
                "Facebook Ads client not configured or error occurred.",
                style="color: #64748b; text-align: center; padding: 24px;",
            )

        total_creatives = data.get("total_creatives", 0)
        accounts = data.get("accounts", [])

        # Summary KPI row
        kpi_row = ui.div(
            ui.div(
                ui.div("Total Creatives", class_="kpi-label"),
                ui.div(fmt_number(total_creatives), class_="kpi-value"),
                ui.div(f"Across {data.get('total_accounts', 0)} accounts", class_="kpi-sub"),
                class_="kpi-card",
                style="flex: 1; min-width: 200px;",
            ),
            ui.div(
                ui.div("Accounts with Creatives", class_="kpi-label"),
                ui.div(fmt_number(data.get("accounts_with_creatives", 0)), class_="kpi-value"),
                ui.div(f"of {data.get('total_accounts', 0)} total", class_="kpi-sub"),
                class_="kpi-card",
                style="flex: 1; min-width: 200px;",
            ),
            style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px;",
        )

        if total_creatives == 0:
            return ui.div(kpi_row, ui.div("No creatives found", style="color: #64748b;"))

        # Build per-account creative tables
        account_sections = []
        for acc in accounts:
            creatives = acc.get("creatives", [])
            if not creatives:
                continue

            # Type badge helper
            def type_badge(ctype):
                colors = {
                    "video": ("#1e3a5f", "#7dd3fc"),
                    "image": ("#1a3a2a", "#6ee7b7"),
                    "carousel": ("#3b1f5e", "#c4b5fd"),
                }
                bg, fg = colors.get(ctype, ("#374151", "#9ca3af"))
                return ui.span(
                    ctype.title(),
                    style=f"background: {bg}; color: {fg}; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;",
                )

            rows = []
            for c in creatives:
                status = c.get("status", "UNKNOWN").upper()
                if status == "ACTIVE":
                    status_badge = ui.span("Active", class_="badge-active")
                elif status == "PAUSED":
                    status_badge = ui.span("Paused", class_="badge-paused")
                else:
                    status_badge = ui.span(status.title(), class_="badge-paused")

                # Thumbnail cell
                thumb_url = c.get("preview_url") or c.get("thumbnail_url") or ""
                if thumb_url:
                    thumb = ui.tags.img(
                        src=thumb_url,
                        style="width: 48px; height: 48px; object-fit: cover; border-radius: 6px; border: 1px solid #2d3348;",
                    )
                else:
                    thumb = ui.span("—", style="color: #64748b;")

                # Truncate body text
                body_text = c.get("body", "") or ""
                if len(body_text) > 80:
                    body_text = body_text[:80] + "…"

                rows.append(
                    ui.tags.tr(
                        ui.tags.td(thumb),
                        ui.tags.td(c.get("name", "—")),
                        ui.tags.td(type_badge(c.get("type", "unknown"))),
                        ui.tags.td(status_badge),
                        ui.tags.td(c.get("title", "—") or "—"),
                        ui.tags.td(body_text or "—", style="max-width: 250px; font-size: 12px; color: #94a3b8;"),
                    )
                )

            creative_table = ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("Preview"),
                        ui.tags.th("Creative Name"),
                        ui.tags.th("Type"),
                        ui.tags.th("Status"),
                        ui.tags.th("Title"),
                        ui.tags.th("Body"),
                    )
                ),
                ui.tags.tbody(*rows),
            )

            account_sections.append(
                ui.div(
                    ui.tags.h4(
                        f"{acc.get('account_name', 'Unknown')} ",
                        ui.span(
                            f"({acc.get('account_id', '')}) — {len(creatives)} creatives",
                            style="font-size: 12px; color: #64748b; font-weight: 400;",
                        ),
                        style="color: #e2e8f0; font-size: 14px; font-weight: 600; margin-bottom: 8px;",
                    ),
                    creative_table,
                    style="margin-bottom: 24px;",
                )
            )

        return ui.div(kpi_row, *account_sections)

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
            if status == "ACTIVE":
                badge = ui.span("Active", class_="badge-active")
            elif status == "PAUSED":
                badge = ui.span("Paused", class_="badge-paused")
            else:
                badge = ui.span(status.title(), class_="badge-archived")

            rows.append(
                ui.tags.tr(
                    ui.tags.td(c.get("name", "—")),
                    ui.tags.td(badge),
                    ui.tags.td(fmt_currency(c.get("spend", 0), currency)),
                    ui.tags.td(fmt_number(c.get("impressions", 0))),
                    ui.tags.td(fmt_number(c.get("clicks", 0))),
                    ui.tags.td(fmt_currency(c.get("cpc", 0), currency)),
                    ui.tags.td(f"{c.get('ctr', 0):.2f}%"),
                    ui.tags.td(f"{c.get('roas', 0):.2f}x"),
                )
            )

        return ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Campaign"),
                    ui.tags.th("Status"),
                    ui.tags.th("Spend"),
                    ui.tags.th("Impressions"),
                    ui.tags.th("Clicks"),
                    ui.tags.th("CPC"),
                    ui.tags.th("CTR"),
                    ui.tags.th("ROAS"),
                )
            ),
            ui.tags.tbody(*rows),
        )


# ============================================
# App instance (mounted by FastAPI)
# ============================================
shiny_app = App(app_ui, server)
