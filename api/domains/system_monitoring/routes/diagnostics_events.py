"""
Diagnostics: aggregate errors and signals from automation history, pipeline DB, spill file, and logs.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from shared.services.response_cache import cached_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/system_monitoring",
    tags=["System Monitoring"],
)


@router.get("/diagnostics/events")
@cached_response(ttl=30)
def get_diagnostics_events(
    since_hours: float = Query(24, ge=1, le=168, description="Look back window (hours)"),
    max_per_source: int = Query(
        200, ge=10, le=2000, description="Cap rows per DB source / activity scan"
    ),
    include_activity_jsonl: bool = Query(True, description="Parse logs/activity.jsonl tail"),
    include_plain_logs: bool = Query(
        True, description="Heuristic scan of pipeline.log / api.log for ERROR lines"
    ),
    log_dir: str | None = Query(
        None,
        description="Override LOG_DIR (default: config.paths.LOG_DIR)",
    ),
) -> dict[str, Any]:
    """
    Collect normalized diagnostic events for operator review: failed automation runs,
    failed pipeline traces/checkpoints, pending DB spill, API/RSS errors from activity.jsonl,
    and keyword hits in plain log tails.

    Safe to call on a schedule (cron or automation). Responses are cached briefly.
    """
    from services.diagnostics_event_collector_service import collect_diagnostic_events

    ld: Path | None = Path(log_dir) if log_dir else None
    try:
        data = collect_diagnostic_events(
            since_hours=since_hours,
            max_per_source=max_per_source,
            include_activity_jsonl=include_activity_jsonl,
            include_plain_logs=include_plain_logs,
            log_dir=ld,
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.warning("get_diagnostics_events: %s", e)
        return {"success": False, "message": str(e)[:500], "data": None}


@router.get("/diagnostics/summary")
@cached_response(ttl=30)
def get_diagnostics_summary(
    since_hours: float = Query(24, ge=1, le=168),
) -> dict[str, Any]:
    """Same collection as /diagnostics/events but returns counts only (smaller payload)."""
    from services.diagnostics_event_collector_service import collect_diagnostic_events

    try:
        full = collect_diagnostic_events(
            since_hours=since_hours,
            max_per_source=150,
            include_activity_jsonl=True,
            include_plain_logs=True,
        )
        return {
            "success": True,
            "data": {
                "generated_at_utc": full.get("generated_at_utc"),
                "since_hours": full.get("since_hours"),
                "total": full.get("total"),
                "counts_by_severity": full.get("counts_by_severity"),
                "counts_by_source": full.get("counts_by_source"),
            },
        }
    except Exception as e:
        logger.warning("get_diagnostics_summary: %s", e)
        return {"success": False, "message": str(e)[:500], "data": None}
