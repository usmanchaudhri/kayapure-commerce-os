"""Per-account campaign dropdown for the Ads Performance tab.

Campaigns are fetched only when the dropdown is opened (lazy load), then
cached for the current date range so collapsing/reopening does not refetch.

Phase 1 loads campaign list + batched insights.
Phase 2 (background) attaches ad previews and goal/destination metadata.
"""

from __future__ import annotations

import re
from typing import Callable

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from shiny_app.lib.campaign_table import attach_account_fields, build_campaigns_table
from shiny_app.lib.date_ranges import ResolvedDateRange

GetPeriod = Callable[[], ResolvedDateRange]

_CHEVRON_SVG = (
    '<svg class="account-campaigns-chevron-icon" width="22" height="22" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>'
)


def account_campaigns_module_id(acc_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", acc_id or "account")
    return f"accamp_{safe}"


@module.ui
def account_campaigns_ui():
    return ui.output_ui("campaigns_dropdown")


@module.server
def account_campaigns_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    acc_id: str,
    acc_name: str,
    currency: str,
    get_period: GetPeriod,
):
    expanded = reactive.Value(False)
    fetching = reactive.Value(False)
    enriching = reactive.Value(False)
    payload = reactive.Value(None)
    error_message = reactive.Value("")
    loaded_period_key = reactive.Value("")
    sort_mode = reactive.Value("created")

    def _period_key() -> str:
        period = get_period()
        return f"{period.since}|{period.until}"

    def _toggle_id() -> str:
        return str(session.ns("toggle_campaigns"))

    def _sort_id() -> str:
        return str(session.ns("sort_mode"))

    async def _enrich_phase_two(base_payload: dict, period_key: str) -> None:
        if base_payload.get("enrichment_loaded"):
            return
        campaigns = list(base_payload.get("campaigns") or [])
        if not campaigns:
            return
        enriching.set(True)
        try:
            from services.marketing import marketing_service

            fb_client = marketing_service._fb_client
            if not fb_client:
                return
            enriched = await fb_client.enrich_account_campaigns(acc_id, campaigns)
            # Only apply if still on the same period / expand session
            if loaded_period_key.get() != period_key:
                return
            next_payload = {
                **base_payload,
                "campaigns": enriched,
                "enrichment_loaded": True,
            }
            payload.set(next_payload)
        except Exception as exc:
            error_message.set(f"Details partially unavailable: {exc}")
        finally:
            enriching.set(False)

    async def _load_campaigns(force: bool = False) -> None:
        key = _period_key()
        if fetching.get():
            return
        if not force and payload.get() is not None and loaded_period_key.get() == key:
            return

        fetching.set(True)
        error_message.set("")
        try:
            from services.marketing import marketing_service

            fb_client = marketing_service._fb_client
            if not fb_client:
                error_message.set("Facebook Ads client is not configured.")
                payload.set({"campaigns": [], "campaign_count": 0, "enrichment_loaded": True})
                loaded_period_key.set(key)
                return

            period = get_period()
            # Phase 1 only — list + batched insights (no /ads or /adsets yet)
            data = await fb_client.get_account_campaigns(
                acc_id,
                since=period.since,
                until=period.until,
                account_name=acc_name,
                currency=currency,
                include_insights=True,
                include_enrichment=False,
                force_refresh=force,
            )
            payload.set(data)
            loaded_period_key.set(key)
            if data.get("error"):
                error_message.set(str(data["error"]))
            fetching.set(False)
            # Phase 2 in background so the table paints first
            await _enrich_phase_two(data, key)
            return
        except Exception as exc:
            error_message.set(str(exc))
            payload.set({"campaigns": [], "campaign_count": 0, "enrichment_loaded": True})
            loaded_period_key.set(key)
        finally:
            fetching.set(False)

    @reactive.effect
    @reactive.event(input.toggle_campaigns)
    async def _toggle_dropdown():
        if expanded.get():
            expanded.set(False)
            return
        expanded.set(True)
        await _load_campaigns()

    @reactive.effect
    @reactive.event(input.sort_mode)
    def _change_sort():
        val = str(input.sort_mode() or "")
        if val in ("created", "spend"):
            sort_mode.set(val)

    @reactive.effect
    async def _reload_when_date_range_changes():
        if not expanded.get():
            return
        key = _period_key()
        if loaded_period_key.get() == key:
            return
        await _load_campaigns(force=True)

    def _toggle_button(*, is_open: bool, count_label: str) -> ui.Tag:
        return ui.tags.button(
            ui.span(ui.HTML(_CHEVRON_SVG), class_="account-campaigns-chevron"),
            ui.span(
                ui.span("Campaigns", class_="account-campaigns-toggle-title"),
                ui.span(count_label, class_="account-campaigns-toggle-sub"),
                class_="account-campaigns-toggle-copy",
            ),
            type="button",
            class_="btn-account-campaigns-toggle",
            **{
                "aria-expanded": "true" if is_open else "false",
                "onclick": (
                    f"Shiny.setInputValue('{_toggle_id()}', Date.now(), {{priority: 'event'}});"
                ),
            },
        )

    def _sort_bar(active: str) -> ui.Tag:
        def chip(value: str, label: str) -> ui.Tag:
            is_active = active == value
            return ui.tags.button(
                label,
                type="button",
                class_="account-campaigns-sort-chip" + (" is-active" if is_active else ""),
                onclick=(
                    f"Shiny.setInputValue('{_sort_id()}', '{value}', {{priority: 'event'}});"
                ),
            )

        return ui.div(
            ui.span("Sort", class_="account-campaigns-sort-label"),
            chip("created", "Created date"),
            chip("spend", "Spend"),
            class_="account-campaigns-sort",
        )

    @render.ui
    def campaigns_dropdown():
        is_open = expanded.get()
        data = payload.get() or {}
        count = int(data.get("campaign_count") or 0)
        if fetching.get() and is_open:
            count_label = "Loading campaigns for this account..."
        elif enriching.get() and is_open:
            count_label = f"{count} campaign{'s' if count != 1 else ''} · loading creatives…"
        elif data and is_open:
            count_label = f"{count} campaign{'s' if count != 1 else ''} on this account"
        else:
            count_label = "View ads run on this account"

        wrapper_class = "account-campaigns" + (" is-open" if is_open else "")
        toggle = _toggle_button(is_open=is_open, count_label=count_label)

        if not is_open:
            return ui.div(toggle, class_=wrapper_class)

        if fetching.get() or payload.get() is None:
            return ui.div(
                toggle,
                ui.div(
                    ui.div(class_="spinner"),
                    ui.div("Loading campaigns for this account...", class_="loading-text"),
                    class_="account-campaigns-body loading-spinner",
                ),
                class_=wrapper_class,
            )

        err = error_message.get()
        if err and not data.get("campaigns"):
            return ui.div(
                toggle,
                ui.div(
                    f"Could not load campaigns: {err}",
                    class_="account-campaigns-body account-campaigns-empty",
                ),
                class_=wrapper_class,
            )

        period = get_period()
        active_sort = sort_mode.get()
        sort_note = (
            "newest created first"
            if active_sort == "created"
            else "highest spend first"
        )
        campaigns = attach_account_fields(
            data.get("campaigns") or [],
            account_id=acc_id,
            account_name=acc_name,
            currency=data.get("currency") or currency,
            period_since=period.since,
            period_until=period.until,
            period_label=period.label,
        )
        note_bits = [
            f"{len(campaigns)} campaign{'s' if len(campaigns) != 1 else ''}",
            sort_note,
            period.label,
        ]
        if enriching.get():
            note_bits.append("loading creatives & goals…")
        return ui.div(
            toggle,
            ui.div(
                ui.div(
                    ui.div(" · ".join(note_bits), class_="account-campaigns-note"),
                    _sort_bar(active_sort),
                    class_="account-campaigns-toolbar",
                ),
                build_campaigns_table(
                    campaigns,
                    insights_label=period.label,
                    sort=active_sort,
                    empty_message="No campaigns found for this account in the selected date range.",
                ),
                class_="account-campaigns-body",
            ),
            class_=wrapper_class,
        )
