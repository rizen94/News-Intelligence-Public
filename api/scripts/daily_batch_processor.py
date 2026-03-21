#!/usr/bin/env python3
"""
Daily Batch Processor for News Intelligence System
Runs comprehensive article processing pipeline at 4am daily
Processes RSS feeds, ML analysis, topic clustering, and more
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "api"))

# Configure logging
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f"daily_batch_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def process_rss_feeds():
    """Process all RSS feeds and collect new articles"""
    logger.info("=" * 80)
    logger.info("PHASE 1: RSS Feed Processing")
    logger.info("=" * 80)

    try:
        from services.rss import RSSService

        service = RSSService()
        processor = service.processing
        result = await processor.process_all_feeds()

        if result.get("success"):
            logger.info(
                f"✅ RSS Processing Complete: {result.get('processed', 0)} feeds processed, {result.get('errors', 0)} errors"
            )
            return result
        else:
            logger.error(f"❌ RSS Processing Failed: {result.get('error', 'Unknown error')}")
            return None

    except Exception as e:
        logger.error(f"❌ RSS Processing Exception: {e}", exc_info=True)
        return None


async def process_articles_ml():
    """Process articles through ML pipeline (sentiment, entities, quality)"""
    logger.info("=" * 80)
    logger.info("PHASE 2: ML Article Processing")
    logger.info("=" * 80)

    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            logger.error("❌ Database connection failed")
            return None

        try:
            with conn.cursor() as cur:
                # Get unprocessed articles from last 24 hours
                yesterday = datetime.now() - timedelta(days=1)
                cur.execute(
                    """
                    SELECT id, title, content, summary, source_domain, published_at
                    FROM articles
                    WHERE (processing_status IS NULL OR processing_status = 'raw' OR processing_status = 'pending')
                    AND created_at >= %s
                    ORDER BY published_at DESC
                    LIMIT 500
                """,
                    (yesterday,),
                )

                articles = cur.fetchall()
                logger.info(f"Found {len(articles)} articles to process")

                if len(articles) == 0:
                    logger.info("No articles to process")
                    return {"success": True, "processed": 0}

                # Update processing stage to indicate processing started
                # The actual ML processing will be handled by the API endpoints
                # For now, we'll mark them as being processed
                article_ids = [article[0] for article in articles]

                if article_ids:
                    placeholders = ",".join(["%s"] * len(article_ids))
                    cur.execute(
                        f"""
                        UPDATE articles
                        SET processing_status = 'ml_processing',
                            updated_at = NOW()
                        WHERE id IN ({placeholders})
                    """,
                        article_ids,
                    )
                    conn.commit()

                logger.info(
                    f"✅ ML Processing Initiated: {len(articles)} articles queued for processing"
                )
                logger.info(
                    "Note: Full ML processing (sentiment, quality, entities) will be handled by API endpoints"
                )
                return {"success": True, "queued": len(articles), "total": len(articles)}

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"❌ ML Processing Exception: {e}", exc_info=True)
        return None


async def process_topic_clustering():
    """Process topic clustering for recent articles - domain-aware"""
    logger.info("=" * 80)
    logger.info("PHASE 3: Topic Clustering (Domain-Aware)")
    logger.info("=" * 80)

    from domains.content_analysis.services.topic_clustering_service import TopicClusteringService
    from shared.database.connection import get_db_config, get_db_connection

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("❌ Database connection failed")
            return None

        # Get all active domains
        domains = []
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT domain_key, schema_name FROM domains WHERE is_active = TRUE")
                domains = cur.fetchall()
                logger.info(f"Found {len(domains)} active domains for topic clustering")
        except Exception as e:
            logger.error(f"Error fetching domains: {e}")
            return None

        total_processed = 0

        # Process each domain separately
        for domain_key, schema_name in domains:
            logger.info(f"\n📊 Processing domain: {domain_key} (schema: {schema_name})")

            try:
                # Initialize service for this domain
                topic_clustering_service = TopicClusteringService(
                    get_db_config(), domain=domain_key
                )

                # Get articles from this domain schema (last 7 days, not just 24 hours)
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {schema_name}, public")
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    cur.execute(
                        """
                        SELECT id, title, content, summary, source_domain, published_at
                        FROM articles
                        WHERE (processing_status IS NULL OR processing_status != 'topic_clustering')
                        AND created_at >= %s
                        ORDER BY published_at DESC
                        LIMIT 200
                    """,
                        (seven_days_ago,),
                    )

                    articles = cur.fetchall()
                    logger.info(f"   Found {len(articles)} articles in {domain_key} domain")

                    if len(articles) == 0:
                        logger.info(f"   ⚠️  No articles to cluster in {domain_key}")
                        continue

                    # Convert to dict format
                    articles_list = []
                    for article in articles:
                        articles_list.append(
                            {
                                "id": article[0],
                                "title": article[1],
                                "content": article[2] or "",
                                "summary": article[3] or "",
                                "source_domain": article[4],
                                "published_at": article[5].isoformat() if article[5] else None,
                            }
                        )

                    # Process articles one by one (TopicClusteringService processes individual articles)
                    batch_size = 10
                    domain_processed = 0

                    for i in range(0, len(articles_list), batch_size):
                        batch = articles_list[i : i + batch_size]
                        logger.info(
                            f"   Processing batch {i // batch_size + 1} ({len(batch)} articles)..."
                        )

                        for article in batch:
                            try:
                                # Process individual article
                                result = await topic_clustering_service.process_article(
                                    article["id"]
                                )

                                if result.get("success"):
                                    domain_processed += 1
                                    logger.debug(
                                        f"   ✅ Article {article['id']} processed: {result.get('total_assigned', 0)} topics assigned"
                                    )
                                else:
                                    logger.warning(
                                        f"   ⚠️  Article {article['id']} failed: {result.get('error', 'Unknown error')}"
                                    )

                            except Exception as e:
                                logger.error(
                                    f"   ❌ Error processing article {article.get('id', 'unknown')}: {e}"
                                )
                                continue

                        # Small delay between batches
                        await asyncio.sleep(1)

                    total_processed += domain_processed
                    logger.info(f"   ✅ {domain_key} domain: {domain_processed} articles processed")

            except Exception as e:
                logger.error(f"❌ Error processing domain {domain_key}: {e}")
                import traceback

                traceback.print_exc()
                continue

        logger.info(f"✅ Topic Clustering Complete: {total_processed} articles processed")
        return {"success": True, "processed": total_processed, "total": total_processed}
    except Exception as e:
        logger.error(f"❌ Topic Clustering Exception: {e}", exc_info=True)
        return None
    finally:
        if conn is not None:
            conn.close()


async def update_statistics():
    """Update system statistics and metrics"""
    logger.info("=" * 80)
    logger.info("PHASE 4: Statistics Update")
    logger.info("=" * 80)

    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            logger.error("❌ Database connection failed")
            return None

        try:
            with conn.cursor() as cur:
                # Update article counts
                cur.execute("""
                    SELECT
                        COUNT(*) as total_articles,
                        COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_articles,
                        COUNT(CASE WHEN processing_status = 'topic_clustering' OR processing_status = 'processed' THEN 1 END) as processed_articles
                    FROM articles
                """)

                stats = cur.fetchone()
                logger.info(
                    f"📊 Statistics: {stats[0]} total articles, {stats[1]} today, {stats[2]} processed"
                )

                conn.commit()
                return {
                    "success": True,
                    "stats": {"total": stats[0], "today": stats[1], "processed": stats[2]},
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"❌ Statistics Update Exception: {e}", exc_info=True)
        return None


async def main():
    """Main batch processing function"""
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("🚀 DAILY BATCH PROCESSOR STARTING")
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    results = {
        "rss_processing": None,
        "ml_processing": None,
        "topic_clustering": None,
        "statistics": None,
    }

    try:
        # Phase 1: RSS Feed Processing
        results["rss_processing"] = await process_rss_feeds()

        # Wait a bit between phases
        await asyncio.sleep(5)

        # Phase 2: ML Processing
        results["ml_processing"] = await process_articles_ml()

        # Wait a bit between phases
        await asyncio.sleep(5)

        # Phase 3: Topic Clustering
        results["topic_clustering"] = await process_topic_clustering()

        # Phase 4: Statistics
        results["statistics"] = await update_statistics()

        # Summary
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("=" * 80)
        logger.info("✅ DAILY BATCH PROCESSOR COMPLETE")
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")
        logger.info("=" * 80)
        logger.info("SUMMARY:")
        logger.info(f"  RSS Processing: {results['rss_processing']}")
        logger.info(f"  ML Processing: {results['ml_processing']}")
        logger.info(f"  Topic Clustering: {results['topic_clustering']}")
        logger.info(f"  Statistics: {results['statistics']}")
        logger.info("=" * 80)

        # Return success if at least RSS processing worked
        if results["rss_processing"] and results["rss_processing"].get("success"):
            return 0
        else:
            return 1

    except Exception as e:
        logger.error(f"❌ FATAL ERROR in batch processor: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
