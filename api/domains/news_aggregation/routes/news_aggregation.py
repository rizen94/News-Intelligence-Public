"""
Domain 1: News Aggregation Routes
Handles RSS feed processing, article ingestion, and content quality assessment
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from domains.news_aggregation.services.article_service import ArticleService
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path, Query
from shared.database.connection import get_db_connection
from shared.domain_registry import DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import (
    DOMAIN_DATA_SCHEMAS,
    resolve_article_id_to_schema,
    validate_domain,
)
from shared.services.llm_service import TaskType, llm_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api", tags=["News Aggregation"], responses={404: {"description": "Not found"}}
)


@router.get("/health")
async def health_check():
    """Health check for News Aggregation domain"""
    try:
        # Check database connection
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "domain": "news_aggregation",
                "status": "unhealthy",
                "error": "Database connection failed",
            }

        # Check LLM service (1s timeout — don't block health when Ollama is busy)
        llm_status = await llm_service.get_model_status(timeout_seconds=1.0)

        conn.close()

        return {
            "success": True,
            "domain": "news_aggregation",
            "status": "healthy",
            "llm_service": llm_status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "news_aggregation",
            "status": "unhealthy",
            "error": str(e),
        }


@router.get("/{domain}/rss_feeds")
async def get_domain_rss_feeds(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)):
    """Get all configured RSS feeds for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        # Get schema name
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT schema_name FROM domains WHERE domain_key = %s", (domain,))
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=400, detail=f"Domain {domain} not found")
                schema_name = result[0]

            # Get feeds from domain schema with article counts and all metadata
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                        rf.id,
                        rf.feed_name,
                        rf.feed_url,
                        rf.description,
                        rf.category,
                        rf.is_active,
                        rf.last_fetched_at,
                        rf.fetch_interval_seconds,
                        rf.created_at,
                        rf.updated_at,
                        rf.last_error_message,
                        COALESCE(article_counts.article_count, 0) as article_count
                    FROM {schema_name}.rss_feeds rf
                    LEFT JOIN (
                        SELECT
                            source_domain,
                            COUNT(*) as article_count
                        FROM {schema_name}.articles
                        GROUP BY source_domain
                    ) article_counts ON rf.feed_name = article_counts.source_domain
                    ORDER BY rf.feed_name
                """)

                feeds = []
                for row in cur.fetchall():
                    # Convert fetch_interval_seconds to minutes for frontend (update_interval)
                    fetch_interval_seconds = row[7] if row[7] else 1800  # Default 30 minutes
                    update_interval_minutes = fetch_interval_seconds // 60

                    feeds.append(
                        {
                            "id": row[0],
                            "name": row[1],  # Frontend expects "name" not "feed_name"
                            "feed_name": row[1],  # Keep both for compatibility
                            "url": row[2],  # Frontend expects "url" not "feed_url"
                            "feed_url": row[2],  # Keep both for compatibility
                            "description": row[3] if row[3] else None,
                            "category": row[4] if row[4] else None,
                            "is_active": row[5],
                            "last_fetched_at": row[6].isoformat() if row[6] else None,
                            "update_interval": update_interval_minutes,  # Frontend expects minutes
                            "fetch_interval_seconds": fetch_interval_seconds,  # Keep for API compatibility
                            "created_at": row[8].isoformat() if row[8] else None,
                            "updated_at": row[9].isoformat() if row[9] else None,
                            "last_error": row[10] if row[10] else None,
                            "article_count": row[11] if len(row) > 11 else 0,
                        }
                    )

                return {
                    "success": True,
                    "data": {"feeds": feeds, "domain": domain, "total": len(feeds)},
                    "count": len(feeds),
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching RSS feeds for domain {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _get_schema_for_domain(conn, domain: str):
    """Resolve schema_name from domain key. Raises HTTPException if invalid."""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    with conn.cursor() as cur:
        cur.execute("SELECT schema_name FROM domains WHERE domain_key = %s", (domain,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=400, detail=f"Domain {domain} not found")
        return result[0]


@router.post("/{domain}/rss_feeds")
async def create_domain_rss_feed(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    feed_data: dict[str, Any] = Body(...),
):
    """Create a new RSS feed in the given domain with duplicate prevention."""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            schema_name = _get_schema_for_domain(conn, domain)
            feed_url = feed_data.get("feed_url") or feed_data.get("url")
            feed_name = feed_data.get("feed_name") or feed_data.get("name")
            if not feed_url or not feed_name:
                raise HTTPException(status_code=400, detail="feed_url and feed_name are required")
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, feed_name, is_active FROM {schema_name}.rss_feeds WHERE feed_url = %s
                """,
                    (feed_url,),
                )
                existing = cur.fetchone()
                if existing:
                    return {
                        "success": False,
                        "error": "duplicate_url",
                        "data": {
                            "existing_feed": {
                                "id": existing[0],
                                "name": existing[1],
                                "is_active": existing[2],
                            }
                        },
                        "message": f"RSS feed with URL already exists (ID: {existing[0]})",
                    }
                fetch_interval = (
                    feed_data.get("fetch_interval_seconds")
                    or (feed_data.get("update_interval") and int(feed_data["update_interval"]) * 60)
                    or 3600
                )
                cur.execute(
                    f"""
                    INSERT INTO {schema_name}.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        feed_name,
                        feed_url,
                        feed_data.get("is_active", True),
                        fetch_interval,
                        datetime.now(),
                    ),
                )
                feed_id = cur.fetchone()[0]
                conn.commit()
                return {
                    "success": True,
                    "data": {"feed_id": feed_id, "domain": domain},
                    "message": "RSS feed created successfully",
                    "timestamp": datetime.now().isoformat(),
                }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{domain}/rss_feeds/{feed_id}")
async def update_domain_rss_feed(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    feed_id: int = Path(..., description="Feed ID"),
    feed_data: dict[str, Any] = Body(...),
):
    """Update an RSS feed in the given domain."""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            schema_name = _get_schema_for_domain(conn, domain)
            updates = []
            params = []
            if "feed_name" in feed_data and feed_data["feed_name"] is not None:
                updates.append("feed_name = %s")
                params.append(feed_data["feed_name"])
            elif "name" in feed_data and feed_data["name"] is not None:
                updates.append("feed_name = %s")
                params.append(feed_data["name"])
            if "feed_url" in feed_data and feed_data["feed_url"] is not None:
                updates.append("feed_url = %s")
                params.append(feed_data["feed_url"])
            elif "url" in feed_data and feed_data["url"] is not None:
                updates.append("feed_url = %s")
                params.append(feed_data["url"])
            if "is_active" in feed_data:
                updates.append("is_active = %s")
                params.append(bool(feed_data["is_active"]))
            if "fetch_interval_seconds" in feed_data:
                updates.append("fetch_interval_seconds = %s")
                params.append(int(feed_data["fetch_interval_seconds"]))
            elif "update_interval" in feed_data and feed_data["update_interval"] is not None:
                updates.append("fetch_interval_seconds = %s")
                params.append(int(feed_data["update_interval"]) * 60)
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            updates.append("updated_at = %s")
            params.append(datetime.now())
            params.append(feed_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {schema_name}.rss_feeds SET " + ", ".join(updates) + " WHERE id = %s",
                    params,
                )
                if cur.rowcount == 0:
                    raise HTTPException(
                        status_code=404, detail=f"Feed {feed_id} not found in domain {domain}"
                    )
                conn.commit()
            return {
                "success": True,
                "data": {"feed_id": feed_id, "domain": domain},
                "message": "RSS feed updated successfully",
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{domain}/rss_feeds/{feed_id}")
async def delete_domain_rss_feed(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    feed_id: int = Path(..., description="Feed ID"),
):
    """Delete an RSS feed from the given domain."""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            schema_name = _get_schema_for_domain(conn, domain)
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {schema_name}.rss_feeds WHERE id = %s", (feed_id,))
                if cur.rowcount == 0:
                    raise HTTPException(
                        status_code=404, detail=f"Feed {feed_id} not found in domain {domain}"
                    )
                conn.commit()
            return {
                "success": True,
                "data": {"feed_id": feed_id, "domain": domain},
                "message": "RSS feed deleted successfully",
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rss_feeds")
async def create_rss_feed(feed_data: dict[str, Any] = Body(...)):
    """Create RSS feed (legacy). Prefer POST /{domain}/rss_feeds. Uses domain from body or defaults to politics."""
    domain = feed_data.get("domain") or "politics"
    if domain not in ("politics", "finance", "science-tech"):
        raise HTTPException(
            status_code=400, detail="domain must be politics, finance, or science-tech"
        )
    # Delegate to domain-scoped create
    return await create_domain_rss_feed(domain=domain, feed_data=feed_data)


@router.post("/{domain}/rss_feeds/collect_now")
async def collect_rss_feeds_now(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)):
    """Trigger immediate RSS feed collection and wait for completion"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        # Import collector function
        import os
        import sys

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        from collectors.rss_collector import collect_rss_feeds

        logger.info(f"Starting RSS feed collection via API for domain: {domain}")

        # Run collection synchronously (collects from all domains)
        articles_added = collect_rss_feeds()

        return {
            "success": True,
            "message": "RSS feed collection completed",
            "articles_added": articles_added,
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error collecting RSS feeds: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "RSS feed collection failed",
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/fetch_articles")
async def fetch_articles_from_feeds(background_tasks: BackgroundTasks):
    """Trigger RSS collection for all domains (uses collect_rss_feeds; domain-scoped feeds)."""

    def _run_collect():
        try:
            from collectors.rss_collector import collect_rss_feeds

            return collect_rss_feeds()
        except Exception as e:
            logger.error("collect_rss_feeds failed: %s", e)
            return None

    background_tasks.add_task(_run_collect)
    return {
        "success": True,
        "message": "RSS collection started for all domains (collect_rss_feeds)",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/{domain}/articles")
async def get_domain_articles(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN, description="Domain key"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of articles (max 100 for performance)"
    ),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    hours: int | None = Query(None, ge=1, description="Filter articles from last N hours"),
    search: str | None = Query(None, description="Search in title and content"),
    source_domain: str | None = Query(None, description="Filter by source domain"),
    processing_status: str | None = Query(None, description="Filter by processing status"),
    unlinked: bool | None = Query(
        None, description="Only show articles not linked to any storyline"
    ),
    quality_first: bool | None = Query(
        False, description="Order by quality_tier then quality_score before recency"
    ),
    max_quality_tier: int | None = Query(
        None, ge=1, le=4, description="Only articles with quality_tier <= this (1=best, 4=worst)"
    ),
):
    """
    Get articles for a specific domain with optional filtering and pagination.

    Domain-aware endpoint that returns articles from the specified domain schema.
    """
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        # Create domain-aware service
        article_service = ArticleService(domain=domain)

        # Build filters
        filters = {}
        if source_domain:
            filters["source_domain"] = source_domain
        if processing_status:
            filters["processing_status"] = processing_status
        if hours:
            from datetime import datetime, timedelta

            filters["published_after"] = datetime.now() - timedelta(hours=hours)
        if unlinked:
            filters["unlinked"] = True
        if quality_first:
            filters["quality_first"] = True
        if max_quality_tier is not None:
            filters["max_quality_tier"] = max_quality_tier

        # Get articles
        result = article_service.get_articles(limit=limit, offset=offset, filters=filters)

        # Apply search filter if provided (post-query for now, can be optimized)
        if search:
            articles = result["data"]["articles"]
            search_lower = search.lower()
            filtered_articles = [
                a
                for a in articles
                if search_lower in (a.get("title", "") or "").lower()
                or search_lower in (a.get("content", "") or "").lower()
            ]
            result["data"]["articles"] = filtered_articles
            result["data"]["count"] = len(filtered_articles)

        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching articles for domain {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/articles/{article_id}")
async def get_domain_article(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_id: int = Path(..., description="Article ID"),
):
    """Get a single article by ID from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        # Create domain-aware service
        article_service = ArticleService(domain=domain)

        # Get article
        article = article_service.get_article(article_id)

        if not article:
            raise HTTPException(
                status_code=404, detail=f"Article {article_id} not found in domain {domain}"
            )

        return {"success": True, "data": article, "domain": domain}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error fetching article {article_id} from domain {domain}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/articles/{article_id}/fetch-full-content")
async def post_fetch_article_full_content(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_id: int = Path(..., description="Article ID"),
):
    """Fetch full article body from the source URL, persist it, and return it for the article reader."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        from services.article_content_enrichment_service import fetch_full_content_for_article

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, partial(fetch_full_content_for_article, domain, article_id)
        )

        if result.get("not_found"):
            raise HTTPException(
                status_code=404, detail=f"Article {article_id} not found in domain {domain}"
            )

        if result.get("success"):
            return {
                "success": True,
                "data": {"content": result.get("content") or ""},
                "domain": domain,
            }

        return {
            "success": False,
            "message": result.get("message") or "Could not fetch article text.",
            "data": {"content": (result.get("content") or "")},
            "domain": domain,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching full content for article {article_id} in domain {domain}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{domain}/articles/{article_id}")
async def delete_domain_article(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_id: int = Path(..., description="Article ID"),
):
    """Delete an article from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Check if article exists
                cur.execute(f"SELECT id FROM {schema}.articles WHERE id = %s", (article_id,))
                if not cur.fetchone():
                    raise HTTPException(
                        status_code=404, detail=f"Article {article_id} not found in domain {domain}"
                    )

                # Delete article (cascade will handle related records)
                cur.execute(f"DELETE FROM {schema}.articles WHERE id = %s", (article_id,))
                conn.commit()

                return {
                    "success": True,
                    "message": f"Article {article_id} deleted successfully",
                    "domain": domain,
                }
        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error deleting article {article_id} from domain {domain}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{domain}/articles")
async def delete_domain_articles_bulk(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_ids: list[int] = Body(..., description="List of article IDs to delete"),
):
    """Bulk delete articles from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        if not article_ids:
            raise HTTPException(status_code=400, detail="No article IDs provided")

        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Delete articles
                placeholders = ",".join(["%s"] * len(article_ids))
                cur.execute(
                    f"DELETE FROM {schema}.articles WHERE id IN ({placeholders})", article_ids
                )
                deleted_count = cur.rowcount
                conn.commit()

                return {
                    "success": True,
                    "message": f"Deleted {deleted_count} article(s) successfully",
                    "deleted_count": deleted_count,
                    "domain": domain,
                }
        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk deleting articles from domain {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backward compatibility (redirects to politics domain)
@router.get("/articles/recent")
async def get_recent_articles_legacy(
    limit: int = 50,
    hours: int | None = None,
    page: int | None = None,
    offset: int | None = None,
    search: str | None = None,
    source_domain: str | None = None,
    sort: str | None = None,
):
    """
    Legacy endpoint - redirects to politics domain.
    Use /api/{domain}/articles instead.
    """
    # Redirect to politics domain
    return await get_domain_articles(
        domain="politics",
        limit=limit,
        offset=offset if offset is not None else ((page - 1) * limit if page else 0),
        hours=hours,
        search=search,
        source_domain=source_domain,
        processing_status=None,
    )


@router.post("/articles/{article_id}/analyze_quality")
async def analyze_article_quality(article_id: int, background_tasks: BackgroundTasks):
    """Analyze article quality using LLM"""
    try:
        schema = resolve_article_id_to_schema(article_id)
        if not schema:
            raise HTTPException(status_code=404, detail="Article not found")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, content, url, source_domain
                    FROM {schema}.articles
                    WHERE id = %s
                """,
                    (article_id,),
                )

                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")

                # Start background quality analysis
                background_tasks.add_task(process_article_quality, article + (schema,))

                return {
                    "success": True,
                    "message": "Quality analysis started",
                    "article_id": article_id,
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error starting quality analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_aggregation_statistics():
    """Get news aggregation statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                total_articles = 0
                yesterday = datetime.now() - timedelta(days=1)
                recent_articles = 0
                active_feeds = 0
                weighted_q = 0.0
                q_rows = 0
                for sch in DOMAIN_DATA_SCHEMAS:
                    cur.execute(f"SELECT COUNT(*) FROM {sch}.articles")
                    total_articles += cur.fetchone()[0] or 0
                    cur.execute(
                        f"SELECT COUNT(*) FROM {sch}.articles WHERE created_at >= %s",
                        (yesterday,),
                    )
                    recent_articles += cur.fetchone()[0] or 0
                    cur.execute(f"SELECT COUNT(*) FROM {sch}.rss_feeds WHERE is_active = true")
                    active_feeds += cur.fetchone()[0] or 0
                    cur.execute(f"""
                        SELECT COUNT(*), COALESCE(AVG(quality_score), 0)
                        FROM {sch}.articles
                        WHERE quality_score IS NOT NULL
                    """)
                    cnt, av = cur.fetchone()
                    cnt = cnt or 0
                    if cnt:
                        weighted_q += float(av or 0) * cnt
                        q_rows += cnt
                avg_quality = (weighted_q / q_rows) if q_rows else 0.0

                return {
                    "success": True,
                    "data": {
                        "total_articles": total_articles,
                        "recent_articles_24h": recent_articles,
                        "active_rss_feeds": active_feeds,
                        "average_quality_score": round(avg_quality, 2),
                    },
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _log_rss_pull(feed_id, feed_name, status, fetched, saved, start_time, error=None):
    """Standardized RSS pull logging."""
    try:
        from shared.logging.activity_logger import log_rss_pull

        duration_ms = (time.time() - start_time) * 1000
        log_rss_pull(
            feed_id=feed_id,
            feed_name=feed_name,
            status=status,
            articles_fetched=fetched,
            articles_saved=saved,
            duration_ms=duration_ms,
            error=error,
        )
    except Exception:
        pass


# Background task functions
async def process_rss_feeds(feeds: list[tuple]):
    """Deprecated legacy helper. Domain-scoped ingestion uses collectors.rss_collector.collect_rss_feeds."""
    logger.warning(
        "process_rss_feeds(feeds=) is deprecated (%s feeds ignored); use collect_rss_feeds()",
        len(feeds) if feeds else 0,
    )
    try:
        from collectors.rss_collector import collect_rss_feeds

        collect_rss_feeds()
    except Exception as e:
        logger.error("collect_rss_feeds: %s", e)


async def process_article_quality(article: tuple):
    """Background task to analyze article quality using LLM"""
    try:
        if len(article) >= 6:
            article_id, title, content, url, source_domain, schema = article[:6]
        else:
            article_id, title, content, url, source_domain = article[:5]
            schema = resolve_article_id_to_schema(article_id)
        if not schema:
            logger.error("process_article_quality: no schema for article %s", article_id)
            return

        # Use LLM to analyze quality
        quality_analysis = await llm_service.generate_summary(
            content, TaskType.COMPREHENSIVE_ANALYSIS
        )

        if quality_analysis["success"]:
            # Update article with quality analysis
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE {schema}.articles
                            SET quality_score = %s,
                                summary = %s,
                                updated_at = %s
                            WHERE id = %s
                        """,
                            (
                                85,  # Placeholder quality score
                                quality_analysis["summary"],
                                datetime.now(),
                                article_id,
                            ),
                        )
                        conn.commit()
                        logger.info(f"Updated quality analysis for article {article_id}")
                finally:
                    conn.close()

    except Exception as e:
        logger.error(f"Error processing article quality: {e}")
