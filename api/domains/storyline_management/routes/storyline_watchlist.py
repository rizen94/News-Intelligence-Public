"""
Watchlist Routes for News Intelligence v5.0 (Phase 5)
Manage watched storylines, alerts, and monitoring dashboard data.
"""

from fastapi import APIRouter, HTTPException, Path, Query, Body
from typing import Optional
import logging

from config.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Watchlist"],
    responses={404: {"description": "Not found"}},
)


# ------------------------------------------------------------------
# Watchlist CRUD
# ------------------------------------------------------------------

@router.get("/watchlist")
async def get_watchlist():
    """Get all watched storylines with unread alert counts."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        return {"success": True, "data": svc.get_watchlist()}
    finally:
        conn.close()


@router.post("/watchlist/{storyline_id}")
async def add_to_watchlist(
    storyline_id: int = Path(...),
    user_label: Optional[str] = Body(None),
    notes: Optional[str] = Body(None),
    alert_on_reactivation: bool = Body(True),
    weekly_digest: bool = Body(True),
):
    """Add a storyline to the watchlist."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        result = svc.add_to_watchlist(
            storyline_id, user_label, notes,
            alert_on_reactivation, weekly_digest,
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    finally:
        conn.close()


@router.delete("/watchlist/{storyline_id}")
async def remove_from_watchlist(storyline_id: int = Path(...)):
    """Remove a storyline from the watchlist."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        result = svc.remove_from_watchlist(storyline_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    finally:
        conn.close()


# ------------------------------------------------------------------
# Alerts
# ------------------------------------------------------------------

@router.get("/watchlist/alerts")
async def get_alerts(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    """Get watchlist alerts."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        return {"success": True, "data": svc.get_alerts(unread_only, limit)}
    finally:
        conn.close()


@router.post("/watchlist/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: int = Path(...)):
    """Mark a single alert as read."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        svc.mark_alert_read(alert_id)
        return {"success": True}
    finally:
        conn.close()


@router.post("/watchlist/alerts/read-all")
async def mark_all_alerts_read():
    """Mark all alerts as read."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        count = svc.mark_all_read()
        return {"success": True, "marked": count}
    finally:
        conn.close()


# ------------------------------------------------------------------
# Dashboard / monitoring data
# ------------------------------------------------------------------

@router.get("/monitoring/activity-feed")
async def get_activity_feed(limit: int = Query(30, ge=1, le=100)):
    """Real-time feed of storyline event activity."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        return {"success": True, "data": svc.get_story_activity_feed(limit)}
    finally:
        conn.close()


@router.get("/monitoring/dormant-alerts")
async def get_dormant_alerts(days: int = Query(30, ge=7, le=365)):
    """Watched storylines that have been dormant beyond threshold."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        return {"success": True, "data": svc.get_dormant_story_alerts(days)}
    finally:
        conn.close()


@router.get("/monitoring/coverage-gaps")
async def get_coverage_gaps(days: int = Query(7, ge=1, le=90)):
    """Active storylines missing recent source coverage."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        return {"success": True, "data": svc.get_coverage_gaps(days)}
    finally:
        conn.close()


@router.get("/monitoring/cross-domain-connections")
async def get_cross_domain_connections():
    """Storylines sharing core entities across different topics."""
    from services.watchlist_service import WatchlistService
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        svc = WatchlistService(conn)
        return {"success": True, "data": svc.get_cross_domain_connections()}
    finally:
        conn.close()
