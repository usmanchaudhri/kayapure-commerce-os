"""Shared date-range filter used by Ads Performance."""

from datetime import date, timedelta

from shiny import ui

DATE_RANGE_CHOICES = {
    "today": "Today",
    "yesterday": "Yesterday",
    "7": "Last 7 days",
    "30": "Last 30 days",
    "60": "Last 60 days",
    "90": "Last 90 days",
    "180": "Last 6 months",
    "365": "Last 1 year",
    "custom": "Custom range",
}


def date_range_filter(*, select_id: str, custom_output_id: str, selected: str = "30"):
    return ui.div(
        ui.div(
            ui.tags.label("Date range", **{"for": select_id}),
            ui.input_select(
                select_id,
                label=None,
                choices=DATE_RANGE_CHOICES,
                selected=selected,
            ),
            class_="dash-filter-select",
        ),
        ui.output_ui(custom_output_id),
        class_="dash-filter",
    )


def custom_date_fields(*, since_id: str, until_id: str):
    today = date.today()
    month_ago = today - timedelta(days=29)
    return ui.div(
        ui.div(
            ui.tags.label("From", **{"for": since_id}),
            ui.input_date(since_id, label=None, value=month_ago),
            class_="dash-filter-field",
        ),
        ui.div(
            ui.tags.label("To", **{"for": until_id}),
            ui.input_date(until_id, label=None, value=today),
            class_="dash-filter-field",
        ),
        class_="dash-filter-custom",
    )
