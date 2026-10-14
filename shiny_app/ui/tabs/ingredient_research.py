"""Ingredient Research Lab nav panel — CAMEL Workforce Agent #1."""

from shiny import ui


def nav_panel():
    """Build the Ingredient Research Lab main nav panel.

    Returns:
        A Shiny ``nav_panel`` with agent inputs, live execution log, and results.
    """
    return ui.nav_panel(
        "Ingredient Lab",
        ui.div(
            ui.div(
                ui.span("R&D · CAMEL Workforce", class_="pls-featured-badge"),
                ui.tags.h3("Ingredient Research Lab"),
                ui.div(
                    "Run the multi-agent research workforce: librarian → PubMed evidence "
                    "scout → synergy analyst → claim guard. Watch live execution, then "
                    "review ranked combination candidates.",
                    class_="subtitle",
                ),
                style="flex: 1;",
            ),
            class_="pls-header",
        ),
        ui.div(
            ui.div(
                ui.input_text_area(
                    "ir_goal",
                    "Health goal",
                    value="adult male vitality and energy support",
                    placeholder="e.g. stress support, immunity, joint comfort",
                    rows=2,
                    width="100%",
                ),
                ui.div(
                    ui.input_select(
                        "ir_format",
                        "Delivery format",
                        choices={
                            "gummy": "Gummy",
                            "powder": "Powder / drink mix",
                            "capsule": "Capsule",
                            "sachet": "Liquid sachet",
                            "drops": "Drops",
                        },
                        selected="gummy",
                        width="100%",
                    ),
                    ui.input_select(
                        "ir_market",
                        "Market / claims context",
                        choices={"PK": "Pakistan (PK)", "US": "United States (US)"},
                        selected="PK",
                        width="100%",
                    ),
                    ui.input_numeric(
                        "ir_max_ingredients",
                        "Max ingredients / combo",
                        value=7,
                        min=2,
                        max=12,
                        width="100%",
                    ),
                    ui.input_numeric(
                        "ir_ingredient_limit",
                        "Research pool size",
                        value=12,
                        min=5,
                        max=40,
                        width="100%",
                    ),
                    class_="ir-controls-grid",
                ),
                ui.input_checkbox_group(
                    "ir_include_tags",
                    "Catalog tags to include",
                    choices={
                        "highlighted": "Highlighted (priority marks)",
                        "seven_in_one_family": "7-in-1 Shilajit family",
                    },
                    selected=["highlighted", "seven_in_one_family"],
                    inline=True,
                ),
                ui.input_text(
                    "ir_exclude",
                    "Exclude ingredients (comma-separated)",
                    value="Yohimbine, Senna Leaf, St John Wort",
                    width="100%",
                ),
                ui.input_text_area(
                    "ir_explicit",
                    "Force-include ingredients (optional, one per line)",
                    value="",
                    placeholder="Shilajit (Asphaltum Punjabianum)\nAshwagandha (Withania Somnifera)",
                    rows=3,
                    width="100%",
                ),
                ui.div(
                    ui.input_action_button(
                        "ir_run",
                        "Run research agents",
                        class_="btn-primary pls-scan-btn",
                    ),
                    ui.output_ui("ir_status_badge"),
                    class_="ir-run-row",
                ),
                class_="pls-controls ir-controls",
            ),
            class_="ir-layout-top",
        ),
        ui.div(
            ui.div(
                ui.div("Live agent execution", class_="gf-card-title"),
                ui.div(
                    "Workforce task assignment, worker starts/completions, and stream "
                    "snippets — so you can see how results were produced.",
                    class_="gf-card-sub",
                ),
                ui.output_ui("ir_live_log"),
                class_="gf-card ir-live-card",
            ),
            ui.div(
                ui.div("Results", class_="gf-card-title"),
                ui.output_ui("ir_results"),
                class_="gf-card ir-results-card",
            ),
            class_="ir-layout-bottom",
        ),
        value="ingredient_research",
    )
