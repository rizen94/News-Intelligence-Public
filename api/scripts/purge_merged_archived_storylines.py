#!/usr/bin/env python3
"""
Hard-delete storylines folded into another row (merged_into_id IS NOT NULL).

Before delete: move storyline_articles to canonical, reparent child storylines,
clear refinement queue / suggestions, then DELETE.

Usage:
  PYTHONPATH=. python3 scripts/purge_merged_archived_storylines.py --dry-run
  PYTHONPATH=. python3 scripts/purge_merged_archived_storylines.py --domain politics --domain finance
  PYTHONPATH=. python3 scripts/purge_merged_archived_storylines.py --ongoing-megas-only --dry-run
"""

from __future__ import annotations

import argparse
import logging

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.storyline_article_counts import reconcile_all_storyline_counts

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def purge_domain(
    domain_key: str,
    *,
    dry_run: bool,
    ongoing_only: bool,
) -> dict[str, int]:
    schema = resolve_domain_schema(domain_key)
    stats: dict[str, int] = {}
    ongoing_sql = " AND s.title ILIKE 'Ongoing:%'" if ongoing_only else ""
    ongoing_parent_sql = " AND parent.title ILIKE 'Ongoing:%'" if ongoing_only else ""

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {schema}.storylines s
                WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                """
            )
            stats["candidates"] = int(cur.fetchone()[0] or 0)

            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {schema}.storylines s
                WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                  AND EXISTS (
                    SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id
                  )
                """
            )
            stats["with_articles"] = int(cur.fetchone()[0] or 0)

            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {schema}.storylines
                WHERE parent_storyline_id IN (
                    SELECT id FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                )
                """
            )
            stats["children_to_reparent"] = int(cur.fetchone()[0] or 0)

            if dry_run or stats["candidates"] == 0:
                return stats

            cur.execute(
                f"""
                INSERT INTO {schema}.storyline_articles
                    (storyline_id, article_id, relevance_score, added_at)
                SELECT s.merged_into_id, sa.article_id, sa.relevance_score, COALESCE(sa.added_at, NOW())
                FROM {schema}.storylines s
                JOIN {schema}.storyline_articles sa ON sa.storyline_id = s.id
                WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                ON CONFLICT (storyline_id, article_id) DO NOTHING
                """
            )
            stats["articles_moved"] = int(cur.rowcount or 0)

            cur.execute(
                f"""
                DELETE FROM {schema}.storyline_articles sa
                USING {schema}.storylines s
                WHERE sa.storyline_id = s.id
                  AND s.merged_into_id IS NOT NULL{ongoing_sql}
                """
            )
            stats["article_links_removed"] = int(cur.rowcount or 0)

            cur.execute(
                f"""
                UPDATE {schema}.storylines child
                SET parent_storyline_id = parent.merged_into_id,
                    updated_at = NOW()
                FROM {schema}.storylines parent
                WHERE child.parent_storyline_id = parent.id
                  AND parent.merged_into_id IS NOT NULL{ongoing_parent_sql}
                """
            )
            stats["children_reparented"] = int(cur.rowcount or 0)

            cur.execute(
                f"""
                DELETE FROM intelligence.content_refinement_queue
                WHERE domain_key = %s
                  AND storyline_id IN (
                    SELECT id FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                  )
                """,
                (domain_key,),
            )
            stats["queue_rows_deleted"] = int(cur.rowcount or 0)

            try:
                cur.execute(
                    f"""
                    DELETE FROM public.storyline_article_suggestions
                    WHERE domain_key = %s
                      AND storyline_id IN (
                        SELECT id FROM {schema}.storylines s
                        WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                      )
                    """,
                    (domain_key,),
                )
                stats["suggestions_deleted"] = int(cur.rowcount or 0)
            except Exception:
                stats["suggestions_deleted"] = 0

            cur.execute(
                f"""
                DELETE FROM {schema}.storylines s
                WHERE s.merged_into_id IS NOT NULL{ongoing_sql}
                """
            )
            stats["storylines_deleted"] = int(cur.rowcount or 0)

            stats["counts_reconciled"] = reconcile_all_storyline_counts(
                cur, schema, include_merged=True
            )

            conn.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete folded archived storylines")
    parser.add_argument("--domain", action="append", help="Domain key (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Report counts only")
    parser.add_argument(
        "--ongoing-megas-only",
        action="store_true",
        help="Only delete archived rows titled 'Ongoing: *'",
    )
    args = parser.parse_args()

    domains = args.domain or list(get_pipeline_active_domain_keys())
    for domain_key in domains:
        stats = purge_domain(
            domain_key,
            dry_run=args.dry_run,
            ongoing_only=args.ongoing_megas_only,
        )
        logger.info("[%s] %s dry_run=%s", domain_key, stats, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
