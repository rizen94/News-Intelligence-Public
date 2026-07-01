#!/usr/bin/env python3
"""
One-shot repair: fold duplicate is_mega_storyline rows (same title) and fix article_count
from COUNT(DISTINCT storyline_articles). Safe to re-run.
"""

from __future__ import annotations

import argparse
import logging

from services.storyline_consolidation_service import (
    _BAD_MEGA_TITLE_RENAMES,
    derive_mega_storyline_title,
    get_consolidation_service,
)
from shared.domain_registry import get_pipeline_active_domain_keys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fold duplicate mega-storylines by title")
    parser.add_argument(
        "--domain",
        action="append",
        help="Domain key (repeatable). Default: all pipeline-active domains.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; no writes")
    parser.add_argument(
        "--refresh-counts",
        action="store_true",
        help="Recompute article_count/description for all active megas (no fold)",
    )
    parser.add_argument(
        "--fix-bad-titles",
        action="store_true",
        help="Rename known bad mega titles (e.g. Ongoing: Apy) and refresh counts",
    )
    parser.add_argument(
        "--reconcile-all-counts",
        action="store_true",
        help="Reconcile article_count/total_articles for all non-merged storylines from storyline_articles",
    )
    args = parser.parse_args()

    domains = args.domain or list(get_pipeline_active_domain_keys())
    svc = get_consolidation_service()
    total_folded = 0
    total_refreshed = 0
    total_reconciled = 0

    from services.storyline_consolidation_service import _schema_for_domain
    from shared.storyline_article_counts import reconcile_all_storyline_counts

    for domain_key in domains:
        schema = _schema_for_domain(domain_key)
        conn = svc.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT LOWER(TRIM(title)) AS tkey, array_agg(id ORDER BY id) AS ids
                    FROM {schema}.storylines
                    WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
                      AND merged_into_id IS NULL
                      AND title IS NOT NULL
                    GROUP BY LOWER(TRIM(title))
                    HAVING COUNT(*) > 1
                    """
                )
                dup_groups = cur.fetchall()
                for tkey, ids in dup_groups:
                    canonical_id = int(ids[0])
                    dup_ids = [int(x) for x in ids[1:]]
                    logger.info(
                        "[%s] title=%r canonical=%s fold=%s",
                        domain_key,
                        tkey,
                        canonical_id,
                        dup_ids,
                    )
                    if args.dry_run:
                        continue
                    svc._fold_duplicate_mega_rows(cur, schema, tkey, canonical_id)
                    for dup_id in dup_ids:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET merged_into_id = %s, status = 'archived', updated_at = NOW()
                            WHERE id = %s
                            """,
                            (canonical_id, dup_id),
                        )
                    svc._refresh_mega_counts_from_db(cur, schema, canonical_id)
                    total_folded += len(dup_ids)
                if args.refresh_counts and not args.dry_run:
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.storylines
                        WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
                          AND merged_into_id IS NULL
                        """
                    )
                    for (mega_id,) in cur.fetchall():
                        svc._refresh_mega_counts_from_db(cur, schema, int(mega_id))
                        total_refreshed += 1
                if args.reconcile_all_counts and not args.dry_run:
                    total_reconciled += reconcile_all_storyline_counts(cur, schema)
                elif args.reconcile_all_counts and args.dry_run:
                    cur.execute(
                        f"""
                        SELECT COUNT(*)::int FROM {schema}.storylines s
                        WHERE s.merged_into_id IS NULL
                          AND (
                            s.article_count IS DISTINCT FROM (
                                SELECT COUNT(*)::int FROM {schema}.storyline_articles sa
                                WHERE sa.storyline_id = s.id
                            )
                            OR s.total_articles IS DISTINCT FROM (
                                SELECT COUNT(*)::int FROM {schema}.storyline_articles sa
                                WHERE sa.storyline_id = s.id
                            )
                          )
                        """
                    )
                    total_reconciled += int(cur.fetchone()[0] or 0)
                if args.fix_bad_titles:
                    cur.execute(
                        f"""
                        SELECT id, title FROM {schema}.storylines
                        WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
                          AND merged_into_id IS NULL
                        """
                    )
                    for mega_id, title in cur.fetchall():
                        tkey = (title or "").strip().lower()
                        new_title = _BAD_MEGA_TITLE_RENAMES.get(tkey)
                        if not new_title:
                            continue
                        logger.info(
                            "[%s] rename mega %s: %r -> %r",
                            domain_key,
                            mega_id,
                            title,
                            new_title,
                        )
                        if args.dry_run:
                            continue
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET title = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (new_title, mega_id),
                        )
                        svc._fold_duplicate_mega_rows(cur, schema, new_title, int(mega_id))
                        svc._refresh_mega_counts_from_db(cur, schema, int(mega_id))
                        total_refreshed += 1
                if not args.dry_run:
                    conn.commit()
        except Exception as e:
            logger.error("[%s] repair failed: %s", domain_key, e)
            conn.rollback()
        finally:
            conn.close()

    logger.info(
        "Done. folded_duplicate_megas=%s refreshed_megas=%s reconciled_storylines=%s dry_run=%s",
        total_folded,
        total_refreshed,
        total_reconciled,
        args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
