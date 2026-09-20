"""Display helpers for currency and numbers in the Shiny dashboard."""

from datetime import datetime

CURRENCY_SYMBOLS = {
    "PKR": "Rs",
    "USD": "$",
    "GBP": "£",
    "EUR": "€",
    "AED": "AED",
    "SAR": "SAR",
    "INR": "₹",
    "CAD": "C$",
    "AUD": "A$",
}


def fmt_currency(value, currency="USD"):
    """Format a number with the correct currency symbol."""
    sym = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{sym}{value:,.2f}"


def fmt_number(value):
    """Format a number with commas."""
    return f"{value:,}"


def fmt_number_compact(value) -> str:
    """Compact number for dense KPI cards (e.g. 1.2M, 450K)."""
    val = float(value or 0)
    if abs(val) >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    if abs(val) >= 10_000:
        return f"{val / 1_000:.1f}K"
    return fmt_number(int(val))


def fmt_currency_compact(value, currency="USD") -> str:
    """Compact currency for dense KPI cards."""
    sym = CURRENCY_SYMBOLS.get(currency, currency)
    val = float(value or 0)
    if abs(val) >= 1_000_000:
        return f"{sym}{val / 1_000_000:.2f}M"
    if abs(val) >= 10_000:
        return f"{sym}{val / 1_000:.1f}K"
    return fmt_currency(val, currency)


def fmt_pct(value):
    """Format a percentage with two decimal places."""
    return f"{float(value):.2f}%"


_CAMPAIGN_OBJECTIVE_LABELS = {
    "OUTCOME_SALES": "Sales",
    "OUTCOME_ENGAGEMENT": "Engagement",
    "OUTCOME_AWARENESS": "Awareness",
    "OUTCOME_TRAFFIC": "Traffic",
    "OUTCOME_LEADS": "Leads",
    "OUTCOME_APP_PROMOTION": "App Promotion",
    "CONVERSIONS": "Conversions",
    "LINK_CLICKS": "Link Clicks",
    "REACH": "Reach",
    "BRAND_AWARENESS": "Brand Awareness",
    "VIDEO_VIEWS": "Video Views",
    "LEAD_GENERATION": "Lead Generation",
    "MESSAGES": "Messages",
    "APP_INSTALLS": "App Installs",
    "PRODUCT_CATALOG_SALES": "Catalog Sales",
}


def fmt_campaign_objective(objective: str) -> str:
    """Human-readable label for a Meta campaign objective."""
    if not objective or objective == "—":
        return "—"
    normalized = objective.strip().upper()
    if normalized in _CAMPAIGN_OBJECTIVE_LABELS:
        return _CAMPAIGN_OBJECTIVE_LABELS[normalized]
    return normalized.replace("OUTCOME_", "").replace("_", " ").title()


_OPTIMIZATION_GOAL_LABELS = {
    "OFFSITE_CONVERSIONS": "Conversions",
    "VALUE": "Conversion value",
    "LINK_CLICKS": "Link clicks",
    "LANDING_PAGE_VIEWS": "Landing page views",
    "REACH": "Reach",
    "IMPRESSIONS": "Impressions",
    "THRUPLAY": "ThruPlay",
    "CONVERSATIONS": "Conversations",
    "LEAD_GENERATION": "Leads",
    "QUALITY_LEAD": "Quality leads",
    "APP_INSTALLS": "App installs",
    "APP_EVENTS": "App events",
    "POST_ENGAGEMENT": "Post engagement",
    "PAGE_LIKES": "Page likes",
    "EVENT_RESPONSES": "Event responses",
    "VIDEO_VIEWS": "Video views",
    "DERIVED_EVENTS": "Derived events",
    "AD_RECALL_LIFT": "Ad recall",
    "ENGAGED_USERS": "Engaged users",
    "PROFILE_VISIT": "Profile visits",
    "MESSAGING_PURCHASE_CONVERSION": "Messaging purchases",
    "MESSAGING_APPOINTMENT_CONVERSION": "Messaging appointments",
}


def fmt_optimization_goal(goal: str) -> str:
    """Human-readable Meta ad set optimization goal."""
    if not goal or goal == "—":
        return "—"
    normalized = goal.strip().upper()
    if normalized in _OPTIMIZATION_GOAL_LABELS:
        return _OPTIMIZATION_GOAL_LABELS[normalized]
    return normalized.replace("_", " ").title()


def fmt_destination_type(destination_type: str) -> str:
    """Human-readable ad set destination."""
    if not destination_type or destination_type == "—":
        return "—"
    normalized = destination_type.strip().upper()
    labels = {
        "WEBSITE": "Website",
        "APP": "App",
        "MESSENGER": "Messenger",
        "WHATSAPP": "WhatsApp",
        "INSTAGRAM_DIRECT": "Instagram",
        "PHONE_CALL": "Phone call",
        "SHOP_AUTOMATIC": "Shop",
        "ON_PAGE": "Facebook Page",
        "ON_AD": "On ad",
        "UNDEFINED": "",
    }
    if normalized in labels:
        return labels[normalized] or "—"
    return normalized.replace("_", " ").title()


def fmt_campaign_destination(destination: str, detail: str = "") -> str:
    """Format destination with optional detail (phone, URL) for tooltips."""
    if not destination or destination == "—":
        return "—"
    if detail:
        return f"{destination} ({detail})"
    return destination


def fmt_campaign_run_dates(campaign: dict) -> str:
    """Format campaign schedule or activity window for display."""
    start = (campaign.get("start_time") or campaign.get("date_start") or "").strip()
    stop = (campaign.get("stop_time") or campaign.get("date_stop") or "").strip()

    start_label = fmt_date_display(start[:10]) if start else ""
    stop_label = fmt_date_display(stop[:10]) if stop else ""

    if start_label and stop_label and start_label != stop_label:
        return f"{start_label} → {stop_label}"
    if start_label:
        return f"{start_label} → ongoing"
    if stop_label:
        return stop_label
    return "—"


def fmt_budget(value_cents, currency="USD"):
    """Format a budget value from cents to currency display."""
    if value_cents is None or value_cents == 0:
        return "\u2014"
    return fmt_currency(float(value_cents) / 100, currency)


COMPACT_KPI_VALUE_STYLE = ""
COMPACT_KPI_LABEL_STYLE = ""
COMPACT_KPI_SUB_STYLE = ""
COMPACT_KPI_CARD_STYLE = ""
COMPACT_KPI_ROW_STYLE = ""


def fmt_date_display(value: str) -> str:
    """Format YYYY-MM-DD as Month DD, YYYY."""
    if not value or value == "?":
        return value
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        return value


def fmt_date_range(since: str, until: str) -> str:
    """Format a date range for dashboard display."""
    return f"{fmt_date_display(since)} → {fmt_date_display(until)}"
