"""Shiny reactive handlers (the `server` side of the dashboard UI)."""

from shiny import Inputs, Outputs, Session

from shiny_app.handlers import (
    ai_reports,
    campaigns,
    creative_intelligence,
    daily_diagnosis,
    dashboard,
    funnel_reconciliation,
    ingredient_research,
    postex,
    profit_leak_scanner,
    saleor_mcp,
    shell,
    supplement_economics,
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    shell.register(input, output, session)
    dashboard.register(input, output, session)
    campaigns.register(input, output, session)
    profit_leak_scanner.register(input, output, session)
    daily_diagnosis.register(input, output, session)
    creative_intelligence.register(input, output, session)
    funnel_reconciliation.register(input, output, session)
    supplement_economics.register(input, output, session)
    ai_reports.register(input, output, session)
    saleor_mcp.register(input, output, session)
    ingredient_research.register(input, output, session)
    postex.register(input, output, session)
