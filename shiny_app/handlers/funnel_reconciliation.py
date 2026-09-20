"""Funnel & Measurement Reconciliation — Shiny handlers."""

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.growth_feature_common import (
    custom_dates_output,
    date_range_from_input,
    error_block,
    loading_block,
    selected_account_id,
)


def register(input: Inputs, output: Outputs, session: Session) -> None:
    result_val = reactive.Value(None)
    loading = reactive.Value(False)
    error_val = reactive.Value("")

    @render.ui
    def funnel_rec_custom_dates():
        return custom_dates_output(input, "funnel_rec")

    @reactive.calc
    async def funnel_rec_accounts():
        input.refresh()
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return []
        return await fb.get_all_ad_accounts()

    @render.ui
    async def funnel_rec_account_select():
        accounts = await funnel_rec_accounts()
        choices = {"__all__": "All ad accounts"}
        for acc in accounts:
            acc_id = acc.get("id", "")
            choices[acc_id] = f"{acc.get('name', 'Unknown')} ({acc_id})"
        return ui.input_select("funnel_rec_account", None, choices=choices, selected="__all__", width="320px")

    async def _run():
        loading.set(True)
        error_val.set("")
        try:
            from services.funnel_reconciliation import funnel_reconciliation_service

            period = date_range_from_input(input, "funnel_rec")
            result = await funnel_reconciliation_service.reconcile_all(
                since=period.since,
                until=period.until,
                account_id=selected_account_id(input, "funnel_rec"),
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
    @reactive.event(input.funnel_rec_run)
    async def _on_run():
        await _run()

    @render.ui
    def funnel_rec_content():
        if loading.get():
            return loading_block("Reconciling funnel stages and store orders…")

        err = error_val.get()
        if err and not result_val.get():
            return error_block("Reconciliation unavailable", err)

        result = result_val.get()
        if not result:
            return ui.div(
                ui.div("Funnel & measurement reconciliation", class_="gf-card-title"),
                ui.div(
                    "See where Meta funnel events drop off and how platform purchases "
                    "compare to store paid orders.",
                    class_="gf-card-sub",
                ),
                class_="gf-card gf-card-empty",
            )

        stages = result.get("funnel_stages") or []
        measurement = result.get("measurement") or {}
        flags = result.get("campaign_flags") or []
        health = result.get("health_score", 0)
        summary = result.get("summary", "")

        funnel_rows = []
        for stage in stages:
            rate = stage.get("conversion_rate_pct")
            rate_text = f"{rate:.1f}% from prior stage" if rate is not None else "—"
            funnel_rows.append(
                ui.div(
                    ui.div(stage.get("label", ""), class_="gf-funnel-label"),
                    ui.div(f"{stage.get('count', 0):,}", class_="gf-funnel-count"),
                    ui.div(rate_text, class_="gf-funnel-rate"),
                    class_="gf-funnel-row",
                )
            )

        gap_status = measurement.get("status", "aligned")
        status_class = "gf-status-ok" if gap_status == "aligned" else "gf-status-warn"

        flag_cards = [
            ui.div(
                ui.div(f.get("campaign_name", ""), class_="gf-list-title"),
                ui.div(", ".join(i.replace("_", " ") for i in f.get("issues", [])), class_="gf-list-sub"),
                class_="gf-list-card",
            )
            for f in flags[:8]
        ]

        return ui.div(
            ui.div(
                ui.div(
                    ui.div("Funnel health", class_="gf-hero-title"),
                    ui.div(f"{health}/100", class_="gf-health-score"),
                    ui.div(summary, class_="gf-hero-text"),
                    class_="gf-hero-main",
                ),
                ui.div(
                    ui.div("Meta vs store", class_="gf-section-label"),
                    ui.div(
                        f"Meta {measurement.get('meta_purchases', 0)} · "
                        f"Store {measurement.get('store_orders', 0)} · "
                        f"Gap {measurement.get('gap_pct', 0):.0f}%",
                        class_=f"gf-measurement-line {status_class}",
                    ),
                    ui.div(measurement.get("explanation", ""), class_="gf-section-text"),
                    class_="gf-measurement-card",
                ),
                class_="gf-hero-split",
            ),
            ui.div(
                ui.div("Funnel stages", class_="gf-board-title"),
                ui.div(*funnel_rows, class_="gf-funnel-table"),
                class_="gf-board-section",
            ),
            ui.div(
                ui.div("Campaign funnel flags", class_="gf-board-title"),
                ui.div(*flag_cards, class_="gf-list-grid") if flag_cards else ui.div("No campaign-level funnel issues flagged.", class_="gf-card-sub"),
                class_="gf-board-section",
            ),
        )
