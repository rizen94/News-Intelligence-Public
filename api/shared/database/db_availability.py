"""
Lightweight DB reachability for automation scheduling.

When PostgreSQL is unreachable, the automation manager can pause scheduling new phases
(except `pending_db_flush`) so workers do not burn CPU/LLM on work that cannot persist.

Env:
  AUTOMATION_PAUSE_WHEN_DB_DOWN — default "true"
  DB_HEALTH_CACHE_SECONDS — default "8" (avoid SELECT 1 every scheduler tick)
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional, Tuple

_lock = threading.Lock()
_cached: Tuple[float, bool] = (0.0, True)


def is_automation_db_ready() -> bool:
    """
    Return True if DB appears reachable (cached for a few seconds).
    Used by automation scheduler; not a substitute for transaction-level error handling.
    """
    global _cached

    if os.getenv("AUTOMATION_PAUSE_WHEN_DB_DOWN", "true").lower() not in ("1", "true", "yes"):
        return True

    try:
        ttl = float(os.getenv("DB_HEALTH_CACHE_SECONDS", "8"))
    except ValueError:
        ttl = 8.0

    now = time.monotonic()
    with _lock:
        ts, ok = _cached
        if now - ts < ttl:
            return ok

    ok = _probe_db()
    with _lock:
        _cached = (now, ok)
    return ok


def _probe_db() -> bool:
    """
    Server reachability only — **not** the pooled checkout used by normal work.
    Prevents mistaking pool exhaustion (timeout waiting for a free connection) for DB down.
    """
    try:
        from shared.database.connection import probe_database_server_reachable

        return probe_database_server_reachable()
    except Exception:
        return False


def invalidate_db_health_cache() -> None:
    """Call after successful flush so the next tick re-probes immediately."""
    global _cached
    with _lock:
        _cached = (0.0, True)
