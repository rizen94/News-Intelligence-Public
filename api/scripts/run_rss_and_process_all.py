#!/usr/bin/env python3
"""
Pull latest from RSS feeds, then process all articles (entity extraction + topic extraction).
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from collectors.rss_collector import collect_rss_feeds
    from shared.database.connection import get_db_connection
    from domains.content_analysis.services.topic_extraction_queue_worker import TopicExtractionQueueWorker

    print("=" * 60)
    print("1. RSS Feed Collection")
    print("=" * 60)
    articles_added = collect_rss_feeds()
    print(f"   Articles added: {articles_added}\n")

    print("=" * 60)
    print("2. Queue unprocessed articles & process (entity + topic extraction)")
    print("=" * 60)

    domains = [("politics", "politics"), ("finance", "finance"), ("science-tech", "science_tech")]
    total_processed = 0
    max_batches_per_domain = 200  # Safety limit
    batch_size = 5

    for domain_key, schema in domains:
        conn = get_db_connection()
        if not conn:
            print(f"   Skipping {domain_key}: no DB connection")
            continue
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN {schema}.topic_extraction_queue tq ON a.id = tq.article_id
                    WHERE a.content IS NOT NULL AND LENGTH(a.content) > 100
                    AND tq.id IS NULL
                """)
                unqueued = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM {schema}.topic_extraction_queue WHERE status IN ('pending', 'processing')")
                pending = cur.fetchone()[0]
            conn.close()

            to_queue = unqueued
            if to_queue > 0:
                conn2 = get_db_connection()
                queued_count = 0
                try:
                    with conn2.cursor() as cur:
                        cur.execute(f"SET search_path TO {schema}, public")
                        cur.execute(f"""
                            SELECT a.id FROM {schema}.articles a
                            LEFT JOIN {schema}.topic_extraction_queue tq ON a.id = tq.article_id
                            WHERE a.content IS NOT NULL AND LENGTH(a.content) > 100
                            AND tq.id IS NULL
                            ORDER BY a.created_at DESC
                            LIMIT 500
                        """)
                        ids = [r[0] for r in cur.fetchall()]
                        for aid in ids:
                            try:
                                cur.execute(f"""
                                    INSERT INTO {schema}.topic_extraction_queue (article_id, status, priority, created_at)
                                    VALUES (%s, 'pending', 2, NOW())
                                    ON CONFLICT (article_id) DO NOTHING
                                """, (aid,))
                                if cur.rowcount > 0:
                                    queued_count += 1
                            except Exception:
                                pass
                    conn2.commit()
                    print(f"   {domain_key}: queued {queued_count} articles")
                finally:
                    conn2.close()
            else:
                print(f"   {domain_key}: {pending} already queued, 0 new to queue")

            # Process batches until queue empty or limit hit
            worker = TopicExtractionQueueWorker(get_db_connection, schema=schema)
            worker.batch_size = batch_size
            batch_num = 0
            while batch_num < max_batches_per_domain:
                await worker._process_queue_batch()
                stats = worker.get_queue_stats()
                batch_num += 1
                if stats.get("pending", 0) == 0 and stats.get("processing", 0) == 0:
                    break
                total_processed += batch_size
                if batch_num % 10 == 0 or batch_num <= 3:
                    print(f"   {domain_key}: batch {batch_num}, pending={stats.get('pending', 0)}")
            print(f"   {domain_key}: done ({batch_num} batches)\n")
        except Exception as e:
            print(f"   {domain_key}: error - {e}\n")

    print("=" * 60)
    print("Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
