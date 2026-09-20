"""Daily Account Diagnosis nav panel."""

from shiny import ui

from shiny_app.ui.date_range_filter import date_range_filter


def nav_panel():
    return ui.nav_panel(
        "Daily Diagnosis",
        ui.div(
            ui.div(
                ui.span("Supplement growth", class_="pls-featured-badge"),
                ui.tags.h3("Daily Account Diagnosis"),
                ui.div(
                    "Five plain-English sentences on traffic, creative, landing, checkout, "
                    "and repeat economics — no Ads Manager jargon.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            date_range_filter(
                select_id="daily_dx_date_range",
                custom_output_id="daily_dx_custom_dates",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.output_ui("daily_dx_account_select"),
            ui.input_action_button("daily_dx_run", "Generate diagnosis", class_="btn-primary pls-scan-btn"),
            class_="pls-controls",
        ),
        ui.output_ui("daily_dx_content"),
        value="daily_diagnosis",
    )
