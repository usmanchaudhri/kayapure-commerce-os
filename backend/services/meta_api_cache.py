"""Simple in-memory TTL cache for Meta Marketing API responses."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Optional


class TtlCache:
    """Process-wide TTL cache. Not shared across workers — good enough for one uvicorn process."""

    def __init__(self, default_ttl_seconds: float = 180.0):
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if now >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, prefix: Optional[str] = None) -> int:
        with self._lock:
            if prefix is None:
                count = len(self._store)
                self._store.clear()
                return count
            keys = [k for k in self._store if k.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)
            return len(keys)


# Shared caches used by FacebookAdsClient
ACCOUNT_LIST_CACHE = TtlCache(default_ttl_seconds=300.0)  # 5 min
ACCOUNT_SPEND_CACHE = TtlCache(default_ttl_seconds=180.0)  # 3 min
CAMPAIGN_PAYLOAD_CACHE = TtlCache(default_ttl_seconds=180.0)  # 3 min
