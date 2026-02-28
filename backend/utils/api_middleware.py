"""
KayaPure Commerce OS - API Logging Middleware

Provides FastAPI middleware that:
  1. Assigns a correlation ID to every request
  2. Logs request start/end with timing
  3. Logs errors with full context
  4. Adds correlation ID to response headers for frontend debugging
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.logging_config import get_logger, set_correlation_id

logger = get_logger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every API request with timing and correlation IDs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or extract correlation ID
        cid = request.headers.get("X-Correlation-ID", f"req-{uuid.uuid4().hex[:12]}")
        set_correlation_id(cid)

        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        logger.info(
            f"→ {method} {path}" + (f"?{query}" if query else ""),
            extra={
                "http_method": method,
                "path": path,
                "query": query,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "")[:100],
            },
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = cid

            log_fn = logger.info if response.status_code < 400 else logger.warning
            if response.status_code >= 500:
                log_fn = logger.error

            log_fn(
                f"← {method} {path} → {response.status_code} ({elapsed:.1f}ms)",
                extra={
                    "http_method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed, 1),
                },
            )

            return response

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"✗ {method} {path} → EXCEPTION ({elapsed:.1f}ms): {e}",
                extra={
                    "http_method": method,
                    "path": path,
                    "duration_ms": round(elapsed, 1),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise
