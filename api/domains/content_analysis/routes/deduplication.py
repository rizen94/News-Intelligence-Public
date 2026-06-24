"""
Unified Deduplication API Endpoints
Provides API endpoints for detecting and managing duplicates for both RSS feeds and articles
"""

from fastapi import APIRouter

# Routers for feeds and articles
router_feeds = APIRouter(prefix="/feeds", tags=["Deduplication - Feeds"])
router_articles = APIRouter(prefix="/articles", tags=["Deduplication - Articles"])


# ==================== FEEDS DEDUPLICATION ====================

from datetime import datetime
from typing import Any

from fastapi import HTTPException, Query
from pydantic import BaseModel
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import get_domain_data_schemas

from scripts.rss_duplicate_detector import RSSDuplicateDetector


def _find_rss_feed_schema(conn, feed_id: int) -> str | None:
    """Return domain schema name containing this rss_feeds.id, or None."""
    with conn.cursor() as cur:
        for sch in get_domain_data_schemas():
            cur.execute(
                f"SELECT 1 FROM {sch}.rss_feeds WHERE id = %s LIMIT 1",
                (feed_id,),
            )
            if cur.fetchone():
                return sch
    return None


logger = logging.getLogger(__name__)


class DuplicateDetectionResponse(BaseModel):
    success: bool
    data: dict[str, Any]
    message: str
    timestamp: str


class DuplicateMergeRequest(BaseModel):
    duplicate_id: int
    keep_feed_id: int
    remove_feed_ids: list[int]
    dry_run: bool = True


@router_feeds.get("/detect")
async def detect_duplicates():
    """Detect RSS feed duplicates"""
    try:
        detector = RSSDuplicateDetector()

        if not detector.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            report = detector.generate_duplicate_report()

            return DuplicateDetectionResponse(
                success=True,
                data=report,
                message=f"Found {report['summary']['total_issues']} duplicate issues",
                timestamp=datetime.now().isoformat(),
            )

        finally:
            detector.close_connection()

    except Exception as e:
        logger.error(f"Error detecting duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_feeds.get("/exact")
async def get_exact_duplicates():
    """Get feeds with exact URL duplicates"""
    try:
        detector = RSSDuplicateDetector()

        if not detector.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            duplicates = detector.detect_exact_duplicates()

            return {
                "success": True,
                "data": {"duplicates": duplicates, "count": len(duplicates)},
                "message": f"Found {len(duplicates)} exact URL duplicates",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            detector.close_connection()

    except Exception as e:
        logger.error(f"Error getting exact duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_feeds.get("/similar")
async def get_similar_feeds():
    """Get feeds with similar domains"""
    try:
        detector = RSSDuplicateDetector()

        if not detector.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            similar_feeds = detector.detect_similar_feeds()

            return {
                "success": True,
                "data": {"similar_feeds": similar_feeds, "count": len(similar_feeds)},
                "message": f"Found {len(similar_feeds)} domains with multiple feeds",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            detector.close_connection()

    except Exception as e:
        logger.error(f"Error getting similar feeds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_feeds.post("/merge")
async def merge_duplicates(request: DuplicateMergeRequest):
    """Merge duplicate RSS feeds"""
    try:
        detector = RSSDuplicateDetector()

        if not detector.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            conn = detector.conn
            sch = _find_rss_feed_schema(conn, request.keep_feed_id)
            if not sch:
                raise HTTPException(
                    status_code=404,
                    detail=f"RSS feed id {request.keep_feed_id} not found in any domain schema",
                )
            for rid in request.remove_feed_ids:
                rs = _find_rss_feed_schema(conn, rid)
                if rs != sch:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"remove_feed_ids must belong to the same schema as keep_feed_id "
                            f"({sch}); feed {rid} is in {rs!r}"
                        ),
                    )

            duplicate_info = {
                "ids": [request.keep_feed_id] + request.remove_feed_ids,
                "type": "exact_url",
                "url": "",
                "names": [],
                "active_status": [],
                "domain_schema": sch,
            }

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT feed_url, feed_name, is_active
                    FROM {sch}.rss_feeds
                    WHERE id = %s
                    """,
                    (request.keep_feed_id,),
                )

                result = cur.fetchone()
                if result:
                    duplicate_info["url"] = result[0]
                    duplicate_info["names"] = [result[1]]
                    duplicate_info["active_status"] = [result[2]]

            # Perform merge
            merge_results = detector.auto_merge_duplicates(
                [duplicate_info], dry_run=request.dry_run
            )

            return {
                "success": True,
                "data": merge_results,
                "message": f"{'Dry run: ' if request.dry_run else ''}Merged {len(request.remove_feed_ids)} duplicate feeds",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            detector.close_connection()

    except Exception as e:
        logger.error(f"Error merging duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_feeds.post("/auto_merge")
async def auto_merge_all_duplicates(dry_run: bool = Query(True, description="Dry run mode")):
    """Automatically merge all detected duplicates"""
    try:
        detector = RSSDuplicateDetector()

        if not detector.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            # Detect duplicates
            duplicates = detector.detect_exact_duplicates()

            if not duplicates:
                return {
                    "success": True,
                    "data": {"merged": [], "errors": [], "total_processed": 0},
                    "message": "No duplicates found to merge",
                    "timestamp": datetime.now().isoformat(),
                }

            # Merge duplicates
            merge_results = detector.auto_merge_duplicates(duplicates, dry_run=dry_run)

            return {
                "success": True,
                "data": merge_results,
                "message": f"{'Dry run: ' if dry_run else ''}Processed {merge_results['total_processed']} duplicate feeds",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            detector.close_connection()

    except Exception as e:
        logger.error(f"Error in auto-merge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_feeds.post("/prevent")
async def add_duplicate_prevention():
    """Add database constraints to prevent future duplicates"""
    try:
        detector = RSSDuplicateDetector()

        if not detector.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            success = detector.add_duplicate_prevention_constraints()

            return {
                "success": success,
                "data": {"constraints_added": success},
                "message": "Duplicate prevention constraints added"
                if success
                else "Failed to add constraints",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            detector.close_connection()

    except Exception as e:
        logger.error(f"Error adding duplicate prevention: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_feeds.get("/stats")
async def get_duplicate_stats():
    """Get duplicate detection statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                total_feeds = 0
                active_feeds = 0
                feeds_with_articles = 0
                duplicate_count = 0
                for sch in get_domain_data_schemas():
                    cur.execute(f"SELECT COUNT(*) FROM {sch}.rss_feeds")
                    total_feeds += cur.fetchone()[0] or 0
                    cur.execute(f"SELECT COUNT(*) FROM {sch}.rss_feeds WHERE is_active = true")
                    active_feeds += cur.fetchone()[0] or 0
                    cur.execute(f"""
                        SELECT COUNT(DISTINCT rss_feed_id)
                        FROM {sch}.articles
                        WHERE rss_feed_id IS NOT NULL
                    """)
                    feeds_with_articles += cur.fetchone()[0] or 0
                    cur.execute(f"""
                        SELECT COUNT(*) FROM (
                            SELECT feed_url, COUNT(*) AS count
                            FROM {sch}.rss_feeds
                            GROUP BY feed_url
                            HAVING COUNT(*) > 1
                        ) duplicates
                    """)
                    duplicate_count += cur.fetchone()[0] or 0

                return {
                    "success": True,
                    "data": {
                        "total_feeds": total_feeds,
                        "active_feeds": active_feeds,
                        "inactive_feeds": total_feeds - active_feeds,
                        "feeds_with_articles": feeds_with_articles,
                        "duplicate_groups": duplicate_count,
                        "active_percentage": (active_feeds / total_feeds * 100)
                        if total_feeds > 0
                        else 0,
                    },
                    "message": "Duplicate statistics retrieved",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting duplicate stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ARTICLES DEDUPLICATION ====================

import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException, Query
from pydantic import BaseModel
from scripts.article_deduplication import ArticleDeduplicationSystem
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import (
    get_domain_data_schemas,
    resolve_article_id_to_schema,
)

logger = logging.getLogger(__name__)


class DeduplicationResponse(BaseModel):
    success: bool
    data: dict[str, Any]
    message: str
    timestamp: str


class DuplicateMergeRequest(BaseModel):
    duplicate_type: str
    keep_article_id: int
    remove_article_ids: list[int]
    dry_run: bool = True


@router_articles.get("/detect")
async def detect_duplicates():
    """Detect all types of article duplicates"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            report = deduplicator.generate_deduplication_report()

            return DeduplicationResponse(
                success=True,
                data=report,
                message=f"Found {report['summary']['total_issues']} duplicate issues",
                timestamp=datetime.now().isoformat(),
            )

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error detecting duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_articles.get("/url")
async def get_url_duplicates():
    """Get articles with exact URL duplicates"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            duplicates = deduplicator.detect_url_duplicates()

            return {
                "success": True,
                "data": {"duplicates": duplicates, "count": len(duplicates)},
                "message": f"Found {len(duplicates)} exact URL duplicates",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error getting URL duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_articles.get("/content")
async def get_content_duplicates():
    """Get articles with duplicate content"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            duplicates = deduplicator.detect_content_duplicates()

            return {
                "success": True,
                "data": {"duplicates": duplicates, "count": len(duplicates)},
                "message": f"Found {len(duplicates)} content duplicates",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error getting content duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_articles.get("/similar")
async def get_content_similarities():
    """Get articles with similar content"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            similarities = deduplicator.detect_content_similarities()

            return {
                "success": True,
                "data": {"similarities": similarities, "count": len(similarities)},
                "message": f"Found {len(similarities)} content similarity groups",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error getting content similarities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_articles.post("/merge")
async def merge_duplicates(request: DuplicateMergeRequest):
    """Merge duplicate articles"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            # Create a duplicate structure for the merge function
            duplicate_info = {
                "type": request.duplicate_type,
                "article_ids": [request.keep_article_id] + request.remove_article_ids,
                "url": "",  # Will be filled from database
                "titles": [],  # Will be filled from database
            }

            # Get article details
            conn = deduplicator.conn
            with conn.cursor() as cur:
                sch = resolve_article_id_to_schema(request.keep_article_id)
                if not sch:
                    raise HTTPException(status_code=404, detail="Article not found")
                cur.execute(
                    f"""
                    SELECT url, title
                    FROM {sch}.articles
                    WHERE id = %s
                    """,
                    (request.keep_article_id,),
                )

                result = cur.fetchone()
                if result:
                    duplicate_info["url"] = result[0]
                    duplicate_info["titles"] = [result[1]]

            # Perform merge
            merge_results = deduplicator.merge_duplicates([duplicate_info], dry_run=request.dry_run)

            return {
                "success": True,
                "data": merge_results,
                "message": f"{'Dry run: ' if request.dry_run else ''}Merged {len(request.remove_article_ids)} duplicate articles",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error merging duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router_articles.post("/auto_merge")
async def auto_merge_url_duplicates(dry_run: bool = Query(True, description="Dry run mode")):
    """Automatically merge all URL duplicates"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            # Detect URL duplicates
            duplicates = deduplicator.detect_url_duplicates()

            if not duplicates:
                return {
                    "success": True,
                    "data": {"merged": [], "errors": [], "total_processed": 0},
                    "message": "No URL duplicates found to merge",
                    "timestamp": datetime.now().isoformat(),
                }

            # Merge duplicates
            merge_results = deduplicator.merge_duplicates(duplicates, dry_run=dry_run)

            return {
                "success": True,
                "data": merge_results,
                "message": f"{'Dry run: ' if dry_run else ''}Processed {merge_results['total_processed']} duplicate articles",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error auto-merging duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MAIN ROUTER ====================

main_router = APIRouter(prefix="/deduplication", tags=["Deduplication"])
main_router.include_router(router_feeds)
main_router.include_router(router_articles)