"""Ingredient Research Lab — Shiny handlers with live Workforce progress."""

from __future__ import annotations

import asyncio
from html import escape
from typing import Any, Dict, List

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.growth_feature_common import error_block, loading_block


def _split_csv(raw: str) -> List[str]:
    """Split a comma-separated string into trimmed non-empty parts.

    Args:
        raw: Raw input string.

    Returns:
        List of tokens.
    """
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _split_lines(raw: str) -> List[str]:
    """Split multiline text into non-empty lines.

    Args:
        raw: Raw textarea value.

    Returns:
        List of lines.
    """
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def _kind_class(kind: str) -> str:
    """Map event kind to a CSS modifier class.

    Args:
        kind: Event kind string.

    Returns:
        CSS class suffix.
    """
    if kind in {"task_failed", "error"}:
        return "is-error"
    if kind in {"task_completed", "run_completed", "all_tasks_completed"}:
        return "is-success"
    if kind in {"task_started", "workforce_running", "stream"}:
        return "is-active"
    if kind in {"pool_selected", "task_assigned", "task_decomposed"}:
        return "is-info"
    return "is-muted"


def _render_events(events: List[Dict[str, Any]], *, running: bool) -> ui.Tag:
    """Render the live execution timeline.

    Args:
        events: Progress event dicts.
        running: Whether a run is in progress.

    Returns:
        Shiny UI tag tree.
    """
    if not events and not running:
        return ui.div(
            ui.div(
                "No run yet. Configure inputs and click "
                "“Run research agents” to watch the Workforce live.",
                class_="gf-card-sub",
            ),
            class_="ir-live-empty",
        )

    rows = []
    for event in events[-120:]:
        kind = str(event.get("kind") or "log")
        title = escape(str(event.get("title") or kind))
        detail = escape(str(event.get("detail") or ""))
        worker = escape(str(event.get("worker") or ""))
        ts = escape(str(event.get("ts") or "")[-12:])
        meta_bits = []
        if worker:
            meta_bits.append(f"worker: {worker}")
        if ts:
            meta_bits.append(ts)
        meta = " · ".join(meta_bits)
        rows.append(
            ui.div(
                ui.div(
                    ui.span(kind.replace("_", " "), class_="ir-event-kind"),
                    ui.span(title, class_="ir-event-title"),
                    class_="ir-event-head",
                ),
                ui.div(meta, class_="ir-event-meta") if meta else ui.div(),
                ui.pre(detail, class_="ir-event-detail") if detail else ui.div(),
                class_=f"ir-event {_kind_class(kind)}",
            )
        )

    footer = (
        ui.div(
            ui.div(class_="spinner"),
            ui.span("Agents working…", class_="loading-text"),
            class_="ir-live-footer",
        )
        if running
        else ui.div()
    )
    return ui.div(*rows, footer, class_="ir-live-log", id="ir_live_log_scroll")


def _render_report(report: Any) -> ui.Tag:
    """Render a ResearchReport into result cards.

    Args:
        report: ``ResearchReport`` pydantic model.

    Returns:
        Shiny UI tag tree.
    """
    data = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
    summary = escape(str(data.get("summary") or ""))
    meta = data.get("run_metadata") or {}
    combos = data.get("combo_candidates") or []
    dossiers = data.get("ingredient_dossiers") or []
    open_q = data.get("open_questions") or []
    rejected = data.get("rejected_or_deferred") or []
    citations = data.get("citations") or []

    combo_cards = []
    for idx, combo in enumerate(combos, start=1):
        ingredients = ", ".join(combo.get("ingredients") or [])
        flags = combo.get("safety_flags") or []
        combo_cards.append(
            ui.div(
                ui.div(
                    f"#{idx} {escape(str(combo.get('name') or 'Combo'))}",
                    class_="ir-combo-name",
                ),
                ui.div(escape(ingredients), class_="ir-combo-ings"),
                ui.div(escape(str(combo.get("rationale") or "")), class_="ir-combo-rationale"),
                ui.div(
                    ui.span(
                        f"synergy: {escape(str(combo.get('synergy_type') or ''))}",
                        class_="ir-chip",
                    ),
                    ui.span(
                        f"evidence: {escape(str(combo.get('evidence_grade') or ''))}",
                        class_="ir-chip",
                    ),
                    ui.span(
                        f"confidence: {float(combo.get('confidence') or 0):.2f}",
                        class_="ir-chip",
                    ),
                    class_="ir-chip-row",
                ),
                ui.div(
                    escape(str(combo.get("claim_safe_positioning") or "")),
                    class_="ir-combo-claim",
                )
                if combo.get("claim_safe_positioning")
                else ui.div(),
                ui.div(
                    "Safety: " + escape("; ".join(map(str, flags))),
                    class_="ir-combo-flags",
                )
                if flags
                else ui.div(),
                class_="ir-combo-card",
            )
        )

    dossier_rows = []
    for d in dossiers[:20]:
        cites = d.get("citations") or []
        cite_bits = []
        for c in cites[:3]:
            pmid = c.get("pmid") or ""
            url = c.get("url") or ""
            label = pmid or (c.get("title") or "citation")
            if url:
                cite_bits.append(f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(str(label))}</a>')
            else:
                cite_bits.append(escape(str(label)))
        findings = "; ".join(d.get("key_findings") or [])
        dossier_rows.append(
            ui.tags.tr(
                ui.tags.td(escape(str(d.get("name") or ""))),
                ui.tags.td(escape(str(d.get("evidence_grade") or ""))),
                ui.tags.td(escape(findings[:240])),
                ui.tags.td(ui.HTML(", ".join(cite_bits) if cite_bits else "—")),
            )
        )

    return ui.div(
        ui.div(
            ui.div("Summary", class_="ir-section-label"),
            ui.p(ui.HTML(summary.replace("\n", "<br/>"))),
            ui.div(
                f"Run {escape(str(meta.get('run_id') or ''))} · "
                f"pool {meta.get('pool_size', 0)} · "
                f"{meta.get('duration_seconds', 0)}s · "
                f"model {escape(str(meta.get('model') or ''))}",
                class_="gf-card-sub",
            ),
            class_="ir-summary",
        ),
        ui.div("Combination candidates", class_="ir-section-label"),
        ui.div(*combo_cards, class_="ir-combo-list")
        if combo_cards
        else ui.div("No combos returned.", class_="gf-card-sub"),
        ui.div("Ingredient dossiers", class_="ir-section-label"),
        ui.tags.table(
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Ingredient"),
                    ui.tags.th("Evidence"),
                    ui.tags.th("Findings"),
                    ui.tags.th("Citations"),
                )
            ),
            ui.tags.tbody(*dossier_rows),
            class_="ir-dossier-table",
        )
        if dossier_rows
        else ui.div("No dossiers returned.", class_="gf-card-sub"),
        ui.div("Open questions", class_="ir-section-label") if open_q else ui.div(),
        ui.tags.ul(*[ui.tags.li(escape(str(q))) for q in open_q]) if open_q else ui.div(),
        ui.div("Deferred / rejected", class_="ir-section-label") if rejected else ui.div(),
        ui.tags.ul(
            *[
                ui.tags.li(
                    f"{escape(str(r.get('item') or ''))}: {escape(str(r.get('reason') or ''))}"
                )
                for r in rejected
            ]
        )
        if rejected
        else ui.div(),
        ui.div(
            f"{len(citations)} citation(s) in report · "
            f"{escape(str(data.get('disclaimer') or '')[:180])}…",
            class_="gf-card-sub ir-disclaimer",
        ),
        class_="ir-results-inner",
    )


def register(input: Inputs, output: Outputs, session: Session) -> None:
    """Register Ingredient Lab reactive handlers.

    Args:
        input: Shiny inputs.
        output: Shiny outputs.
        session: Shiny session.
    """
    events_val: reactive.Value[List[Dict[str, Any]]] = reactive.Value([])
    running_val = reactive.Value(False)
    error_val = reactive.Value("")
    report_val = reactive.Value(None)
    status_val = reactive.Value("Idle")

    @render.ui
    def ir_status_badge():
        """Render a compact run status badge."""
        label = status_val.get() or "Idle"
        running = running_val.get()
        cls = "ir-status is-running" if running else "ir-status"
        return ui.span(label, class_=cls)

    @render.ui
    def ir_live_log():
        """Render the live Workforce execution timeline."""
        if running_val.get():
            reactive.invalidate_later(0.6)
        return _render_events(events_val.get() or [], running=bool(running_val.get()))

    @render.ui
    def ir_results():
        """Render final research results or loading/error states."""
        if running_val.get() and not report_val.get():
            return loading_block(
                "Workforce is researching ingredients and drafting combinations…"
            )
        err = error_val.get()
        if err and not report_val.get():
            return error_block("Research failed", err)
        report = report_val.get()
        if not report:
            return ui.div(
                ui.div(
                    "Results will appear here after the agents finish — "
                    "combos, dossiers, citations, and claim-safe positioning.",
                    class_="gf-card-sub",
                ),
                class_="ir-results-empty",
            )
        return _render_report(report)

    @reactive.effect
    @reactive.event(input.ir_run)
    async def _on_run():
        """Start a CAMEL Workforce research run with live event streaming."""
        if running_val.get():
            return

        from services.ingredient_research import ingredient_research_service
        from services.ingredient_research.schemas import IngredientComboRequest

        if not ingredient_research_service.is_ready:
            error_val.set(
                "Ingredient research is not configured. "
                "Set GOOGLE_API_KEY or LLM_BASE_MODEL_API_KEY in backend/.env."
            )
            report_val.set(None)
            return

        goal = (input.ir_goal() or "").strip()
        if len(goal) < 3:
            error_val.set("Please enter a health goal (at least 3 characters).")
            return

        running_val.set(True)
        error_val.set("")
        report_val.set(None)
        events_val.set([])
        status_val.set("Running")

        buffer: List[Dict[str, Any]] = []

        def on_event(event: Dict[str, Any]) -> None:
            """Append a progress event for the live log poller."""
            buffer.append(event)
            # Cap memory for very chatty stream modes.
            if len(buffer) > 400:
                del buffer[:-300]

        request = IngredientComboRequest(
            goal=goal,
            max_ingredients=int(input.ir_max_ingredients() or 7),
            format=str(input.ir_format() or "gummy"),
            market=str(input.ir_market() or "PK"),
            include_tags=list(input.ir_include_tags() or []),
            exclude=_split_csv(input.ir_exclude() or ""),
            ingredient_limit=int(input.ir_ingredient_limit() or 12),
            explicit_ingredients=_split_lines(input.ir_explicit() or ""),
        )

        async def _poll_events(task: asyncio.Task) -> None:
            """Push buffered events into reactive state while the run is active."""
            while not task.done():
                if buffer:
                    events_val.set(list(buffer))
                await asyncio.sleep(0.5)
            if buffer:
                events_val.set(list(buffer))

        try:
            task = asyncio.create_task(
                ingredient_research_service.research_combos(
                    request,
                    on_event=on_event,
                )
            )
            poller = asyncio.create_task(_poll_events(task))
            report = await task
            await poller
            report_val.set(report)
            status_val.set("Completed")
            events_val.set(list(buffer))
        except Exception as exc:  # noqa: BLE001
            error_val.set(str(exc))
            status_val.set("Failed")
            events_val.set(list(buffer))
            report_val.set(None)
        finally:
            running_val.set(False)
