"""
Activity feed service — thread-safe in-memory store of current and recent backend activities.
Used by AutomationManager (and optionally RSS/LLM) to expose "what the system is doing"
for the enhanced monitoring UI. Call add_current when starting work, complete when done.
"""

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_MAX_RECENT = 100


class ActivityFeedService:
    """Thread-safe store of current and recent activities for monitoring UI."""

    def __init__(self, max_recent: int = _MAX_RECENT):
        self._current: dict[str, dict[str, Any]] = {}
        self._recent: deque = deque(maxlen=max_recent)
        self._lock = threading.Lock()

    def add_current(self, activity_id: str, message: str, **meta: Any) -> None:
        """Record that an activity has started. Replaces any existing with same id."""
        with self._lock:
            self._current[activity_id] = {
                "id": activity_id,
                "message": message,
                "started_at": datetime.now(timezone.utc).isoformat(),
                **{k: v for k, v in meta.items() if v is not None},
            }

    def complete(
        self, activity_id: str, success: bool = True, error_message: str | None = None
    ) -> None:
        """Mark activity as done; move from current to recent."""
        with self._lock:
            entry = self._current.pop(activity_id, None)
            if not entry:
                return
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
            entry["success"] = success
            if error_message:
                entry["error_message"] = error_message
            self._recent.appendleft(entry)

    def get_snapshot(self, recent_limit: int = 50) -> dict[str, Any]:
        """Return current activities and recent completed (for API)."""
        with self._lock:
            current_list = list(self._current.values())
            recent_list = list(self._recent)[:recent_limit]
        return {
            "current": current_list,
            "recent": recent_list,
        }


# Singleton for use by AutomationManager and API
_feed: ActivityFeedService | None = None
_feed_lock = threading.Lock()


def get_activity_feed() -> ActivityFeedService:
    global _feed
    if _feed is None:
        with _feed_lock:
            if _feed is None:
                _feed = ActivityFeedService()
    return _feed
