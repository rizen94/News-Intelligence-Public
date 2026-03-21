#!/usr/bin/env python3
"""
Storyline Articles Routes
Managing articles within storylines (add, remove, list available)
"""

import logging
import math
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from shared.database.connection import get_db_connection
from shared.domain_registry import DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import validate_domain

from ..routes.storyline_management import trigger_storyline_evolution
from ..schemas.storyline_schemas import AddArticleRequest, PaginationInfo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storyline Articles"], responses={404: {"description": "Not found"}})


async def validate_domain_dependency(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)) -> str:
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    return domain


@router.post("/{domain}/storylines/{storyline_id}/articles/{article_id}")
async def add_article_to_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    article_id: int = Path(..., description="Article ID", ge=1),
    request: AddArticleRequest | None = None,
    background_tasks: BackgroundTasks = None,
):
    """Add an article to a storyline in a specific domain"""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Check if article exists
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

                # Add the article
                relevance_score = request.relevance_score if request else 0.5
                cur.execute(
                    f"""
                    INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at, relevance_score)
                    VALUES (%s, %s, %s, %s)
                """,
                    (storyline_id, article_id, datetime.now(), relevance_score),
                )

                # Update article count
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

                if os.getenv("STORYLINE_ENQUEUE_FINISHER_ON_NEW_ARTICLE", "1") == "1":
                    try:
                        from services.content_refinement_queue_service import (
                            JOB_NARRATIVE_FINISHER,
                            enqueue_content_refinement,
                            enqueue_initial_narrative_finisher,
                            storyline_needs_initial_master_narrative,
                        )

                        if storyline_needs_initial_master_narrative(domain, storyline_id):
                            enqueue_initial_narrative_finisher(
                                domain, storyline_id, source="add_article"
                            )
                        else:
                            enqueue_content_refinement(
                                domain,
                                storyline_id,
                                JOB_NARRATIVE_FINISHER,
                                priority="medium",
                                metadata={
                                    "finisher_pass": "refresh",
                                    "source": "add_article",
                                    "article_id": article_id,
                                },
                            )
                    except Exception as enq_e:
                        logger.debug("finisher enqueue on add_article: %s", enq_e)

                # Trigger intelligent storyline evolution in background
                if background_tasks:
                    background_tasks.add_task(
                        trigger_storyline_evolution, domain, storyline_id, [article_id]
                    )

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


@router.delete("/{domain}/storylines/{storyline_id}/articles/{article_id}")
async def remove_article_from_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    article_id: int = Path(..., description="Article ID", ge=1),
    background_tasks: BackgroundTasks = None,
):
    """Remove an article from a storyline in a specific domain"""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Check if article is in storyline
                cur.execute(
                    f"""
                    SELECT storyline_id FROM {schema}.storyline_articles
                    WHERE storyline_id = %s AND article_id = %s
                """,
                    (storyline_id, article_id),
                )

                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found in storyline")

                # Remove the article
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles
                    WHERE storyline_id = %s AND article_id = %s
                """,
                    (storyline_id, article_id),
                )

                # Update article count
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
                    background_tasks.add_task(trigger_storyline_evolution, domain, storyline_id, [])

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


@router.get("/{domain}/storylines/{storyline_id}/available_articles")
async def get_domain_available_articles_for_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        50, ge=1, le=100, description="Items per page (max 100 for performance)"
    ),
    search: str | None = Query(None, description="Search term for article title/summary"),
):
    """Get paginated list of articles available to add to a storyline"""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Build query for articles not in storyline
                base_query = f"""
                    FROM {schema}.articles a
                    WHERE a.id NOT IN (
                        SELECT sa.article_id
                        FROM {schema}.storyline_articles sa
                        WHERE sa.storyline_id = %s
                    )
                """
                params = [storyline_id]

                # Add search filter if provided
                if search:
                    base_query += " AND (a.title ILIKE %s OR a.summary ILIKE %s)"
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern, search_pattern])

                # Get total count
                count_query = f"SELECT COUNT(*) {base_query}"
                cur.execute(count_query, params)
                total = cur.fetchone()[0]

                # Calculate pagination
                offset = (page - 1) * page_size
                pages = math.ceil(total / page_size) if total > 0 else 0

                # Get paginated results
                query = f"""
                    SELECT a.id, a.title, a.summary, a.published_at, a.source_domain
                    {base_query}
                    ORDER BY a.published_at DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(query, params + [page_size, offset])

                articles = []
                for row in cur.fetchall():
                    articles.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "summary": row[2],
                            "published_at": row[3].isoformat() if row[3] else None,
                            "source_domain": row[4],
                        }
                    )

                pagination = PaginationInfo(
                    page=page,
                    page_size=page_size,
                    total=total,
                    pages=pages,
                    has_next=page < pages,
                    has_prev=page > 1,
                )

                return {
                    "success": True,
                    "data": {"articles": articles},
                    "pagination": pagination.dict(),
                    "count": len(articles),
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))
