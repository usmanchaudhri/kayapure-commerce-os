"""Funnel & Measurement Reconciliation nav panel."""

from shiny import ui

from shiny_app.ui.date_range_filter import date_range_filter


def nav_panel():
    return ui.nav_panel(
        "Funnel Reconciliation",
        ui.div(
            ui.div(
                ui.span("Supplement growth", class_="pls-featured-badge"),
                ui.tags.h3("Funnel & Measurement"),
                ui.div(
                    "Stage-by-stage funnel drop-off and Meta vs store purchase reconciliation.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            date_range_filter(
                select_id="funnel_rec_date_range",
                custom_output_id="funnel_rec_custom_dates",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.output_ui("funnel_rec_account_select"),
            ui.input_action_button("funnel_rec_run", "Reconcile", class_="btn-primary pls-scan-btn"),
            class_="pls-controls",
        ),
        ui.output_ui("funnel_rec_content"),
        value="funnel_reconciliation",
    )
