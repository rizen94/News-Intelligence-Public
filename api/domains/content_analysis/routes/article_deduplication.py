"""
Article Deduplication API Endpoints
Provides API endpoints for detecting and managing duplicate articles
"""

import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from scripts.article_deduplication import ArticleDeduplicationSystem
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import (
    DOMAIN_DATA_SCHEMAS,
    resolve_article_id_to_schema,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/articles", tags=["Article Deduplication"])


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


@router.get("/duplicates/detect")
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


@router.get("/duplicates/url")
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


@router.get("/duplicates/content")
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


@router.get("/duplicates/similar")
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


@router.post("/duplicates/merge")
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


@router.post("/duplicates/auto_merge")
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
        logger.error(f"Error in auto-merge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/duplicates/prevent")
async def add_deduplication_prevention():
    """Add database constraints to prevent future duplicates"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            success = deduplicator.add_deduplication_constraints()
            hash_count = deduplicator.populate_content_hashes()

            return {
                "success": success,
                "data": {"constraints_added": success, "content_hashes_populated": hash_count},
                "message": "Deduplication prevention constraints added"
                if success
                else "Failed to add constraints",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error adding deduplication prevention: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/duplicates/stats")
async def get_deduplication_stats():
    """Get deduplication statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                total_articles = 0
                articles_with_hash = 0
                url_duplicate_count = 0
                content_duplicate_count = 0
                daily_map = {}
                for sch in DOMAIN_DATA_SCHEMAS:
                    cur.execute(f"SELECT COUNT(*) FROM {sch}.articles")
                    total_articles += cur.fetchone()[0] or 0
                    cur.execute(
                        f"SELECT COUNT(*) FROM {sch}.articles WHERE content_hash IS NOT NULL"
                    )
                    articles_with_hash += cur.fetchone()[0] or 0
                    cur.execute(f"""
                        SELECT COUNT(*) FROM (
                            SELECT url, COUNT(*) as count
                            FROM {sch}.articles
                            GROUP BY url
                            HAVING COUNT(*) > 1
                        ) duplicates
                    """)
                    url_duplicate_count += cur.fetchone()[0] or 0
                    cur.execute(f"""
                        SELECT COUNT(*) FROM (
                            SELECT content_hash, COUNT(*) as count
                            FROM {sch}.articles
                            WHERE content_hash IS NOT NULL
                            GROUP BY content_hash
                            HAVING COUNT(*) > 1
                        ) duplicates
                    """)
                    content_duplicate_count += cur.fetchone()[0] or 0
                    cur.execute(f"""
                        SELECT DATE(created_at) as date, COUNT(*) as count
                        FROM {sch}.articles
                        WHERE created_at >= NOW() - INTERVAL '7 days'
                        GROUP BY DATE(created_at)
                    """)
                    for date, count in cur.fetchall():
                        k = str(date)
                        daily_map[k] = daily_map.get(k, 0) + (count or 0)
                daily_counts = sorted(daily_map.items(), key=lambda x: x[0], reverse=True)

                return {
                    "success": True,
                    "data": {
                        "total_articles": total_articles,
                        "articles_with_content_hash": articles_with_hash,
                        "url_duplicate_groups": url_duplicate_count,
                        "content_duplicate_groups": content_duplicate_count,
                        "daily_counts": [{"date": d, "count": c} for d, c in daily_counts],
                        "hash_coverage_percentage": (articles_with_hash / total_articles * 100)
                        if total_articles > 0
                        else 0,
                    },
                    "message": "Deduplication statistics retrieved",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting deduplication stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/duplicates/analyze_similarity")
async def analyze_article_similarity(
    article_id: int, threshold: float = Query(0.85, description="Similarity threshold")
):
    """Analyze similarity of a specific article with others"""
    try:
        deduplicator = ArticleDeduplicationSystem()

        if not deduplicator.connect_database():
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            # Set custom threshold
            deduplicator.content_similarity_threshold = threshold

            # Get the target article
            with deduplicator.conn.cursor() as cur:
                sch = resolve_article_id_to_schema(article_id)
                if not sch:
                    raise HTTPException(status_code=404, detail="Article not found")
                cur.execute(
                    f"""
                    SELECT id, title, content, url, source_domain, created_at
                    FROM {sch}.articles
                    WHERE id = %s
                """,
                    (article_id,),
                )

                target_article = cur.fetchone()
                if not target_article:
                    raise HTTPException(status_code=404, detail="Article not found")

                # Find similar articles
                cur.execute(
                    f"""
                    SELECT id, title, content, url, source_domain, created_at
                    FROM {sch}.articles
                    WHERE id != %s AND content IS NOT NULL AND LENGTH(content) > 200
                    ORDER BY created_at DESC
                    LIMIT 100
                """,
                    (article_id,),
                )

                other_articles = cur.fetchall()

            # Calculate similarities
            similarities = []
            target_content = deduplicator.clean_content(target_article[2])

            for other_article in other_articles:
                other_content = deduplicator.clean_content(other_article[2])
                similarity = SequenceMatcher(None, target_content, other_content).ratio()

                if similarity >= threshold:
                    similarities.append(
                        {
                            "article_id": other_article[0],
                            "title": other_article[1],
                            "url": other_article[3],
                            "domain": other_article[4],
                            "created_at": other_article[5].isoformat(),
                            "similarity": similarity,
                        }
                    )

            # Sort by similarity
            similarities.sort(key=lambda x: x["similarity"], reverse=True)

            return {
                "success": True,
                "data": {
                    "target_article": {
                        "id": target_article[0],
                        "title": target_article[1],
                        "url": target_article[3],
                        "domain": target_article[4],
                        "created_at": target_article[5].isoformat(),
                    },
                    "similar_articles": similarities,
                    "threshold": threshold,
                    "count": len(similarities),
                },
                "message": f"Found {len(similarities)} similar articles",
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            deduplicator.close_connection()

    except Exception as e:
        logger.error(f"Error analyzing article similarity: {e}")
        raise HTTPException(status_code=500, detail=str(e))
