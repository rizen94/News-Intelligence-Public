"""
API Request Tracker — Priority Hierarchy for Web vs ML
When users are actively loading pages, ML/Ollama workers yield to keep responses fast.
High-frequency polling (Monitor, health, status) does NOT count as "user active" so
Ollama/GPU can run; only non-polling requests trigger the yield window.
"""

import time
import logging
from threading import Lock

logger = logging.getLogger(__name__)

_last_request_at: float = 0.0
_lock = Lock()
_YIELD_WINDOW_SECONDS = 15  # Workers skip ML when API was active within this window

# Paths that are polled every few seconds (Monitor, health, status). We do NOT record these
# so that having the Monitor open doesn't block ML/Ollama. Only "real" user actions trigger yield.
_POLLING_PATH_SUBSTRINGS = (
    "/api/system_monitoring/",  # All Monitor dashboard endpoints (overview, automation, pipeline, etc.)
    "/automation/status",
    "/monitoring/overview",
    "/pipeline_status",
    "/sources_collected",
    "/process_run_summary",
    "/orchestrator/dashboard",
    "/orchestrator/status",
    "/health",
    "/status",
    "/database/stats",
    "/devices",
    "/health/feeds",
)


def record_request(path: str | None = None) -> None:
    """
    Call from middleware on each API request.
    If path is provided and is a known polling endpoint, we do not update last_request_at,
    so ML workers are not blocked when the user only has status/Monitor open.
    """
    global _last_request_at
    if path:
        path_lower = (path.split("?")[0] or "").lower()
        if any(sub in path_lower for sub in _POLLING_PATH_SUBSTRINGS):
            return
    with _lock:
        _last_request_at = time.monotonic()


def should_yield_to_api() -> bool:
    """
    Returns True if ML workers should skip processing this cycle.
    Web page loads take priority — workers yield when API is recently active.
    """
    with _lock:
        if _last_request_at == 0:
            return False
        elapsed = time.monotonic() - _last_request_at
        return elapsed < _YIELD_WINDOW_SECONDS


def get_seconds_since_last_request() -> float:
    """For debugging/metrics"""
    with _lock:
        if _last_request_at == 0:
            return float("inf")
        return time.monotonic() - _last_request_at
