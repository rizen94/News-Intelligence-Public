"""
API Request Tracker — Priority Hierarchy for Web vs ML
When users are actively loading pages, ML/Ollama workers yield to keep responses fast.
"""

import time
import logging
from threading import Lock

logger = logging.getLogger(__name__)

_last_request_at: float = 0.0
_lock = Lock()
_YIELD_WINDOW_SECONDS = 15  # Workers skip ML when API was active within this window


def record_request() -> None:
    """Call from middleware on each API request"""
    global _last_request_at
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
