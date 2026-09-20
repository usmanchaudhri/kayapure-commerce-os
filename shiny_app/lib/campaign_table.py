"""Shared campaign table markup used by Ads Performance."""

from __future__ import annotations

import json
from itertools import groupby
from typing import Iterable, Literal

from shiny import ui

from shiny_app.lib.formatting import (
    fmt_budget,
    fmt_campaign_objective,
    fmt_currency,
    fmt_date_display,
    fmt_destination_type,
    fmt_number,
    fmt_optimization_goal,
)

SortMode = Literal["spend", "status_date", "created"]


def campaign_spend(campaign: dict) -> float:
    perf = campaign.get("performance") or {}
    try:
        return float(perf.get("spend") or 0)
    except (TypeError, ValueError):
        return 0.0


def campaign_created_key(campaign: dict) -> str:
    return campaign.get("created_time") or campaign.get("start_time") or ""


def sort_campaigns(campaigns: Iterable[dict], mode: SortMode = "created") -> list[dict]:
    items = list(campaigns)
    if mode == "spend":
        return sorted(items, key=campaign_spend, reverse=True)
    if mode == "created":
        return sorted(items, key=campaign_created_key, reverse=True)

    def status_rank(campaign: dict) -> int:
        status = (campaign.get("status") or "UNKNOWN").upper()
        if status == "ACTIVE":
            return 0
        if status == "PAUSED":
            return 1
        return 2

    items.sort(key=lambda c: (c.get("start_time") or c.get("created_time") or "1970-01-01"), reverse=True)
    items.sort(key=status_rank)
    grouped: list[dict] = []
    for _, group in groupby(items, key=status_rank):
        group_list = list(group)
        group_list.sort(
            key=lambda c: c.get("start_time") or c.get("created_time") or "1970-01-01",
            reverse=True,
        )
        grouped.extend(group_list)
    return grouped


def attach_account_fields(
    campaigns: Iterable[dict],
    *,
    account_id: str,
    account_name: str,
    currency: str,
    period_since: str = "",
    period_until: str = "",
    period_label: str = "",
) -> list[dict]:
    attached = []
    for campaign in campaigns:
        item = dict(campaign)
        item["_account_id"] = account_id
        item["_account_name"] = account_name
        item["_currency"] = currency
        if period_since:
            item["_period_since"] = period_since
        if period_until:
            item["_period_until"] = period_until
        if period_label:
            item["_period_label"] = period_label
        attached.append(item)
    return attached


def _status_badge(status: str) -> tuple[str, str]:
    if status == "ACTIVE":
        return "badge-active", "Active"
    if status == "PAUSED":
        return "badge-paused", "Paused"
    if status == "DELETED":
        return "badge-deleted", "Deleted"
    return "badge-archived", status.title()


def _budget_display(campaign: dict, currency: str) -> str:
    daily_budget = campaign.get("daily_budget")
    lifetime_budget = campaign.get("lifetime_budget")
    if daily_budget and int(daily_budget) > 0:
        return f"{fmt_budget(int(daily_budget), currency)}/day"
    if lifetime_budget and int(lifetime_budget) > 0:
        return f"{fmt_budget(int(lifetime_budget), currency)} lifetime"
    return "—"


def _campaign_action_payload(campaign: dict) -> str:
    return json.dumps(json.dumps({
        "id": campaign.get("id", ""),
        "name": campaign.get("name", "—"),
        "status": (campaign.get("status") or "UNKNOWN").upper(),
        "objective": campaign.get("objective", "—"),
        "daily_budget": campaign.get("daily_budget"),
        "lifetime_budget": campaign.get("lifetime_budget"),
        "created_time": campaign.get("created_time", ""),
        "start_time": campaign.get("start_time", ""),
        "stop_time": campaign.get("stop_time", ""),
        "buying_type": campaign.get("buying_type", ""),
        "bid_strategy": campaign.get("bid_strategy", ""),
        "budget_remaining": campaign.get("budget_remaining", ""),
        "performance": campaign.get("performance"),
        "thumbnail_url": campaign.get("thumbnail_url") or "",
        "ad_preview_name": campaign.get("ad_preview_name", ""),
        "optimization_goal": campaign.get("optimization_goal", ""),
        "destination_type": campaign.get("destination_type", ""),
        "_account_name": campaign.get("_account_name", ""),
        "_account_id": campaign.get("_account_id", ""),
        "_currency": campaign.get("_currency", "USD"),
        "_period_since": campaign.get("_period_since", ""),
        "_period_until": campaign.get("_period_until", ""),
        "_period_label": campaign.get("_period_label", ""),
    }))


def meta_ads_campaign_url(account_id: str, campaign_id: str) -> str | None:
    """Deep link into Meta Ads Manager for a specific campaign."""
    if not account_id or not campaign_id:
        return None
    act = account_id.removeprefix("act_")
    if not act.isdigit() or not str(campaign_id).isdigit():
        return None
    return (
        "https://www.facebook.com/adsmanager/manage/campaigns"
        f"?act={act}&selected_campaign_ids={campaign_id}"
    )


def _campaign_name_cell(name: str, account_id: str, campaign_id: str) -> ui.Tag:
    href = meta_ads_campaign_url(account_id, campaign_id)
    if href:
        name_node = ui.tags.a(
            name,
            href=href,
            target="_blank",
            rel="noopener noreferrer",
            class_="campaign-name-link",
            title="Open in Meta Ads Manager",
        )
    else:
        name_node = ui.span(name)
    return ui.tags.td(
        ui.div(name_node, class_="campaign-name"),
        ui.div(campaign_id or "—", class_="campaign-id"),
    )


def _campaign_row(campaign: dict) -> ui.Tag:
    campaign_id = campaign.get("id", "")
    name = campaign.get("name", "—")
    account_id = campaign.get("_account_id", "")
    status = (campaign.get("status") or "UNKNOWN").upper()
    objective = campaign.get("objective", "—")
    currency = campaign.get("_currency", "USD")
    created_time = campaign.get("created_time", "")
    created_display = fmt_date_display(created_time[:10]) if created_time else "—"
    thumb_url = campaign.get("thumbnail_url") or ""
    payload = _campaign_action_payload(campaign)

    perf = campaign.get("performance")
    if perf:
        spend_display = fmt_currency(perf.get("spend", 0), currency)
        clicks_display = fmt_number(perf.get("clicks", 0))
        impressions_display = fmt_number(perf.get("impressions", 0))
        ctr_display = f"{perf.get('ctr', 0):.2f}%"
    else:
        spend_display = "—"
        clicks_display = "—"
        impressions_display = "—"
        ctr_display = "—"

    badge_class, badge_label = _status_badge(status)
    goal_label = fmt_campaign_objective(objective)
    opt_label = fmt_optimization_goal(campaign.get("optimization_goal") or "")
    dest_label = fmt_destination_type(campaign.get("destination_type") or "")
    goal_bits = [ui.div(goal_label, class_="campaign-goal-primary")]
    if opt_label != "—" and opt_label != goal_label:
        goal_bits.append(ui.div(f"Optimize: {opt_label}", class_="campaign-goal-secondary"))
    if dest_label != "—":
        goal_bits.append(ui.div(dest_label, class_="campaign-goal-secondary"))

    if status == "ACTIVE":
        toggle_btn = ui.tags.button(
            "Pause",
            type="button",
            class_="btn-pause",
            onclick=f"Shiny.setInputValue('pause_campaign', {payload}, {{priority: 'event'}});",
        )
    elif status == "PAUSED":
        toggle_btn = ui.tags.button(
            "Activate",
            type="button",
            class_="btn-activate",
            onclick=f"Shiny.setInputValue('activate_campaign', {payload}, {{priority: 'event'}});",
        )
    else:
        toggle_btn = ui.span()

    if thumb_url:
        thumb_cell = ui.tags.img(
            src=thumb_url,
            class_="campaign-thumb",
            alt=campaign.get("ad_preview_name") or name,
            title=campaign.get("ad_preview_name") or "Ad creative",
            loading="lazy",
        )
    else:
        thumb_cell = ui.div("—", class_="campaign-thumb-placeholder", title="No ad creative preview")

    return ui.tags.tr(
        ui.tags.td(thumb_cell, class_="campaign-thumb-cell"),
        _campaign_name_cell(name, account_id, campaign_id),
        ui.tags.td(ui.span(badge_label, class_=badge_class)),
        ui.tags.td(*goal_bits, class_="campaign-goal-cell"),
        ui.tags.td(_budget_display(campaign, currency)),
        ui.tags.td(created_display),
        ui.tags.td(
            ui.div(f"Spend: {spend_display}", style="font-size: 14px;"),
            ui.div(f"Clicks: {clicks_display} | Impr: {impressions_display}", style="font-size: 12px; color: #64748b;"),
            ui.div(f"CTR: {ctr_display}", style="font-size: 12px; color: #64748b;"),
        ),
        ui.tags.td(
            ui.div(
                ui.tags.button(
                    "View",
                    type="button",
                    class_="btn-view",
                    onclick=f"Shiny.setInputValue('view_campaign', {payload}, {{priority: 'event'}});",
                ),
                ui.tags.button(
                    "AI Report",
                    type="button",
                    class_="btn-ai-report",
                    title="Deep AI analysis of this campaign (ad sets, ads, creatives)",
                    onclick=f"Shiny.setInputValue('campaign_ai_report', {payload}, {{priority: 'event'}});",
                ),
                toggle_btn,
                ui.tags.button(
                    "Budget",
                    type="button",
                    class_="btn-edit",
                    onclick=f"Shiny.setInputValue('edit_budget_campaign', {payload}, {{priority: 'event'}});",
                ),
                ui.tags.button(
                    "Delete",
                    type="button",
                    class_="btn-delete",
                    onclick=f"Shiny.setInputValue('delete_campaign', {payload}, {{priority: 'event'}});",
                ),
                class_="campaign-actions",
            ),
        ),
    )


def build_campaigns_table(
    campaigns: Iterable[dict],
    *,
    insights_label: str,
    sort: SortMode = "created",
    empty_message: str = "No campaigns found for this account.",
) -> ui.Tag:
    """Render the campaign management table used across dashboard tabs."""
    rows_data = sort_campaigns(campaigns, mode=sort)
    if not rows_data:
        return ui.div(empty_message, class_="account-campaigns-empty")

    rows = [_campaign_row(campaign) for campaign in rows_data]
    perf_header = f"Performance ({insights_label})"
    return ui.div(
        ui.tags.table(
            ui.tags.thead(ui.tags.tr(
                ui.tags.th("Ad"),
                ui.tags.th("Campaign"),
                ui.tags.th("Status"),
                ui.tags.th("Goal"),
                ui.tags.th("Budget"),
                ui.tags.th("Created"),
                ui.tags.th(perf_header),
                ui.tags.th("Actions"),
            )),
            ui.tags.tbody(*rows),
        ),
        class_="campaigns-table-wrap",
    )
