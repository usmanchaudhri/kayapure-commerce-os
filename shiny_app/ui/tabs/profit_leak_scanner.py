"""Profit Leak Scanner nav panel."""

from shiny import ui

from shiny_app.ui.date_range_filter import date_range_filter


def nav_panel():
    return ui.nav_panel(
        "Profit Leak Scanner",
        ui.div(
            ui.div(
                ui.span("Supplement growth", class_="pls-featured-badge"),
                ui.tags.h3("Profit Leak Scanner"),
                ui.div(
                    "Find where ad budget is leaking, estimate the opportunity, "
                    "and get the next test to run — ranked by financial impact.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            date_range_filter(
                select_id="profit_leak_date_range",
                custom_output_id="profit_leak_custom_dates",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.output_ui("profit_leak_account_select"),
            ui.input_action_button(
                "profit_leak_scan",
                "Run scan",
                class_="btn-primary pls-scan-btn",
            ),
            ui.output_ui("profit_leak_history_select"),
            class_="pls-controls",
        ),
        ui.output_ui("profit_leak_summary"),
        ui.output_ui("profit_leak_board"),
        value="profit_leak_scanner",
    )
