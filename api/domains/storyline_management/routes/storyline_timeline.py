"""
Storyline Timeline & Narrative Routes (v5.0 Phase 4)
Endpoints for building timelines and generating narrative summaries.
"""

from fastapi import APIRouter, HTTPException, Path, Query
import logging

from config.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Storyline Timeline"],
    responses={404: {"description": "Not found"}},
)


@router.get("/{domain}/storylines/{storyline_id}/timeline")
async def get_storyline_timeline(
    domain: str = Path(...),
    storyline_id: int = Path(...),
):
    """Build and return a structured chronological timeline for a storyline."""
    from services.timeline_builder_service import TimelineBuilderService

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        svc = TimelineBuilderService(conn)
        timeline = svc.build_timeline(storyline_id)
        if not timeline.get("events"):
            raise HTTPException(status_code=404, detail="No events found for this storyline")
        return {"success": True, "data": timeline}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timeline build failed for storyline {storyline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{domain}/storylines/{storyline_id}/narrative")
async def get_storyline_narrative(
    domain: str = Path(...),
    storyline_id: int = Path(...),
    mode: str = Query("chronological", regex="^(chronological|briefing)$"),
):
    """Generate a journalist-quality narrative from the storyline's timeline."""
    from services.timeline_builder_service import TimelineBuilderService
    from services.narrative_synthesis_service import NarrativeSynthesisService

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        tb = TimelineBuilderService(conn)
        timeline = tb.build_timeline(storyline_id)
        if not timeline.get("events"):
            raise HTTPException(status_code=404, detail="No events found for this storyline")

        ns = NarrativeSynthesisService()
        try:
            if mode == "briefing":
                result = await ns.generate_briefing(timeline)
            else:
                result = await ns.generate_chronological_narrative(timeline)
        finally:
            await ns.close()

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Narrative generation failed for storyline {storyline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{domain}/events")
async def list_domain_events(
    domain: str = Path(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str = Query(None),
    ongoing_only: bool = Query(False),
    article_id: int = Query(None),
):
    """List extracted events, optionally filtered by type, ongoing status, or source article."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        cursor = conn.cursor()
        conditions = ["ce.canonical_event_id IS NULL"]
        params: list = []

        if event_type:
            conditions.append("ce.event_type = %s")
            params.append(event_type)
        if ongoing_only:
            conditions.append("ce.is_ongoing = true")
        if article_id:
            conditions.append("ce.source_article_id = %s")
            params.append(article_id)

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        cursor.execute(f"""
            SELECT ce.id, ce.title, ce.event_type, ce.actual_event_date,
                   ce.date_precision, ce.location, ce.source_count,
                   ce.is_ongoing, ce.storyline_id, ce.importance_score
            FROM chronological_events ce
            WHERE {where}
            ORDER BY ce.actual_event_date DESC NULLS LAST
            LIMIT %s OFFSET %s
        """, params)

        events = []
        for r in cursor.fetchall():
            events.append({
                "id": r[0], "title": r[1], "event_type": r[2],
                "event_date": r[3].isoformat() if r[3] else None,
                "date_precision": r[4], "location": r[5],
                "source_count": r[6], "is_ongoing": r[7],
                "storyline_id": r[8],
                "importance": float(r[9]) if r[9] else 0,
            })

        cursor.execute(f"SELECT COUNT(*) FROM chronological_events ce WHERE {where}",
                       params[:-2] if params[:-2] else [])
        total = cursor.fetchone()[0]
        cursor.close()

        return {"success": True, "data": events, "total": total}
    except Exception as e:
        logger.error(f"Event listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
