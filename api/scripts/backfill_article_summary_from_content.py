#!/usr/bin/env python3
"""
Seed articles.summary from enriched content where the reader dek was never written.

Run on Widow after deploying article_evidence_text / seed_reader_summary fixes:
  PYTHONPATH=api python3 api/scripts/backfill_article_summary_from_content.py --dry-run
  PYTHONPATH=api python3 api/scripts/backfill_article_summary_from_content.py
"""

from __future__ import annotations

import argparse
import logging

from api.shared.database import get_db_connection
from api.shared.domain_registry import iter_url_schema_pairs
from services.article_content_enrichment_service import (
    reader_summary_seed_from_body,
    seed_reader_summary_if_empty,
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-per-schema", type=int, default=5000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    conn = get_db_connection()
    if not conn:
        raise SystemExit("no_db_connection")

    total = 0
    try:
        for domain_key, schema in iter_url_schema_pairs():
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, content
                    FROM {schema}.articles
                    WHERE LENGTH(TRIM(COALESCE(content, ''))) > 200
                      AND (summary IS NULL OR LENGTH(TRIM(summary)) < 60)
                      AND COALESCE(enrichment_status, '') NOT IN ('removed', 'inaccessible')
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (args.limit_per_schema,),
                )
                rows = cur.fetchall()
            if not rows:
                continue
            updated = 0
            for article_id, content in rows:
                seed = reader_summary_seed_from_body(content)
                if not seed:
                    continue
                if args.dry_run:
                    updated += 1
                    continue
                with conn.cursor() as cur:
                    seed_reader_summary_if_empty(cur, schema, int(article_id), content)
                updated += 1
            if not args.dry_run:
                conn.commit()
            logger.info("%s (%s): would_update=%s", domain_key, schema, updated)
            total += updated
    finally:
        conn.close()

    logger.info("done total=%s dry_run=%s", total, args.dry_run)


if __name__ == "__main__":
    main()