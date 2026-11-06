"""
Domain 3: Storyline Management Routes - Background Tasks and Legacy Routes
This file contains background task functions and legacy routes that are being migrated.
New routes should be added to feature-specific files (storyline_crud.py, storyline_evolution.py, etc.)
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path, Query
from api.config.settings import MODELS
from api.shared.database import get_db_connection
from api.shared.domain_registry import DOMAIN_PATH_PATTERN, resolve_domain_schema
from api.shared.services.domain_aware_service import validate_domain
from api.shared.services.llm_service import llm_service

from ..services.proactive_detection_service import ProactiveDetectionService
from ..services.quality_assessment_service import QualityAssessmentService
from ..services.rag_analysis_service import RAGAnalysisService, trigger_storyline_evolution, perform_rag_analysis_background
from ..services.storyline_service import StorylineService
from services.article_content_enrichment_service import format_article_content_excerpt

logger = logging.getLogger(__name__)

# Legacy router - routes are being migrated to feature-specific files
# NOTE: This router is included via the consolidated router in __init__.py
# Prefix removed since it's included in a router that already has /api prefix
router = APIRouter(
    tags=["Storyline Management (Legacy)"], responses={404: {"description": "Not found"}}
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
            "primary_model": MODELS["primary"],
            "secondary_model": MODELS["secondary"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "storyline_management",
            "status": "unhealthy",
            "error": str(e),
        }


# CRITICAL ROUTE ORDER: Specific routes (like /emerging) MUST come before parameterized routes (like /{storyline_id})
# FastAPI matches routes in order, so /emerging would be matched as /{storyline_id} if defined after


@router.get("/{domain}/storylines/emerging")
async def get_domain_emerging_storylines(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    hours: int = Query(24, ge=1, le=168),
    min_articles: int = Query(3, ge=2, le=20),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(
        100, ge=1, le=200, description="Maximum number of storylines (max 200 for performance)"
    ),
    offset: int = Query(0, ge=0, description="Number of storylines to skip"),
    status: str | None = Query(None, description="Filter by status"),
):
    """Get all storylines for a specific domain with pagination"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Build query with optional status filter
                where_clause = ""
                params = []

                if status:
                    where_clause = "WHERE s.status = %s"
                    params.append(status)

                # Get total count
                count_query = f"SELECT COUNT(*) FROM {schema}.storylines s {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()[0]

                # Get paginated storylines
                query = f"""
                    SELECT s.id, s.title, s.description, s.created_at, s.updated_at,
                           s.status, s.article_count, s.document_status,
                           s.editorial_document->>'lede' as editorial_lede,
                           (SELECT MAX(sa.added_at) FROM {schema}.storyline_articles sa
                            WHERE sa.storyline_id = s.id) AS last_article_added_at
                    FROM {schema}.storylines s
                    {where_clause}
                    ORDER BY (SELECT MAX(sa2.added_at) FROM {schema}.storyline_articles sa2 WHERE sa2.storyline_id = s.id) DESC NULLS LAST,
                             s.updated_at DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])

                cur.execute(query, params)

                storylines = []
                for row in cur.fetchall():
                    laa = row[9] if len(row) > 9 else None
                    storylines.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "description": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "updated_at": row[4].isoformat() if row[4] else None,
                            "status": row[5],
                            "article_count": row[6] if len(row) > 6 else 0,
                            "document_status": row[7] if len(row) > 7 else None,
                            "editorial_lede": row[8] if len(row) > 8 else None,
                            "last_article_added_at": laa.isoformat() if laa else None,
                        }
                    )

                return {
                    "success": True,
                    "data": {
                        "storylines": storylines,
                        "domain": domain,
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    },
                    "count": len(storylines),
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines")
async def create_domain_storyline(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN), storyline_data: dict[str, Any] = None
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
            article_ids=storyline_data.get("article_ids") if storyline_data else None,
        )

        if result.get("success"):
            return {
                "success": True,
                "data": {**result.get("data", {}), "domain": domain},
                "message": "Storyline created successfully",
                "timestamp": datetime.now().isoformat(),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    storyline_data: dict[str, Any] = None,
):
    """Update an existing storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

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
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET title = %s, description = %s, updated_at = %s,
                        article_count = (
                            SELECT COUNT(*) FROM {schema}.storyline_articles
                            WHERE storyline_id = %s
                        )
                    WHERE id = %s
                """,
                    (
                        storyline_data.get("title"),
                        storyline_data.get("description", ""),
                        datetime.now(),
                        storyline_id,
                        storyline_id,
                    ),
                )

                conn.commit()

                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "title": storyline_data.get("title"),
                        "description": storyline_data.get("description", ""),
                        "status": "active",
                    },
                    "message": "Storyline updated successfully",
                    "timestamp": datetime.now().isoformat(),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
):
    """Delete a storyline and all its associated articles in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # First, remove all articles from the storyline in domain schema
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                """,
                    (storyline_id,),
                )

                # Then delete the storyline itself from domain schema
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                conn.commit()

                return {
                    "success": True,
                    "message": "Storyline deleted successfully",
                    "timestamp": datetime.now().isoformat(),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    article_id: int = Path(..., description="Article ID"),
    background_tasks: BackgroundTasks = None,
):
    """Remove an article from a storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Check if article exists in storyline before removing
                cur.execute(
                    f"""
                    SELECT storyline_id FROM {schema}.storyline_articles
                    WHERE storyline_id = %s AND article_id = %s
                """,
                    (storyline_id, article_id),
                )

                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found in storyline")

                # Remove the article from the storyline
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles
                    WHERE storyline_id = %s AND article_id = %s
                """,
                    (storyline_id, article_id),
                )

                # Update article count in domain schema
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """,
                    (storyline_id, datetime.now(), storyline_id),
                )

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
                    "timestamp": datetime.now().isoformat(),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    article_id: int = Path(..., description="Article ID"),
    request: dict[str, Any] = None,
    background_tasks: BackgroundTasks = None,
):
    """Add an article to a storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

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
                    raise HTTPException(
                        status_code=404, detail=f"Article with ID {article_id} not found"
                    )

                # Check if article is already in storyline
                cur.execute(
                    f"""
                    SELECT storyline_id FROM {schema}.storyline_articles
                    WHERE storyline_id = %s AND article_id = %s
                """,
                    (storyline_id, article_id),
                )

                if cur.fetchone():
                    raise HTTPException(status_code=400, detail="Article already in storyline")

                # Add the article to the storyline in domain schema
                cur.execute(
                    f"""
                    INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at, relevance_score)
                    VALUES (%s, %s, %s, %s)
                """,
                    (
                        storyline_id,
                        article_id,
                        datetime.now(),
                        request.get("relevance_score", 0.5) if request else 0.5,
                    ),
                )

                # Update article count in domain schema
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """,
                    (storyline_id, datetime.now(), storyline_id),
                )

                conn.commit()

                # Trigger storyline evolution in background
                if background_tasks:
                    background_tasks.add_task(trigger_storyline_evolution, domain, storyline_id)

                return {
                    "success": True,
                    "message": "Article added to storyline successfully. Storyline evolution triggered.",
                    "timestamp": datetime.now().isoformat(),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    limit: int = Query(50, ge=1, le=100),  # Max 100 for performance
    search: str | None = Query(None),
):
    """Get articles that can be added to a storyline (not already in it) from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

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
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary,
                           LEFT(a.content, 300) as content_excerpt
                    FROM {schema}.articles a
                    {where_clause}
                    ORDER BY a.published_at DESC
                    LIMIT %s
                """
                params.append(limit)

                cur.execute(query, params)

                articles = []
                for row in cur.fetchall():
                    articles.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "url": row[2],
                            "source_domain": row[3],
                            "published_at": row[4].isoformat() if row[4] else None,
                            "summary": row[5],
                            "content_excerpt": format_article_content_excerpt(
                                row[6] if len(row) > 6 else None, 300
                            ),
                        }
                    )

                return {
                    "success": True,
                    "data": {"articles": articles},
                    "count": len(articles),
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting available articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}")
async def get_domain_storyline(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
):
    """Get a single storyline with all its articles from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Get storyline details from domain schema
                cur.execute(
                    f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, analysis_summary, quality_score, article_count,
                           ml_processing_status, priority,
                           editorial_document, document_version, document_status
                    FROM {schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Get articles in storyline from domain schema
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at,
                           a.summary, LEFT(a.content, 1000) as content_excerpt
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at ASC
                """,
                    (storyline_id,),
                )

                articles = []
                for row in cur.fetchall():
                    articles.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "url": row[2],
                            "source_domain": row[3],
                            "published_at": row[4].isoformat() if row[4] else None,
                            "summary": row[5],
                            "content_excerpt": format_article_content_excerpt(
                                row[6] if len(row) > 6 else None, 1000
                            ),
                        }
                    )

                cur.execute(
                    f"""
                    SELECT MAX(sa.added_at) FROM {schema}.storyline_articles sa
                    WHERE sa.storyline_id = %s
                    """,
                    (storyline_id,),
                )
                laa_r = cur.fetchone()
                last_article_added_at = laa_r[0] if laa_r and laa_r[0] else None

                return {
                    "success": True,
                    "data": {
                        "storyline": {
                            "id": storyline[0],
                            "title": storyline[1],
                            "description": storyline[2],
                            "created_at": storyline[3].isoformat() if storyline[3] else None,
                            "updated_at": storyline[4].isoformat() if storyline[4] else None,
                            "last_article_added_at": last_article_added_at.isoformat()
                            if last_article_added_at
                            else None,
                            "status": storyline[5],
                            "analysis_summary": storyline[6],
                            "quality_score": float(storyline[7]) if storyline[7] else None,
                            "article_count": storyline[8] or 0,
                            "ml_processing_status": storyline[9] if len(storyline) > 9 else None,
                            "priority": storyline[10] if len(storyline) > 10 else None,
                            "editorial_document": storyline[11] if len(storyline) > 11 else None,
                            "document_version": storyline[12] if len(storyline) > 12 else None,
                            "document_status": storyline[13] if len(storyline) > 13 else None,
                        },
                        "articles": articles,
                    },
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/add_article")
async def add_article_to_domain_storyline_by_id(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    request: dict[str, Any] = None,
):
    """Add an article to a storyline by article ID in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

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
                cur.execute(
                    f"""
                    INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (storyline_id, article_id) DO NOTHING
                """,
                    (storyline_id, article_id, datetime.now()),
                )
                inserted = cur.rowcount > 0

                if inserted:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET article_count = (
                            SELECT COUNT(*) FROM {schema}.storyline_articles
                            WHERE storyline_id = %s
                        ),
                        updated_at = %s
                        WHERE id = %s
                        """,
                        (storyline_id, datetime.now(), storyline_id),
                    )

                conn.commit()

                return {
                    "success": True,
                    "message": "Article added to storyline successfully",
                    "storyline_id": storyline_id,
                    "article_id": article_id,
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error adding article to storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/analyze")
async def analyze_domain_storyline(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None,
):
    """Generate comprehensive storyline analysis using RAG in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Get storyline and articles from domain schema
                cur.execute(
                    f"""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM {schema}.storylines s
                    WHERE s.id = %s
                """,
                    (storyline_id,),
                )

                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.content, a.summary, a.published_at, a.source_domain, a.url
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at ASC
                """,
                    (storyline_id,),
                )

                articles = cur.fetchall()

                if not articles:
                    raise HTTPException(status_code=400, detail="No articles in storyline")

                from services.content_refinement_queue_service import (
                    JOB_COMPREHENSIVE_RAG,
                    enqueue_content_refinement,
                )

                enq = enqueue_content_refinement(
                    domain, storyline_id, JOB_COMPREHENSIVE_RAG, priority="medium"
                )
                if not enq.get("success"):
                    raise HTTPException(
                        status_code=500,
                        detail=enq.get("error", "Failed to queue analysis"),
                    )
                _ = background_tasks

                return {
                    "success": True,
                    "message": enq.get("message", "Queued for background processing"),
                    "storyline_id": storyline_id,
                    "articles_count": len(articles),
                    "queue_id": enq.get("queue_id"),
                    "already_queued": enq.get("already_queued", False),
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error starting storyline analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/timeline")
async def get_domain_storyline_timeline(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
):
    """Get chronological timeline for a storyline in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Get timeline events directly from timeline_events table (in public schema for now)
                # Note: timeline_events may need to be domain-aware in future
                cur.execute(
                    """
                    SELECT id, event_id, title, description, event_date, event_time,
                           source, url, importance_score, event_type, location,
                           entities, tags, ml_generated, confidence_score,
                           source_article_ids, created_at, updated_at
                    FROM timeline_events
                    WHERE storyline_id = %s
                    ORDER BY event_date ASC, event_time ASC
                """,
                    (str(storyline_id),),
                )

                timeline_events = []
                for row in cur.fetchall():
                    timeline_events.append(
                        {
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
                            "updated_at": row[17].isoformat() if row[17] else None,
                        }
                    )

                # Build narrative connecting timeline events
                narrative = ""
                if timeline_events:
                    first = timeline_events[0]
                    last = timeline_events[-1]
                    first_title = first.get("title", "")
                    last_title = last.get("title", "")
                    first_date = first.get("event_date", "")
                    last_date = last.get("event_date", "")
                    narrative = f"Timeline spans {len(timeline_events)} events"
                    if first_date and last_date and first_date != last_date:
                        narrative += f" from {first_date} to {last_date}"
                    narrative += "."
                    if first_title and last_title and first_title != last_title:
                        narrative += f' Coverage began with "{first_title}" and most recently "{last_title}".'

                return {
                    "success": True,
                    "data": {
                        "timeline_events": timeline_events,
                        "narrative": narrative,
                    },
                    "storyline_id": storyline_id,
                    "events_count": len(timeline_events),
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/suggestions")
async def get_domain_storyline_suggestions(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
):
    """Get AI-powered storyline suggestions in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Get storyline context from domain schema
                cur.execute(
                    f"""
                    SELECT s.title, s.description, s.analysis_summary
                    FROM {schema}.storylines s
                    WHERE s.id = %s
                """,
                    (storyline_id,),
                )

                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Get related articles (not in storyline) from domain schema
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.summary, a.published_at, a.source_domain,
                           LEFT(a.content, 300) as content_excerpt
                    FROM {schema}.articles a
                    WHERE a.id NOT IN (
                        SELECT sa.article_id FROM {schema}.storyline_articles sa
                        WHERE sa.storyline_id = %s
                    )
                    AND a.published_at >= %s
                    ORDER BY a.published_at DESC
                    LIMIT 20
                """,
                    (storyline_id, datetime.now() - timedelta(days=7)),
                )

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
                                "source_domain": row[4],
                                "content_excerpt": format_article_content_excerpt(
                                    row[5] if len(row) > 5 else None, 300
                                ),
                            }
                            for row in related_articles
                        ],
                    },
                    "storyline_id": storyline_id,
                    "suggestions_count": len(related_articles),
                    "timestamp": datetime.now().isoformat(),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    new_article_ids: list[int] | None = Body(None),
    force_evolution: bool = Query(False),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
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
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to get suggestions")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting improvements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/report")
async def get_domain_storyline_report(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    report_type: str = Query("comprehensive", regex="^(comprehensive|executive|summary)$"),
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
            raise HTTPException(
                status_code=500, detail=result.get("error", "Report generation failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/{storyline_id}/rag_analysis")
async def perform_domain_rag_analysis(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None,
):
    """Perform comprehensive RAG analysis"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        from services.content_refinement_queue_service import (
            JOB_COMPREHENSIVE_RAG,
            enqueue_content_refinement,
        )

        enq = enqueue_content_refinement(
            domain, storyline_id, JOB_COMPREHENSIVE_RAG, priority="medium"
        )
        if not enq.get("success"):
            raise HTTPException(
                status_code=500,
                detail=enq.get("error", "Failed to queue analysis"),
            )
        _ = background_tasks
        return {
            "success": True,
            "message": enq.get("message", "Queued for background processing"),
            "storyline_id": storyline_id,
            "queue_id": enq.get("queue_id"),
            "already_queued": enq.get("already_queued", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing RAG analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/correlations")
async def get_domain_storyline_correlations(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
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
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to find correlations")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/detect")
async def detect_domain_storylines(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    hours: int = Query(24, ge=1, le=168),
    min_articles: int = Query(3, ge=2, le=20),
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
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
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
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to get correlations")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/predict")
async def predict_domain_storyline_developments(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
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


