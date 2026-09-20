"""
KayaPure Commerce OS — Shiny Dashboard (Meta Ads)
Embedded in FastAPI via ASGI mount at /dashboard.

- Profit Leak Scanner: deterministic funnel leak detection ranked by impact
- Ads Performance: per-account reports, campaign dropdowns, and campaign actions
"""

from shiny import App

from shiny_app.handlers import server
from shiny_app.ui import build_app_ui

app_ui = build_app_ui()

# App instance (mounted by FastAPI at /dashboard; also runnable via `shiny run`)
shiny_app = App(app_ui, server)
# `shiny run` looks for an attribute named `app` by default
app = shiny_app
