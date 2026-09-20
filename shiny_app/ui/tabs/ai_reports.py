"""AI Reports nav panel."""

from shiny import ui

from shiny_app.ui.date_range_filter import date_range_filter


def nav_panel():
    return ui.nav_panel(
        "Ads Performance",
        ui.div(
            ui.div(
                ui.span("Featured", class_="ai-reports-featured-badge"),
                ui.tags.h3("Ads Performance"),
                ui.div(
                    "Your primary command center — generate intelligent reports "
                    "to analyse and improve ad spend across every account.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            date_range_filter(
                select_id="ai_reports_date_range",
                custom_output_id="ai_reports_custom_dates",
            ),
            class_="ai-reports-header",
        ),
        ui.output_ui("ai_reports_table_header"),
        ui.div(
            ui.output_ui("ai_reports_accounts_list"),
        ),
        ui.div(
            ui.output_ui("pending_actions_panel"),
            style="margin-top: 24px;",
        ),
        value="ai_reports",
    )
