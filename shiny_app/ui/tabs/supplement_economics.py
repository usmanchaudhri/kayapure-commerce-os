"""Supplement Economics nav panel."""

from shiny import ui

from shiny_app.ui.date_range_filter import date_range_filter


def nav_panel():
    return ui.nav_panel(
        "Unit Economics",
        ui.div(
            ui.div(
                ui.span("Supplement growth", class_="pls-featured-badge"),
                ui.tags.h3("Supplement Economics"),
                ui.div(
                    "First-order CAC, break-even CPA, and 60/90-day contribution margin "
                    "for supplement DTC economics.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            date_range_filter(
                select_id="supp_econ_date_range",
                custom_output_id="supp_econ_custom_dates",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.output_ui("supp_econ_account_select"),
            ui.input_action_button("supp_econ_run", "Calculate economics", class_="btn-primary pls-scan-btn"),
            class_="pls-controls",
        ),
        ui.div(
            ui.div("Cost assumptions", class_="gf-section-label"),
            ui.div(
                ui.input_numeric("supp_econ_product_cost", "Product cost ($)", value=12, min=0),
                ui.input_numeric("supp_econ_shipping", "Shipping ($)", value=5, min=0),
                ui.input_numeric("supp_econ_aov", "Avg order value ($)", value=48, min=0),
                ui.input_numeric("supp_econ_discount_pct", "Avg discount %", value=15, min=0, max=90),
                ui.input_numeric("supp_econ_refund_pct", "Refund rate %", value=5, min=0, max=100),
                ui.input_numeric("supp_econ_sub_share", "Subscription share %", value=25, min=0, max=100),
                ui.input_numeric("supp_econ_ltv_60", "60-day LTV multiplier", value=1.35, min=1, max=5),
                ui.input_numeric("supp_econ_ltv_90", "90-day LTV multiplier", value=1.55, min=1, max=5),
                class_="supp-econ-inputs",
            ),
            class_="gf-assumptions-panel",
        ),
        ui.output_ui("supp_econ_content"),
        value="supplement_economics",
    )
