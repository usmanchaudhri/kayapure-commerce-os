"""
KayaPure Commerce OS - Structured Logging Configuration

Provides:
  1. JSON-formatted file logging (logs/kayapure.log) with rotation
  2. Human-readable colored console logging
  3. Component-specific loggers (mcp, agent, api, workflow, marketing, etc.)
  4. Request correlation IDs for tracing requests across components
  5. Performance timing decorators

Log files are written to: backend/logs/
  - kayapure.log       → All logs (JSON, rotated at 5MB, 5 backups)
  - mcp.log            → MCP-specific logs (tool calls, responses, errors)
  - agent.log          → LangGraph workflow logs (node execution, state transitions)
  - api.log            → HTTP request/response logs

Usage:
  from utils.logging_config import get_logger, log_timing, set_correlation_id
  logger = get_logger("mcp")
  logger.info("Connected to Meta Ads MCP", extra={"tools": 46})
"""

import json
import logging
import logging.handlers
import os
import sys
import time
import uuid
import contextvars
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional

# ============================================
# Correlation ID for request tracing
# ============================================
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set a correlation ID for the current context. Returns the ID."""
    cid = cid or f"req-{uuid.uuid4().hex[:12]}"
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return _correlation_id.get()


# ============================================
# JSON Log Formatter
# ============================================
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log analysis."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if present
        cid = get_correlation_id()
        if cid:
            log_entry["correlation_id"] = cid

        # Add extra fields (passed via logger.info("msg", extra={...}))
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "module",
            "filename", "levelno", "levelname", "pathname", "process",
            "processName", "thread", "threadName", "msecs", "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                try:
                    json.dumps(value)  # Ensure serializable
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, default=str)


# ============================================
# Colored Console Formatter
# ============================================
class ColoredFormatter(logging.Formatter):
    """Human-readable colored console output for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    COMPONENT_COLORS = {
        "kayapure.mcp": "\033[96m",       # Bright Cyan
        "kayapure.agent": "\033[95m",     # Bright Magenta
        "kayapure.api": "\033[94m",       # Bright Blue
        "kayapure.workflow": "\033[93m",  # Bright Yellow
        "kayapure.marketing": "\033[92m", # Bright Green
        "kayapure.startup": "\033[97m",   # Bright White
    }

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.COLORS.get(record.levelname, "")
        comp_color = self.COMPONENT_COLORS.get(record.name, self.DIM)

        # Short component name
        short_name = record.name.replace("kayapure.", "")

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        cid = get_correlation_id()
        cid_str = f" {self.DIM}[{cid[:12]}]{self.RESET}" if cid else ""

        return (
            f"{self.DIM}{timestamp}{self.RESET} "
            f"{level_color}{record.levelname:<7}{self.RESET} "
            f"{comp_color}[{short_name}]{self.RESET}"
            f"{cid_str} "
            f"{record.getMessage()}"
        )


# ============================================
# Setup Logging
# ============================================
_initialized = False


def setup_logging(
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> None:
    """
    Initialize the logging system with file and console handlers.

    Creates:
      - logs/kayapure.log  (all logs, JSON format, rotating)
      - logs/mcp.log       (MCP-specific, JSON format, rotating)
      - logs/agent.log     (Agent/workflow, JSON format, rotating)
      - logs/api.log       (API requests, JSON format, rotating)
      - Console output     (colored, human-readable)
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Root kayapure logger
    root_logger = logging.getLogger("kayapure")
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False

    # ---- Console Handler (colored, human-readable) ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)

    # ---- Main Log File (all logs, JSON) ----
    main_handler = logging.handlers.RotatingFileHandler(
        log_path / "kayapure.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8",
    )
    main_handler.setLevel(file_level)
    main_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(main_handler)

    # ---- Component-Specific Log Files ----
    component_files = {
        "kayapure.mcp": "mcp.log",
        "kayapure.mcp_client": "mcp.log",
        "kayapure.marketing": "mcp.log",
        "kayapure.agent": "agent.log",
        "kayapure.workflow": "agent.log",
        "kayapure.api": "api.log",
        "kayapure.startup": "api.log",
    }

    for logger_name, filename in component_files.items():
        comp_logger = logging.getLogger(logger_name)
        comp_logger.setLevel(logging.DEBUG)

        file_handler = logging.handlers.RotatingFileHandler(
            log_path / filename,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(JSONFormatter())
        comp_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ============================================
# Logger Factory
# ============================================
def get_logger(component: str) -> logging.Logger:
    """
    Get a component-specific logger.

    Usage:
      logger = get_logger("mcp")          → kayapure.mcp
      logger = get_logger("workflow")      → kayapure.workflow
      logger = get_logger("api")           → kayapure.api
    """
    name = f"kayapure.{component}" if not component.startswith("kayapure.") else component
    return logging.getLogger(name)


# ============================================
# Performance Timing Decorator
# ============================================
def log_timing(component: str, operation: str):
    """
    Decorator that logs execution time of async functions.

    Usage:
      @log_timing("mcp", "call_tool")
      async def call_tool(self, tool_name, arguments):
          ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(component)
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                logger.info(
                    f"{operation} completed in {elapsed:.1f}ms",
                    extra={"operation": operation, "duration_ms": round(elapsed, 1)},
                )
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{operation} failed after {elapsed:.1f}ms: {e}",
                    extra={"operation": operation, "duration_ms": round(elapsed, 1), "error": str(e)},
                    exc_info=True,
                )
                raise
        return wrapper
    return decorator


# ============================================
# LangSmith Tracing Setup
# ============================================
def setup_langsmith_tracing() -> bool:
    """
    Configure LangSmith tracing if environment variables are set.

    Required env vars:
      LANGSMITH_API_KEY     - Your LangSmith API key
      LANGSMITH_PROJECT     - Project name (default: "kayapure-commerce-os")

    Optional:
      LANGSMITH_ENDPOINT    - Custom endpoint (default: https://api.smith.langchain.com)

    Returns True if tracing was enabled, False otherwise.
    """
    logger = get_logger("startup")

    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        logger.info(
            "LangSmith tracing DISABLED — set LANGSMITH_API_KEY in .env to enable. "
            "Get a free key at https://smith.langchain.com"
        )
        return False

    # Set the environment variables LangChain expects
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "kayapure-commerce-os")

    endpoint = os.getenv("LANGSMITH_ENDPOINT", "")
    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    logger.info(
        f"LangSmith tracing ENABLED — project: {os.environ['LANGCHAIN_PROJECT']}",
        extra={
            "langsmith_project": os.environ["LANGCHAIN_PROJECT"],
            "langsmith_endpoint": os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
        },
    )
    return True
