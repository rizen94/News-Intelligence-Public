#!/usr/bin/env python3
"""
Storyline Helper Routes
Supporting endpoints (suggestions, timeline, validation, improvements)
"""

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from typing import Optional
from datetime import datetime, timedelta
import logging

from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from ..services.quality_assessment_service import QualityAssessmentService

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Storyline Helpers"],
    responses={404: {"description": "Not found"}}
)


async def validate_domain_dependency(domain: str = Path(..., pattern="^(politics|finance|science-tech)$")) -> str:
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    return domain


def _parse_json_col(val):
    """Parse JSON/JSONB column to dict or list."""
    if val is None:
        return {} if isinstance(val, dict) else []
    if isinstance(val, (dict, list)):
        return val
    try:
        import json
        return json.loads(val) if isinstance(val, str) else val
    except (TypeError, ValueError):
        return {} if isinstance(val, dict) else []


def _build_timeline_metadata(events: list) -> dict:
    """Compute gaps, milestones, time_span from events for rich timeline display."""
    dated = [e for e in events if e.get("event_date")]
    gaps = []
    milestones = []
    time_span = None

    if len(dated) >= 2:
        dated_sorted = sorted(dated, key=lambda x: x["event_date"])
        for i in range(len(dated_sorted) - 1):
            d1 = dated_sorted[i]["event_date"]
            d2 = dated_sorted[i + 1]["event_date"]
            if isinstance(d1, str):
                try:
                    d1 = datetime.fromisoformat(d1.replace("Z", "+00:00")).date()
                except Exception:
                    continue
            if isinstance(d2, str):
                try:
                    d2 = datetime.fromisoformat(d2.replace("Z", "+00:00")).date()
                except Exception:
                    continue
            delta = (d2 - d1).days if hasattr(d2 - d1, "days") else 0
            if delta > 7:
                gaps.append({
                    "after_event_id": dated_sorted[i].get("id") or dated_sorted[i].get("event_id"),
                    "before_event_id": dated_sorted[i + 1].get("id") or dated_sorted[i + 1].get("event_id"),
                    "gap_days": delta,
                    "from_date": d1.isoformat() if hasattr(d1, "isoformat") else str(d1),
                    "to_date": d2.isoformat() if hasattr(d2, "isoformat") else str(d2),
                })

        first = dated_sorted[0]["event_date"]
        last = dated_sorted[-1]["event_date"]
        if isinstance(first, str):
            try:
                first = datetime.fromisoformat(first.replace("Z", "+00:00")).date()
            except Exception:
                first = None
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last.replace("Z", "+00:00")).date()
            except Exception:
                last = None
        if first and last and hasattr(last - first, "days"):
            time_span = {
                "start": first.isoformat(),
                "end": last.isoformat(),
                "days": (last - first).days,
            }

    if dated:
        first_evt = min(dated, key=lambda e: e["event_date"])
        milestones.append({
            "type": "first_event",
            "event_id": first_evt.get("id") or first_evt.get("event_id"),
            "label": "Story begins",
        })
    high_importance = [e for e in events if float(e.get("importance_score") or e.get("importance") or 0) >= 0.8]
    for e in high_importance[:5]:
        milestones.append({
            "type": "escalation",
            "event_id": e.get("id") or e.get("event_id"),
            "label": (e.get("title") or "")[:60],
        })

    return {"gaps": gaps, "milestones": milestones, "time_span": time_span}


@router.get("/{domain}/storylines/{storyline_id}/timeline")
async def get_domain_storyline_timeline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """
    Get timeline of events for a storyline.
    Returns events from timeline_events (domain schema) with gaps, milestones, and time_span.
    Compatible with both StorylineDetail and StoryTimeline (interactive) pages.
    """
    try:
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                # Check if storyline exists
                cur.execute(f"SELECT id, title FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get timeline events - flexible column selection for schema evolution
                events_rows = []
                try:
                    cur.execute(f"""
                        SELECT id, event_id, title, description, event_date,
                               COALESCE(importance_score, 0.5) as importance_score,
                               COALESCE(event_type, 'general') as event_type,
                               location, entities, tags
                        FROM {schema}.timeline_events
                        WHERE storyline_id = %s
                        ORDER BY event_date ASC NULLS LAST, importance_score DESC NULLS LAST
                    """, (storyline_id,))
                    events_rows = cur.fetchall()
                except Exception:
                    try:
                        cur.execute(f"""
                            SELECT event_id, title, description, event_date,
                                   COALESCE(importance_score, 0.5), COALESCE(event_type, 'general'),
                                   location, entities, tags
                            FROM {schema}.timeline_events
                            WHERE storyline_id = %s
                            ORDER BY event_date ASC NULLS LAST
                        """, (storyline_id,))
                        rows = cur.fetchall()
                        events_rows = [(i + 1, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for i, r in enumerate(rows)]
                    except Exception:
                        pass
                
                events = []
                for row in events_rows:
                    # Handle both (id, event_id, ...) and (event_id, ...) row formats
                    row_id = row[0] if len(row) >= 10 else (row[0] if isinstance(row[0], int) else hash(row[0]))
                    event_id = row[1] if len(row) >= 10 else row[0]
                    title = row[2] if len(row) >= 10 else row[1]
                    desc = row[3] if len(row) >= 10 else row[2]
                    evt_date = row[4] if len(row) >= 10 else row[3]
                    imp = float(row[5]) if len(row) >= 10 and row[5] is not None else 0.5
                    evt_type = (row[6] or "general") if len(row) >= 10 else (row[4] if len(row) > 4 else "general")
                    loc = row[7] if len(row) >= 10 else (row[6] if len(row) > 6 else None)
                    entities_val = row[8] if len(row) >= 10 else (row[7] if len(row) > 7 else [])
                    tags_val = row[9] if len(row) >= 10 else (row[8] if len(row) > 8 else [])
                    
                    evt = {
                        "id": row_id,
                        "event_id": event_id,
                        "title": title or "Untitled Event",
                        "description": desc,
                        "event_date": evt_date.isoformat() if evt_date and hasattr(evt_date, "isoformat") else (evt_date if isinstance(evt_date, str) else None),
                        "date_precision": "exact",
                        "event_type": str(evt_type).replace(" ", "_").lower() or "general",
                        "location": loc or "unknown",
                        "importance": imp,
                        "importance_score": imp,
                        "source_count": 1,
                        "is_ongoing": False,
                        "outcome": "",
                        "key_actors": _parse_json_col(entities_val) if isinstance(_parse_json_col(entities_val), list) else [],
                        "entities": _parse_json_col(entities_val),
                        "tags": _parse_json_col(tags_val) if isinstance(_parse_json_col(tags_val), list) else [],
                    }
                    events.append(evt)
                
                meta = _build_timeline_metadata(events)
                source_count = len(set(e.get("source", {}).get("domain") for e in events if e.get("source"))) or 1
                
                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "storyline_title": storyline[1],
                        "events": events,
                        "gaps": meta["gaps"],
                        "milestones": meta["milestones"],
                        "event_count": len(events),
                        "time_span": meta["time_span"],
                        "source_count": source_count,
                    },
                    "count": len(events),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/suggestions")
async def get_domain_storyline_suggestions(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get article suggestions for a storyline"""
    try:
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline
                cur.execute(f"SELECT id, title FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get recent articles not in storyline
                cur.execute(f"""
                    SELECT a.id, a.title, a.summary, a.published_at, a.source_domain
                    FROM {schema}.articles a
                    WHERE a.id NOT IN (
                        SELECT sa.article_id 
                        FROM {schema}.storyline_articles sa 
                        WHERE sa.storyline_id = %s
                    )
                    AND a.published_at >= %s
                    ORDER BY a.published_at DESC
                    LIMIT %s
                """, (storyline_id, datetime.now() - timedelta(days=7), limit))
                
                related_articles = cur.fetchall()
                
                return {
                    "success": True,
                    "data": {
                        "storyline_title": storyline[1],
                        "suggested_articles": [
                            {
                                "id": row[0],
                                "title": row[1],
                                "summary": row[2],
                                "published_at": row[3].isoformat() if row[3] else None,
                                "source_domain": row[4]
                            }
                            for row in related_articles
                        ]
                    },
                    "storyline_id": storyline_id,
                    "suggestions_count": len(related_articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/validate_accuracy")
async def validate_domain_storyline_accuracy(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Validate factual accuracy of storyline"""
    try:
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.validate_factual_accuracy(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Validation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating accuracy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/suggestions_improvements")
async def get_domain_storyline_improvements(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Get suggestions for improving storyline"""
    try:
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.suggest_improvements(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get suggestions"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting improvement suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

