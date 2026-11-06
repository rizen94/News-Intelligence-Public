"""Pending item cleanup service — handles stale/dormant articles that no longer need processing.

Covers two failure modes:
1. **Enrichment fast-path bypass**: Articles with existing content (≥500 chars) were fast-pathed to
   `enriched` without triggering downstream entity extraction / context sync.  Force-reprocess them
   when they lack required downstream state (entities, topics, contexts).
2. **Orphaned pending items**: Articles stuck in `pending` beyond a configured TTL that will never be
   processed (e.g., expired RSS sources, dead URLs, content behind paywall that can't be fetched).

Usage: register as a scheduled phase in ``automation_manager.py`` or run via cron::

    PYTHONPATH=api python3 api/services/pending_cleanup_service.py --dry-run
    PYTHONPATH=api python3 api/services/pending_cleanup_service.py --apply
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Configurable thresholds (seconds from now)
_PENDING_TTL_HOURS = int(os.environ.get("PENDING_CLEANUP_PENDING_TTL_HOURS", "24"))
_FASTPATH_REPROCESS_DAYS = int(
    os.environ.get("PENDING_CLEANUP_FASTPATH_REPROCESS_DAYS", "7")
)

# Minimum entity count below which we consider an enriched article "incomplete"
_MIN_ENTITY_COUNT = 2
_MIN_TOPIC_COUNT = 1


def stale_pending_items_count(*, schema_name: str, ttl_hours: int | None = None) -> dict[str, int]:
    """Count stale pending items by age bracket.

    Returns dict with keys 'total', 'over_6h', 'over_12h', 'over_24h', 'over_72h'.
    """
    ttl = ttl_hours or _PENDING_TTL_HOURS
    try:
        from api.shared.database import get_db_connection, get_db_config

        conn = get_db_connection()
        if not conn:
            logger.warning("pending_cleanup: no DB connection for %s", schema_name)
            return {}
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '120s'")
            query = f"""
                SELECT
                    COUNT(*)::int AS total,
                    COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '6 hours')::int AS over_6h,
                    COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '12 hours')::int AS over_12h,
                    COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '24 hours')::int AS over_24h,
                    COUNT(*) FILTER (WHERE updated_at < NOW() - INTERVAL '72 hours')::int AS over_72h
                FROM {schema_name}.articles
                WHERE (enrichment_status IS NULL OR enrichment_status = 'pending'
                       OR enrichment_status = 'failed' OR enrichment_status = 'pull_deferred')
                  AND COALESCE(enrichment_attempts, 0) >= 3
                  AND url IS NOT NULL AND url != ''
            """
            cur.execute(query)
            row = cur.fetchone()
            if row:
                result = dict(row)
                result.setdefault("over_6h", 0)
                result.setdefault("over_12h", 0)
                result.setdefault("over_24h", 0)
                result.setdefault("over_72h", 0)
                return result
            return {}
    except Exception as e:
        logger.warning("pending_cleanup count failed for %s: %s", schema_name, e)
        return {}


def fast_path_incomplete_items(*, schema_name: str, days: int | None = None) -> dict[str, int]:
    """Count articles fast-pathed to 'enriched' that lack downstream state."""
    days = days or _FASTPATH_REPROCESS_DAYS
    try:
        from api.shared.database import get_db_connection

        conn = get_db_connection()
        if not conn:
            logger.warning("pending_cleanup: no DB connection for incomplete check %s", schema_name)
            return {}
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '120s'")
            query = f"""
                SELECT
                    COUNT(*)::int AS enriched_incomplete,
                    COUNT(*) FILTER (WHERE COALESCE(LENGTH(a.content), 0) >= {500} AND
                        (a.enrichment_status IS NULL OR a.enrichment_status IN ('pending', 'failed'))):int AS pending_no_entities
                FROM {schema_name}.articles a
                LEFT JOIN LATERAL (
                    SELECT COUNT(DISTINCT e.entity_name)::int AS cnt
                    FROM {schema_name}.entities e WHERE e.article_id = a.id
                ) ents ON true
                LEFT JOIN LATERAL (
                    SELECT COUNT(DISTINCT t.topic)::int AS cnt
                    FROM {schema_name}.topics t WHERE t.article_id = a.id
                ) topcs ON true
                WHERE a.enrichment_status = 'enriched'
                  AND a.updated_at < NOW() - INTERVAL '%s days'
                  AND (ents.cnt IS NULL OR ents.cnt < %s)
            """
            cur.execute(query, (days, _MIN_ENTITY_COUNT))
            row = cur.fetchone()
            if row:
                return dict(row) if row else {"enriched_incomplete": 0}
            return {}
    except Exception as e:
        logger.warning("pending_cleanup incomplete check failed for %s: %s", schema_name, e)
        return {}


def fix_stale_pending_items(*, schema_name: str, ttl_hours: int | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Force-update stale pending items and resubmit them for enrichment."""
    ttl = ttl_hours or _PENDING_TTL_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl)
    results = {"marked_inaccessible": 0, "reset_for_reprocess": 0, "errors": []}

    try:
        from api.shared.database import get_db_connection

        conn = get_db_connection()
        if not conn:
            logger.warning("pending_cleanup: no DB connection for fixes %s", schema_name)
            return results

        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '180s'")

            if not dry_run:
                try:
                    cur.execute(
                        f"""
                        UPDATE {schema_name}.articles
                        SET enrichment_status = 'inaccessible',
                            processing_status = 'ml_processed',
                            updated_at = NOW()
                        WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed', 'pull_deferred'))
                          AND COALESCE(enrichment_attempts, 0) >= 3
                          AND updated_at < %s
                          AND url IS NOT NULL AND url != ''
                        RETURNING id
                        """,
                        (cutoff,),
                    )
                    rows = cur.fetchall()
                    count = len(rows) if rows else 0
                    results["marked_inaccessible"] += count
                    conn.commit()
                    logger.info("pending_cleanup %s: marked %d stale pending items as inaccessible", schema_name, count)
                except Exception as e:
                    results["errors"].append(f"mark_inaccessible ({schema_name}): {e}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass

            try:
                cur.execute(
                    f"""
                    UPDATE {schema_name}.articles
                    SET enrichment_status = 'pending',
                        processing_status = NULL,
                        updated_at = NOW()
                    WHERE enrichment_status = 'enriched'
                      AND COALESCE(LENGTH(content), 0) >= 500
                      AND (processing_status IS NULL OR processing_status = '')
                      AND updated_at < NOW() - INTERVAL '%s days'
                    RETURNING id
                    """,
                    (_FASTPATH_REPROCESS_DAYS,),
                )
                rows = cur.fetchall()
                count = len(rows) if rows else 0
                results["reset_for_reprocess"] += count
                conn.commit()
                logger.info("pending_cleanup %s: reset %d incomplete enriched items for reprocessing", schema_name, count)
            except Exception as e:
                results["errors"].append(f"reset_incomplete ({schema_name}): {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

    except Exception as e:
        results["errors"].append(f"general ({schema_name}): {e}")

    return results


def run_cleanup(*, dry_run: bool = True) -> dict[str, Any]:
    """Run pending cleanup across all active schemas."""
    from api.shared.domain_registry import pipeline_url_schema_pairs

    all_results: dict[str, Any] = {"schemas": {}, "summary": {}}
    pairs = list(pipeline_url_schema_pairs())
    if not pairs:
        logger.warning("pending_cleanup: no active domains found")
        return all_results

    for domain_key, schema_name in pairs:
        schema_results = {}
        counts = stale_pending_items_count(schema_name=schema_name)
        if counts:
            schema_results["pending_counts"] = counts
        incomplete = fast_path_incomplete_items(schema_name=schema_name)
        if incomplete:
            schema_results["incomplete_counts"] = incomplete
        fixes = fix_stale_pending_items(schema_name=schema_name, dry_run=dry_run)
        schema_results["fixes"] = fixes
        all_results["schemas"][schema_name] = schema_results

    total_pending = sum(
        s.get("pending_counts", {}).get("total", 0) for s in all_results["schemas"].values()
    )
    total_marked = sum(
        s.get("fixes", {}).get("marked_inaccessible", 0) for s in all_results["schemas"].values()
    )
    total_reset = sum(
        s.get("fixes", {}).get("reset_for_reprocess", 0) for s in all_results["schemas"].values()
    )
    all_results["summary"]["total_stale_pending"] = total_pending
    all_results["summary"]["total_marked_inaccessible"] = total_marked
    all_results["summary"]["total_reset_for_reprocess"] = total_reset

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Pending item cleanup service")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (default is dry-run)")
    parser.add_argument("--schema", type=str, default=None, help="Single schema to process")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    results = run_cleanup(dry_run=not args.apply)

    import json
    print(json.dumps(results, indent=2, default=str))

    if not args.apply:
        print("\n[Dry-run mode — add --apply to make changes]")
    else:
        total_marked = results["summary"]["total_marked_inaccessible"]
        total_reset = results["summary"]["total_reset_for_reprocess"]
        print(f"\nDone: {total_marked} marked inaccessible, {total_reset} reset for reprocessing")


if __name__ == "__main__":
    main()
