"""App shell handlers — main nav drawer routing."""

from shiny import Inputs, Outputs, Session, reactive, ui

_NAV_BUTTONS = {
    "nav_dashboard": "dashboard",
    "nav_profit_leak_scanner": "profit_leak_scanner",
    "nav_daily_diagnosis": "daily_diagnosis",
    "nav_creative_intelligence": "creative_intelligence",
    "nav_funnel_reconciliation": "funnel_reconciliation",
    "nav_supplement_economics": "supplement_economics",
    "nav_ai_reports": "ai_reports",
    "nav_saleor_mcp": "saleor_mcp",
    "nav_ingredient_research": "ingredient_research",
    "nav_postex": "postex",
}


def _make_nav_handler(panel_id: str, session: Session):
    async def _go():
        ui.update_navset("main_nav", selected=panel_id)
        await session.send_custom_message("nav_activated", {"id": panel_id})

    return _go


def register(input: Inputs, output: Outputs, session: Session) -> None:
    for button_id, panel_id in _NAV_BUTTONS.items():
        handler = _make_nav_handler(panel_id, session)

        @reactive.effect
        @reactive.event(getattr(input, button_id))
        async def _on_nav(_handler=handler):
            await _handler()

    @reactive.effect
    @reactive.event(input.refresh)
    def _invalidate_meta_caches_on_refresh():
        """Force fresh Graph data after an explicit Refresh click."""
        from services.meta_api_cache import (
            ACCOUNT_LIST_CACHE,
            ACCOUNT_SPEND_CACHE,
            CAMPAIGN_PAYLOAD_CACHE,
        )

        ACCOUNT_LIST_CACHE.invalidate()
        ACCOUNT_SPEND_CACHE.invalidate()
        CAMPAIGN_PAYLOAD_CACHE.invalidate()
