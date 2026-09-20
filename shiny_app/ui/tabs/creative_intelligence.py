"""Creative Intelligence nav panel."""

from shiny import ui

from shiny_app.ui.date_range_filter import date_range_filter


def nav_panel():
    return ui.nav_panel(
        "Creative Intelligence",
        ui.div(
            ui.div(
                ui.span("Supplement growth", class_="pls-featured-badge"),
                ui.tags.h3("Creative Intelligence"),
                ui.div(
                    "Winning message patterns, fatigue signals, and a structured creative test backlog.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            date_range_filter(
                select_id="creative_intel_date_range",
                custom_output_id="creative_intel_custom_dates",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.output_ui("creative_intel_account_select"),
            ui.input_action_button("creative_intel_run", "Analyze creatives", class_="btn-primary pls-scan-btn"),
            class_="pls-controls",
        ),
        ui.output_ui("creative_intel_content"),
        value="creative_intelligence",
    )
