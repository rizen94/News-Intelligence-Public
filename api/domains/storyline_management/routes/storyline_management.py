"""
Domain 3: Storyline Management Routes
Handles storyline creation, timeline generation, and RAG-enhanced analysis
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/storyline-management",
    tags=["Storyline Management"],
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

@router.get("/storylines")
async def get_storylines():
    """Get all storylines"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, description, created_at, updated_at,
                           article_count, quality_score, status
                    FROM storylines 
                    ORDER BY updated_at DESC
                """)
                
                storylines = []
                for row in cur.fetchall():
                    storylines.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "updated_at": row[4].isoformat() if row[4] else None,
                        "article_count": row[5] or 0,
                        "quality_score": row[6],
                        "status": row[7]
                    })
                
                return {
                    "success": True,
                    "data": {"storylines": storylines},
                    "count": len(storylines),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storylines")
async def create_storyline(storyline_data: Dict[str, Any]):
    """Create a new storyline"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO storylines (title, description, created_at, updated_at, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    storyline_data.get("title"),
                    storyline_data.get("description", ""),
                    datetime.now(),
                    datetime.now(),
                    "active"
                ))
                
                storyline_id = cur.fetchone()[0]
                conn.commit()
                
                return {
                    "success": True,
                    "data": {"storyline_id": storyline_id},
                    "message": "Storyline created successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error creating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storylines/{storyline_id}")
async def get_storyline(storyline_id: int):
    """Get detailed storyline information"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline details
                cur.execute("""
                    SELECT id, title, description, created_at, updated_at,
                           article_count, quality_score, status, analysis_summary
                    FROM storylines 
                    WHERE id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get articles in storyline
                cur.execute("""
                    SELECT a.id, a.title, a.url, a.source, a.published_at, a.summary
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at ASC
                """, (storyline_id,))
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "url": row[2],
                        "source": row[3],
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
                            "article_count": storyline[5] or 0,
                            "quality_score": storyline[6],
                            "status": storyline[7],
                            "analysis_summary": storyline[8]
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

@router.post("/storylines/{storyline_id}/add-article")
async def add_article_to_storyline(storyline_id: int, request: Dict[str, Any]):
    """Add an article to a storyline"""
    try:
        article_id = request.get("article_id")
        if not article_id:
            raise HTTPException(status_code=400, detail="Article ID is required")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute("SELECT id FROM storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Check if article exists
                cur.execute("SELECT id FROM articles WHERE id = %s", (article_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found")
                
                # Add article to storyline
                cur.execute("""
                    INSERT INTO storyline_articles (storyline_id, article_id, added_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (storyline_id, article_id) DO NOTHING
                """, (storyline_id, article_id, datetime.now()))
                
                # Update article count
                cur.execute("""
                    UPDATE storylines 
                    SET article_count = (
                        SELECT COUNT(*) FROM storyline_articles 
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

@router.post("/storylines/{storyline_id}/analyze")
async def analyze_storyline(storyline_id: int, background_tasks: BackgroundTasks):
    """Generate comprehensive storyline analysis using RAG"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline and articles
                cur.execute("""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM storylines s
                    WHERE s.id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                cur.execute("""
                    SELECT a.title, a.content, a.summary, a.published_at, a.source
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
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

@router.get("/storylines/{storyline_id}/timeline")
async def get_storyline_timeline(storyline_id: int):
    """Get chronological timeline for a storyline"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, a.title, a.published_at, a.source, a.summary,
                           te.event_type, te.event_description, te.confidence_score
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
                    LEFT JOIN timeline_events te ON a.id = te.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at ASC
                """, (storyline_id,))
                
                timeline_events = []
                for row in cur.fetchall():
                    timeline_events.append({
                        "article_id": row[0],
                        "title": row[1],
                        "published_at": row[2].isoformat() if row[2] else None,
                        "source": row[3],
                        "summary": row[4],
                        "event_type": row[5],
                        "event_description": row[6],
                        "confidence_score": row[7]
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

@router.get("/storylines/{storyline_id}/suggestions")
async def get_storyline_suggestions(storyline_id: int):
    """Get AI-powered storyline suggestions"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline context
                cur.execute("""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM storylines s
                    WHERE s.id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get related articles (not in storyline)
                cur.execute("""
                    SELECT a.id, a.title, a.summary, a.published_at, a.source
                    FROM articles a
                    WHERE a.id NOT IN (
                        SELECT sa.article_id FROM storyline_articles sa 
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
                                "source": row[4]
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
            article_title, content, summary, published_at, source = article
            context_parts.append(f"\n- {article_title} ({source}, {published_at})")
            if summary:
                context_parts.append(f"  Summary: {summary}")
            else:
                context_parts.append(f"  Content: {content[:500]}...")
        
        storyline_context = "\n".join(context_parts)
        
        # Generate comprehensive analysis using LLM
        analysis_result = await llm_service.generate_storyline_analysis(storyline_context)
        
        if analysis_result["success"]:
            # Update storyline with analysis
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
                            90,  # High quality score for RAG analysis
                            datetime.now(),
                            storyline_id
                        ))
                        conn.commit()
                        logger.info(f"Updated RAG analysis for storyline {storyline_id}")
                finally:
                    conn.close()
        
    except Exception as e:
        logger.error(f"Error in storyline RAG analysis: {e}")
