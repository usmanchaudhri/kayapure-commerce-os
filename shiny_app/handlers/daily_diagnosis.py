"""Daily Account Diagnosis — Shiny handlers."""

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.growth_feature_common import (
    custom_dates_output,
    date_range_from_input,
    error_block,
    loading_block,
    selected_account_id,
)
from shiny_app.lib.formatting import fmt_currency


def _account_select_ui(accounts, prefix: str):
    choices = {"__all__": "All ad accounts"}
    for acc in accounts:
        acc_id = acc.get("id", "")
        choices[acc_id] = f"{acc.get('name', 'Unknown')} ({acc_id})"
    return ui.input_select(f"{prefix}_account", None, choices=choices, selected="__all__", width="320px")


def register(input: Inputs, output: Outputs, session: Session) -> None:
    result_val = reactive.Value(None)
    loading = reactive.Value(False)
    error_val = reactive.Value("")

    @render.ui
    def daily_dx_custom_dates():
        return custom_dates_output(input, "daily_dx")

    @reactive.calc
    async def daily_dx_accounts():
        input.refresh()
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return []
        return await fb.get_all_ad_accounts()

    @render.ui
    async def daily_dx_account_select():
        return _account_select_ui(await daily_dx_accounts(), "daily_dx")

    async def _run():
        loading.set(True)
        error_val.set("")
        try:
            from services.daily_account_diagnosis import daily_account_diagnosis_service

            period = date_range_from_input(input, "daily_dx")
            result = await daily_account_diagnosis_service.diagnose_all(
                since=period.since,
                until=period.until,
                account_id=selected_account_id(input, "daily_dx"),
                explain=True,
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
    @reactive.event(input.daily_dx_run)
    async def _on_run():
        await _run()

    @reactive.effect
    @reactive.event(input.refresh)
    async def _on_refresh():
        if result_val.get():
            await _run()

    @render.ui
    def daily_dx_content():
        if loading.get():
            return loading_block("Generating plain-English account diagnosis…")

        err = error_val.get()
        if err and not result_val.get():
            return error_block("Diagnosis unavailable", err)

        result = result_val.get()
        if not result:
            return ui.div(
                ui.div("Your daily account diagnosis", class_="gf-card-title"),
                ui.div(
                    "Select a date range and generate a five-sentence diagnosis covering "
                    "traffic, creative, landing, checkout, and repeat economics.",
                    class_="gf-card-sub",
                ),
                class_="gf-card gf-card-empty",
            )

        sections = result.get("sections") or []
        sentences = result.get("sentences") or []
        diagnosis = result.get("diagnosis") or " ".join(sentences)

        section_cards = []
        for sec in sections:
            section_cards.append(
                ui.div(
                    ui.div(sec.get("label", ""), class_="gf-section-label"),
                    ui.div(sec.get("sentence", ""), class_="gf-section-text"),
                    class_="gf-section-card",
                )
            )

        period = (result.get("period") or {}).get("label", "")

        return ui.div(
            ui.div(
                ui.div("Today's account diagnosis", class_="gf-hero-title"),
                ui.div(diagnosis, class_="gf-hero-text"),
                ui.div(period, class_="gf-hero-meta"),
                class_="gf-hero-card",
            ),
            ui.div(*section_cards, class_="gf-section-grid"),
        )
