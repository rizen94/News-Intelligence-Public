"""
Storyline Automation Routes
API endpoints for managing RAG-enhanced article discovery and automation controls
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Query, Body
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import json
import psycopg2.extras

from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from services.storyline_automation_service import StorylineAutomationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4",
    tags=["Storyline Automation"],
    responses={404: {"description": "Not found"}}
)

# Note: StorylineAutomationService will need domain context per request


@router.get("/storylines/{storyline_id}/automation/settings")
async def get_automation_settings(storyline_id: int):
    """Get automation settings for a storyline"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT automation_enabled, automation_mode, automation_settings,
                           search_keywords, search_entities, search_exclude_keywords,
                           automation_frequency_hours, last_automation_run
                    FROM storylines
                    WHERE id = %s
                """, (storyline_id,))
                
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                (automation_enabled, automation_mode, automation_settings_json,
                 search_keywords, search_entities, search_exclude_keywords,
                 frequency_hours, last_run) = result
                
                # Handle both dict (from psycopg2 JSONB) and string (legacy)
                if isinstance(automation_settings_json, dict):
                    settings = automation_settings_json
                elif isinstance(automation_settings_json, str):
                    settings = json.loads(automation_settings_json) if automation_settings_json else {}
                else:
                    settings = {}
                
                return {
                    "success": True,
                    "data": {
                        "automation_enabled": automation_enabled or False,
                        "automation_mode": automation_mode or "disabled",
                        "settings": settings,
                        "search_keywords": search_keywords or [],
                        "search_entities": search_entities or [],
                        "search_exclude_keywords": search_exclude_keywords or [],
                        "frequency_hours": frequency_hours or 24,
                        "last_automation_run": last_run.isoformat() if last_run else None
                    },
                    "storyline_id": storyline_id
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/storylines/{storyline_id}/automation/settings")
async def update_automation_settings(storyline_id: int, settings: Dict[str, Any]):
    """Update automation settings for a storyline"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Verify storyline exists
                cur.execute("SELECT id FROM storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Extract settings
                automation_enabled = settings.get("automation_enabled", False)
                automation_mode = settings.get("automation_mode", "disabled")
                automation_settings = settings.get("settings", {})
                search_keywords = settings.get("search_keywords", [])
                search_entities = settings.get("search_entities", [])
                search_exclude_keywords = settings.get("search_exclude_keywords", [])
                frequency_hours = settings.get("frequency_hours", 24)
                
                # Update storyline
                # Use psycopg2.extras.Json for proper JSONB handling
                cur.execute("""
                    UPDATE storylines
                    SET automation_enabled = %s,
                        automation_mode = %s,
                        automation_settings = %s,
                        search_keywords = %s,
                        search_entities = %s,
                        search_exclude_keywords = %s,
                        automation_frequency_hours = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    automation_enabled,
                    automation_mode,
                    psycopg2.extras.Json(automation_settings) if automation_settings else psycopg2.extras.Json({}),
                    search_keywords,
                    search_entities,
                    search_exclude_keywords,
                    frequency_hours,
                    datetime.now(),
                    storyline_id
                ))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Automation settings updated",
                    "storyline_id": storyline_id
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating automation settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/storylines/{storyline_id}/automation/discover")
async def discover_articles(storyline_id: int, force_refresh: bool = False):
    """Trigger RAG-enhanced article discovery for a storyline"""
    try:
        result = await automation_service.discover_articles_for_storyline(
            storyline_id,
            force_refresh=force_refresh
        )
        return result
        
    except Exception as e:
        logger.error(f"Error discovering articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storylines/{storyline_id}/automation/suggestions")
async def get_article_suggestions(storyline_id: int, status: Optional[str] = None):
    """Get pending article suggestions for a storyline"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query
                where_clause = "WHERE storyline_id = %s"
                params = [storyline_id]
                
                if status:
                    where_clause += " AND status = %s"
                    params.append(status)
                else:
                    where_clause += " AND status = 'pending'"
                
                cur.execute(f"""
                    SELECT s.id, s.article_id, s.relevance_score, s.semantic_score,
                           s.keyword_score, s.quality_score, s.combined_score,
                           s.matched_keywords, s.matched_entities, s.reasoning,
                           s.suggested_at, s.expires_at,
                           a.title, a.summary, a.url, a.source_domain, a.published_at
                    FROM storyline_article_suggestions s
                    JOIN articles a ON s.article_id = a.id
                    {where_clause}
                    ORDER BY s.combined_score DESC, s.suggested_at DESC
                    LIMIT 50
                """, params)
                
                suggestions = []
                for row in cur.fetchall():
                    suggestions.append({
                        "suggestion_id": row[0],
                        "article": {
                            "id": row[1],
                            "title": row[12],
                            "summary": row[13],
                            "url": row[14],
                            "source_domain": row[15],
                            "published_at": row[16].isoformat() if row[16] else None
                        },
                        "scores": {
                            "relevance": float(row[2]) if row[2] else 0.0,
                            "semantic": float(row[3]) if row[3] else 0.0,
                            "keyword": float(row[4]) if row[4] else 0.0,
                            "quality": float(row[5]) if row[5] else 0.0,
                            "combined": float(row[6]) if row[6] else 0.0
                        },
                        "matched_keywords": row[7] or [],
                        "matched_entities": row[8] or [],
                        "reasoning": row[9],
                        "suggested_at": row[10].isoformat() if row[10] else None,
                        "expires_at": row[11].isoformat() if row[11] else None
                    })
                
                return {
                    "success": True,
                    "data": {
                        "suggestions": suggestions,
                        "count": len(suggestions)
                    },
                    "storyline_id": storyline_id
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/storylines/{storyline_id}/automation/suggestions/{suggestion_id}/approve")
async def approve_suggestion(storyline_id: int, suggestion_id: int):
    """Approve a suggested article and add it to the storyline"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get suggestion
                cur.execute("""
                    SELECT article_id FROM storyline_article_suggestions
                    WHERE id = %s AND storyline_id = %s AND status = 'pending'
                """, (suggestion_id, storyline_id))
                
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Suggestion not found or already processed")
                
                article_id = result[0]
                
                # Add article to storyline (reuse existing endpoint logic)
                cur.execute("""
                    INSERT INTO storyline_articles (storyline_id, article_id, added_at, relevance_score)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (storyline_id, article_id) DO NOTHING
                """, (storyline_id, article_id, datetime.now(), 0.7))
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=400, detail="Article already in storyline")
                
                # Update suggestion status
                cur.execute("""
                    UPDATE storyline_article_suggestions
                    SET status = 'approved', reviewed_at = %s
                    WHERE id = %s
                """, (datetime.now(), suggestion_id))
                
                # Update storyline article count
                cur.execute("""
                    UPDATE storylines
                    SET article_count = (
                        SELECT COUNT(*) FROM storyline_articles WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """, (storyline_id, datetime.now(), storyline_id))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Article added to storyline",
                    "article_id": article_id,
                    "storyline_id": storyline_id
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving suggestion: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/storylines/{storyline_id}/automation/suggestions/{suggestion_id}/reject")
async def reject_suggestion(storyline_id: int, suggestion_id: int, reason: Optional[str] = None):
    """Reject a suggested article"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE storyline_article_suggestions
                    SET status = 'rejected', reviewed_at = %s, review_notes = %s
                    WHERE id = %s AND storyline_id = %s
                """, (datetime.now(), reason, suggestion_id, storyline_id))
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Suggestion not found")
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Suggestion rejected",
                    "suggestion_id": suggestion_id
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

