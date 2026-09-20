"""Creative Intelligence — Shiny handlers."""

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
    def creative_intel_custom_dates():
        return custom_dates_output(input, "creative_intel")

    @reactive.calc
    async def creative_intel_accounts():
        input.refresh()
        from services.marketing import marketing_service

        fb = marketing_service._fb_client
        if not fb:
            return []
        return await fb.get_all_ad_accounts()

    @render.ui
    async def creative_intel_account_select():
        accounts = await creative_intel_accounts()
        choices = {"__all__": "All ad accounts"}
        for acc in accounts:
            acc_id = acc.get("id", "")
            choices[acc_id] = f"{acc.get('name', 'Unknown')} ({acc_id})"
        return ui.input_select(
            "creative_intel_account", None, choices=choices, selected="__all__", width="320px"
        )

    async def _run():
        loading.set(True)
        error_val.set("")
        try:
            from services.creative_intelligence import creative_intelligence_service

            period = date_range_from_input(input, "creative_intel")
            result = await creative_intelligence_service.analyze_all(
                since=period.since,
                until=period.until,
                account_id=selected_account_id(input, "creative_intel"),
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
    @reactive.event(input.creative_intel_run)
    async def _on_run():
        await _run()

    @render.ui
    def creative_intel_content():
        if loading.get():
            return loading_block("Analyzing creative patterns and fatigue…")

        err = error_val.get()
        if err and not result_val.get():
            return error_block("Creative analysis unavailable", err)

        result = result_val.get()
        if not result:
            return ui.div(
                ui.div("Creative intelligence", class_="gf-card-title"),
                ui.div(
                    "Run analysis to see winning message patterns, fatigued campaigns, "
                    "and a structured test backlog.",
                    class_="gf-card-sub",
                ),
                class_="gf-card gf-card-empty",
            )

        insight = result.get("pattern_insight", "")
        patterns = result.get("patterns") or []
        winners = result.get("winners") or []
        fatigued = result.get("fatigued_campaigns") or []
        backlog = result.get("test_backlog") or []

        pattern_rows = [
            ui.div(
                ui.span(p.get("label", ""), class_="gf-tag"),
                ui.span(f"Spend ${p.get('spend', 0):,.0f}", class_="gf-metric-pill"),
                ui.span(f"CTR {p.get('avg_ctr', 0):.2f}%", class_="gf-metric-pill"),
                class_="gf-pattern-row",
            )
            for p in patterns[:6]
        ]

        winner_cards = []
        for w in winners[:4]:
            winner_cards.append(
                ui.div(
                    ui.div(w.get("name", "Creative")[:60], class_="gf-list-title"),
                    ui.div(
                        ", ".join(t.replace("_", " ") for t in w.get("tags", [])),
                        class_="gf-list-sub",
                    ),
                    ui.div((w.get("body") or "")[:160], class_="gf-list-body"),
                    class_="gf-list-card",
                )
            )

        fatigue_rows = [
            ui.div(
                ui.span(f.get("campaign_name", ""), class_="gf-list-title"),
                ui.span(
                    f"Freq {f.get('frequency', 0):.1f} · CTR {f.get('ctr', 0):.2f}%",
                    class_="gf-list-sub",
                ),
                class_="gf-list-card",
            )
            for f in fatigued[:5]
        ]

        test_cards = []
        for test in backlog:
            test_cards.append(
                ui.div(
                    ui.div(f"Test #{test.get('priority', '')}", class_="gf-section-label"),
                    ui.div(test.get("hypothesis", ""), class_="gf-section-text"),
                    ui.div(
                        ui.span(f"Variable: {test.get('variable', '')}", class_="gf-test-meta"),
                        ui.span(f"Metric: {test.get('success_metric', '')}", class_="gf-test-meta"),
                        ui.span(f"{test.get('duration_days', '')} days · {test.get('budget', '')}", class_="gf-test-meta"),
                        class_="gf-test-meta-row",
                    ),
                    ui.div(test.get("decision_rule", ""), class_="gf-test-rule"),
                    class_="gf-test-card",
                )
            )

        return ui.div(
            ui.div(
                ui.div("Pattern insight", class_="gf-hero-title"),
                ui.div(insight, class_="gf-hero-text"),
                class_="gf-hero-card",
            ),
            ui.div(
                ui.div("Message patterns by spend", class_="gf-board-title"),
                ui.div(*pattern_rows, class_="gf-pattern-list") if pattern_rows else ui.div("No pattern data yet.", class_="gf-card-sub"),
                class_="gf-board-section",
            ),
            ui.div(
                ui.div("Top-performing creatives", class_="gf-board-title"),
                ui.div(*winner_cards, class_="gf-list-grid") if winner_cards else ui.div(),
                class_="gf-board-section",
            ),
            ui.div(
                ui.div("Fatigue signals", class_="gf-board-title"),
                ui.div(*fatigue_rows, class_="gf-list-grid") if fatigue_rows else ui.div("No fatigue flags.", class_="gf-card-sub"),
                class_="gf-board-section",
            ),
            ui.div(
                ui.div("Structured test backlog", class_="gf-board-title"),
                ui.div(*test_cards, class_="gf-test-grid"),
                class_="gf-board-section",
            ),
        )
