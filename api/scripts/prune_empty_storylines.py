#!/usr/bin/env python3
"""
Archive or delete active storylines with zero articles and no child storylines.

Usage:
  PYTHONPATH=. python3 scripts/prune_empty_storylines.py --domain politics --dry-run
  PYTHONPATH=. python3 scripts/prune_empty_storylines.py --min-age-days 30
"""

from __future__ import annotations

import argparse
import logging

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def prune_domain(
    domain_key: str,
    *,
    min_age_days: int,
    dry_run: bool,
    delete: bool,
) -> int:
    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.title FROM {schema}.storylines s
                WHERE s.merged_into_id IS NULL
                  AND s.status != 'archived'
                  AND NOT EXISTS (
                    SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM {schema}.storylines ch WHERE ch.parent_storyline_id = s.id
                  )
                  AND s.created_at < NOW() - (%s || ' days')::interval
                """,
                (min_age_days,),
            )
            rows = cur.fetchall()
            if dry_run:
                logger.info("[%s] would prune %s empty storylines", domain_key, len(rows))
                return len(rows)
            if delete:
                ids = [r[0] for r in rows]
                if ids:
                    cur.execute(
                        f"DELETE FROM {schema}.storylines WHERE id = ANY(%s)",
                        (ids,),
                    )
            else:
                for sid, title in rows:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET status = 'archived', updated_at = NOW()
                        WHERE id = %s
                        """,
                        (sid,),
                    )
            conn.commit()
            logger.info("[%s] pruned %s empty storylines (delete=%s)", domain_key, len(rows), delete)
            return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune empty storylines")
    parser.add_argument("--domain", action="append")
    parser.add_argument("--min-age-days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delete", action="store_true", help="Hard delete instead of archive")
    args = parser.parse_args()
    domains = args.domain or list(get_pipeline_active_domain_keys())
    total = 0
    for dk in domains:
        total += prune_domain(
            dk, min_age_days=args.min_age_days, dry_run=args.dry_run, delete=args.delete
        )
    logger.info("total pruned: %s", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
