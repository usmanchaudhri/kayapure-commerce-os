"""Campaign actions shared by Ads Performance — approvals, View, AI Report, mutations."""
import json
from datetime import datetime, timedelta

from shiny import Inputs, Outputs, Session, reactive, render, ui

from shiny_app.handlers.ai_reports import build_report_modal_content
from shiny_app.lib.action_client import (
    approve_action,
    deny_action,
    list_pending_actions,
    propose_meta_activate,
    propose_meta_budget,
    propose_meta_delete,
    propose_meta_pause,
)
from shiny_app.lib.formatting import CURRENCY_SYMBOLS, fmt_budget, fmt_currency, fmt_number
from shiny_app.lib.report_cache import SessionReportCache
from shiny_app.lib.report_pdf import generate_report_pdf


def _parse_campaign_payload(raw):
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            if raw.startswith("{"):
                return json.loads(raw)
            return {"id": raw, "name": raw}
        except (json.JSONDecodeError, TypeError):
            return {"id": raw, "name": raw}
    return None


def register(input: Inputs, output: Outputs, session: Session) -> None:
    # ============================================
    # Pending action queue
    # ============================================

    @reactive.calc
    def pending_actions_data():
        input.refresh()
        input.approve_action_id()
        input.deny_action_id()
        return list_pending_actions()

    @render.ui
    def pending_actions_panel():
        actions = pending_actions_data()
        if not actions:
            return ui.div(
                "No pending actions. Campaign changes are queued here for approval.",
                style="color: #64748b; font-size: 14px; padding: 12px 16px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b;",
            )

        cards = []
        for action in actions:
            aid = action["id"]
            cards.append(
                ui.div(
                    ui.div(
                        ui.span(f"#{aid}", style="color: #22d3ee; font-weight: 700; margin-right: 8px;"),
                        ui.span(action["title"], style="font-weight: 600;"),
                        style="margin-bottom: 4px;",
                    ),
                    ui.div(action["description"], style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;"),
                    ui.div(
                        ui.tags.button(
                            "Approve",
                            type="button",
                            class_="btn-activate",
                            onclick=f"Shiny.setInputValue('approve_action_id', {aid}, {{priority: 'event'}});",
                        ),
                        ui.tags.button(
                            "Deny",
                            type="button",
                            class_="btn-delete",
                            onclick=f"Shiny.setInputValue('deny_action_id', {aid}, {{priority: 'event'}});",
                        ),
                        class_="campaign-actions",
                    ),
                    style="padding: 12px 16px; background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; margin-bottom: 8px;",
                )
            )

        return ui.div(
            ui.div("Pending Approvals", class_="card-header", style="margin-bottom: 12px;"),
            *cards,
        )

    @reactive.effect
    @reactive.event(input.approve_action_id)
    async def _approve_queued_action():
        action_id = input.approve_action_id()
        if not action_id:
            return
        try:
            result = await approve_action(int(action_id))
            status = result.get("status", "completed")
            ui.notification_show(f"Action #{action_id} {status}. Click Refresh to update campaigns.", type="message", duration=5)
        except Exception as e:
            ui.notification_show(f"Approve failed: {e}", type="error", duration=6)

    @reactive.effect
    @reactive.event(input.deny_action_id)
    async def _deny_queued_action():
        action_id = input.deny_action_id()
        if not action_id:
            return
        try:
            await deny_action(int(action_id))
            ui.notification_show(f"Action #{action_id} denied.", type="warning", duration=4)
        except Exception as e:
            ui.notification_show(f"Deny failed: {e}", type="error", duration=6)

    campaign_report_cache = SessionReportCache()
    last_campaign_report = reactive.Value(None)  # dict with acc_id, camp_id, etc.

    # ---- Campaign detail modal ----

    @reactive.effect
    @reactive.event(input.view_campaign)
    async def _show_campaign_modal():
        """Show detail modal when View is clicked; lazy-load modal-only fields."""
        raw = input.view_campaign()
        if not raw:
            return
        try:
            c = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        campaign_id = c.get("id", "Unknown")
        account_id = c.get("_account_id", "") or ""
        name = c.get("name", "Untitled")

        # Fetch View-only fields (buying_type, bid_strategy, budget_remaining, thumbnail)
        needs_detail = not c.get("buying_type") or not c.get("bid_strategy") or not c.get("thumbnail_url")
        if needs_detail and account_id and campaign_id and campaign_id != "Unknown":
            try:
                from services.marketing import marketing_service

                fb = marketing_service._fb_client
                if fb:
                    extras = await fb.get_campaign_modal_details(account_id, str(campaign_id))
                    c = {**c, **{k: v for k, v in extras.items() if v not in (None, "")}}
                    if extras.get("name"):
                        name = extras["name"]
            except Exception:
                pass

        status = c.get("status", "UNKNOWN").upper()
        objective = c.get("objective", "—")
        currency = c.get("_currency", "USD")
        daily_budget = c.get("daily_budget")
        lifetime_budget = c.get("lifetime_budget")
        budget_remaining = c.get("budget_remaining", "")
        created_time = c.get("created_time", "")[:10] if c.get("created_time") else "—"
        start_time = c.get("start_time", "")[:10] if c.get("start_time") else "—"
        stop_time = c.get("stop_time", "")[:10] if c.get("stop_time") else "—"
        buying_type = c.get("buying_type", "—") or "—"
        bid_strategy = c.get("bid_strategy", "—") or "—"
        account_name = c.get("_account_name", "—")
        perf = c.get("performance")

        # Status badge
        if status == "ACTIVE":
            badge_class, badge_label = "badge-active", "Active"
        elif status == "PAUSED":
            badge_class, badge_label = "badge-paused", "Paused"
        elif status == "DELETED":
            badge_class, badge_label = "badge-deleted", "Deleted"
        else:
            badge_class, badge_label = "badge-archived", status.title()

        obj_display = objective.replace("OUTCOME_", "").replace("_", " ").title() if objective != "—" else "—"

        if daily_budget and int(daily_budget) > 0:
            budget_display = f"{fmt_budget(int(daily_budget), currency)}/day"
        elif lifetime_budget and int(lifetime_budget) > 0:
            budget_display = f"{fmt_budget(int(lifetime_budget), currency)} lifetime"
        else:
            budget_display = "—"

        budget_remaining_display = fmt_budget(int(budget_remaining), currency) if budget_remaining and str(budget_remaining).isdigit() and int(budget_remaining) > 0 else "—"

        thumb_url = c.get("thumbnail_url") or ""
        if thumb_url:
            preview_section = ui.tags.img(
                src=thumb_url,
                class_="campaign-modal-preview",
                alt=c.get("ad_preview_name") or name,
            )
        else:
            preview_section = ui.div(
                "No ad creative preview available for this campaign.",
                style="color: #64748b; font-size: 14px; margin-bottom: 16px; padding: 16px; background: var(--surface-2); border-radius: 8px;",
            )

        insights_label = c.get("_period_label") or "Selected period"
        perf_title = f"Performance ({insights_label})"

        # Performance section
        if perf:
            perf_section = ui.div(
                ui.tags.h4(perf_title, style="color: #94a3b8; font-size: 16px; margin-top: 20px; margin-bottom: 12px;"),
                ui.div(
                    ui.div(ui.tags.label("Spend"), ui.span(fmt_currency(perf.get("spend", 0), currency)), class_="detail-item"),
                    ui.div(ui.tags.label("Impressions"), ui.span(fmt_number(perf.get("impressions", 0))), class_="detail-item"),
                    ui.div(ui.tags.label("Clicks"), ui.span(fmt_number(perf.get("clicks", 0))), class_="detail-item"),
                    ui.div(ui.tags.label("CPC"), ui.span(fmt_currency(perf.get("cpc", 0), currency)), class_="detail-item"),
                    ui.div(ui.tags.label("CTR"), ui.span(f"{perf.get('ctr', 0):.2f}%"), class_="detail-item"),
                    ui.div(ui.tags.label("Reach"), ui.span(fmt_number(perf.get("reach", 0))), class_="detail-item"),
                    class_="detail-grid-3",
                ),
            )
        else:
            perf_section = ui.div(
                ui.tags.h4(perf_title, style="color: #94a3b8; font-size: 16px; margin-top: 20px; margin-bottom: 12px;"),
                ui.div("No performance data available for this period.", style="color: #475569; font-size: 15px;"),
            )

        modal = ui.modal(
            preview_section,
            # Campaign details grid
            ui.div(
                ui.div(ui.tags.label("Campaign ID"), ui.span(campaign_id, style="font-family: monospace; font-size: 14px;"), class_="detail-item"),
                ui.div(ui.tags.label("Status"), ui.span(badge_label, class_=badge_class), class_="detail-item"),
                ui.div(ui.tags.label("Objective"), ui.span(obj_display, class_="badge-objective"), class_="detail-item"),
                ui.div(ui.tags.label("Budget"), ui.span(budget_display), class_="detail-item"),
                ui.div(ui.tags.label("Budget Remaining"), ui.span(budget_remaining_display), class_="detail-item"),
                ui.div(ui.tags.label("Buying Type"), ui.span(buying_type.title() if buying_type != "—" else "—"), class_="detail-item"),
                ui.div(ui.tags.label("Bid Strategy"), ui.span(bid_strategy.replace("_", " ").title() if bid_strategy != "—" else "—"), class_="detail-item"),
                ui.div(ui.tags.label("Created"), ui.span(created_time), class_="detail-item"),
                ui.div(ui.tags.label("Start Date"), ui.span(start_time), class_="detail-item"),
                ui.div(ui.tags.label("End Date"), ui.span(stop_time), class_="detail-item"),
                ui.div(ui.tags.label("Account"), ui.span(account_name), class_="detail-item"),
                ui.div(ui.tags.label("Account ID"), ui.span(account_id, style="font-family: monospace; font-size: 14px;"), class_="detail-item"),
                class_="detail-grid",
            ),

            perf_section,

            title=name,
            size="l",
            easy_close=True,
        )
        ui.modal_show(modal)

    # ---- Campaign AI Report (deep dive) ----

    def _campaign_report_type(campaign_id: str) -> str:
        return f"campaign:{campaign_id}"

    def _resolve_campaign_period(c: dict) -> tuple[str, str, int]:
        since = c.get("_period_since") or ""
        until = c.get("_period_until") or ""
        if since and until:
            try:
                days = (
                    datetime.strptime(until, "%Y-%m-%d")
                    - datetime.strptime(since, "%Y-%m-%d")
                ).days + 1
            except Exception:
                days = 30
            return since, until, max(1, days)

        # Fall back to Ads Performance date range if available
        try:
            from shiny_app.lib.date_ranges import resolve_date_range

            range_val = "30"
            try:
                range_val = input.ai_reports_date_range() or "30"
            except Exception:
                range_val = "30"
            period = resolve_date_range(range_val)
            return period.since, period.until, period.days
        except Exception:
            until_dt = datetime.utcnow()
            since_dt = until_dt - timedelta(days=29)
            return since_dt.strftime("%Y-%m-%d"), until_dt.strftime("%Y-%m-%d"), 30

    def _close_campaign_modals():
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

    def _open_campaign_report_modal(
        result: dict,
        *,
        acc_id: str,
        acc_name: str,
        campaign_id: str,
        campaign_name: str,
        from_cache: bool,
    ) -> None:
        ui.modal_show(ui.modal(
            build_report_modal_content(
                result,
                acc_name,
                acc_id=acc_id,
                from_cache=from_cache,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
            ),
            title=f"Campaign AI Report \u2014 {campaign_name}",
            size="xl",
            easy_close=True,
        ))

    async def _generate_campaign_report(c: dict, *, force: bool) -> None:
        campaign_id = str(c.get("id") or "")
        campaign_name = c.get("name") or campaign_id
        acc_id = c.get("_account_id") or ""
        acc_name = c.get("_account_name") or acc_id
        currency = c.get("_currency") or "USD"
        if not campaign_id or not acc_id:
            ui.notification_show("Missing campaign or account id.", type="error", duration=4)
            return

        since, until, days = _resolve_campaign_period(c)
        report_type = _campaign_report_type(campaign_id)
        last_campaign_report.set({
            "account_id": acc_id,
            "account_name": acc_name,
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "since": since,
            "until": until,
            "days": days,
            "currency": currency,
        })

        if not force:
            cached = campaign_report_cache.get(acc_id, report_type, days)
            if cached:
                _open_campaign_report_modal(
                    cached.get("result") or {},
                    acc_id=acc_id,
                    acc_name=acc_name,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    from_cache=True,
                )
                return

        ui.modal_show(ui.modal(
            ui.div(
                ui.div(class_="spinner"),
                ui.div(
                    "Running deep campaign analysis (ad sets, ads, creatives)...",
                    style="margin-top: 16px; font-size: 16px; color: #94a3b8;",
                ),
                ui.div(
                    "This usually takes 20–45 seconds.",
                    style="margin-top: 6px; font-size: 14px; color: #475569;",
                ),
                class_="ai-report-modal-loading",
            ),
            title=f"Analyzing \u2014 {campaign_name}",
            size="l",
            easy_close=True,
        ))

        try:
            from services.ads_analysis_agent import ads_analysis_agent_service

            result = await ads_analysis_agent_service.analyze_campaign(
                account_id=acc_id,
                campaign_id=campaign_id,
                since=since,
                until=until,
                account_name=acc_name,
                campaign_name=campaign_name,
                currency=currency,
                force_refresh=force,
            )
            campaign_report_cache.put(acc_id, report_type, days, result)
            _close_campaign_modals()
            _open_campaign_report_modal(
                result,
                acc_id=acc_id,
                acc_name=acc_name,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                from_cache=False,
            )
        except Exception as e:
            _close_campaign_modals()
            ui.modal_show(ui.modal(
                ui.div(f"Failed to generate campaign report: {e}", class_="ai-report-error"),
                title=f"Report Error \u2014 {campaign_name}",
                size="l",
                easy_close=True,
            ))

    @reactive.effect
    @reactive.event(input.campaign_ai_report)
    async def _handle_campaign_ai_report():
        c = _parse_campaign_payload(input.campaign_ai_report())
        if not c:
            return
        await _generate_campaign_report(c, force=False)

    @reactive.effect
    @reactive.event(input.campaign_ai_report_regen)
    async def _handle_campaign_ai_report_regen():
        val = input.campaign_ai_report_regen() or ""
        parts = str(val).split("|")
        # acc_id|acc_name|campaign|camp_id|camp_name
        if len(parts) < 5:
            meta = last_campaign_report.get() or {}
            c = {
                "id": meta.get("campaign_id"),
                "name": meta.get("campaign_name"),
                "_account_id": meta.get("account_id"),
                "_account_name": meta.get("account_name"),
                "_currency": meta.get("currency", "USD"),
                "_period_since": meta.get("since"),
                "_period_until": meta.get("until"),
            }
        else:
            c = {
                "id": parts[3],
                "name": parts[4],
                "_account_id": parts[0],
                "_account_name": parts[1],
                "_currency": (last_campaign_report.get() or {}).get("currency", "USD"),
                "_period_since": (last_campaign_report.get() or {}).get("since"),
                "_period_until": (last_campaign_report.get() or {}).get("until"),
            }
        if not c.get("id"):
            return
        await _generate_campaign_report(c, force=True)

    @reactive.effect
    @reactive.event(input.campaign_ai_report_pdf)
    async def _handle_campaign_ai_report_pdf():
        val = input.campaign_ai_report_pdf() or ""
        parts = str(val).split("|")
        meta = last_campaign_report.get() or {}
        if len(parts) >= 5:
            acc_id, acc_name, _, camp_id, camp_name = (
                parts[0], parts[1], parts[2], parts[3], parts[4]
            )
        else:
            acc_id = meta.get("account_id") or ""
            acc_name = meta.get("account_name") or ""
            camp_id = meta.get("campaign_id") or ""
            camp_name = meta.get("campaign_name") or ""
        if not acc_id or not camp_id:
            ui.notification_show("No campaign report available to export.", type="warning", duration=4)
            return

        report_type = _campaign_report_type(camp_id)
        days = int(meta.get("days") or 30)
        cached = campaign_report_cache.get(acc_id, report_type, days)
        # Fallback: scan cache for this campaign if day key drifted
        if not cached:
            for key, entry in list(campaign_report_cache._store.items()):
                if key.startswith(f"{acc_id}|{report_type}|"):
                    cached = entry
                    break
        if not cached:
            ui.notification_show("Generate the campaign report first.", type="warning", duration=4)
            return
        try:
            import os

            label = f"{acc_name} / {camp_name}"
            filepath = generate_report_pdf(
                cached.get("result") or {}, label, f"{acc_id}_{camp_id}"
            )
            filename = os.path.basename(filepath)
            await session.send_custom_message(
                "download_pdf",
                {
                    "url": f"/api/marketing/report-pdfs/{filename}",
                    "filename": filename,
                },
            )
        except Exception as e:
            ui.notification_show(f"PDF export failed: {e}", type="error", duration=5)

    # ---- Pause campaign ----

    @reactive.effect
    @reactive.event(input.pause_campaign)
    async def _pause_campaign():
        c = _parse_campaign_payload(input.pause_campaign())
        if not c:
            return
        try:
            action_id = propose_meta_pause(c.get("id", ""), c.get("name", c.get("id", "")))
            ui.notification_show(
                f"Pause queued as action #{action_id}. Approve it in Pending Approvals above.",
                type="message", duration=6,
            )
        except Exception as e:
            ui.notification_show(f"Failed to queue pause: {e}", type="error", duration=6)

    # ---- Activate campaign ----

    @reactive.effect
    @reactive.event(input.activate_campaign)
    async def _activate_campaign():
        c = _parse_campaign_payload(input.activate_campaign())
        if not c:
            return
        try:
            action_id = propose_meta_activate(c.get("id", ""), c.get("name", c.get("id", "")))
            ui.notification_show(
                f"Activation queued as action #{action_id}. Approve it in Pending Approvals above.",
                type="message", duration=6,
            )
        except Exception as e:
            ui.notification_show(f"Failed to queue activation: {e}", type="error", duration=6)

    # ---- Delete campaign ----

    @reactive.effect
    @reactive.event(input.delete_campaign)
    async def _delete_campaign():
        c = _parse_campaign_payload(input.delete_campaign())
        if not c:
            return
        try:
            action_id = propose_meta_delete(c.get("id", ""), c.get("name", c.get("id", "")))
            ui.notification_show(
                f"Archive queued as action #{action_id}. Approve it in Pending Approvals above.",
                type="warning", duration=6,
            )
        except Exception as e:
            ui.notification_show(f"Failed to queue delete: {e}", type="error", duration=6)

    # ---- Edit budget modal ----

    @reactive.effect
    @reactive.event(input.edit_budget_campaign)
    async def _show_edit_budget_modal():
        raw = input.edit_budget_campaign()
        if not raw:
            return
        try:
            c = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        campaign_id = c.get("id", "")
        name = c.get("name", "")
        currency = c.get("_currency", "USD")
        daily_budget = c.get("daily_budget")
        current_budget_display = fmt_budget(int(daily_budget), currency) if daily_budget and int(daily_budget) > 0 else "Not set"
        current_budget_value = str(int(daily_budget) // 100) if daily_budget and int(daily_budget) > 0 else ""

        sym = CURRENCY_SYMBOLS.get(currency, currency)

        modal = ui.modal(
            ui.div(
                ui.div(f"Current daily budget: {current_budget_display}", style="color: #94a3b8; font-size: 16px; margin-bottom: 16px;"),
                ui.div(
                    ui.input_text(
                        "new_budget_value",
                        f"New Daily Budget ({sym})",
                        value=current_budget_value,
                        placeholder=f"e.g., 500 ({sym}500.00/day)",
                        width="100%",
                    ),
                    ui.div(
                        f"Enter the amount in whole {currency} (e.g., 500 = {sym}500.00/day). "
                        f"The value will be converted to cents for the API.",
                        style="font-size: 14px; color: #475569; margin-top: 6px;",
                    ),
                    style="margin-bottom: 20px;",
                ),
                # Hidden input to pass campaign_id
                ui.tags.script(f"document.getElementById('budget_campaign_id_store').value = '{campaign_id}';"),
                ui.tags.input(type="hidden", id="budget_campaign_id_store", value=campaign_id),
                ui.div(
                    ui.input_action_button(
                        "submit_budget",
                        f"Update Budget for {name[:40]}",
                        class_="action-btn action-btn-primary",
                        style="width: 100%; padding: 12px;",
                    ),
                ),
            ),
            title=f"Edit Budget — {name}",
            size="m",
            easy_close=True,
        )
        ui.modal_show(modal)

    @reactive.effect
    @reactive.event(input.submit_budget)
    async def _handle_budget_update():
        new_value = input.new_budget_value()
        if not new_value:
            ui.notification_show("Please enter a budget value.", type="error", duration=4)
            return

        try:
            budget_whole = int(float(new_value))
            budget_cents = budget_whole * 100
        except (ValueError, TypeError):
            ui.notification_show("Invalid budget value. Please enter a number.", type="error", duration=4)
            return

        # Get campaign_id from the last edit_budget_campaign event
        raw = input.edit_budget_campaign()
        if not raw:
            ui.notification_show("Campaign not found.", type="error", duration=4)
            return
        try:
            c = json.loads(raw)
            campaign_id = c.get("id", "")
        except (json.JSONDecodeError, TypeError):
            ui.notification_show("Campaign not found.", type="error", duration=4)
            return

        currency = c.get("_currency", "USD")
        sym = CURRENCY_SYMBOLS.get(currency, currency)

        try:
            action_id = propose_meta_budget(campaign_id, c.get("name", campaign_id), budget_cents)
            ui.notification_show(
                f"Budget update queued as action #{action_id}. Approve it in Pending Approvals above.",
                type="message", duration=6,
            )
            ui.modal_remove()
        except Exception as e:
            ui.notification_show(f"Failed to queue budget update: {e}", type="error", duration=6)

    # ============================================
