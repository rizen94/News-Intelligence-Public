#!/usr/bin/env python3
"""
One-time backfill: seed {schema}.story_entity_index from storyline_articles + article_entities.

Usage:
  PYTHONPATH=api uv run python api/scripts/backfill_story_entity_index.py
  PYTHONPATH=api uv run python api/scripts/backfill_story_entity_index.py --domain politics
  PYTHONPATH=api uv run python api/scripts/backfill_story_entity_index.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backfill_domain(domain_key: str, *, dry_run: bool = False) -> int:
    schema = resolve_domain_schema(domain_key)
    inserted = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sa.storyline_id, ec.canonical_name, ec.entity_type, COUNT(*) AS cnt
                FROM {schema}.storyline_articles sa
                JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                GROUP BY sa.storyline_id, ec.canonical_name, ec.entity_type
                """
            )
            rows = cur.fetchall()
            for storyline_id, name, etype, cnt in rows:
                if not (name or "").strip():
                    continue
                if dry_run:
                    inserted += 1
                    continue
                cur.execute(
                    f"""
                    INSERT INTO {schema}.story_entity_index
                        (storyline_id, entity_name, entity_type, mention_count, is_core_entity)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (storyline_id, entity_name, entity_type)
                    DO UPDATE SET
                        mention_count = GREATEST(
                            {schema}.story_entity_index.mention_count,
                            EXCLUDED.mention_count
                        ),
                        last_seen_at = CURRENT_TIMESTAMP
                    """,
                    (
                        storyline_id,
                        name.strip(),
                        etype or "other",
                        int(cnt or 1),
                        int(cnt or 0) >= 3,
                    ),
                )
                inserted += cur.rowcount
        if not dry_run:
            conn.commit()
    logger.info("%s: %s rows upserted", domain_key, inserted)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill story_entity_index from article entities")
    parser.add_argument("--domain", help="Single domain_key (default: all pipeline domains)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    domains = [args.domain] if args.domain else list(get_pipeline_active_domain_keys())
    total = 0
    for dk in domains:
        try:
            total += backfill_domain(dk, dry_run=args.dry_run)
        except Exception as e:
            logger.error("%s failed: %s", dk, e)
            return 1
    logger.info("Done. Total upserts: %s", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
