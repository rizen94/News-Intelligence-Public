#!/usr/bin/env python3
"""
Remove or archive storyline_article_suggestions whose storyline_id does not exist
in the domain schema's storylines table.

Default: --dry-run (counts only). Requires --apply to DELETE.

Run from repo root:
  PYTHONPATH=api python3 api/scripts/golden_path_prune_orphan_suggestions.py
  PYTHONPATH=api python3 api/scripts/golden_path_prune_orphan_suggestions.py --apply
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune orphan storyline_article_suggestions")
    parser.add_argument("--apply", action="store_true", help="Execute DELETE (default dry-run)")
    parser.add_argument("--domain", default=None, help="Limit to domain_key (e.g. politics)")
    parser.add_argument("--limit", type=int, default=50000, help="Max rows per domain per batch")
    args = parser.parse_args()

    from api.shared.database import get_db_connection
    from api.shared.domain_registry import get_active_domain_keys, resolve_domain_schema

    conn = get_db_connection()
    if not conn:
        logger.error("No DB connection")
        return 1

    domains = [args.domain] if args.domain else list(get_active_domain_keys())
    total_orphan = 0
    total_deleted = 0

    try:
        for dk in domains:
            schema = resolve_domain_schema(dk)
            if not schema:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.storyline_article_suggestions s
                    WHERE s.domain_key = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM {}.storylines st WHERE st.id = s.storyline_id
                      )
                    """.format(schema),
                    (dk,),
                )
                n = int(cur.fetchone()[0])
                total_orphan += n
                logger.info("%s (%s): %s orphan suggestions", dk, schema, n)

                if args.apply and n > 0:
                    cur.execute(
                        """
                        DELETE FROM public.storyline_article_suggestions s
                        WHERE s.ctid IN (
                            SELECT s2.ctid
                            FROM public.storyline_article_suggestions s2
                            WHERE s2.domain_key = %s
                              AND NOT EXISTS (
                                  SELECT 1 FROM {}.storylines st WHERE st.id = s2.storyline_id
                              )
                            LIMIT %s
                        )
                        """.format(schema),
                        (dk, args.limit),
                    )
                    deleted = cur.rowcount
                    conn.commit()
                    total_deleted += deleted
                    logger.info("  deleted %s rows (batch limit %s)", deleted, args.limit)

        if args.apply:
            logger.info("Total deleted this run: %s", total_deleted)
        else:
            logger.info("Total orphan (dry-run): %s — re-run with --apply to delete", total_orphan)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
