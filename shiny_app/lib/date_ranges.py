"""Shared date-range helpers for dashboard filters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class ResolvedDateRange:
    since: str
    until: str
    days: int
    label: str


def _fmt(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def resolve_date_range(
    range_val: str,
    *,
    custom_since: Optional[str] = None,
    custom_until: Optional[str] = None,
) -> ResolvedDateRange:
    """Map a preset or custom range to since/until strings and day count."""
    today = date.today()

    if range_val == "today":
        since = until = today
        label = "Today"
    elif range_val == "yesterday":
        day = today - timedelta(days=1)
        since = until = day
        label = "Yesterday"
    elif range_val == "custom":
        since_d = _parse_date(custom_since)
        until_d = _parse_date(custom_until)
        if not since_d or not until_d:
            since_d = today - timedelta(days=29)
            until_d = today
            label = "Last 30 days"
        elif since_d > until_d:
            since_d, until_d = until_d, since_d
            label = f"{_fmt(since_d)} → {_fmt(until_d)}"
        else:
            label = f"{_fmt(since_d)} → {_fmt(until_d)}"
        since, until = since_d, until_d
    elif range_val == "7":
        since = today - timedelta(days=6)
        until = today
        label = "Last 7 days"
    elif range_val == "30":
        since = today - timedelta(days=29)
        until = today
        label = "Last 30 days"
    elif range_val == "60":
        since = today - timedelta(days=59)
        until = today
        label = "Last 60 days"
    elif range_val == "90":
        since = today - timedelta(days=89)
        until = today
        label = "Last 90 days"
    elif range_val == "180":
        since = today - timedelta(days=179)
        until = today
        label = "Last 6 months"
    elif range_val == "365":
        since = today - timedelta(days=364)
        until = today
        label = "Last 1 year"
    else:
        days = max(int(range_val), 1)
        since = today - timedelta(days=days - 1)
        until = today
        label = f"Last {days} days"

    days = (until - since).days + 1
    return ResolvedDateRange(since=_fmt(since), until=_fmt(until), days=days, label=label)


def parse_account_created(value: Optional[str]) -> float:
    """Parse Facebook created_time for sorting (newer = larger timestamp)."""
    if not value:
        return 0.0
    cleaned = value.replace("+0000", "+00:00")
    try:
        if "T" in cleaned:
            return datetime.fromisoformat(cleaned[:25]).timestamp()
        return datetime.strptime(cleaned[:10], "%Y-%m-%d").timestamp()
    except ValueError:
        return 0.0
