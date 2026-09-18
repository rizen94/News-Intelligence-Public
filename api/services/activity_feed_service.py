"""
Activity feed service — thread-safe in-memory store of current and recent backend activities.
Used by AutomationManager (and optionally RSS/LLM) to expose "what the system is doing"
for the enhanced monitoring UI. Call add_current when starting work, complete when done.
"""

import copy
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
        # Stable phase:* ids are shared across concurrent workers — refcount completions.
        self._stable_phase_refs: dict[str, int] = {}

    @staticmethod
    def _is_stable_phase_id(activity_id: str) -> bool:
        return str(activity_id).startswith("phase:")

    def add_current(self, activity_id: str, message: str, **meta: Any) -> None:
        """Record that an activity has started. Replaces any existing with same id."""
        with self._lock:
            stable = self._is_stable_phase_id(activity_id)
            if stable:
                refs = int(self._stable_phase_refs.get(activity_id, 0) or 0) + 1
                self._stable_phase_refs[activity_id] = refs
                existing = self._current.get(activity_id)
                if existing is not None:
                    existing["message"] = message
                    for key, value in meta.items():
                        if value is not None:
                            existing[key] = value
                    existing["running_instances"] = refs
                    return
            self._current[activity_id] = {
                "id": activity_id,
                "message": message,
                "started_at": datetime.now(timezone.utc).isoformat(),
                **{k: v for k, v in meta.items() if v is not None},
            }
            if stable:
                self._current[activity_id]["running_instances"] = self._stable_phase_refs[activity_id]

    def update_current_progress(
        self,
        activity_id: str,
        *,
        message: str | None = None,
        **meta: Any,
    ) -> None:
        """Update an in-flight activity without resetting started_at."""
        with self._lock:
            entry = self._current.get(activity_id)
            if not entry:
                return
            if message is not None:
                entry["message"] = message
            for key, value in meta.items():
                if value is not None:
                    entry[key] = value
            if self._is_stable_phase_id(activity_id):
                entry["running_instances"] = int(
                    self._stable_phase_refs.get(activity_id, 1) or 1
                )

    def complete(
        self, activity_id: str, success: bool = True, error_message: str | None = None
    ) -> None:
        """Mark activity as done; move from current to recent."""
        with self._lock:
            stable = self._is_stable_phase_id(activity_id)
            refs_before = int(self._stable_phase_refs.get(activity_id, 0) or 0) if stable else 0
            if stable and refs_before > 1:
                self._stable_phase_refs[activity_id] = refs_before - 1
                entry = self._current.get(activity_id)
                if entry is not None:
                    entry["running_instances"] = refs_before - 1
                return

            if stable:
                self._stable_phase_refs.pop(activity_id, None)

            entry = self._current.pop(activity_id, None)
            if not entry:
                return
            entry = copy.deepcopy(entry)
            entry.pop("running_instances", None)
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
            entry["success"] = success
            if error_message:
                entry["error_message"] = error_message
            self._recent.appendleft(entry)

    def reconcile_stale_current(
        self,
        active_by_phase: dict[str, int],
        *,
        grace_seconds: float = 180.0,
        now: datetime | None = None,
    ) -> int:
        """
        Drop in-memory \"current\" rows when AutomationManager reports zero workers for
        that phase and the row is older than grace_seconds (orphaned after hang/restart).
        """
        if not self._current:
            return 0
        now_dt = now or datetime.now(timezone.utc)
        removed = 0
        with self._lock:
            stale_ids: list[str] = []
            for activity_id, entry in self._current.items():
                phase = entry.get("task_name")
                if not isinstance(phase, str) or not phase.strip():
                    continue
                if int(active_by_phase.get(phase.strip(), 0) or 0) > 0:
                    continue
                # NOTE: we intentionally do NOT let a positive stable-phase refcount veto
                # cleanup here. Reaching this point means AutomationManager authoritatively
                # reports zero active workers for this phase, so any remaining refcount is a
                # leaked reference (task cancelled/killed before its finally ran). Honouring it
                # would keep a phantom "running" row alive forever; instead we let the age check
                # below decide and reset the refcount when the row is reconciled.
                started_raw = entry.get("started_at")
                if not started_raw:
                    stale_ids.append(activity_id)
                    continue
                try:
                    raw = str(started_raw).strip()
                    if raw.endswith("Z"):
                        raw = raw[:-1] + "+00:00"
                    started = datetime.fromisoformat(raw)
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    age = (now_dt - started.astimezone(timezone.utc)).total_seconds()
                except Exception:
                    stale_ids.append(activity_id)
                    continue
                if age > grace_seconds:
                    stale_ids.append(activity_id)
            for activity_id in stale_ids:
                entry = self._current.pop(activity_id, None)
                if self._is_stable_phase_id(activity_id):
                    self._stable_phase_refs.pop(activity_id, None)
                if not entry:
                    continue
                entry = copy.deepcopy(entry)
                entry.pop("running_instances", None)
                entry["completed_at"] = now_dt.isoformat()
                entry["success"] = False
                entry["error_message"] = "stale_activity_reconciled"
                self._recent.appendleft(entry)
                removed += 1
        return removed

    def get_snapshot(self, recent_limit: int = 50) -> dict[str, Any]:
        """Return current activities and recent completed (for API)."""
        with self._lock:
            current_list = copy.deepcopy(list(self._current.values()))
            recent_list = copy.deepcopy(list(self._recent)[:recent_limit])
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
