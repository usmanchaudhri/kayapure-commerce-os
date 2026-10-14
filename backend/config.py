"""
KayaPure Commerce OS - Configuration Module
Manages all environment variables and application settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables (override=True ensures .env values take precedence
# over system environment variables like the webdev DATABASE_URL)
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class Settings:
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://kayapure:kayapure123@localhost:5432/kayapure_db",
    )
    DATABASE_URL_ASYNC: str = os.getenv(
        "DATABASE_URL_ASYNC",
        "postgresql+asyncpg://kayapure:kayapure123@localhost:5432/kayapure_db",
    )

    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    STRATEGY_MODEL: str = os.getenv("STRATEGY_MODEL", "gpt-4.1-mini")
    PARSING_MODEL: str = os.getenv("PARSING_MODEL", "gpt-4.1-nano")
    LLM_BASE_MODEL: str = os.getenv("LLM_BASE_MODEL", "gemini-3.1-pro-preview")
    LLM_BASE_MODEL_API_KEY: str = os.getenv("LLM_BASE_MODEL_API_KEY", "")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "kayapure-secret-key")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "kayapure-encryption-key-32bytes!")

    # Firecracker
    FIRECRACKER_MOCK: bool = os.getenv("FIRECRACKER_MOCK", "true").lower() == "true"
    VM_BOOT_TIME_MS: int = int(os.getenv("VM_BOOT_TIME_MS", "125"))
    VM_SNAPSHOT_PATH: str = os.getenv("VM_SNAPSHOT_PATH", "/tmp/firecracker/snapshots")

    # API Keys (legacy direct integrations)
    SHOPIFY_API_KEY: str = os.getenv("SHOPIFY_API_KEY", "mock_shopify_key")
    META_ADS_API_KEY: str = os.getenv("META_ADS_API_KEY", "mock_meta_ads_api_key")
    AMAZON_SP_API_KEY: str = os.getenv("AMAZON_SP_API_KEY", "mock_amazon_sp_key")
    FLEXPORT_API_KEY: str = os.getenv("FLEXPORT_API_KEY", "mock_flexport_key")

    # Facebook Marketing API (Graph API v21.0)
    # Authentication: Long-Lived User Access Token (60-day validity)
    # Get yours at: https://developers.facebook.com/tools/explorer/
    FACEBOOK_ACCESS_TOKEN: str = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
    META_ADS_ACCOUNT_ID: str = os.getenv("META_ADS_ACCOUNT_ID", "")

    # Facebook API toggle: when True and token is set, use live API; otherwise mock
    FACEBOOK_ADS_ENABLED: bool = os.getenv("FACEBOOK_ADS_ENABLED", "false").lower() == "true"

    # LangSmith Tracing
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "kayapure-commerce-os")
    LANGSMITH_TRACING_ENABLED: bool = os.getenv("LANGSMITH_TRACING_V2", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")

    # Feature Flags — comma-separated list of enabled data sources
    # Valid values: marketing, commerce, logistics, dwh, vm, diagnostic
    # Example: ENABLED_SOURCES=marketing,commerce,dwh
    ENABLED_SOURCES_RAW: str = os.getenv("ENABLED_SOURCES", "marketing,commerce,logistics,dwh,vm,diagnostic")

    @property
    def enabled_sources(self) -> set:
        """Parse ENABLED_SOURCES into a set of lowercase source names."""
        return {s.strip().lower() for s in self.ENABLED_SOURCES_RAW.split(",") if s.strip()}

    def is_source_enabled(self, source: str) -> bool:
        """Check if a specific data source is enabled."""
        return source.lower() in self.enabled_sources

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:3001"]

    @property
    def facebook_ads_ready(self) -> bool:
        """Check if Facebook Ads API is fully configured and enabled."""
        return (
            self.FACEBOOK_ADS_ENABLED
            and bool(self.FACEBOOK_ACCESS_TOKEN)
            and bool(self.META_ADS_ACCOUNT_ID)
        )

    # WhatsApp Cloud API
    WHATSAPP_ENABLED: bool = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

    @property
    def whatsapp_ready(self) -> bool:
        return (
            self.WHATSAPP_ENABLED
            and bool(self.WHATSAPP_ACCESS_TOKEN)
            and bool(self.WHATSAPP_PHONE_NUMBER_ID)
        )

    # Apify
    APIFY_TOKEN: str = os.getenv("APIFY_TOKEN", "")
    APIFY_AMAZON_REVIEWS_ACTOR: str = os.getenv(
        "APIFY_AMAZON_REVIEWS_ACTOR", "junglee~amazon-reviews-scraper"
    )
    APIFY_AMAZON_CATALOG_ACTOR: str = os.getenv(
        "APIFY_AMAZON_CATALOG_ACTOR", "junglee~amazon-crawler"
    )
    APIFY_WEBHOOK_SECRET: str = os.getenv("APIFY_WEBHOOK_SECRET", "")
    APIFY_PUBLIC_BASE_URL: str = os.getenv("APIFY_PUBLIC_BASE_URL", "http://127.0.0.1:8000")

    @property
    def apify_ready(self) -> bool:
        return bool(self.APIFY_TOKEN)

    @property
    def apify_webhook_url(self) -> str:
        base = (self.APIFY_PUBLIC_BASE_URL or "http://127.0.0.1:8000").rstrip("/")
        return f"{base}/webhooks/apify"

    # Saleor MCP (https://mcp.saleor.app/)
    # Point SALEOR_MCP_URL at a local `uv run saleor-mcp` or hosted https://mcp.saleor.app/mcp
    SALEOR_MCP_URL: str = os.getenv("SALEOR_MCP_URL", "http://127.0.0.1:6000/mcp")
    SALEOR_API_URL: str = os.getenv("SALEOR_API_URL", "")
    SALEOR_AUTH_TOKEN: str = os.getenv("SALEOR_AUTH_TOKEN", "")

    # PostEx COD Merchant API (https://www.postex.pk/)
    POSTEX_TOKEN: str = os.getenv("POSTEX_TOKEN", "")
    POSTEX_BASE_URL: str = os.getenv(
        "POSTEX_BASE_URL",
        "https://api.postex.pk/services/integration/api/order/v1",
    )
    # Optional — shown on CPR PDF Contact Details (portal shows merchant email)
    POSTEX_MERCHANT_EMAIL: str = os.getenv(
        "POSTEX_MERCHANT_EMAIL",
        "info@kayapuressence.com",
    )
    # Order sync / sales consolidation
    POSTEX_SYNC_SINCE: str = os.getenv("POSTEX_SYNC_SINCE", "2024-01-01")
    POSTEX_SYNC_LOOKBACK_DAYS: int = int(os.getenv("POSTEX_SYNC_LOOKBACK_DAYS", "30"))
    POSTEX_SYNC_CHUNK_DAYS: int = int(os.getenv("POSTEX_SYNC_CHUNK_DAYS", "14"))
    POSTEX_SYNC_ON_STARTUP: bool = os.getenv("POSTEX_SYNC_ON_STARTUP", "true").lower() in (
        "1",
        "true",
        "yes",
    )

    # Ingredient research agent (CAMEL Workforce — Agent #1)
    # Prefer GOOGLE_API_KEY for CAMEL ModelFactory; fall back to LLM_BASE_MODEL_API_KEY.
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "") or os.getenv(
        "LLM_BASE_MODEL_API_KEY", ""
    )
    NCBI_API_KEY: str = os.getenv("NCBI_API_KEY", "")
    INGREDIENT_RESEARCH_DEFAULT_LIMIT: int = int(
        os.getenv("INGREDIENT_RESEARCH_DEFAULT_LIMIT", "30")
    )
    INGREDIENT_RESEARCH_MAX_COMBOS: int = int(
        os.getenv("INGREDIENT_RESEARCH_MAX_COMBOS", "5")
    )
    INGREDIENT_RESEARCH_TIMEOUT_SEC: int = int(
        os.getenv("INGREDIENT_RESEARCH_TIMEOUT_SEC", "600")
    )
    INGREDIENT_RESEARCH_MODEL_PLATFORM: str = os.getenv(
        "INGREDIENT_RESEARCH_MODEL_PLATFORM", "gemini"
    )
    INGREDIENT_RESEARCH_MODEL_TYPE: str = os.getenv(
        "INGREDIENT_RESEARCH_MODEL_TYPE", ""
    ) or os.getenv("LLM_BASE_MODEL", "gemini-2.0-flash")

    @property
    def ingredient_research_ready(self) -> bool:
        """Return True when a Gemini/Google API key is available for CAMEL."""
        return bool(self.GOOGLE_API_KEY or self.LLM_BASE_MODEL_API_KEY)


settings = Settings()
