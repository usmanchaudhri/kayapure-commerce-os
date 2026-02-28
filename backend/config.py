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

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "kayapure-secret-key")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "kayapure-encryption-key-32bytes!")

    # Firecracker
    FIRECRACKER_MOCK: bool = os.getenv("FIRECRACKER_MOCK", "true").lower() == "true"
    VM_BOOT_TIME_MS: int = int(os.getenv("VM_BOOT_TIME_MS", "125"))
    VM_SNAPSHOT_PATH: str = os.getenv("VM_SNAPSHOT_PATH", "/tmp/firecracker/snapshots")

    # API Keys (legacy direct integrations)
    SHOPIFY_API_KEY: str = os.getenv("SHOPIFY_API_KEY", "mock_shopify_key")
    META_ADS_API_KEY: str = os.getenv("META_ADS_API_KEY", "mock_meta_ads_key")
    AMAZON_SP_API_KEY: str = os.getenv("AMAZON_SP_API_KEY", "mock_amazon_sp_key")
    FLEXPORT_API_KEY: str = os.getenv("FLEXPORT_API_KEY", "mock_flexport_key")

    # MCP (Model Context Protocol) Configuration
    # Meta Ads MCP — Pipeboard hosted server
    MCP_META_ADS_URL: str = os.getenv(
        "MCP_META_ADS_URL",
        "https://mcp.pipeboard.co/meta-ads-mcp",
    )
    MCP_META_ADS_TOKEN: str = os.getenv("MCP_META_ADS_TOKEN", "")
    META_ADS_ACCOUNT_ID: str = os.getenv("META_ADS_ACCOUNT_ID", "")

    # MCP mode toggle: when True and token is set, use live MCP; otherwise mock
    MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() == "true"

    # LangSmith Tracing
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "kayapure-commerce-os")
    LANGSMITH_TRACING_ENABLED: bool = os.getenv("LANGSMITH_TRACING_V2", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:3001"]

    @property
    def mcp_meta_ads_ready(self) -> bool:
        """Check if Meta Ads MCP is fully configured and enabled."""
        return (
            self.MCP_ENABLED
            and bool(self.MCP_META_ADS_TOKEN)
            and bool(self.META_ADS_ACCOUNT_ID)
        )


settings = Settings()
