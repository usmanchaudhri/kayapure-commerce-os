"""Profit Leak Scanner tab — Shiny reactive handlers."""

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.lib.date_ranges import resolve_date_range
from shiny_app.lib.formatting import fmt_currency
from shiny_app.ui.date_range_filter import custom_date_fields

_CATEGORY_LABELS = {
    "spend_concentration": "Weak CPA / spend concentration",
    "ad_spend_concentration": "Ad-level spend concentration",
    "post_click_leak": "High-click, low-purchase",
    "funnel_lpv_to_atc": "Landing view → cart leak",
    "funnel_atc_to_checkout": "Cart → checkout leak",
    "creative_fatigue": "Creative fatigue",
    "discount_margin_leak": "Discount / margin leak",
    "new_customer_distortion": "New-customer quality",
    "measurement_gap": "Meta ↔ store measurement",
    # Legacy categories from earlier scans
    "zero_conversion_spend": "Zero-conversion spend",
    "low_roas_spend": "Low ROAS spend",
}

_SEVERITY_COLORS = {
    "critical": "#f87171",
    "high": "#fb923c",
    "medium": "#fbbf24",
    "low": "#94a3b8",
}


def _current_date_range(input: Inputs):
    range_val = "30"
    custom_since = None
    custom_until = None
    try:
        range_val = input.profit_leak_date_range() or "30"
    except Exception:
        range_val = "30"
    if range_val == "custom":
        try:
            custom_since = input.profit_leak_date_since()
            custom_until = input.profit_leak_date_until()
        except Exception:
            pass
    return resolve_date_range(range_val, custom_since=custom_since, custom_until=custom_until)


def _confidence_label(value: float) -> str:
    if value >= 0.8:
        return "High"
    if value >= 0.65:
        return "Medium"
    return "Low"


def _format_evidence_bullet(ev: dict) -> str:
    label = (ev.get("metric_name") or "").replace("_", " ").title()
    observed = ev.get("observed_value", "—")
    comparison = ev.get("comparison_value")
    comp_label = ev.get("comparison_label", "")
    if comparison not in (None, ""):
        suffix = f" vs {comparison}"
        if comp_label:
            suffix += f" ({comp_label})"
        return f"{label}: {observed}{suffix}"
    return f"{label}: {observed}"


def _store_economics_from_result(result: dict) -> dict | None:
    for account in result.get("accounts") or []:
        store_economics = (account.get("summary") or {}).get("store_economics")
        if store_economics:
            return store_economics
    return None


def _build_diagnosis_modal(result: dict) -> ui.Tag:
    findings = list(result.get("findings") or [])
    summary = result.get("summary") or {}
    currency = summary.get("currency", "USD")
    period_label = summary.get("period_label", "")
    finding_count = summary.get("finding_count", len(findings))
    opp_min = summary.get("total_opportunity_min", 0)
    opp_max = summary.get("total_opportunity_max", 0)
    explain_meta = result.get("explain_meta") or {}
    model_name = explain_meta.get("model_name") or "the advisor model"
    store_economics = _store_economics_from_result(result)

    context_rows = [
        ui.div(
            ui.span("Period", class_="pls-diagnosis-context-label"),
            ui.span(period_label or "—", class_="pls-diagnosis-context-value"),
            class_="pls-diagnosis-context-row",
        ),
        ui.div(
            ui.span("Estimated opportunity", class_="pls-diagnosis-context-label"),
            ui.span(
                f"{fmt_currency(opp_min, currency)} – {fmt_currency(opp_max, currency)} / month",
                class_="pls-diagnosis-context-value",
            ),
            class_="pls-diagnosis-context-row",
        ),
        ui.div(
            ui.span("Findings analyzed", class_="pls-diagnosis-context-label"),
            ui.span(str(finding_count), class_="pls-diagnosis-context-value"),
            class_="pls-diagnosis-context-row",
        ),
    ]
    if store_economics:
        context_rows.append(
            ui.div(
                ui.span("Store contribution / order", class_="pls-diagnosis-context-label"),
                ui.span(
                    fmt_currency(store_economics.get("contribution_per_order", 0), currency),
                    class_="pls-diagnosis-context-value",
                ),
                class_="pls-diagnosis-context-row",
            )
        )
        context_rows.append(
            ui.div(
                ui.span("Break-even CPA", class_="pls-diagnosis-context-label"),
                ui.span(
                    fmt_currency(store_economics.get("break_even_cpa", 0), currency),
                    class_="pls-diagnosis-context-value",
                ),
                class_="pls-diagnosis-context-row",
            )
        )

    reason_items: list[ui.Tag] = []
    if not findings:
        reason_items.append(
            ui.div(
                "No findings were available for this scan. Run a scan with sufficient campaign spend "
                "and LLM explanations enabled.",
                class_="pls-diagnosis-empty",
            )
        )
    for rank, finding in enumerate(findings, start=1):
        category = _CATEGORY_LABELS.get(finding.get("category", ""), finding.get("category", "Finding"))
        severity = (finding.get("severity") or "medium").upper()
        account_name = finding.get("account_name", "")
        diagnosis = finding.get("diagnosis") or ""
        evidence = finding.get("evidence") or []
        evidence_bullets = [_format_evidence_bullet(ev) for ev in evidence[:6]]
        observed_facts = finding.get("llm_observed_facts") or []

        meta_bits = [category, severity]
        if account_name:
            meta_bits.insert(0, account_name)

        reason_items.append(
            ui.div(
                ui.div(
                    ui.span(str(rank), class_="pls-diagnosis-rank"),
                    ui.div(
                        ui.div(finding.get("title", "Finding"), class_="pls-diagnosis-reason-title"),
                        ui.div(" · ".join(meta_bits), class_="pls-diagnosis-reason-meta"),
                        class_="pls-diagnosis-reason-head",
                    ),
                    class_="pls-diagnosis-reason-top",
                ),
                ui.div(diagnosis, class_="pls-diagnosis-reason-text"),
                ui.div(
                    ui.div("Evidence", class_="pls-diagnosis-evidence-label"),
                    ui.tags.ul(
                        *[ui.tags.li(line) for line in evidence_bullets],
                        class_="pls-diagnosis-evidence-list",
                    ),
                    class_="pls-diagnosis-evidence-block",
                ) if evidence_bullets else ui.div(),
                ui.div(
                    ui.div("Advisor observed facts", class_="pls-diagnosis-evidence-label"),
                    ui.tags.ul(
                        *[ui.tags.li(fact) for fact in observed_facts[:4]],
                        class_="pls-diagnosis-evidence-list",
                    ),
                    class_="pls-diagnosis-evidence-block",
                ) if observed_facts else ui.div(),
                class_="pls-diagnosis-reason-item",
            )
        )

    return ui.modal(
        ui.div(
            ui.div(
                "The account diagnosis is synthesized from deterministic leak detectors "
                "(thresholds, account baselines, and store economics) and then summarized "
                f"in plain language by {model_name}. Each item below is a ranked finding "
                "with the metrics that triggered it.",
                class_="pls-diagnosis-modal-intro",
            ),
            ui.div(*context_rows, class_="pls-diagnosis-modal-context"),
            ui.div("Reasons behind this conclusion", class_="pls-diagnosis-modal-section-title"),
            ui.div(*reason_items, class_="pls-diagnosis-modal-list"),
        ),
        title="How we reached this diagnosis",
        footer=ui.modal_button("Close"),
        size="l",
        easy_close=True,
    )


def _diagnosis_details_trigger(*, disabled: bool = False) -> ui.Tag:
    if disabled:
        return ui.span(
            "?",
            class_="pls-diagnosis-info-btn pls-diagnosis-info-btn-disabled",
            title="Run a scan to see how the diagnosis was built",
            aria_hidden="true",
        )
    return ui.tags.button(
        "?",
        type="button",
        class_="pls-diagnosis-info-btn",
        title="How we reached this conclusion",
        aria_label="How we reached this conclusion",
        onclick=(
            "Shiny.setInputValue('profit_leak_diagnosis_details', Date.now(), {priority: 'event'});"
        ),
    )


def _finding_card(finding: dict, rank: int) -> ui.Tag:
    currency = finding.get("currency", "USD")
    severity = finding.get("severity", "medium")
    severity_color = _SEVERITY_COLORS.get(severity, "#94a3b8")
    category = _CATEGORY_LABELS.get(finding.get("category", ""), finding.get("category", "Finding"))
    impact_min = finding.get("estimated_impact_min", 0)
    impact_max = finding.get("estimated_impact_max", 0)
    confidence = finding.get("confidence", 0)
    account_name = finding.get("account_name", "")
    finding_id = finding.get("id", "")
    status = finding.get("status", "open")

    evidence_rows = []
    for ev in finding.get("evidence", [])[:6]:
        label = ev.get("metric_name", "").replace("_", " ").title()
        observed = ev.get("observed_value", "—")
        comparison = ev.get("comparison_value")
        comp_label = ev.get("comparison_label", "")
        if comparison not in (None, ""):
            value_text = f"{observed} vs {comparison} ({comp_label})" if comp_label else f"{observed} vs {comparison}"
        else:
            value_text = str(observed)
        evidence_rows.append(
            ui.div(
                ui.span(label, class_="pls-evidence-label"),
                ui.span(value_text, class_="pls-evidence-value"),
                class_="pls-evidence-row",
            )
        )

    llm_block = []
    llm_explanation = finding.get("llm_explanation") or ""
    if llm_explanation:
        llm_block.append(ui.div("Advisor explanation", class_="pls-llm-label"))
        llm_block.append(ui.div(llm_explanation, class_="pls-llm-text"))

    facts = finding.get("llm_observed_facts") or []
    if facts:
        llm_block.append(
            ui.div(
                ui.div("Observed facts", class_="pls-llm-sublabel"),
                ui.tags.ul(*[ui.tags.li(f) for f in facts[:5]], class_="pls-llm-list"),
            )
        )

    hypotheses = finding.get("llm_hypotheses") or []
    if hypotheses:
        hyp_items = []
        for hyp in hypotheses[:3]:
            text = hyp.get("text", "") if isinstance(hyp, dict) else str(hyp)
            conf = hyp.get("confidence") if isinstance(hyp, dict) else None
            label = f"{text} ({_confidence_label(conf)} confidence)" if conf is not None else text
            hyp_items.append(ui.tags.li(label))
        llm_block.append(
            ui.div(
                ui.div("Likely causes", class_="pls-llm-sublabel"),
                ui.tags.ul(*hyp_items, class_="pls-llm-list"),
            )
        )

    llm_action = finding.get("llm_recommended_action") or ""
    if llm_action:
        llm_block.append(
            ui.div(
                ui.span("Next step", class_="pls-llm-sublabel"),
                ui.span(llm_action, class_="pls-llm-action"),
                class_="pls-llm-action-row",
            )
        )

    llm_caveats = finding.get("llm_caveats") or finding.get("caveats") or []
    if llm_caveats:
        llm_block.append(
            ui.div(
                ui.div("Caveats", class_="pls-llm-sublabel"),
                ui.tags.ul(*[ui.tags.li(c) for c in llm_caveats[:3]], class_="pls-llm-list pls-llm-caveats"),
            )
        )

    experiment = finding.get("experiment") or {}
    experiment_block = []
    if experiment.get("hypothesis"):
        experiment_block.append(
            ui.div(
                ui.span("Suggested test", class_="pls-evidence-label"),
                ui.span(experiment.get("hypothesis", ""), class_="pls-evidence-value"),
                class_="pls-evidence-row",
            )
        )

    creative_brief = experiment.get("creative_brief")
    if isinstance(creative_brief, dict) and creative_brief:
        brief_parts = []
        hooks = creative_brief.get("hooks") or []
        if hooks:
            brief_parts.append(
                ui.div(
                    ui.span("Creative hooks", class_="pls-evidence-label"),
                    ui.tags.ul(*[ui.tags.li(h) for h in hooks[:3]], class_="pls-llm-list"),
                )
            )
        openings = creative_brief.get("visual_openings") or []
        if openings:
            brief_parts.append(
                ui.div(
                    ui.span("Visual openings", class_="pls-evidence-label"),
                    ui.tags.ul(*[ui.tags.li(o) for o in openings[:3]], class_="pls-llm-list"),
                )
            )
        offer_variation = creative_brief.get("offer_variation")
        if offer_variation:
            brief_parts.append(
                ui.div(
                    ui.span("Offer variation", class_="pls-evidence-label"),
                    ui.span(offer_variation, class_="pls-evidence-value"),
                    class_="pls-evidence-row",
                )
            )
        if brief_parts:
            experiment_block.append(ui.div(ui.div("Creative brief", class_="pls-llm-sublabel"), *brief_parts))

    meta_line = []
    if account_name:
        meta_line.append(ui.span(account_name, class_="pls-finding-account"))
    meta_line.append(ui.span(category, class_="pls-finding-category"))
    meta_line.append(ui.span(f"Confidence: {_confidence_label(confidence)}", class_="pls-finding-confidence"))
    meta_line.append(ui.span(f"Status: {status}", class_="pls-finding-status"))

    status_buttons = []
    if finding_id:
        for action, label, css_class in (
            ("accepted", "Accept", "btn-activate"),
            ("dismissed", "Dismiss", "btn-delete"),
            ("inconclusive", "Inconclusive", "btn-view"),
            ("completed", "Done", "btn-view"),
        ):
            status_buttons.append(
                ui.tags.button(
                    label,
                    type="button",
                    class_=css_class,
                    onclick=(
                        f"Shiny.setInputValue('profit_leak_finding_status', "
                        f"'{finding_id}|{action}', {{priority: 'event'}});"
                    ),
                )
            )

    return ui.div(
        ui.div(
            ui.span(str(rank), class_="pls-rank"),
            ui.div(
                ui.div(finding.get("title", "Finding"), class_="pls-finding-title"),
                ui.div(*meta_line, class_="pls-finding-meta"),
                class_="pls-finding-head",
            ),
            ui.div(
                ui.div("Est. monthly opportunity", class_="pls-impact-label"),
                ui.div(
                    f"{fmt_currency(impact_min, currency)} – {fmt_currency(impact_max, currency)}",
                    class_="pls-impact-value",
                ),
                class_="pls-impact",
            ),
            class_="pls-finding-top",
        ),
        ui.div(finding.get("diagnosis", ""), class_="pls-diagnosis"),
        ui.div(*llm_block, class_="pls-llm-block") if llm_block else ui.div(),
        ui.div(finding.get("recommendation", ""), class_="pls-recommendation"),
        ui.div(*evidence_rows, *experiment_block, class_="pls-evidence"),
        ui.div(
            *status_buttons,
            ui.span(severity.upper(), style=f"color: {severity_color}; font-weight: 700; font-size: 12px; margin-left: auto;"),
            class_="pls-finding-footer",
        ),
        class_="pls-finding-card",
        **{"data-severity": severity},
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    scan_result = reactive.Value(None)
    scan_loading = reactive.Value(False)
    scan_error = reactive.Value("")

    @render.ui
    def profit_leak_custom_dates():
        try:
            range_val = input.profit_leak_date_range()
        except Exception:
            range_val = "30"
        if range_val != "custom":
            return ui.div()
        return custom_date_fields(
            since_id="profit_leak_date_since",
            until_id="profit_leak_date_until",
        )

    @reactive.calc
    async def profit_leak_accounts():
        input.refresh()
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return []
        return await fb.get_all_ad_accounts()

    @render.ui
    async def profit_leak_account_select():
        accounts = await profit_leak_accounts()
        choices = {"__all__": "All ad accounts"}
        for acc in accounts:
            acc_id = acc.get("id", "")
            label = f"{acc.get('name', 'Unknown')} ({acc_id})"
            choices[acc_id] = label
        try:
            current = input.profit_leak_account() or "__all__"
        except Exception:
            current = "__all__"
        return ui.input_select(
            "profit_leak_account",
            None,
            choices=choices,
            selected=current if current in choices else "__all__",
            width="320px",
        )

    @render.ui
    def profit_leak_history_select():
        from models.database import SessionLocal
        from services.profit_leak_store import list_profit_leak_runs

        db = SessionLocal()
        try:
            runs = list_profit_leak_runs(db, limit=15)
        finally:
            db.close()

        if not runs:
            return ui.div()

        choices = {"": "Load a previous scan…"}
        for run in runs:
            label = (
                f"#{run.id} · {run.period_start.strftime('%Y-%m-%d')} → "
                f"{run.period_end.strftime('%Y-%m-%d')} · "
                f"{(run.summary_json or {}).get('finding_count', 0)} findings"
            )
            choices[str(run.id)] = label

        return ui.input_select(
            "profit_leak_load_run",
            None,
            choices=choices,
            selected="",
            width="360px",
        )

    async def _run_scan(*, force: bool = False) -> None:
        scan_loading.set(True)
        scan_error.set("")
        try:
            from models.database import SessionLocal
            from services.profit_leak_scanner import profit_leak_scanner_service

            period = _current_date_range(input)
            account_id = None
            try:
                selected = input.profit_leak_account() or "__all__"
                if selected and selected != "__all__":
                    account_id = selected
            except Exception:
                pass

            db = SessionLocal()
            try:
                result = await profit_leak_scanner_service.scan_all_accounts(
                    since=period.since,
                    until=period.until,
                    account_id=account_id,
                    force_refresh=force,
                    explain=True,
                    persist=True,
                    db=db,
                )
            finally:
                db.close()

            if result.get("error"):
                scan_error.set(str(result["error"]))
            scan_result.set(result)
        except Exception as exc:
            scan_error.set(str(exc))
            scan_result.set(None)
        finally:
            scan_loading.set(False)

    @reactive.effect
    @reactive.event(input.profit_leak_scan)
    async def _on_scan_click():
        await _run_scan(force=True)

    @reactive.effect
    @reactive.event(input.profit_leak_load_run)
    def _load_previous_run():
        run_id = input.profit_leak_load_run()
        if not run_id:
            return
        from models.database import SessionLocal
        from services.profit_leak_store import get_profit_leak_run, run_to_result

        db = SessionLocal()
        try:
            run = get_profit_leak_run(db, int(run_id))
            if run:
                scan_result.set(run_to_result(run))
                scan_error.set("")
        finally:
            db.close()

    @reactive.effect
    @reactive.event(input.profit_leak_finding_status)
    def _update_finding_status():
        raw = input.profit_leak_finding_status()
        if not raw or "|" not in raw:
            return
        finding_id, status = raw.split("|", 1)
        from models.database import SessionLocal
        from services.profit_leak_store import update_finding_status

        db = SessionLocal()
        try:
            update_finding_status(db, finding_id, status)
        finally:
            db.close()

        current = scan_result.get()
        if not current:
            return
        updated_findings = []
        for f in current.get("findings", []):
            merged = dict(f)
            if merged.get("id") == finding_id:
                merged["status"] = status
            updated_findings.append(merged)
        scan_result.set({**current, "findings": updated_findings})
        ui.notification_show(f"Finding marked as {status}.", type="message", duration=3)

    @reactive.effect
    @reactive.event(input.refresh)
    async def _on_refresh():
        if scan_result.get() is not None:
            await _run_scan(force=True)

    @reactive.effect
    @reactive.event(input.profit_leak_diagnosis_details)
    def _show_diagnosis_modal():
        result = scan_result.get()
        if not result:
            return
        ui.modal_show(_build_diagnosis_modal(result))

    @render.ui
    def profit_leak_summary():
        if scan_loading.get():
            return ui.div(
                ui.div(class_="spinner"),
                ui.div(
                    "Scanning accounts, persisting findings, and generating advisor explanations…",
                    class_="loading-text",
                ),
                class_="loading-spinner",
            )

        err = scan_error.get()
        if err and not scan_result.get():
            return ui.div(
                ui.div("Scan could not complete", class_="pls-summary-title"),
                ui.div(err, class_="pls-summary-sub"),
                class_="pls-summary-card pls-summary-error",
            )

        result = scan_result.get()
        if not result:
            return ui.div(
                ui.div("Estimated avoidable waste", class_="pls-summary-title"),
                ui.div(
                    "Select a date range and run a scan. Findings are saved with evidence "
                    "and plain-English advisor explanations.",
                    class_="pls-summary-sub",
                ),
                class_="pls-summary-card pls-summary-empty",
            )

        summary = result.get("summary") or {}
        currency = summary.get("currency", "USD")
        opp_min = summary.get("total_opportunity_min", 0)
        opp_max = summary.get("total_opportunity_max", 0)
        finding_count = summary.get("finding_count", 0)
        accounts_scanned = summary.get("accounts_scanned", 0)
        period_label = summary.get("period_label", "")
        run_id = result.get("analysis_run_id")
        executive = result.get("executive_summary") or ""
        explain_meta = result.get("explain_meta") or {}
        explained = explain_meta.get("explained_count", 0)

        saved_line = f"Saved as scan #{run_id}" if run_id else ""
        if result.get("from_cache"):
            saved_line = f"Loaded from database · scan #{result.get('analysis_run_id', '')}"

        return ui.div(
            ui.div(
                ui.div("Estimated monthly opportunity", class_="pls-summary-kicker"),
                ui.div(
                    f"{fmt_currency(opp_min, currency)} – {fmt_currency(opp_max, currency)}",
                    class_="pls-summary-amount",
                ),
                ui.div(
                    f"{finding_count} findings across {accounts_scanned} account(s) · {period_label}",
                    class_="pls-summary-sub",
                ),
                ui.div(saved_line, class_="pls-summary-saved") if saved_line else ui.div(),
                class_="pls-summary-main",
            ),
            ui.div(
                ui.div(
                    ui.span("Account diagnosis", class_="pls-summary-note-title"),
                    _diagnosis_details_trigger(disabled=not bool(result.get("findings"))),
                    class_="pls-summary-note-heading",
                ),
                ui.div(
                    executive
                    or "Advisor summary will appear after a scan with LLM explanations enabled.",
                    class_="pls-summary-note",
                ),
                ui.div(
                    ui.tags.button(
                        "View how we reached this conclusion",
                        type="button",
                        class_="pls-diagnosis-details-link",
                        onclick=(
                            "Shiny.setInputValue('profit_leak_diagnosis_details', Date.now(), "
                            "{priority: 'event'});"
                        ),
                    )
                    if result.get("findings")
                    else (
                        f"{explained} findings explained by advisor" if explained else ""
                    ),
                    class_="pls-summary-meta",
                ),
                class_="pls-summary-aside",
            ),
            class_="pls-summary-card",
        )

    @render.ui
    def profit_leak_board():
        if scan_loading.get():
            return ui.div()

        result = scan_result.get()
        if not result:
            return ui.div()

        findings = list(result.get("findings") or [])
        if not findings:
            return ui.div(
                ui.div("No material leaks detected", class_="pls-empty-title"),
                ui.div(
                    "No campaigns met the thresholds for this period. "
                    "Try a longer range or confirm campaigns have sufficient spend.",
                    class_="pls-empty-sub",
                ),
                class_="pls-empty-state",
            )

        cards = [_finding_card(f, idx) for idx, f in enumerate(findings, start=1)]
        return ui.div(
            ui.div("Prioritized action board", class_="pls-board-title"),
            ui.div(*cards, class_="pls-board"),
        )
