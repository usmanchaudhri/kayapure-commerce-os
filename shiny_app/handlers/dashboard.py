"""Dashboard tab — overall ads summary."""

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.lib.date_ranges import resolve_date_range
from shiny_app.lib.formatting import fmt_currency, fmt_date_range, fmt_number, fmt_pct
from shiny_app.lib.metric_tooltips import metric_label


def _current_date_range(input: Inputs):
    """Resolve the dashboard date filter into a since/until period.

    Args:
        input: Shiny inputs.

    Returns:
        Resolved date range with since, until, and label.
    """
    range_val = "30"
    custom_since = None
    custom_until = None
    try:
        range_val = input.dashboard_date_range() or "30"
    except Exception:
        range_val = "30"
    if range_val == "custom":
        try:
            custom_since = input.dashboard_date_since()
            custom_until = input.dashboard_date_until()
        except Exception:
            pass
    return resolve_date_range(range_val, custom_since=custom_since, custom_until=custom_until)


def _metric_card(label, value, *, tip_key: str = ""):
    """Render a single dashboard metric tile.

    Args:
        label: Metric label node or text.
        value: Formatted metric value string.
        tip_key: Optional metric tooltip key.

    Returns:
        Shiny UI div for the metric card.
    """
    label_node = (
        metric_label(label, tip_key, class_="dash-metric-label")
        if tip_key
        else ui.div(label, class_="dash-metric-label")
    )
    return ui.div(
        label_node,
        ui.div(value, class_="dash-metric-value"),
        class_="dash-metric",
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    """Register Overview dashboard reactive handlers.

    Args:
        input: Shiny inputs.
        output: Shiny outputs.
        session: Shiny session.
    """

    @reactive.calc
    async def summary_data():
        """Fetch all-account spend totals for the selected period."""
        input.refresh()
        # Explicit dependencies: preset + custom from/to (always mounted in UI).
        input.dashboard_date_range()
        try:
            input.dashboard_date_since()
            input.dashboard_date_until()
        except Exception:
            pass

        from services.marketing import marketing_service

        if not marketing_service._fb_client:
            return {"error": "Facebook Ads client is not configured."}

        period = _current_date_range(input)
        data = await marketing_service._fb_client.get_total_spend_all_accounts(
            since=period.since,
            until=period.until,
        )
        if isinstance(data, dict):
            data = {**data, "_period_label": period.label}
        return data

    @render.ui
    async def dashboard_summary():
        """Render hero spend + delivery/efficiency metric groups."""
        data = await summary_data()

        if data is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading overall summary...", class_="loading-text"),
                class_="loading-spinner",
            )

        if data.get("error"):
            return ui.div(str(data["error"]), class_="dash-empty")

        period = data.get("period") or {}
        period_label = data.get("_period_label") or "Selected period"
        totals = data.get("grand_totals") or {}
        currency_totals = data.get("currency_totals") or {}

        sorted_currencies = sorted(
            currency_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        primary_currency = sorted_currencies[0][0] if sorted_currencies else "USD"
        primary_spend = float(sorted_currencies[0][1]) if sorted_currencies else 0.0

        chips = [
            ui.span(
                f"{cur}: {fmt_currency(amount, cur)}",
                class_="dash-hero-chip",
            )
            for cur, amount in sorted_currencies
        ]

        since = period.get("since") or "?"
        until = period.get("until") or "?"

        hero = ui.div(
            metric_label("Spend", "spend", class_="dash-hero-label"),
            ui.div(
                fmt_currency(primary_spend, primary_currency),
                class_="dash-hero-value",
            ),
            ui.div(*chips, class_="dash-hero-chips") if chips else ui.div(),
            ui.div(
                ui.span(period_label, class_="dash-hero-range"),
                ui.span("·", class_="dash-hero-dot"),
                ui.span(fmt_date_range(since, until), class_="dash-hero-dates"),
                class_="dash-hero-period",
            ),
            class_="dash-hero",
        )

        delivery = ui.div(
            ui.div("Delivery", class_="dash-group-label"),
            ui.div(
                _metric_card(
                    "Impressions",
                    fmt_number(
                        data.get("grand_total_impressions", totals.get("impressions", 0))
                    ),
                    tip_key="impressions",
                ),
                _metric_card(
                    "Clicks",
                    fmt_number(data.get("grand_total_clicks", totals.get("clicks", 0))),
                    tip_key="clicks",
                ),
                _metric_card(
                    "Reach",
                    fmt_number(totals.get("reach", 0)),
                    tip_key="reach",
                ),
                _metric_card(
                    "Conversion",
                    fmt_number(totals.get("conversions", 0)),
                    tip_key="conversions",
                ),
                class_="dash-metrics dash-metrics-4",
            ),
            class_="dash-group",
        )

        efficiency = ui.div(
            ui.div("Efficiency", class_="dash-group-label"),
            ui.div(
                _metric_card("Avg CTR", fmt_pct(totals.get("ctr", 0)), tip_key="ctr"),
                _metric_card(
                    "Avg CPC",
                    fmt_currency(totals.get("cpc", 0), primary_currency),
                    tip_key="cpc",
                ),
                _metric_card(
                    "Avg CPM",
                    fmt_currency(totals.get("cpm", 0), primary_currency),
                    tip_key="cpm",
                ),
                class_="dash-metrics dash-metrics-3",
            ),
            class_="dash-group",
        )

        return ui.div(hero, delivery, efficiency)
