"""Dashboard nav panel — overall ads summary."""

from shiny import ui

from shiny_app.ui.date_range_filter import DATE_RANGE_CHOICES, custom_date_fields


def nav_panel():
    """Build the Overview (all-account totals) main nav panel.

    Returns:
        A Shiny ``nav_panel`` with date filter and summary output.
    """
    return ui.nav_panel(
        "Dashboard",
        ui.div(
            ui.div(
                ui.div("Overview", class_="dash-kicker"),
                ui.tags.h2("All-account totals", class_="dash-title"),
                ui.div(
                    ui.div(
                        ui.tags.label("Date range", **{"for": "dashboard_date_range"}),
                        ui.input_select(
                            "dashboard_date_range",
                            label=None,
                            choices=DATE_RANGE_CHOICES,
                            selected="30",
                        ),
                        class_="dash-filter-select",
                    ),
                    # Keep custom dates mounted so changing them always refreshes.
                    ui.panel_conditional(
                        "input.dashboard_date_range === 'custom'",
                        custom_date_fields(
                            since_id="dashboard_date_since",
                            until_id="dashboard_date_until",
                        ),
                    ),
                    class_="dash-filter",
                ),
                class_="dash-toolbar",
            ),
            ui.output_ui("dashboard_summary"),
            class_="dash-overview",
        ),
        value="dashboard",
    )
