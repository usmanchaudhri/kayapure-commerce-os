"""Shared metric glossary for dashboard KPI labels and table headers."""

from typing import Optional

from shiny import ui

METRIC_TOOLTIPS = {
    "spend": "Total amount spent on ads in the selected period.",
    "impressions": "How many times your ads were shown on screen.",
    "clicks": "Total number of clicks on your ads (all click types).",
    "reach": "Number of unique people who saw your ads at least once.",
    "ctr": "Click-through rate — clicks ÷ impressions × 100.",
    "cpc": "Cost per click — average amount spent for each click.",
    "cpm": "Cost per 1,000 impressions — average cost to show the ad 1,000 times.",
    "frequency": "Average number of times each person saw your ads.",
    "link_clicks": "Clicks that went to your destination (website, WhatsApp, etc.).",
    "conversions": "Tracked conversion events (for example purchases) attributed to the ads.",
    "roas": "Return on ad spend — revenue attributed to ads ÷ ad spend.",
    "objective": "Campaign goal set in Meta Ads (Sales, Engagement, Awareness, etc.).",
    "destination": "Where the ad sends people — Website, WhatsApp, Product Catalog, etc.",
}


def metric_help(metric_key: str):
    """Small help mark; floating tooltip is shown by dashboard JS on hover."""
    tip = METRIC_TOOLTIPS.get(metric_key, "")
    if not tip:
        return None
    return ui.span(
        "?",
        class_="metric-tip",
        **{
            "data-tip": tip,
            "aria-label": tip,
            "tabindex": "0",
            "role": "button",
        },
    )


def metric_label(text: str, metric_key: Optional[str] = None, *, class_: str = "", style: str = ""):
    """Label text with an optional metric help tip next to it."""
    tip = metric_help(metric_key) if metric_key else None
    kids = [text]
    if tip is not None:
        kids.append(tip)
    # Avoid overflow:hidden clipping the help icon / hover target on KPI labels.
    cleaned_style = (style or "").replace("overflow:hidden;", "overflow:visible;")
    cleaned_style = cleaned_style.replace("text-overflow:ellipsis;", "")
    return ui.span(*kids, class_=f"metric-label-wrap {class_}".strip(), style=cleaned_style or None)


def metric_th(text: str, metric_key: Optional[str] = None):
    """Table header cell with an optional metric help tip."""
    tip = metric_help(metric_key) if metric_key else None
    if tip is None:
        return ui.tags.th(text)
    return ui.tags.th(ui.span(text, " ", tip, class_="metric-label-wrap"))
