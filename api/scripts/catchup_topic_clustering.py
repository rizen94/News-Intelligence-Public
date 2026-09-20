#!/usr/bin/env python3
"""
Catch up topic_clustering backlog using parallel batches and fast-lane matching.

Usage:
  cd api && set -a && . ../.env && set +a && PYTHONPATH=. python3 scripts/catchup_topic_clustering.py --domain politics --batch-size 50 --concurrency 5
  PYTHONPATH=. python3 scripts/catchup_topic_clustering.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from config.settings import (
    topic_clustering_backlog_uses_pass_marker,
    topic_clustering_batch_size,
    topic_clustering_concurrency,
    topic_clustering_graduation_confidence,
    topic_clustering_iterative_refinement_enabled,
)
from domains.content_analysis.services.topic_clustering_service import (
    TopicClusteringService,
    process_articles_batch,
)
from shared.database.connection import get_db_config, get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def count_pending(schema: str) -> int:
    use_pass = topic_clustering_backlog_uses_pass_marker()
    iterative = topic_clustering_iterative_refinement_enabled()
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if use_pass and not iterative:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {schema}.articles a
                    WHERE a.content IS NOT NULL AND LENGTH(a.content) > 100
                      AND (
                        a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NULL
                        OR TRIM(COALESCE(a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', '')) = ''
                      )
                    """
                )
            else:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM (
                        SELECT a.id
                        FROM {schema}.articles a
                        LEFT JOIN {schema}.article_topic_clusters atc ON a.id = atc.article_id
                        WHERE a.content IS NOT NULL AND LENGTH(a.content) > 100
                        GROUP BY a.id
                        HAVING COALESCE(AVG(atc.confidence_score), 0) < %s
                    ) sub
                    """,
                    (topic_clustering_graduation_confidence(),),
                )
                return int(cur.fetchone()[0] or 0)
            return int(cur.fetchone()[0] or 0)


async def catchup_domain(
    domain_key: str,
    *,
    batch_size: int,
    concurrency: int,
    max_batches: int,
    dry_run: bool,
) -> dict[str, int]:
    schema = resolve_domain_schema(domain_key)
    pending_start = count_pending(schema)
    logger.info("[%s] pending at start: %s", domain_key, pending_start)

    if dry_run:
        return {"pending_start": pending_start, "processed": 0, "batches": 0}

    service = TopicClusteringService(get_db_config(), domain=domain_key)
    service.schema = schema
    use_pass = topic_clustering_backlog_uses_pass_marker()
    iterative = topic_clustering_iterative_refinement_enabled()
    conf = float(topic_clustering_graduation_confidence())

    totals = {"processed": 0, "fast_lane": 0, "llm": 0, "failed": 0, "batches": 0}

    for batch_num in range(max_batches):
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                article_ids = TopicClusteringService.select_pending_article_ids(
                    cur,
                    schema,
                    batch_size=batch_size,
                    use_pass_marker=use_pass,
                    iterative=iterative,
                    confidence_threshold=conf,
                )
        if not article_ids:
            logger.info("[%s] backlog empty after batch %s", domain_key, batch_num)
            break

        result = await process_articles_batch(service, article_ids, concurrency=concurrency)
        totals["processed"] += result.processed
        totals["fast_lane"] += result.fast_lane_hits
        totals["llm"] += result.llm_extractions
        totals["failed"] += result.failed
        totals["batches"] += 1

        pending = count_pending(schema)
        logger.info(
            "[%s] batch %s: processed=%s fast_lane=%s llm=%s failed=%s pending=%s",
            domain_key,
            batch_num + 1,
            result.processed,
            result.fast_lane_hits,
            result.llm_extractions,
            result.failed,
            pending,
        )
        if pending == 0 or result.processed == 0:
            break

    totals["pending_start"] = pending_start
    totals["pending_end"] = count_pending(schema)
    return totals


def main() -> int:
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=True)
    parser = argparse.ArgumentParser(description="Catch up topic_clustering backlog")
    parser.add_argument("--domain", action="append", help="Domain key (repeatable)")
    parser.add_argument("--batch-size", type=int, default=0, help="Override TOPIC_CLUSTERING_BATCH_SIZE")
    parser.add_argument("--concurrency", type=int, default=0, help="Override TOPIC_CLUSTERING_CONCURRENCY")
    parser.add_argument("--max-batches", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    batch_size = args.batch_size or topic_clustering_batch_size()
    concurrency = args.concurrency or topic_clustering_concurrency()
    domains = args.domain or list(get_pipeline_active_domain_keys())

    async def _run() -> None:
        for dk in domains:
            stats = await catchup_domain(
                dk,
                batch_size=batch_size,
                concurrency=concurrency,
                max_batches=args.max_batches,
                dry_run=args.dry_run,
            )
            logger.info("[%s] done: %s", dk, stats)

    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
