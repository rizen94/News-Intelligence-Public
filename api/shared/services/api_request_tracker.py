"""
API Request Tracker — Priority Hierarchy for Web vs ML

Web UI and monitoring are independent of the data pipeline:
- The website and health/status endpoints always respond with currently available data;
  they never wait for background processing (automation, enrichment, entity extraction).
- Pipeline tasks run in their own workers; they may yield when the user loads a page
  (non-polling request) so the UI stays responsive.

When users are actively loading pages, ML/Ollama workers yield to keep responses fast.
High-frequency polling (Monitor, health, status) does NOT count as "user active" so
Ollama/GPU can run; only non-polling requests trigger the yield window.

Yield signal is still a **coarse proxy** (not a true accept-queue depth). It combines:
- in-flight non-polling HTTP requests, and
- a short recency window after the last such request.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_last_request_at: float = 0.0
_inflight_user_requests: int = 0
_yield_hits: int = 0
_lock = Lock()


def _yield_window_seconds() -> float:
    try:
        return max(1.0, float(os.environ.get("API_YIELD_WINDOW_SECONDS", "15")))
    except ValueError:
        return 15.0


# Paths that are polled frequently (Monitor, health, status, backlog). We do NOT record these
# as "user active" so that having the Monitor open doesn't block the pipeline. Only "real"
# user actions (e.g. opening a domain page, editing a storyline) trigger yield.
_POLLING_PATH_SUBSTRINGS = (
    "/api/system_monitoring/",  # All Monitor: overview, automation, pipeline, health, backlog, etc.
    "/automation/status",
    "/monitoring/overview",
    "/pipeline_status",
    "/sources_collected",
    "/process_run_summary",
    "/backlog_status",
    "/fast_stats",
    "/orchestrator/dashboard",
    "/orchestrator/status",
    "/health",
    "/status",
    "/database/stats",
    "/devices",
    "/health/feeds",
)


def _is_polling_path(path: str | None) -> bool:
    if not path:
        return False
    path_lower = (path.split("?")[0] or "").lower()
    return any(sub in path_lower for sub in _POLLING_PATH_SUBSTRINGS)


def record_request(path: str | None = None) -> None:
    """
    Call from middleware on each API request.
    If path is a known polling endpoint, we do not update last_request_at,
    so ML workers are not blocked when the user only has status/Monitor open.
    """
    global _last_request_at
    if _is_polling_path(path):
        return
    with _lock:
        _last_request_at = time.monotonic()


def begin_request(path: str | None = None) -> tuple[float, bool]:
    """
    Middleware entry: record non-polling activity and return ``(start, counted)``
    for end_request pairing. ``counted`` is True when this request affects yield.
    """
    global _inflight_user_requests
    counted = not _is_polling_path(path)
    record_request(path)
    if counted:
        with _lock:
            _inflight_user_requests += 1
    return time.monotonic(), counted


def end_request(token: float | tuple[float, bool] | None = None, *, timed_out: bool = False) -> None:
    """Middleware exit: decrement in-flight user request count when applicable."""
    global _inflight_user_requests
    del timed_out  # reserved for future load accounting
    counted = False
    if isinstance(token, tuple) and len(token) == 2:
        counted = bool(token[1])
    if counted:
        with _lock:
            _inflight_user_requests = max(0, _inflight_user_requests - 1)


def should_yield_to_api() -> bool:
    """
    Returns True if ML workers should skip/defer this cycle.

    True when any non-polling request is in flight, or the last one finished
    within ``API_YIELD_WINDOW_SECONDS`` (default 15).
    """
    global _yield_hits
    with _lock:
        if _inflight_user_requests > 0:
            _yield_hits += 1
            return True
        if _last_request_at == 0:
            return False
        elapsed = time.monotonic() - _last_request_at
        if elapsed < _yield_window_seconds():
            _yield_hits += 1
            return True
        return False


def http_load_should_defer_work() -> bool:
    """Alias used by automation: defer heavy work while the UI is active."""
    return should_yield_to_api()


def get_seconds_since_last_request() -> float:
    """Seconds since last non-polling request (inf if never)."""
    with _lock:
        if _last_request_at == 0:
            return float("inf")
        return time.monotonic() - _last_request_at


def get_api_yield_snapshot() -> dict[str, Any]:
    """Operator/Monitor snapshot of the coarse yield proxy."""
    with _lock:
        inflight = _inflight_user_requests
        last = _last_request_at
        hits = _yield_hits
    window = _yield_window_seconds()
    if last == 0:
        since = None
        yielding = inflight > 0
    else:
        since = time.monotonic() - last
        yielding = inflight > 0 or since < window
    return {
        "yielding": yielding,
        "inflight_user_requests": inflight,
        "seconds_since_last_user_request": since,
        "yield_window_seconds": window,
        "yield_hits": hits,
        "note": (
            "Coarse proxy (inflight + recency window), not accept-queue depth. "
            "Polling Monitor/health paths are excluded."
        ),
    }
