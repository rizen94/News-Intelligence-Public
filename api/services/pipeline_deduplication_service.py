"""
Pipeline Deduplication Service
Automatically runs deduplication after article import in the RSS processing pipeline
"""

import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from config.database import get_db
from scripts.article_deduplication import ArticleDeduplicationSystem
from sqlalchemy import text

from services.pipeline_logger import get_pipeline_logger

logger = logging.getLogger(__name__)


class PipelineDeduplicationService:
    """Pipeline service for automatic article deduplication"""

    def __init__(self):
        self.session = None
        self.pipeline_logger = get_pipeline_logger()
        self.deduplicator = ArticleDeduplicationSystem()

    async def run_deduplication_pipeline(
        self, trace_id: str, feed_id: str | None = None
    ) -> dict[str, Any]:
        """Run deduplication pipeline after article import"""

        try:
            logger.info("Starting pipeline deduplication")
            self.session = next(get_db())

            # Log pipeline checkpoint
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage="deduplication_start",
                status="running",
                metadata={"service": "pipeline_deduplication"},
            )

            # Connect deduplicator to database
            if not self.deduplicator.connect_database():
                raise Exception("Failed to connect deduplicator to database")

            try:
                # Get recently imported articles (last 10 minutes)
                recent_articles = await self._get_recent_articles(feed_id)

                if not recent_articles:
                    logger.info("No recent articles found for deduplication")
                    return {
                        "success": True,
                        "processed": 0,
                        "duplicates_found": 0,
                        "duplicates_merged": 0,
                    }

                logger.info(f"Found {len(recent_articles)} recent articles for deduplication")

                # Run deduplication analysis
                deduplication_results = await self._run_deduplication_analysis(
                    recent_articles, trace_id
                )

                # Log results
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage="deduplication_complete",
                    status="success",
                    metadata={
                        "articles_processed": len(recent_articles),
                        "duplicates_found": deduplication_results["duplicates_found"],
                        "duplicates_merged": deduplication_results["duplicates_merged"],
                    },
                )

                logger.info(
                    f"Deduplication completed: {deduplication_results['duplicates_found']} duplicates found, {deduplication_results['duplicates_merged']} merged"
                )

                return {
                    "success": True,
                    "processed": len(recent_articles),
                    "duplicates_found": deduplication_results["duplicates_found"],
                    "duplicates_merged": deduplication_results["duplicates_merged"],
                }

            finally:
                self.deduplicator.close_connection()

        except Exception as e:
            logger.error(f"Pipeline deduplication failed: {e}")

            # Log error checkpoint
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage="deduplication_error",
                status="error",
                error_message=str(e),
                metadata={"service": "pipeline_deduplication"},
            )

            return {
                "success": False,
                "error": str(e),
                "processed": 0,
                "duplicates_found": 0,
                "duplicates_merged": 0,
            }

        finally:
            if self.session:
                self.session.close()

    async def _get_recent_articles(self, feed_id: str | None = None) -> list[dict[str, Any]]:
        """Get recently imported articles for deduplication"""
        try:
            # Get articles from last 10 minutes
            query_params = {"time_threshold": datetime.now() - timedelta(minutes=10)}
            base_query = """
                SELECT id, title, content, url, source_domain, created_at, feed_id
                FROM articles
                WHERE created_at >= :time_threshold
            """

            if feed_id and feed_id != "all_feeds":
                base_query += " AND feed_id = :feed_id"
                query_params["feed_id"] = feed_id

            base_query += " ORDER BY created_at DESC"

            query = text(base_query)
            result = self.session.execute(query, query_params)

            articles = []
            for row in result:
                articles.append(
                    {
                        "id": row.id,
                        "title": row.title,
                        "content": row.content,
                        "url": row.url,
                        "source_domain": row.source_domain,
                        "created_at": row.created_at,
                        "feed_id": row.feed_id,
                    }
                )

            return articles

        except Exception as e:
            logger.error(f"Error getting recent articles: {e}")
            return []

    async def _run_deduplication_analysis(
        self, articles: list[dict[str, Any]], trace_id: str
    ) -> dict[str, Any]:
        """Run deduplication analysis on recent articles"""
        try:
            duplicates_found = 0
            duplicates_merged = 0

            # Check for URL duplicates
            url_duplicates = self.deduplicator.detect_url_duplicates()
            duplicates_found += len(url_duplicates)

            if url_duplicates:
                logger.info(f"Found {len(url_duplicates)} URL duplicate groups")

                # Auto-merge URL duplicates (dry run first to log)
                merge_results = self.deduplicator.merge_duplicates(url_duplicates, dry_run=True)
                logger.info(
                    f"Would merge {merge_results['total_processed']} URL duplicate articles"
                )

                # Actually merge URL duplicates
                merge_results = self.deduplicator.merge_duplicates(url_duplicates, dry_run=False)
                duplicates_merged += merge_results["total_processed"]

                # Log merge results
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage="url_deduplication",
                    status="success",
                    metadata={
                        "duplicates_found": len(url_duplicates),
                        "articles_merged": merge_results["total_processed"],
                    },
                )

            # Check for content duplicates
            content_duplicates = self.deduplicator.detect_content_duplicates()
            duplicates_found += len(content_duplicates)

            if content_duplicates:
                logger.info(f"Found {len(content_duplicates)} content duplicate groups")

                # Log content duplicates (don't auto-merge, require manual review)
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage="content_deduplication",
                    status="warning",
                    metadata={
                        "duplicates_found": len(content_duplicates),
                        "action": "manual_review_required",
                    },
                )

            # Check for content similarities (only for recent articles)
            content_similarities = await self._check_recent_similarities(articles)
            duplicates_found += len(content_similarities)

            if content_similarities:
                logger.info(f"Found {len(content_similarities)} content similarity groups")

                # Log similarities (don't auto-merge, require manual review)
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage="content_similarity",
                    status="info",
                    metadata={
                        "similarities_found": len(content_similarities),
                        "action": "manual_review_required",
                    },
                )

            return {
                "duplicates_found": duplicates_found,
                "duplicates_merged": duplicates_merged,
                "url_duplicates": len(url_duplicates),
                "content_duplicates": len(content_duplicates),
                "content_similarities": len(content_similarities),
            }

        except Exception as e:
            logger.error(f"Error in deduplication analysis: {e}")
            return {
                "duplicates_found": 0,
                "duplicates_merged": 0,
                "url_duplicates": 0,
                "content_duplicates": 0,
                "content_similarities": 0,
            }

    async def _check_recent_similarities(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Check for content similarities in recent articles"""
        try:
            similarities = []

            # Only check if we have enough articles
            if len(articles) < 2:
                return similarities

            # Compare recent articles with each other
            for i, article1 in enumerate(articles):
                for j, article2 in enumerate(articles[i + 1 :], i + 1):
                    if article1["id"] == article2["id"]:
                        continue

                    # Check content similarity
                    content1 = self.deduplicator.clean_content(article1.get("content", ""))
                    content2 = self.deduplicator.clean_content(article2.get("content", ""))

                    if len(content1) < 100 or len(content2) < 100:
                        continue

                    similarity = SequenceMatcher(None, content1, content2).ratio()

                    if similarity >= self.deduplicator.content_similarity_threshold:
                        similarities.append(
                            {"article1": article1, "article2": article2, "similarity": similarity}
                        )

            return similarities

        except Exception as e:
            logger.error(f"Error checking recent similarities: {e}")
            return []

    async def get_deduplication_metrics(self) -> dict[str, Any]:
        """Get deduplication metrics for pipeline monitoring"""
        try:
            if not self.deduplicator.connect_database():
                return {"error": "Database connection failed"}

            try:
                # Get deduplication statistics
                with self.deduplicator.conn.cursor() as cur:
                    # Total articles
                    cur.execute("SELECT COUNT(*) FROM articles")
                    total_articles = cur.fetchone()[0]

                    # Articles with content hash
                    cur.execute("SELECT COUNT(*) FROM articles WHERE content_hash IS NOT NULL")
                    articles_with_hash = cur.fetchone()[0]

                    # URL duplicates
                    cur.execute("""
                        SELECT COUNT(*) FROM (
                            SELECT url, COUNT(*) as count
                            FROM articles
                            GROUP BY url
                            HAVING COUNT(*) > 1
                        ) duplicates
                    """)
                    url_duplicates = cur.fetchone()[0]

                    # Content duplicates
                    cur.execute("""
                        SELECT COUNT(*) FROM (
                            SELECT content_hash, COUNT(*) as count
                            FROM articles
                            WHERE content_hash IS NOT NULL
                            GROUP BY content_hash
                            HAVING COUNT(*) > 1
                        ) duplicates
                    """)
                    content_duplicates = cur.fetchone()[0]

                    # Recent deduplication activity (last 24 hours)
                    cur.execute("""
                        SELECT COUNT(*) FROM pipeline_traces
                        WHERE stage LIKE '%deduplication%'
                        AND created_at >= NOW() - INTERVAL '24 hours'
                    """)
                    recent_activity = cur.fetchone()[0]

                    return {
                        "total_articles": total_articles,
                        "articles_with_hash": articles_with_hash,
                        "hash_coverage_percentage": (articles_with_hash / total_articles * 100)
                        if total_articles > 0
                        else 0,
                        "url_duplicates": url_duplicates,
                        "content_duplicates": content_duplicates,
                        "recent_deduplication_runs": recent_activity,
                        "last_updated": datetime.now().isoformat(),
                    }

            finally:
                self.deduplicator.close_connection()

        except Exception as e:
            logger.error(f"Error getting deduplication metrics: {e}")
            return {"error": str(e)}
