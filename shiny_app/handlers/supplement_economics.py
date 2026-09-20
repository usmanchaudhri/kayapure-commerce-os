"""Supplement Economics — Shiny handlers."""

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.growth_feature_common import (
    custom_dates_output,
    date_range_from_input,
    error_block,
    loading_block,
    selected_account_id,
)
from shiny_app.lib.formatting import fmt_currency


def _inputs_from_ui(input: Inputs):
    from services.supplement_economics import SupplementEconomicsInputs

    return SupplementEconomicsInputs(
        product_cost=float(input.supp_econ_product_cost() or 12),
        shipping_cost=float(input.supp_econ_shipping() or 5),
        avg_order_value=float(input.supp_econ_aov() or 48),
        avg_discount_pct=float(input.supp_econ_discount_pct() or 15),
        refund_rate_pct=float(input.supp_econ_refund_pct() or 5),
        subscription_share_pct=float(input.supp_econ_sub_share() or 25),
        ltv_multiplier_60d=float(input.supp_econ_ltv_60() or 1.35),
        ltv_multiplier_90d=float(input.supp_econ_ltv_90() or 1.55),
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    result_val = reactive.Value(None)
    loading = reactive.Value(False)
    error_val = reactive.Value("")

    @render.ui
    def supp_econ_custom_dates():
        return custom_dates_output(input, "supp_econ")

    @reactive.calc
    async def supp_econ_accounts():
        input.refresh()
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return []
        return await fb.get_all_ad_accounts()

    @render.ui
    async def supp_econ_account_select():
        accounts = await supp_econ_accounts()
        choices = {"__all__": "All ad accounts"}
        for acc in accounts:
            acc_id = acc.get("id", "")
            choices[acc_id] = f"{acc.get('name', 'Unknown')} ({acc_id})"
        return ui.input_select("supp_econ_account", None, choices=choices, selected="__all__", width="320px")

    async def _run():
        loading.set(True)
        error_val.set("")
        try:
            from services.supplement_economics import (
                save_economics_config,
                supplement_economics_service,
            )

            period = date_range_from_input(input, "supp_econ")
            account_id = selected_account_id(input, "supp_econ") or ""
            config = _inputs_from_ui(input)
            save_economics_config(config, account_id)

            result = await supplement_economics_service.analyze_all(
                since=period.since,
                until=period.until,
                account_id=account_id or None,
                inputs=config,
            )
            if result.get("error"):
                error_val.set(str(result["error"]))
            result_val.set(result)
        except Exception as exc:
            error_val.set(str(exc))
            result_val.set(None)
        finally:
            loading.set(False)

    @reactive.effect
    @reactive.event(input.supp_econ_run)
    async def _on_run():
        await _run()

    @render.ui
    def supp_econ_content():
        if loading.get():
            return loading_block("Calculating supplement unit economics…")

        err = error_val.get()
        if err and not result_val.get():
            return error_block("Economics unavailable", err)

        result = result_val.get()
        if not result:
            return ui.div(
                ui.div("Supplement unit economics", class_="gf-card-title"),
                ui.div(
                    "Enter cost assumptions above, then calculate first-order CAC, break-even CPA, "
                    "and LTV-adjusted contribution by campaign.",
                    class_="gf-card-sub",
                ),
                class_="gf-card gf-card-empty",
            )

        metrics = result.get("metrics") or {}
        mix = result.get("customer_mix") or {}
        verdict = result.get("verdict", "")
        currency = "USD"
        campaigns = result.get("campaign_economics") or []

        kpi_cards = [
            ("First-order CAC", metrics.get("first_order_cac"), "Meta attributed"),
            ("Break-even CPA", metrics.get("break_even_cpa"), "First-order contribution"),
            ("60-day break-even", metrics.get("break_even_cpa_60d"), "LTV-adjusted"),
            ("90-day break-even", metrics.get("break_even_cpa_90d"), "LTV-adjusted"),
        ]

        kpi_row = [
            ui.div(
                ui.div(label, class_="gf-kpi-label"),
                ui.div(
                    fmt_currency(val, currency) if val is not None else "—",
                    class_="gf-kpi-value",
                ),
                ui.div(sub, class_="gf-kpi-sub"),
                class_="gf-kpi-card",
            )
            for label, val, sub in kpi_cards
        ]

        table_rows = []
        for row in campaigns:
            status = row.get("status", "")
            status_label = status.replace("_", " ").title()
            table_rows.append(
                ui.tags.tr(
                    ui.tags.td(row.get("campaign_name", "")[:40]),
                    ui.tags.td(row.get("segment", "")),
                    ui.tags.td(fmt_currency(row.get("spend", 0), currency)),
                    ui.tags.td(fmt_currency(row.get("cpa", 0), currency)),
                    ui.tags.td(fmt_currency(row.get("vs_break_even", 0), currency)),
                    ui.tags.td(status_label),
                )
            )

        return ui.div(
            ui.div(
                ui.div("Economics verdict", class_="gf-hero-title"),
                ui.div(verdict, class_="gf-hero-text"),
                class_="gf-hero-card",
            ),
            ui.div(*kpi_row, class_="gf-kpi-grid"),
            ui.div(
                ui.div("Customer mix", class_="gf-board-title"),
                ui.div(
                    f"Retargeting spend {mix.get('retargeting_spend_share_pct', 0):.0f}% · "
                    f"Prospecting spend {mix.get('prospecting_spend_share_pct', 0):.0f}%",
                    class_="gf-section-text",
                ),
                ui.div(mix.get("note", ""), class_="gf-card-sub"),
                class_="gf-board-section",
            ),
            ui.div(
                ui.div("Campaign economics", class_="gf-board-title"),
                ui.tags.table(
                    ui.tags.thead(
                        ui.tags.tr(
                            ui.tags.th("Campaign"),
                            ui.tags.th("Segment"),
                            ui.tags.th("Spend"),
                            ui.tags.th("CPA"),
                            ui.tags.th("vs break-even"),
                            ui.tags.th("Status"),
                        )
                    ),
                    ui.tags.tbody(*table_rows),
                    class_="gf-data-table",
                )
                if table_rows
                else ui.div("No campaigns with sufficient spend.", class_="gf-card-sub"),
                class_="gf-board-section",
            ),
        )
