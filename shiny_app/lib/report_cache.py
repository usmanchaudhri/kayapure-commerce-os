"""In-memory session cache for AI reports.

Reports live only while the user stays on the AI Reports tab.
Leaving the tab (or changing the date range) clears the cache.
"""

import time
from typing import Any, Dict, Optional


class SessionReportCache:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def _key(self, acc_id: str, report_type: str, days: int) -> str:
        return f"{acc_id}|{report_type}|{days}"

    def get(self, acc_id: str, report_type: str, days: int) -> Optional[Dict[str, Any]]:
        return self._store.get(self._key(acc_id, report_type, days))

    def put(self, acc_id: str, report_type: str, days: int, result: dict) -> None:
        self._store[self._key(acc_id, report_type, days)] = {
            "result": result,
            "timestamp": time.time(),
        }

    def clear(self) -> None:
        self._store.clear()
