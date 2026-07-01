#!/usr/bin/env python3
"""
Backfill intelligence.contexts for domain articles missing article_to_context links.

Usage:
  PYTHONPATH=. python3 scripts/catchup_context_sync.py --domain politics --batch-size 500
  PYTHONPATH=. python3 scripts/catchup_context_sync.py --dry-run
"""

from __future__ import annotations

import argparse
import logging

from services.context_processor_service import sync_domain_articles_to_contexts
from shared.domain_registry import get_pipeline_active_domain_keys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def catchup_domain(domain_key: str, *, batch_size: int, max_batches: int, dry_run: bool) -> int:
    total = 0
    for batch in range(max_batches):
        if dry_run:
            from shared.database.connection import get_db_connection_context
            from shared.domain_registry import resolve_domain_schema
            from shared.article_processing_gates import sql_context_sync_article_ready

            schema = resolve_domain_schema(domain_key)
            ready = sql_context_sync_article_ready("a")
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT COUNT(*)::int FROM {schema}.articles a
                        LEFT JOIN intelligence.article_to_context atc
                          ON atc.domain_key = %s AND atc.article_id = a.id
                        WHERE atc.context_id IS NULL
                          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                          AND ({ready})
                        """,
                        (domain_key,),
                    )
                    pending = int(cur.fetchone()[0] or 0)
            logger.info("[%s] dry-run eligible without context: %s", domain_key, pending)
            return pending
        created = sync_domain_articles_to_contexts(domain_key, limit=batch_size)
        total += created
        logger.info("[%s] batch %s created %s contexts", domain_key, batch + 1, created)
        if created == 0:
            break
    return total


def main() -> int:
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=True)
    parser = argparse.ArgumentParser(description="Catch up context_sync for domain articles")
    parser.add_argument("--domain", action="append", help="Domain key (repeatable)")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-batches", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    domains = args.domain or list(get_pipeline_active_domain_keys())
    grand = 0
    for dk in domains:
        grand += catchup_domain(
            dk,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
            dry_run=args.dry_run,
        )
    logger.info("total contexts created: %s dry_run=%s", grand, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
