#!/usr/bin/env python3
"""
Repair denormalized metrics: word_count, topics.article_count, storyline derived fields.

Usage:
  PYTHONPATH=. python3 scripts/repair_denormalized_metrics.py --dry-run
  PYTHONPATH=. python3 scripts/repair_denormalized_metrics.py --domain politics --word-count --topics
  PYTHONPATH=. python3 scripts/repair_denormalized_metrics.py --storyline-counts --storyline-derived
"""

from __future__ import annotations

import argparse
import logging
import sys

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.storyline_article_counts import (
    reconcile_all_storyline_counts,
    reconcile_all_storyline_derived_metrics,
    reconcile_article_word_counts,
    reconcile_topics_article_count,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _count_mismatched_storylines(cur, schema: str, *, active_only: bool = False) -> int:
    merged_clause = "AND s.merged_into_id IS NULL" if active_only else ""
    cur.execute(
        f"""
        SELECT COUNT(*)::int FROM {schema}.storylines s
        WHERE 1=1 {merged_clause}
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
    return int(cur.fetchone()[0] or 0)


def _count_zero_word_count(cur, schema: str) -> int:
    cur.execute(
        f"""
        SELECT COUNT(*)::int FROM {schema}.articles
        WHERE word_count IS NULL OR word_count = 0
        """
    )
    return int(cur.fetchone()[0] or 0)


def _count_stale_topics(cur, schema: str) -> int:
    cur.execute(
        f"""
        SELECT COUNT(*)::int
        FROM {schema}.topics t
        JOIN (
            SELECT topic_id, COUNT(DISTINCT article_id)::int AS cnt
            FROM {schema}.article_topic_assignments
            GROUP BY topic_id
        ) sub ON sub.topic_id = t.id
        WHERE t.article_count IS DISTINCT FROM sub.cnt
        """
    )
    return int(cur.fetchone()[0] or 0)


def repair_domain(
    domain_key: str,
    *,
    dry_run: bool,
    word_count: bool,
    topics: bool,
    storyline_counts: bool,
    storyline_derived: bool,
) -> dict[str, int]:
    schema = resolve_domain_schema(domain_key)
    stats: dict[str, int] = {}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if word_count:
                pending = _count_zero_word_count(cur, schema)
                stats["word_count_pending"] = pending
                if not dry_run and pending:
                    stats["word_count_updated"] = reconcile_article_word_counts(cur, schema)
                else:
                    stats["word_count_updated"] = 0

            if topics:
                pending = _count_stale_topics(cur, schema)
                stats["topics_pending"] = pending
                if not dry_run and pending:
                    stats["topics_updated"] = reconcile_topics_article_count(cur, schema)
                else:
                    stats["topics_updated"] = 0

            if storyline_counts:
                pending_active = _count_mismatched_storylines(cur, schema, active_only=True)
                pending_all = _count_mismatched_storylines(cur, schema, active_only=False)
                stats["storyline_counts_pending_active"] = pending_active
                stats["storyline_counts_pending_all"] = pending_all
                if not dry_run and pending_all:
                    stats["storyline_counts_updated"] = reconcile_all_storyline_counts(
                        cur, schema, include_merged=True
                    )
                else:
                    stats["storyline_counts_updated"] = 0

            if storyline_derived:
                if dry_run:
                    cur.execute(
                        f"""
                        SELECT COUNT(*)::int FROM {schema}.storylines s
                        WHERE s.merged_into_id IS NULL
                          AND (
                            s.total_entities IS DISTINCT FROM COALESCE((
                                SELECT COUNT(DISTINCT entity_name)::int
                                FROM {schema}.story_entity_index sei
                                WHERE sei.storyline_id = s.id
                            ), 0)
                            OR s.time_span_days IS DISTINCT FROM COALESCE((
                                SELECT GREATEST(
                                    0,
                                    EXTRACT(DAY FROM MAX(a.published_at) - MIN(a.published_at))
                                )::int
                                FROM {schema}.storyline_articles sa
                                JOIN {schema}.articles a ON a.id = sa.article_id
                                WHERE sa.storyline_id = s.id AND a.published_at IS NOT NULL
                            ), 0)
                          )
                        """
                    )
                    pending = int(cur.fetchone()[0] or 0)
                    stats["storyline_derived_pending"] = pending
                    stats["storyline_derived_updated"] = 0
                else:
                    stats["storyline_derived_updated"] = reconcile_all_storyline_derived_metrics(
                        cur, schema
                    )
                    stats["storyline_derived_pending"] = stats["storyline_derived_updated"]

            if not dry_run:
                conn.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair denormalized DB metrics")
    parser.add_argument("--domain", action="append", help="Domain key (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Report pending rows only")
    parser.add_argument("--word-count", action="store_true", help="Backfill articles.word_count")
    parser.add_argument("--topics", action="store_true", help="Sync topics.article_count")
    parser.add_argument(
        "--storyline-counts",
        action="store_true",
        help="Reconcile storylines.article_count/total_articles",
    )
    parser.add_argument(
        "--storyline-derived",
        action="store_true",
        help="Backfill storylines.total_entities and time_span_days",
    )
    parser.add_argument("--all", action="store_true", help="Run all repair steps")
    args = parser.parse_args()

    run_all = args.all or not any(
        [args.word_count, args.topics, args.storyline_counts, args.storyline_derived]
    )
    word_count = run_all or args.word_count
    topics = run_all or args.topics
    storyline_counts = run_all or args.storyline_counts
    storyline_derived = run_all or args.storyline_derived

    domains = args.domain or list(get_pipeline_active_domain_keys())
    for domain_key in domains:
        stats = repair_domain(
            domain_key,
            dry_run=args.dry_run,
            word_count=word_count,
            topics=topics,
            storyline_counts=storyline_counts,
            storyline_derived=storyline_derived,
        )
        logger.info("[%s] %s dry_run=%s", domain_key, stats, args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
