"""
Intelligence products API — daily brief, generate_brief, alert_digest (P2).
Unifies DailyBriefingService and watchlist/event alerts behind /api/products/*.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Intelligence products"])


def _get_daily_briefing_service():
    """Lazy init DailyBriefingService with shared db_config."""
    from shared.database.connection import get_db_config
    from modules.ml.daily_briefing_service import DailyBriefingService
    return DailyBriefingService(get_db_config())


@router.post("/products/generate_brief")
def post_generate_brief(
    date: Optional[str] = Body(None, embed=True, description="YYYY-MM-DD; default today"),
    domain: Optional[str] = Body(None, embed=True),
    include_anomalies: bool = Body(True, embed=True),
    include_storylines: bool = Body(True, embed=True),
    include_deduplication: bool = Body(True, embed=True),
) -> Dict[str, Any]:
    """Generate a daily brief on demand. Returns brief sections and generated_at."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        briefing_date_dt = datetime.combine(briefing_date, datetime.min.time())
        brief = svc.generate_daily_briefing(
            briefing_date_dt,
            include_deduplication=include_deduplication,
            include_storylines=include_storylines,
        )
        if "error" in brief:
            return {"success": False, "data": None, "message": brief["error"]}
        out = {
            "brief_id": None,
            "sections": brief.get("sections", {}),
            "statistics": brief.get("statistics", {}),
            "generated_at": brief.get("generated_at"),
            "briefing_date": brief.get("briefing_date"),
        }
        if include_anomalies and domain:
            try:
                from services.intelligence_analysis_service import get_intelligence_service
                anomalies = get_intelligence_service().detect_anomalies(domain, hours=24)
                out["anomalies"] = [
                    {
                        "entity_type": a.entity_type,
                        "entity_id": a.entity_id,
                        "severity": a.severity,
                        "description": a.description,
                        "detected_at": a.detected_at.isoformat(),
                    }
                    for a in anomalies[:20]
                ]
            except Exception as e:
                logger.debug("Anomalies in brief failed: %s", e)
                out["anomalies"] = []
        return {"success": True, "data": out, "message": None}
    except Exception as e:
        logger.warning("generate_brief failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


@router.get("/products/daily_brief")
def get_daily_brief(
    date: Optional[str] = Query(None, description="YYYY-MM-DD; default today"),
) -> Dict[str, Any]:
    """Return daily brief for the given date (generated on demand)."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        briefing_date_dt = datetime.combine(briefing_date, datetime.min.time())
        brief = svc.generate_daily_briefing(
            briefing_date_dt,
            include_deduplication=True,
            include_storylines=True,
        )
        if "error" in brief:
            return {"success": False, "data": None, "message": brief["error"]}
        return {
            "success": True,
            "data": {
                "briefing_date": brief.get("briefing_date"),
                "generated_at": brief.get("generated_at"),
                "sections": brief.get("sections", {}),
                "statistics": brief.get("statistics", {}),
            },
            "message": None,
        }
    except Exception as e:
        logger.warning("daily_brief failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


@router.get("/products/weekly_digest")
def get_weekly_digest(
    week_start: Optional[str] = Query(None, description="YYYY-MM-DD (Monday) for a specific week"),
    limit: int = Query(10, ge=1, le=52),
) -> Dict[str, Any]:
    """Return stored weekly digests. If week_start given, return that week's digest if present."""
    from services.digest_automation_service import get_digest_service

    svc = get_digest_service()
    if week_start:
        try:
            ws = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "data": None, "message": "Invalid week_start; use YYYY-MM-DD"}
        digests = [d for d in svc.get_latest_weekly_digests(limit=52) if d.get("week_start") == week_start]
        if not digests:
            return {"success": True, "data": {"digests": [], "count": 0}, "message": None}
        return {"success": True, "data": {"digests": digests, "count": len(digests)}, "message": None}
    digests = svc.get_latest_weekly_digests(limit=limit)
    return {"success": True, "data": {"digests": digests, "count": len(digests)}, "message": None}


@router.get("/products/alert_digest")
def get_alert_digest(
    since: Optional[int] = Query(None, description="Only alerts from last N hours"),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
) -> Dict[str, Any]:
    """Alert digest: watchlist alerts (and optionally event alerts) bundled."""
    from shared.database.connection import get_db_connection
    from services.watchlist_service import WatchlistService

    conn = get_db_connection()
    if not conn:
        return {"success": False, "data": None, "message": "Database unavailable"}
    try:
        svc = WatchlistService(conn)
        alerts = svc.get_alerts(unread_only=unread_only, limit=limit)
        if since is not None:
            cutoff = datetime.utcnow() - timedelta(hours=since)
            def _parsed(ts):
                if not ts:
                    return None
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    return None
            alerts = [a for a in alerts if _parsed(a.get("created_at")) and _parsed(a["created_at"]) >= cutoff]
        conn.close()
        return {
            "success": True,
            "data": {
                "alerts": alerts,
                "count": len(alerts),
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
            "message": None,
        }
    except Exception as e:
        logger.warning("alert_digest failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "data": None, "message": str(e)}
