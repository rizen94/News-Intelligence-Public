"""
Domain 3: Storyline Management Routes - Background Tasks and Legacy Routes
This file contains background task functions and legacy routes that are being migrated.
New routes should be added to feature-specific files (storyline_crud.py, storyline_evolution.py, etc.)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Query, Body
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from ..services.storyline_service import StorylineService
from ..services.quality_assessment_service import QualityAssessmentService
from ..services.rag_analysis_service import RAGAnalysisService
from ..services.proactive_detection_service import ProactiveDetectionService

logger = logging.getLogger(__name__)

# Legacy router - routes are being migrated to feature-specific files
# NOTE: This router is NOT included in main_v4.py - it's only used for background task functions
# If this router needs to be included, it should be done via compatibility layer or with proper prefix
router = APIRouter(
    prefix="/api/v4",  # Keep prefix for potential compatibility use, but router is not actively included
    tags=["Storyline Management (Legacy)"],
    responses={404: {"description": "Not found"}}
)

@router.get("/health")
async def health_check():
    """Health check for Storyline Management domain"""
    try:
        # Check LLM service
        llm_status = await llm_service.get_model_status()
        
        return {
            "success": True,
            "domain": "storyline_management",
            "status": "healthy",
            "llm_service": llm_status,
            "primary_model": "llama3.1:8b",
            "secondary_model": "mistral:7b",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "storyline_management",
            "status": "unhealthy",
            "error": str(e)
        }

# CRITICAL ROUTE ORDER: Specific routes (like /emerging) MUST come before parameterized routes (like /{storyline_id})
# FastAPI matches routes in order, so /emerging would be matched as /{storyline_id} if defined after

@router.get("/{domain}/storylines/emerging")
async def get_domain_emerging_storylines(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(24, ge=1, le=168),
    min_articles: int = Query(3, ge=2, le=20)
):
    """Get emerging storylines - Route order critical: must be before {storyline_id} routes"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.detect_emerging_storylines(hours, min_articles)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Detection failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting emerging storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines")
async def get_domain_storylines(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of storylines"),
    offset: int = Query(0, ge=0, description="Number of storylines to skip"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """Get all storylines for a specific domain with pagination"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query with optional status filter
                where_clause = ""
                params = []
                
                if status:
                    where_clause = "WHERE status = %s"
                    params.append(status)
                
                # Get total count
                count_query = f"SELECT COUNT(*) FROM {schema}.storylines {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()[0]
                
                # Get paginated storylines
                query = f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, article_count
                    FROM {schema}.storylines 
                    {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])
                
                cur.execute(query, params)
                
                storylines = []
                for row in cur.fetchall():
                    storylines.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "updated_at": row[4].isoformat() if row[4] else None,
                        "status": row[5],
                        "article_count": row[6] if len(row) > 6 else 0
                    })
                
                return {
                    "success": True,
                    "data": {
                        "storylines": storylines,
                        "domain": domain,
                        "total": total,
                        "limit": limit,
                        "offset": offset
                    },
                    "count": len(storylines),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines")
async def create_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_data: Dict[str, Any] = None
):
    """Create a new storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        storyline_service = StorylineService(domain=domain)
        
        result = await storyline_service.create_storyline_from_articles(
            title=storyline_data.get("title") if storyline_data else "",
            description=storyline_data.get("description") if storyline_data else None,
            article_ids=storyline_data.get("article_ids") if storyline_data else None
        )
        
        if result.get("success"):
            return {
                "success": True,
                "data": {
                    **result.get("data", {}),
                    "domain": domain
                },
                "message": "Storyline created successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Creation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{domain}/storylines/{storyline_id}")
async def update_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    storyline_data: Dict[str, Any] = None
):
    """Update an existing storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if storyline exists in domain schema
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Update storyline in domain schema
                cur.execute(f"""
                    UPDATE {schema}.storylines 
                    SET title = %s, description = %s, updated_at = %s,
                        article_count = (
                            SELECT COUNT(*) FROM {schema}.storyline_articles 
                            WHERE storyline_id = %s
                        )
                    WHERE id = %s
                """, (
                    storyline_data.get("title"),
                    storyline_data.get("description", ""),
                    datetime.now(),
                    storyline_id,
                    storyline_id
                ))
                
                conn.commit()
                
                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "title": storyline_data.get("title"),
                        "description": storyline_data.get("description", ""),
                        "status": "active"
                    },
                    "message": "Storyline updated successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{domain}/storylines/{storyline_id}")
async def delete_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Delete a storyline and all its associated articles in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # First, remove all articles from the storyline in domain schema
                cur.execute(f"""
                    DELETE FROM {schema}.storyline_articles 
                    WHERE storyline_id = %s
                """, (storyline_id,))
                
                # Then delete the storyline itself from domain schema
                cur.execute(f"""
                    DELETE FROM {schema}.storylines 
                    WHERE id = %s
                """, (storyline_id,))
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Storyline deleted successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{domain}/storylines/{storyline_id}/articles/{article_id}")
async def remove_article_from_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    article_id: int = Path(..., description="Article ID"),
    background_tasks: BackgroundTasks = None
):
    """Remove an article from a storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if article exists in storyline before removing
                cur.execute(f"""
                    SELECT storyline_id FROM {schema}.storyline_articles 
                    WHERE storyline_id = %s AND article_id = %s
                """, (storyline_id, article_id))
                
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found in storyline")
                
                # Remove the article from the storyline
                cur.execute(f"""
                    DELETE FROM {schema}.storyline_articles 
                    WHERE storyline_id = %s AND article_id = %s
                """, (storyline_id, article_id))
                
                # Update article count in domain schema
                cur.execute(f"""
                    UPDATE {schema}.storylines 
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles 
                        WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """, (storyline_id, datetime.now(), storyline_id))
                
                conn.commit()
                
                # Trigger intelligent storyline evolution in background
                # This will extract new information and update the summary
                if background_tasks:
                    background_tasks.add_task(
                        trigger_storyline_evolution, domain, storyline_id, [article_id]
                    )
                
                return {
                    "success": True,
                    "message": "Article removed from storyline successfully. Storyline evolution triggered.",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing article from storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines/{storyline_id}/articles/{article_id}")
async def add_article_to_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    article_id: int = Path(..., description="Article ID"),
    request: Dict[str, Any] = None,
    background_tasks: BackgroundTasks = None
):
    """Add an article to a storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if storyline exists in domain schema
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Check if article exists in domain schema
                cur.execute(f"SELECT id FROM {schema}.articles WHERE id = %s", (article_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail=f"Article with ID {article_id} not found")
                
                # Check if article is already in storyline
                cur.execute(f"""
                    SELECT storyline_id FROM {schema}.storyline_articles 
                    WHERE storyline_id = %s AND article_id = %s
                """, (storyline_id, article_id))
                
                if cur.fetchone():
                    raise HTTPException(status_code=400, detail="Article already in storyline")
                
                # Add the article to the storyline in domain schema
                cur.execute(f"""
                    INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at, relevance_score)
                    VALUES (%s, %s, %s, %s)
                """, (
                    storyline_id,
                    article_id,
                    datetime.now(),
                    request.get("relevance_score", 0.5) if request else 0.5
                ))
                
                # Update article count in domain schema
                cur.execute(f"""
                    UPDATE {schema}.storylines 
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles 
                        WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """, (storyline_id, datetime.now(), storyline_id))
                
                conn.commit()
                
                # Trigger storyline evolution in background
                if background_tasks:
                    background_tasks.add_task(
                        trigger_storyline_evolution, domain, storyline_id
                    )
                
                return {
                    "success": True,
                    "message": "Article added to storyline successfully. Storyline evolution triggered.",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding article to storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}/available_articles")
async def get_domain_available_articles_for_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None)
):
    """Get articles that can be added to a storyline (not already in it) from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query with optional search filter
                where_conditions = [
                    f"a.id NOT IN (SELECT sa.article_id FROM {schema}.storyline_articles sa WHERE sa.storyline_id = %s)"
                ]
                params = [storyline_id]
                
                # Add search filter if provided
                if search:
                    where_conditions.append("(a.title ILIKE %s OR a.source_domain ILIKE %s)")
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern, search_pattern])
                
                where_clause = "WHERE " + " AND ".join(where_conditions)
                
                query = f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                    FROM {schema}.articles a
                    {where_clause}
                    ORDER BY a.published_at DESC
                    LIMIT %s
                """
                params.append(limit)
                
                cur.execute(query, params)
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "url": row[2],
                        "source_domain": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "summary": row[5]
                    })
                
                return {
                    "success": True,
                    "data": {"articles": articles},
                    "count": len(articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting available articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}")
async def get_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Get a single storyline with all its articles from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline details from domain schema
                cur.execute(f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, analysis_summary, quality_score, article_count
                    FROM {schema}.storylines 
                    WHERE id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get articles in storyline from domain schema
                cur.execute(f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at ASC
                """, (storyline_id,))
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "url": row[2],
                        "source_domain": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "summary": row[5]
                    })
                
                return {
                    "success": True,
                    "data": {
                        "storyline": {
                            "id": storyline[0],
                            "title": storyline[1],
                            "description": storyline[2],
                            "created_at": storyline[3].isoformat() if storyline[3] else None,
                            "updated_at": storyline[4].isoformat() if storyline[4] else None,
                            "status": storyline[5],
                            "analysis_summary": storyline[6],
                            "quality_score": float(storyline[7]) if storyline[7] else None,
                            "article_count": storyline[8] or 0
                        },
                        "articles": articles
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines/{storyline_id}/add_article")
async def add_article_to_domain_storyline_by_id(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    request: Dict[str, Any] = None
):
    """Add an article to a storyline by article ID in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        article_id = request.get("article_id") if request else None
        if not article_id:
            raise HTTPException(status_code=400, detail="Article ID is required")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if storyline exists in domain schema
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Check if article exists in domain schema
                cur.execute(f"SELECT id FROM {schema}.articles WHERE id = %s", (article_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found")
                
                # Add article to storyline in domain schema
                cur.execute(f"""
                    INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (storyline_id, article_id) DO NOTHING
                """, (storyline_id, article_id, datetime.now()))
                
                # Update article count in domain schema
                cur.execute(f"""
                    UPDATE {schema}.storylines 
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles 
                        WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """, (storyline_id, datetime.now(), storyline_id))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Article added to storyline successfully",
                    "storyline_id": storyline_id,
                    "article_id": article_id,
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error adding article to storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines/{storyline_id}/analyze")
async def analyze_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None
):
    """Generate comprehensive storyline analysis using RAG in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline and articles from domain schema
                cur.execute(f"""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM {schema}.storylines s
                    WHERE s.id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                cur.execute(f"""
                    SELECT a.id, a.title, a.content, a.summary, a.published_at, a.source_domain, a.url
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at ASC
                """, (storyline_id,))
                
                articles = cur.fetchall()
                
                if not articles:
                    raise HTTPException(status_code=400, detail="No articles in storyline")
                
                # Start RAG analysis
                background_tasks.add_task(process_storyline_rag_analysis, storyline_id, storyline, articles)
                
                return {
                    "success": True,
                    "message": "Storyline RAG analysis started",
                    "storyline_id": storyline_id,
                    "articles_count": len(articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting storyline analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}/timeline")
async def get_domain_storyline_timeline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Get chronological timeline for a storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get timeline events directly from timeline_events table (in public schema for now)
                # Note: timeline_events may need to be domain-aware in future
                cur.execute("""
                    SELECT id, event_id, title, description, event_date, event_time,
                           source, url, importance_score, event_type, location,
                           entities, tags, ml_generated, confidence_score,
                           source_article_ids, created_at, updated_at
                    FROM timeline_events
                    WHERE storyline_id = %s
                    ORDER BY event_date ASC, event_time ASC
                """, (str(storyline_id),))
                
                timeline_events = []
                for row in cur.fetchall():
                    timeline_events.append({
                        "id": row[0],
                        "event_id": row[1],
                        "title": row[2],
                        "description": row[3],
                        "event_date": row[4].isoformat() if row[4] else None,
                        "event_time": str(row[5]) if row[5] else None,
                        "source": row[6],
                        "url": row[7],
                        "importance_score": float(row[8]) if row[8] else 0.0,
                        "event_type": row[9],
                        "location": row[10],
                        "entities": row[11] if row[11] else [],
                        "tags": row[12] if row[12] else [],
                        "ml_generated": row[13],
                        "confidence_score": float(row[14]) if row[14] else 0.0,
                        "source_article_ids": row[15] if row[15] else [],
                        "created_at": row[16].isoformat() if row[16] else None,
                        "updated_at": row[17].isoformat() if row[17] else None
                    })
                
                return {
                    "success": True,
                    "data": {"timeline_events": timeline_events},
                    "storyline_id": storyline_id,
                    "events_count": len(timeline_events),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}/suggestions")
async def get_domain_storyline_suggestions(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Get AI-powered storyline suggestions in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline context from domain schema
                cur.execute(f"""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM {schema}.storylines s
                    WHERE s.id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get related articles (not in storyline) from domain schema
                cur.execute(f"""
                    SELECT a.id, a.title, a.summary, a.published_at, a.source_domain
                    FROM {schema}.articles a
                    WHERE a.id NOT IN (
                        SELECT sa.article_id FROM {schema}.storyline_articles sa 
                        WHERE sa.storyline_id = %s
                    )
                    AND a.published_at >= %s
                    ORDER BY a.published_at DESC
                    LIMIT 20
                """, (storyline_id, datetime.now() - timedelta(days=7)))
                
                related_articles = cur.fetchall()
                
                return {
                    "success": True,
                    "data": {
                        "storyline_title": storyline[0],
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
            
    except Exception as e:
        logger.error(f"Error fetching suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# NEW ENDPOINTS: Storyline Evolution, Quality Assessment, Proactive Detection
# ============================================================================

@router.post("/{domain}/storylines/{storyline_id}/evolve")
async def evolve_domain_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    new_article_ids: Optional[List[int]] = Body(None),
    force_evolution: bool = Query(False)
):
    """Evolve storyline with new content"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        storyline_service = StorylineService(domain=domain)
        result = await storyline_service.evolve_storyline_with_new_content(
            storyline_id, new_article_ids, force_evolution
        )
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Evolution failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evolving storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines/{storyline_id}/assess_quality")
async def assess_domain_storyline_quality(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Assess storyline quality"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.assess_storyline_quality(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Assessment failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assessing quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}/validate_accuracy")
async def validate_domain_storyline_accuracy(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Validate factual accuracy of storyline"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
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
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Get improvement suggestions for storyline"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        quality_service = QualityAssessmentService(domain=domain)
        result = await quality_service.suggest_improvements(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get suggestions"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting improvements: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}/report")
async def get_domain_storyline_report(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    report_type: str = Query("comprehensive", regex="^(comprehensive|executive|summary)$")
):
    """Get comprehensive storyline report"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        rag_service = RAGAnalysisService(domain=domain)
        result = await rag_service.generate_storyline_report(storyline_id, report_type)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Report generation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines/{storyline_id}/rag_analysis")
async def perform_domain_rag_analysis(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None
):
    """Perform comprehensive RAG analysis"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        rag_service = RAGAnalysisService(domain=domain)
        
        # Run in background for long-running analysis
        if background_tasks:
            background_tasks.add_task(
                perform_rag_analysis_background, domain, storyline_id
            )
            return {
                "success": True,
                "message": "RAG analysis started in background",
                "storyline_id": storyline_id
            }
        else:
            result = await rag_service.perform_comprehensive_analysis(storyline_id)
            if result.get("success"):
                return result
            else:
                raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing RAG analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def perform_rag_analysis_background(domain: str, storyline_id: int):
    """Background task for RAG analysis"""
    try:
        rag_service = RAGAnalysisService(domain=domain)
        result = await rag_service.perform_comprehensive_analysis(storyline_id)
        if result.get("success"):
            logger.info(f"RAG analysis completed for storyline {storyline_id}")
        else:
            logger.warning(f"RAG analysis failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error in background RAG analysis: {e}")

async def trigger_storyline_evolution(domain: str, storyline_id: int, new_article_ids: Optional[List[int]] = None):
    """
    Background task to trigger intelligent storyline evolution.
    Extracts new information from articles and automatically updates summary and context.
    """
    try:
        storyline_service = StorylineService(domain=domain)
        result = await storyline_service.evolve_storyline_with_new_content(
            storyline_id, new_article_ids, force_evolution=False
        )
        
        if result.get("success"):
            data = result.get("data", {})
            logger.info(
                f"Storyline {storyline_id} evolved successfully - "
                f"Summary updated: {data.get('summary_updated', False)}, "
                f"New articles processed: {data.get('new_articles', 0)}, "
                f"Context updated: {data.get('context_updated', False)}, "
                f"Summary length: {data.get('summary_length', 0)} chars"
            )
        else:
            logger.warning(f"Storyline evolution failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error in storyline evolution background task: {e}")

@router.get("/{domain}/storylines/{storyline_id}/correlations")
async def get_domain_storyline_correlations(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Find correlations with other storylines"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        rag_service = RAGAnalysisService(domain=domain)
        result = await rag_service.find_storyline_correlations(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to find correlations"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/storylines/detect")
async def detect_domain_storylines(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(24, ge=1, le=168),
    min_articles: int = Query(3, ge=2, le=20)
):
    """Detect new storylines from recent articles"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.detect_emerging_storylines(hours, min_articles)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Detection failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/correlations")
async def get_domain_storyline_correlations_all(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """Get all storyline correlations"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.identify_story_correlations()
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get correlations"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/storylines/{storyline_id}/predict")
async def predict_domain_storyline_developments(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., description="Storyline ID")
):
    """Predict potential future developments in storyline"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        detection_service = ProactiveDetectionService(domain=domain)
        result = await detection_service.predict_story_developments(storyline_id)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Prediction failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting developments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def process_storyline_rag_analysis(storyline_id: int, storyline: tuple, articles: List[tuple]):
    """Background task for RAG-enhanced storyline analysis"""
    try:
        title, description, current_summary = storyline
        
        # Build context from articles
        context_parts = [f"Storyline: {title}"]
        if description:
            context_parts.append(f"Description: {description}")
        
        context_parts.append("\nArticles in storyline:")
        for article in articles:
            # articles tuple format: (id, title, content, summary, published_at, source_domain, url)
            article_id, article_title, content, summary, published_at, source, url = article
            context_parts.append(f"\n- {article_title} ({source}, {published_at})")
            if summary:
                context_parts.append(f"  Summary: {summary}")
            else:
                context_parts.append(f"  Content: {content[:500]}...")
        
        storyline_context = "\n".join(context_parts)
        
        # Generate comprehensive analysis using LLM
        analysis_result = await llm_service.generate_storyline_analysis(storyline_context)
        
        if analysis_result["success"]:
            # Update storyline with analysis and extract timeline events
            # Use a new connection since this is a background task
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE storylines 
                            SET analysis_summary = %s,
                                quality_score = %s,
                                updated_at = %s
                            WHERE id = %s
                        """, (
                            analysis_result["analysis"],
                            0.90,  # High quality score for RAG analysis (0.0-1.0 scale)
                            datetime.now(),
                            storyline_id
                        ))
                        conn.commit()
                        logger.info(f"Updated RAG analysis for storyline {storyline_id}")
                    
                    # Extract and store timeline events from articles
                    # Use the same connection but after commit
                    _extract_timeline_events_from_articles(conn, storyline_id, articles, title)
                        
                except Exception as e:
                    logger.error(f"Error updating storyline or extracting timeline: {e}", exc_info=True)
                finally:
                    conn.close()
        
    except Exception as e:
        logger.error(f"Error in storyline RAG analysis: {e}")


def _extract_timeline_events_from_articles(conn, storyline_id: int, articles: List[tuple], storyline_title: str):
    """Extract timeline events from articles and store them in timeline_events table"""
    try:
        from datetime import datetime as dt
        import json
        
        logger.info(f"Starting timeline extraction for storyline {storyline_id} with {len(articles)} articles")
        
        with conn.cursor() as cur:
            # Process each article and create timeline events
            # articles tuple format: (id, title, content, summary, published_at, source_domain, url)
            events_created = 0
            articles_skipped = 0
            
            for article in articles:
                if len(article) != 7:
                    logger.warning(f"Article tuple has unexpected length: {len(article)}, expected 7. Article: {article[:3]}")
                    articles_skipped += 1
                    continue
                    
                article_id, article_title, content, summary, published_at, source, url = article
                
                if not published_at:
                    logger.debug(f"Skipping article {article_id}: no published_at date")
                    articles_skipped += 1
                    continue
                
                # Parse published_at date
                event_date = None
                if isinstance(published_at, dt):
                    event_date = published_at.date()
                elif hasattr(published_at, 'date'):
                    event_date = published_at.date()
                elif isinstance(published_at, str):
                    try:
                        # Handle ISO format strings
                        pub_str = published_at.replace('Z', '+00:00')
                        event_date = dt.fromisoformat(pub_str).date()
                    except Exception as parse_error:
                        logger.warning(f"Could not parse date {published_at}: {parse_error}")
                        continue
                
                if not event_date:
                    continue
                
                # Create timeline event from article
                event_title = article_title[:200] if article_title else "Untitled Event"  # Limit title length
                event_description = summary[:500] if summary else (content[:500] if content else "")
                
                # Generate unique event_id
                event_id = f"storyline_{storyline_id}_article_{article_id}_{event_date.isoformat()}"
                
                # Insert timeline event
                cur.execute("""
                    INSERT INTO timeline_events (
                        event_id, storyline_id, title, description, event_date, event_time,
                        source, url, importance_score, event_type, location, entities, tags,
                        ml_generated, confidence_score, source_article_ids, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (event_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        updated_at = EXCLUDED.updated_at
                """, (
                    event_id,
                    str(storyline_id),
                    event_title,
                    event_description,
                    event_date,
                    None,  # event_time
                    source,
                    url,  # url
                    0.7,  # importance_score
                    'general',  # event_type
                    None,  # location
                    json.dumps([]),  # entities
                    [],  # tags
                    True,  # ml_generated
                    0.8,  # confidence_score
                    [article_id],  # source_article_ids
                    dt.now(),
                    dt.now()
                ))
                
                events_created += 1
            
            conn.commit()
            logger.info(f"Extracted and stored {events_created} timeline events for storyline {storyline_id} (skipped {articles_skipped} articles)")
            
    except Exception as e:
        logger.error(f"Error extracting timeline events from articles: {e}", exc_info=True)
        # Don't fail the whole analysis if timeline extraction fails
