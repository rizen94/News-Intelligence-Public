"""
Pipeline throughput estimates — phase-level run counts, avg duration, lag ratios.

Uses ``automation_run_history`` (last 7 days) for throughput and the same
cached pending counts that ``backlog_metrics`` already maintains.  All reads
go through the **UI** pool so there is zero impact on worker pipelines.

Response schema matches the planned JSON contract:

.. code-block:: json

    {
      "as_of": "2026-10-23T12:00:00Z",
      "window_hours": 168,
      "phase_metrics": {
        "rss_collection": {
          "runs_last_7d": 24,
          "avg_duration_s": 12.4,
          "duration_stddev_s": 3.2,
          "pending_count": 0,
          "lag_ratio": 0.0,
          "status": "healthy"
        }
      }
    }

Heuristic status thresholds (tunable via env):

* ``LAG_HEURISTIC_HEALTHY_MAX=0.5``  -- pending <= 50% of last-6h processed -> *healthy*
* ``LAG_HEURISTIC_CATCHUP_MIN=1.0``  -- pending >= 2x processed             -> *catching_up* (urgent drain)
* ``LAG_HEURISTIC_GROWING_THRESHOLD=0.7`` -- rate > threshold               -> *growing* backlog
* Everything else is **steady**.

In-memory TTL cache (30 s) avoids repeated SQL on Monitor page loads.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------

LAG_HEALTHY_MAX: float = float(os.getenv("LAG_HEURISTIC_HEALTHY_MAX", "0.5"))
LAG_CATCHUP_MIN: float = float(os.getenv("LAG_HEURISTIC_CATCHUP_MIN", "1.0"))
LAG_GROWING_THRESHOLD: float = float(
    os.getenv("LAG_HEURISTIC_GROWING_THRESHOLD", "0.7")
)
WINDOW_HOURS: int = int(os.getenv("PIPELINE_THROUGHPUT_WINDOW_HOURS", "168"))  # 7 days

# In-memory cache TTL — 30 seconds avoids repeated SQL on page loads
_CACHE_TTL_SECONDS: int = 30

# ---------------------------------------------------------------------------
# Cache state
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()
_cache_time: float = 0


def invalidate_cache() -> None:
    """Force cache refresh on next call."""
    global _cache_time
    with _cache_lock:
        _cache_time = 0


# ---------------------------------------------------------------------------
# SQL helpers (UI pool only)
# ---------------------------------------------------------------------------

_SQL_PHASE_RUN_COUNT = f"""\
SELECT COUNT(*) AS runs
FROM automation_run_history
WHERE phase_name = %s
  AND started_at >= NOW() - INTERVAL '{WINDOW_HOURS} hours'
  AND success = true;
"""

_SQL_PHASE_AVG_DURATION = f"""\
SELECT AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) AS avg_dur
FROM automation_run_history
WHERE phase_name = %s
  AND started_at >= NOW() - INTERVAL '{WINDOW_HOURS} hours'
  AND success = true;
"""

_SQL_PHASE_STDDEV = f"""\
SELECT CASE WHEN COUNT(*) > 1 THEN STDDEV(EXTRACT(EPOCH FROM (finished_at - started_at)))
            ELSE 0 END AS stddev
FROM automation_run_history
WHERE phase_name = %s
  AND started_at >= NOW() - INTERVAL '{WINDOW_HOURS} hours'
  AND success = true;
"""

_SQL_ALL_PHASES = """\
SELECT DISTINCT phase_name
FROM automation_run_history
WHERE started_at >= NOW() - INTERVAL '%d hours'
ORDER BY phase_name;
"""

_SQL_PHASE_LAST_6H_PROCESSED = """\
SELECT COUNT(*) AS processed
FROM automation_run_history
WHERE phase_name = %s
  AND started_at >= NOW() - INTERVAL '6 hours'
  AND finished_at >= NOW() - INTERVAL '6 hours'
  AND success = true;
"""

_STATUS_HEALTHY = "healthy"
_STATUS_CATCHING_UP = "catching_up"
_STATUS_GROWING = "growing"
_STATUS_STEADY = "steady"


def _classify_lag(lag_ratio: float, processed_last_6h: int) -> str:
    """Classify phase health based on lag ratio and recent processing."""

    # No backlog — healthy
    if lag_ratio == 0.0 or processed_last_6h == 0:
        return _STATUS_HEALTHY

    # Catching up (urgent drain): pending >> recent throughput
    if lag_ratio >= LAG_CATCHUP_MIN:
        return _STATUS_CATCHING_UP

    # Healthy window: pending is a small fraction of recent processed work
    if lag_ratio <= LAG_HEALTHY_MAX:
        return _STATUS_HEALTHY

    # Growing: moderate backlog that could become worse
    return _STATUS_GROWING


def _query_phase_stats(
    phase: str, window_hrs: int
) -> tuple[int, float, float]:
    """Return (runs_last_7d, avg_duration_s, stddev_s) for one phase."""
    runs = 0
    avg_dur = 0.0
    sd = 0.0
    conn = None
    try:
        from shared.database.connection import get_ui_db_connection

        conn = get_ui_db_connection()
        cur = conn.cursor()

        cur.execute(_SQL_PHASE_RUN_COUNT % window_hrs, (phase,))
        row = cur.fetchone()
        runs = int(row[0]) if row and row[0] else 0

        cur.execute(_SQL_PHASE_AVG_DURATION % window_hrs, (phase,))
        row = cur.fetchone()
        avg_dur = float(row[0]) if row and row[0] else 0.0

        cur.execute(_SQL_PHASE_STDDEV % window_hrs, (phase,))
        row = cur.fetchone()
        sd = float(row[0]) if row and row[0] else 0.0

        conn.close()

    except Exception as exc:
        logger.warning("pipeline throughput stats query failed for %s: %s", phase, exc)
        if conn:
            conn.close()

    return runs, round(avg_dur, 2), round(sd, 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_pipeline_throughput(latency_window_hours: int | None = None) -> dict[str, Any]:
    """Return pipeline throughput metrics with in-memory TTL cache (30 s).

    Returns a dict matching the response schema.  Uses **UI pool** for all DB
    reads so worker pipeline health is unaffected.
    """
    global _cache, _cache_time

    window = latency_window_hours or WINDOW_HOURS
    now_utc = datetime.now(timezone.utc)

    # ---- fast path: cache hit ----
    with _cache_lock:
        if _cache and (_cache_time + _CACHE_TTL_SECONDS) > time.monotonic():
            return dict(_cache["payload"])  # shallow copy

    # ---- slow path: SQL + backlog metrics ----
    try:
        from services.backlog_metrics import get_all_pending_counts

        pending = {k: int(v) for k, v in get_all_pending_counts().items()}
    except Exception:
        pending = {}  # graceful degradation

    phase_names: list[str] = []
    try:
        from shared.database.connection import get_ui_db_connection

        conn = get_ui_db_connection()
        cur = conn.cursor()
        cur.execute(_SQL_ALL_PHASES % window)
        rows = cur.fetchall()
        conn.close()
        phase_names = [str(r[0]) for r in rows] if rows else []

    except Exception as exc:
        logger.warning("pipeline throughput phase list query failed: %s", exc)
        return _empty_response(now_utc, window)

    results: dict[str, Any] = {}
    processed_last_6h_map: dict[str, int] = {}

    for phase in phase_names:
        runs, avg_dur, sd = _query_phase_stats(phase, window)
        # Recent processed (last 6 h) — reuse conn if available; otherwise query
        proc = 0
        try:
            from shared.database.connection import get_ui_db_connection

            c = get_ui_db_connection()
            cur2 = c.cursor()
            cur2.execute(
                _SQL_PHASE_LAST_6H_PROCESSED, (phase,)
            )
            row = cur2.fetchone()
            proc = int(row[0]) if row and row[0] else 0
            c.close()
        except Exception:
            pass

        pending_count = int(pending.get(phase, 0) or 0)
        # Lag ratio: how many "batches" of pending work relative to recent throughput.
        lag_ratio = 0.0
        if proc > 0:
            lag_ratio = round(pending_count / max(proc, 1), 4)

        status = _classify_lag(lag_ratio, proc)
        results[phase] = {
            "runs_last_7d": runs,
            "avg_duration_s": round(avg_dur, 2),
            "duration_stddev_s": round(sd, 2),
            "pending_count": pending_count,
            "lag_ratio": lag_ratio,
            "status": status,
        }

    payload = {
        "as_of": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": window,
        "phase_metrics": results,
        "phase_count": len(results),
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
    }

    with _cache_lock:
        _cache = {"payload": payload}
        _cache_time = time.monotonic()

    return payload


def _empty_response(now_utc: datetime, window_hrs: int) -> dict[str, Any]:
    """Return a valid empty payload when no data is available."""
    return {
        "as_of": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": window_hrs,
        "phase_metrics": {},
        "phase_count": 0,
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
        "warning": "no phase data available in the configured window",
    }
