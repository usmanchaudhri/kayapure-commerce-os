"""AI Reports tab — Shiny reactive handlers."""
import os
import time

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.account_campaigns import (
    account_campaigns_module_id,
    account_campaigns_server,
    account_campaigns_ui,
)
from shiny_app.lib.date_ranges import parse_account_created, resolve_date_range
from shiny_app.lib.formatting import fmt_currency
from shiny_app.lib.report_cache import SessionReportCache
from shiny_app.lib.report_pdf import generate_report_pdf

_CURRENT_REPORT = "current"


def _current_date_range(input: Inputs):
    range_val = "30"
    custom_since = None
    custom_until = None
    try:
        range_val = input.ai_reports_date_range() or "30"
    except Exception:
        range_val = "30"
    if range_val == "custom":
        try:
            custom_since = input.ai_reports_date_since()
            custom_until = input.ai_reports_date_until()
        except Exception:
            pass
    return resolve_date_range(range_val, custom_since=custom_since, custom_until=custom_until)


def _sort_ai_report_accounts(accounts: list) -> list:
    """Highest spend first; newest accounts next when spend ties."""
    return sorted(
        accounts,
        key=lambda a: (
            -float(a.get("spend") or 0),
            -parse_account_created(a.get("created_time")),
            -float(a.get("lifetime_spend") or 0),
        ),
    )


def build_report_modal_content(analysis: dict, acc_name: str, acc_id: str = "",
                                 from_cache: bool = False, cache_age_min: int = 0,
                                 report_type: str = "generate",
                                 *,
                                 campaign_id: str = "",
                                 campaign_name: str = "") -> ui.Tag:
    """Build a nicely formatted modal body from the AdsAnalysisResult dict."""
    a = analysis.get("analysis", {})
    summary = a.get("summary", "No summary available.")
    root_cause = a.get("root_cause") or ""
    findings = a.get("key_findings", [])
    layer_findings = a.get("layer_findings") or []
    risks = a.get("risks", [])
    recs = a.get("recommendations", [])
    confidence = a.get("confidence", 0)
    report_scope = analysis.get("report_scope") or ("campaign" if campaign_id else "account")

    # Data snapshot info
    snap = analysis.get("data_snapshot", {})
    period = snap.get("period", {})
    currency = snap.get("currency", "USD")
    total_spend = snap.get("total_spend", 0)

    sections = []

    # Toolbar: cache label + PDF download + regenerate
    toolbar_items = []
    if from_cache:
        age_text = "Cached for this session"
        check_svg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
        toolbar_items.append(
            ui.span(ui.HTML(check_svg), f" {age_text}", class_="ai-report-cache-label")
        )
    else:
        toolbar_items.append(ui.span("Fresh report", class_="ai-report-cache-label", style="color: #3b82f6;"))

    safe_id = acc_id.replace("'", "\\'")
    safe_name = acc_name.replace("'", "\\'")
    safe_camp_id = (campaign_id or "").replace("'", "\\'")
    safe_camp_name = (campaign_name or "").replace("'", "\\'")
    pdf_svg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 18 15 15"/></svg>'
    if campaign_id:
        pdf_payload = f"{safe_id}|{safe_name}|campaign|{safe_camp_id}|{safe_camp_name}"
        regen_event = "campaign_ai_report_regen"
        pdf_event = "campaign_ai_report_pdf"
    else:
        pdf_payload = f"{safe_id}|{safe_name}"
        regen_event = "regenerate_report_click"
        pdf_event = "download_pdf_click"
    toolbar_items.append(
        ui.tags.button(
            ui.HTML(pdf_svg), " Download PDF",
            type="button",
            class_="btn-download-pdf",
            onclick=f"Shiny.setInputValue('{pdf_event}', '{pdf_payload}', {{priority: 'event'}});",
        )
    )

    refresh_svg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>'
    toolbar_items.append(
        ui.tags.button(
            ui.HTML(refresh_svg), " Regenerate",
            class_="btn-regenerate",
            onclick=f"Shiny.setInputValue('{regen_event}', '{pdf_payload}', {{priority: 'event'}});",
        )
    )

    sections.append(ui.div(*toolbar_items, class_="ai-report-toolbar"))

    # Period + spend header
    period_text = ""
    if period:
        period_text = f"{period.get('start', '?')} \u2192 {period.get('end', '?')}"
    scope_label = (
        f"Campaign deep dive · {campaign_name}" if report_scope == "campaign" and campaign_name
        else ("Campaign deep dive" if report_scope == "campaign" else "Ad Account Analysis")
    )
    sections.append(
        ui.div(
            ui.div(
                ui.span(scope_label, style="color: #64748b; font-size: 14px; display: block; margin-bottom: 4px;"),
                ui.span(f"Period: {period_text}" if period_text else "",
                        style="color: #64748b; font-size: 14px;"),
                ui.span(f"  \u00b7  Total Spend: {fmt_currency(total_spend, currency)}" if total_spend else "",
                        style="color: #64748b; font-size: 14px;"),
                style="margin-bottom: 16px;",
            ),
        )
    )

    # Summary
    sections.append(
        ui.div(
            ui.div("\U0001f4cb Summary", class_="ai-report-section-title"),
            ui.div(summary, class_="ai-report-summary"),
        )
    )

    if root_cause:
        sections.append(
            ui.div(
                ui.div("\U0001f3af Root Cause", class_="ai-report-section-title"),
                ui.div(root_cause, class_="ai-report-summary"),
                style="margin-bottom: 20px;",
            )
        )

    # Key Findings
    if findings:
        finding_items = [ui.div(f, class_="ai-report-finding") for f in findings]
        sections.append(
            ui.div(
                ui.div("\U0001f50d Key Findings", class_="ai-report-section-title"),
                *finding_items,
                style="margin-bottom: 20px;",
            )
        )

    # Layer findings (campaign deep dive)
    if layer_findings:
        layer_cards = []
        for item in layer_findings:
            if not isinstance(item, dict):
                continue
            layer = (item.get("layer") or "campaign").upper()
            name = item.get("name") or "—"
            diagnosis = item.get("diagnosis") or ""
            evidence = item.get("evidence") or ""
            obj_id = item.get("object_id") or ""
            layer_cards.append(
                ui.div(
                    ui.div(
                        ui.span(layer, class_="ai-report-rec-badge priority-medium"),
                        ui.span(f"  {name}", style="font-weight: 700;"),
                        ui.span(f"  ·  {obj_id}" if obj_id else "", style="color: #64748b; font-size: 12px; font-family: monospace;"),
                        style="margin-bottom: 6px;",
                    ),
                    ui.div(diagnosis, class_="ai-report-rec-rationale") if diagnosis else ui.span(),
                    ui.div(evidence, style="color: #64748b; font-size: 13px; margin-top: 4px;") if evidence else ui.span(),
                    class_="ai-report-rec-card",
                )
            )
        if layer_cards:
            sections.append(
                ui.div(
                    ui.div("\U0001f9ea Layer Diagnostics", class_="ai-report-section-title"),
                    *layer_cards,
                    style="margin-bottom: 20px;",
                )
            )

    # Risks
    if risks:
        risk_items = [ui.div(r, class_="ai-report-risk") for r in risks]
        sections.append(
            ui.div(
                ui.div("\u26a0\ufe0f Risks", class_="ai-report-section-title"),
                *risk_items,
                style="margin-bottom: 20px;",
            )
        )

    # Recommendations
    if recs:
        rec_cards = []
        for i, rec in enumerate(recs, 1):
            action = rec.get("action", "—")
            rationale = rec.get("rationale", "")
            impact = rec.get("expected_impact", "")
            priority = rec.get("priority", "medium").lower()
            target_layer = rec.get("target_layer") or ""
            target_name = rec.get("target_name") or ""

            priority_class = f"ai-report-rec-badge priority-{priority}" if priority in ("high", "medium", "low") else "ai-report-rec-badge priority-medium"
            target_bits = []
            if target_layer:
                target_bits.append(target_layer)
            if target_name:
                target_bits.append(target_name)
            target_label = " · ".join(target_bits)

            rec_cards.append(
                ui.div(
                    ui.div(f"{i}. {action}", class_="ai-report-rec-action"),
                    ui.div(rationale, class_="ai-report-rec-rationale") if rationale else ui.span(),
                    ui.div(
                        ui.span(priority.upper(), class_=priority_class),
                        ui.span(target_label, class_="ai-report-rec-badge impact") if target_label else ui.span(),
                        ui.span(impact, class_="ai-report-rec-badge impact") if impact else ui.span(),
                        class_="ai-report-rec-meta",
                    ),
                    class_="ai-report-rec-card",
                )
            )
        sections.append(
            ui.div(
                ui.div("\U0001f4a1 Recommendations", class_="ai-report-section-title"),
                *rec_cards,
                style="margin-bottom: 20px;",
            )
        )

    # Confidence bar
    conf_pct = int(confidence * 100)
    conf_color = "#22c55e" if conf_pct >= 70 else ("#f59e0b" if conf_pct >= 40 else "#f87171")
    sections.append(
        ui.div(
            ui.span("AI Confidence", class_="ai-report-confidence-label"),
            ui.div(
                ui.div(style=f"width: {conf_pct}%; background: {conf_color};", class_="ai-report-confidence-fill"),
                class_="ai-report-confidence-bar",
            ),
            ui.span(f"{conf_pct}%", style=f"color: {conf_color}; font-weight: 700; font-size: 15px;"),
            class_="ai-report-confidence",
        )
    )

    return ui.div(*sections)


def _close_modals():
    """Close Shiny/Bootstrap modals and leftover backdrops that freeze the page."""
    try:
        ui.modal_remove()
    except Exception:
        pass
    ui.insert_ui(
        ui.tags.script(
            """
            (function() {
              document.querySelectorAll('.modal.show, .modal').forEach(function(el) {
                try {
                  if (window.bootstrap && bootstrap.Modal) {
                    var instance = bootstrap.Modal.getInstance(el);
                    if (instance) instance.hide();
                  }
                } catch (e) {}
              });
              document.querySelectorAll('.modal-backdrop').forEach(function(el) { el.remove(); });
              document.body.classList.remove('modal-open');
              document.body.style.removeProperty('overflow');
              document.body.style.removeProperty('padding-right');
            })();
            """
        ),
        selector="body",
        where="beforeEnd",
        immediate=True,
    )


def _report_error_modal(acc_name: str, error: Exception):
    return ui.modal(
        ui.div(f"Failed to generate report: {str(error)}", class_="ai-report-error"),
        ui.div(
            "Please ensure the backend server has been restarted and the OpenAI API key is configured.",
            style="color: #475569; font-size: 14px; text-align: center; margin-top: 12px;",
        ),
        title=f"Report Error \u2014 {acc_name}",
        size="l",
        easy_close=True,
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    session_cache = SessionReportCache()
    last_date_key = reactive.Value("")

    @render.ui
    def ai_reports_custom_dates():
        try:
            range_val = input.ai_reports_date_range()
        except Exception:
            range_val = "30"
        if range_val != "custom":
            return ui.div()
        from shiny_app.ui.date_range_filter import custom_date_fields

        return custom_date_fields(
            since_id="ai_reports_date_since",
            until_id="ai_reports_date_until",
        )

    @render.ui
    def ai_reports_table_header():
        period = _current_date_range(input)
        return ui.div(
            ui.div("Account", class_="ai-report-col-header", style="flex: 2;"),
            ui.div(f"Spend ({period.label})", class_="ai-report-col-header", style="flex: 1; text-align: right;"),
            ui.div("Actions", class_="ai-report-col-header", style="flex: 1.5; text-align: right;"),
            class_="ai-report-table-header",
        )

    @reactive.calc
    async def ai_reports_accounts_data():
        """Fetch all ad accounts with spend for the selected date range."""
        input.refresh()
        input.ai_reports_date_range()
        try:
            input.ai_reports_date_since()
            input.ai_reports_date_until()
        except Exception:
            pass

        from services.marketing import marketing_service
        if not marketing_service._fb_client:
            return None

        period = _current_date_range(input)
        data = await marketing_service._fb_client.get_total_spend_all_accounts(
            since=period.since,
            until=period.until,
        )
        if isinstance(data, dict):
            data = {
                **data,
                "_period_label": period.label,
                "_period_days": period.days,
            }
        return data

    bound_campaign_modules: set[str] = set()

    def _ensure_campaign_module(acc: dict) -> str:
        """Bind a lazy campaign dropdown server for this account (once per session)."""
        acc_id = acc.get("account_id") or ""
        module_id = account_campaigns_module_id(acc_id)
        if module_id not in bound_campaign_modules:
            bound_campaign_modules.add(module_id)
            account_campaigns_server(
                module_id,
                acc_id=acc_id,
                acc_name=acc.get("account_name") or "Unknown",
                currency=acc.get("currency") or "USD",
                get_period=lambda: _current_date_range(input),
            )
        return module_id

    @render.ui
    async def ai_reports_accounts_list():
        """Render the list of ad account cards for the AI Reports tab."""
        data = await ai_reports_accounts_data()

        if data is None:
            return ui.div(
                ui.div(class_="spinner"),
                ui.div("Loading ad accounts...", class_="loading-text"),
                class_="loading-spinner",
            )

        accounts = _sort_ai_report_accounts(list(data.get("accounts", [])))
        period_label = data.get("_period_label", "Selected period")

        if not accounts:
            return ui.div(
                "No ad accounts found. Ensure your Facebook access token is configured.",
                style="color: #64748b; text-align: center; padding: 60px;",
            )

        cards = []
        for acc in accounts:
            acc_id = acc.get("account_id", "")
            acc_name = acc.get("account_name", "Unknown")
            acc_currency = acc.get("currency", "USD")
            acc_status = acc.get("status", "UNKNOWN")
            acc_spend = acc.get("spend", 0)
            is_active = acc_status == "ACTIVE"

            # Status dot
            dot_class = "ai-report-status-dot active" if is_active else "ai-report-status-dot inactive"

            # Spend display
            spend_display = fmt_currency(acc_spend, acc_currency)

            # SVG icons
            envelope_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 4L12 13 2 4"/></svg>'
            clock_svg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
            target_svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'
            target_small_svg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'

            # Safe account ID for JS
            safe_id = acc_id.replace("'", "\\'")
            safe_name = acc_name.replace("'", "\\'")

            card = ui.div(
                # Main row: dot + info + spend + actions
                ui.div(
                    ui.div(class_=dot_class),
                    ui.div(
                        ui.div(acc_name, class_="ai-report-account-name"),
                        ui.div(f"{acc_id}  ·  {acc_currency}", class_="ai-report-account-meta"),
                        class_="ai-report-account-info",
                    ),
                    ui.div(spend_display, class_="ai-report-spend"),
                    ui.div(
                        ui.tags.button(
                            ui.HTML(envelope_svg), " Generate Report",
                            class_="btn-generate-report",
                            onclick=f"Shiny.setInputValue('generate_report_click', '{safe_id}|{safe_name}|{acc_currency}', {{priority: 'event'}});",
                        ),
                        ui.tags.button(
                            ui.HTML(clock_svg), " View Report",
                            class_="btn-view-reports",
                            onclick=f"Shiny.setInputValue('view_reports_click', '{safe_id}|{safe_name}', {{priority: 'event'}});",
                        ),
                        class_="ai-report-actions",
                    ),
                    class_="ai-report-account-row",
                ),
                account_campaigns_ui(_ensure_campaign_module(acc)),
                # Goals section
                ui.div(
                    ui.div(
                        ui.div(
                            ui.HTML(target_svg),
                            ui.span("Set goals for this account"),
                            class_="ai-report-goals-title",
                        ),
                        ui.div(
                            "Define business targets so AI reports evaluate actual performance against your goals.",
                            class_="ai-report-goals-desc",
                        ),
                        ui.tags.button(
                            ui.HTML(target_small_svg), " Add Goals",
                            class_="btn-add-goals",
                            onclick=f"Shiny.setInputValue('add_goals_click', '{safe_id}|{safe_name}', {{priority: 'event'}});",
                        ),
                        class_="ai-report-goals-inner",
                    ),
                    class_="ai-report-goals-section",
                ),
                class_="ai-report-account-card",
            )
            cards.append(card)

        return ui.div(
            ui.div(
                f"Sorted by spend ({period_label}), highest first",
                class_="ai-reports-sort-note",
            ),
            *cards,
        )

    def _report_days() -> int:
        return _current_date_range(input).days

    def _date_key() -> str:
        period = _current_date_range(input)
        return f"{period.since}|{period.until}|{period.days}"

    def _open_report_modal(result: dict, acc_id: str, acc_name: str, *, from_cache: bool) -> None:
        age_min = 0
        if from_cache:
            cached = session_cache.get(acc_id, _CURRENT_REPORT, _report_days()) or {}
            age_min = max(0, int((time.time() - cached.get("timestamp", time.time())) / 60))
        ui.modal_show(ui.modal(
            build_report_modal_content(
                result, acc_name, acc_id=acc_id,
                from_cache=from_cache, cache_age_min=age_min, report_type=_CURRENT_REPORT,
            ),
            title=f"AI Report \u2014 {acc_name}",
            size="l",
            easy_close=True,
        ))

    def _show_cached_or_none(acc_id: str, acc_name: str) -> bool:
        cached = session_cache.get(acc_id, _CURRENT_REPORT, _report_days())
        if not cached:
            return False
        _open_report_modal(cached.get("result") or {}, acc_id, acc_name, from_cache=True)
        return True

    def _analysis_question(acc_name: str, acc_id: str) -> str:
        return (
            f"Analyse the ad performance for account {acc_name} ({acc_id}). "
            f"Find waste, winners, and optimization opportunities. "
            f"Provide specific, actionable recommendations."
        )

    async def _generate_and_show(
        acc_id: str,
        acc_name: str,
        *,
        force: bool,
        loading_title: str,
        loading_msg: str,
    ) -> None:
        if not force and _show_cached_or_none(acc_id, acc_name):
            return

        ui.modal_show(ui.modal(
            ui.div(
                ui.div(class_="spinner"),
                ui.div(loading_msg, style="margin-top: 16px; font-size: 16px; color: #94a3b8;"),
                ui.div("This may take 15\u201330 seconds.", style="margin-top: 6px; font-size: 14px; color: #475569;"),
                class_="ai-report-modal-loading",
            ),
            title=loading_title,
            size="l",
            easy_close=True,
        ))

        try:
            from services.ads_analysis_agent import ads_analysis_agent_service
            result = await ads_analysis_agent_service.analyze(
                days=_report_days(),
                question=_analysis_question(acc_name, acc_id),
                account_id=acc_id,
                account_name=acc_name,
            )
            session_cache.put(acc_id, _CURRENT_REPORT, _report_days(), result)
            _close_modals()
            _open_report_modal(result, acc_id, acc_name, from_cache=False)
        except Exception as e:
            _close_modals()
            ui.modal_show(_report_error_modal(acc_name, e))

    @reactive.effect
    def _clear_cache_when_date_changes():
        key = _date_key()
        previous = last_date_key.get()
        if previous == key:
            return
        if previous:
            session_cache.clear()
        last_date_key.set(key)

    @reactive.effect
    @reactive.event(input.generate_report_click)
    async def _handle_generate_report():
        val = input.generate_report_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        await _generate_and_show(
            acc_id,
            acc_name,
            force=False,
            loading_title=f"Generating Report \u2014 {acc_name}",
            loading_msg="Analysing your ad account data with AI...",
        )

    @reactive.effect
    @reactive.event(input.view_reports_click)
    async def _handle_view_reports():
        val = input.view_reports_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        await _generate_and_show(
            acc_id,
            acc_name,
            force=False,
            loading_title=f"Loading Report \u2014 {acc_name}",
            loading_msg="Fetching AI analysis for your ad account...",
        )

    # ---- AI Reports: Add Goals handler ----
    @reactive.effect
    @reactive.event(input.add_goals_click)
    async def _handle_add_goals():
        val = input.add_goals_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"

        modal = ui.modal(
            ui.div(
                ui.input_text("goal_monthly_spend", "Monthly Spend Target", placeholder="e.g., 50000", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("goal_target_cpc", "Target CPC", placeholder="e.g., 1.50", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("goal_target_ctr", "Target CTR (%)", placeholder="e.g., 3.5", width="100%"),
                style="margin-bottom: 16px;",
            ),
            ui.div(
                ui.input_text("goal_target_roas", "Target ROAS", placeholder="e.g., 4.0", width="100%"),
                style="margin-bottom: 20px;",
            ),
            ui.div(
                ui.tags.button(
                    "Save Goals",
                    class_="action-btn action-btn-primary",
                    style="width: 100%; padding: 12px;",
                    onclick=f"Shiny.setInputValue('save_goals_submit', '{acc_id}', {{priority: 'event'}}); bootstrap.Modal.getInstance(document.querySelector('.modal')).hide();",
                ),
            ),
            title=f"Set Goals — {acc_name}",
            size="m",
            easy_close=True,
        )
        ui.modal_show(modal)

    @reactive.effect
    @reactive.event(input.save_goals_submit)
    async def _handle_save_goals():
        ui.notification_show(
            "Goals saved! AI reports will evaluate performance against these targets. "
            "Goal persistence is coming soon.",
            type="message",
            duration=6,
        )

    @reactive.effect
    @reactive.event(input.download_pdf_click)
    async def _handle_download_pdf():
        val = input.download_pdf_click()
        if not val:
            return
        parts = str(val).split("|", 1)
        acc_id = parts[0] if parts else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        cached = session_cache.get(acc_id, _CURRENT_REPORT, _report_days())
        if not cached:
            ui.notification_show(
                "No report to download. Generate a report first.",
                type="error",
                duration=5,
            )
            return
        try:
            filepath = generate_report_pdf(cached.get("result") or {}, acc_name, acc_id)
            filename = os.path.basename(filepath)
            await session.send_custom_message(
                "download_pdf",
                {"url": f"/api/marketing/report-pdfs/{filename}", "filename": filename},
            )
        except Exception as exc:
            ui.notification_show(f"PDF generation failed: {exc}", type="error", duration=8)

    @reactive.effect
    @reactive.event(input.regenerate_report_click)
    async def _handle_regenerate_report():
        val = input.regenerate_report_click()
        if not val:
            return
        parts = val.split("|")
        acc_id = parts[0] if len(parts) > 0 else ""
        acc_name = parts[1] if len(parts) > 1 else "Unknown"
        await _generate_and_show(
            acc_id,
            acc_name,
            force=True,
            loading_title=f"Regenerating Report \u2014 {acc_name}",
            loading_msg="Regenerating report with fresh data...",
        )


