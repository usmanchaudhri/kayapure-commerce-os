"""Shared helpers for growth feature Shiny handlers."""

from shiny import Inputs, ui

from shiny_app.lib.date_ranges import resolve_date_range
from shiny_app.ui.date_range_filter import custom_date_fields


def date_range_from_input(input: Inputs, prefix: str):
    range_val = "30"
    custom_since = None
    custom_until = None
    try:
        range_val = getattr(input, f"{prefix}_date_range")() or "30"
    except Exception:
        range_val = "30"
    if range_val == "custom":
        try:
            custom_since = getattr(input, f"{prefix}_date_since")()
            custom_until = getattr(input, f"{prefix}_date_until")()
        except Exception:
            pass
    return resolve_date_range(range_val, custom_since=custom_since, custom_until=custom_until)


def custom_dates_output(input: Inputs, prefix: str):
    try:
        range_val = getattr(input, f"{prefix}_date_range")()
    except Exception:
        range_val = "30"
    if range_val != "custom":
        return ui.div()
    return custom_date_fields(
        since_id=f"{prefix}_date_since",
        until_id=f"{prefix}_date_until",
    )


def selected_account_id(input: Inputs, prefix: str) -> str | None:
    try:
        selected = getattr(input, f"{prefix}_account")() or "__all__"
        if selected and selected != "__all__":
            return selected
    except Exception:
        pass
    return None


def loading_block(message: str) -> ui.Tag:
    return ui.div(
        ui.div(class_="spinner"),
        ui.div(message, class_="loading-text"),
        class_="loading-spinner",
    )


def error_block(title: str, message: str) -> ui.Tag:
    return ui.div(
        ui.div(title, class_="gf-card-title"),
        ui.div(message, class_="gf-card-sub"),
        class_="gf-card gf-card-error",
    )
