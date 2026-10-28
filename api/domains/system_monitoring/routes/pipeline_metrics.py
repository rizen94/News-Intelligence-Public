"""
Pipeline throughput metrics endpoint — ``GET /api/system_monitoring/pipeline_metrics``

Lightweight estimates of phase-level throughput, latency, and backlog lag ratios.
All reads go through the UI pool (zero worker pressure) backed by a 30 s in-memory cache.

Query params:
    latency (bool, optional): when true, include duration stats (avg/stddev). Defaults to ``true``.
    window_hours (int, optional): override the 7-day analysis window (min 1).
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/system_monitoring/pipeline_metrics",
    tags=["System Monitoring"],
)


@router.get("")
def get_pipeline_metrics(
    latency: bool = Query(True, description="Include duration stats (avg/stddev). Defaults to true."),
    window_hours: int | None = Query(None, ge=1, le=720, description="Override 7-day analysis window in hours."),
) -> dict:
    """Return pipeline throughput metrics per automation phase."""

    try:
        from services.pipeline_throughput import (
            _empty_response,
            get_pipeline_throughput,
        )

        now_utc = datetime.now(timezone.utc)

        if not latency and window_hours is None:
            # Minimal path: pending + lag only.
            try:
                from services.pipeline_throughput import (
                    WINDOW_HOURS,
                    _SQL_ALL_PHASES,
                    _query_phase_stats,
                    _classify_lag,
                )
                from services.backlog_metrics import get_all_pending_counts

                pending = {k: int(v) for k, v in get_all_pending_counts().items()}
                phase_names = _get_phase_names_cached(WINDOW_HOURS)
            except Exception as exc:
                logger.warning("minimal pipeline metrics failed: %s", exc)
                return _empty_response(now_utc, WINDOW_HOURS)

            results = {}
            for phase in phase_names:
                runs, avg_dur, sd = _query_phase_stats(phase, WINDOW_HOURS)
                proc = _recently_processed(phase)
                pending_count = int(pending.get(phase, 0) or 0)
                lag_ratio = round(pending_count / max(proc, 1), 4) if proc > 0 else 0.0
                results[phase] = {
                    "runs_last_7d": runs,
                    "avg_duration_s": 0.0,
                    "duration_stddev_s": 0.0,
                    "pending_count": pending_count,
                    "lag_ratio": lag_ratio,
                    "status": _classify_lag(lag_ratio, proc),
                }

            return {
                "as_of": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "window_hours": WINDOW_HOURS,
                "phase_metrics": results,
                "phase_count": len(results),
                "cache_ttl_seconds": 30,
            }

        # Full path: latency stats + pending + lag.
        payload = get_pipeline_throughput(latency_window_hours=window_hours)
        return payload

    except Exception as exc:
        logger.warning("pipeline_metrics endpoint error: %s", exc, exc_info=True)
        now_utc = datetime.now(timezone.utc)
        from services.pipeline_throughput import _empty_response, WINDOW_HOURS

        return _empty_response(now_utc, window_hours or WINDOW_HOURS)


# ---------------------------------------------------------------------------
# Helpers (avoid circular import at module level)
# ---------------------------------------------------------------------------

_phase_names_cache: tuple[str, ...] = ()
_phase_names_time: float = 0
_PHASE_NAMES_TTL = 120  # 2 min — phase names change rarely


def _get_phase_names_cached(window_hrs: int) -> list[str]:
    """Cached phase name list so minimal-path callers avoid repeated SQL."""
    global _phase_names_cache, _phase_names_time
    import time

    try:
        from shared.database.connection import get_ui_db_connection

        if (_phase_names_time + _PHASE_NAMES_TTL) > time.monotonic():
            return list(_phase_names_cache)

        conn = get_ui_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT phase_name FROM automation_run_history WHERE started_at >= NOW() - INTERVAL %s ORDER BY phase_name;",
            (f"{window_hrs} hours",),
        )
        rows = cur.fetchall()
        conn.close()
        _phase_names_cache = tuple(str(r[0]) for r in rows) if rows else ()
        _phase_names_time = time.monotonic()
        return list(_phase_names_cache)

    except Exception:
        return list(_phase_names_cache)  # may be empty on first call


def _recently_processed(phase: str) -> int:
    """Count success-finished rows in the last 6 hours for one phase."""
    try:
        from shared.database.connection import get_ui_db_connection

        conn = get_ui_db_connection()
        cur = conn.cursor()
        cur.execute(
            """\
SELECT COUNT(*) AS processed
FROM automation_run_history
WHERE phase_name = %s
  AND started_at >= NOW() - INTERVAL '6 hours'
  AND finished_at >= NOW() - INTERVAL '6 hours'
  AND success = true;""",
            (phase,),
        )
        row = cur.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] else 0
    except Exception:
        return 0
