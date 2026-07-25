#!/usr/bin/env python3
"""
Flush all storylines (and topic clusters) so proteins rebuild from articles.

Keeps: articles, rss_feeds, entities (article-level), banned topics.
Clears: storylines + membership, SEI, refinement/membership queues, topic clusters,
        chronological_events, storyline-scoped intelligence/public orphans.

  PYTHONPATH=api python3 api/scripts/flush_all_storylines.py --dry-run
  PYTHONPATH=api python3 api/scripts/flush_all_storylines.py --apply

Requires explicit --apply. Prefer admin DB port for large deletes.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("flush_all_storylines")

_INTEL_BY_DOMAIN = (
    "storyline_membership_actions",
    "storyline_membership_review_state",
    "content_refinement_queue",
    "storyline_states",
    "storyline_rag_context",
    "research_subject_proteins",
    "matter_docket_status",
    "matter_ruling_events",
    "narrative_expectations",
    "narrative_threads",
    "pattern_matches",
    "story_update_queue",
    "rag_evidence_pull_queue",
    "watch_patterns",
)

_DOMAIN_OPTIONAL = (
    "storyline_article_suggestions",
    "storyline_automation_log",
    "timeline_events",
    "topic_keywords",
    "topic_extraction_queue",
)


def _safe_delete(cur, sql: str, params: tuple | None = None) -> int:
    """Execute DELETE/UPDATE; swallow missing-table errors via savepoint."""
    cur.execute("SAVEPOINT flush_stmt")
    try:
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        n = int(cur.rowcount or 0)
        cur.execute("RELEASE SAVEPOINT flush_stmt")
        return n
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT flush_stmt")
        msg = str(e).lower()
        if (
            "does not exist" in msg
            or "undefined" in msg
            or "undefinedtable" in msg.replace(" ", "")
        ):
            return 0
        # Column missing / permission — skip with log rather than abort whole flush
        logger.warning("skip statement (%s): %s", type(e).__name__, str(e)[:200])
        return 0


def flush_domain(cur, domain_key: str, schema: str, *, dry_run: bool) -> dict[str, Any]:
    stats: dict[str, Any] = {"domain": domain_key, "schema": schema}
    cur.execute(f"SELECT COUNT(*)::int FROM {schema}.storylines")
    stats["storylines_before"] = int(cur.fetchone()[0] or 0)
    cur.execute(f"SELECT COUNT(*)::int FROM {schema}.storyline_articles")
    stats["memberships_before"] = int(cur.fetchone()[0] or 0)

    if dry_run:
        return stats

    for table in _INTEL_BY_DOMAIN:
        n = _safe_delete(
            cur,
            f"DELETE FROM intelligence.{table} WHERE domain_key = %s",
            (domain_key,),
        )
        if n:
            stats[f"intel.{table}"] = n

    n = _safe_delete(
        cur,
        """
        DELETE FROM intelligence.graph_connection_links
        WHERE domain_key = %s
          AND (left_kind = 'storyline' OR right_kind = 'storyline')
        """,
        (domain_key,),
    )
    if n:
        stats["intel.graph_connection_links"] = n

    n = _safe_delete(
        cur,
        """
        DELETE FROM intelligence.tracked_event_storyline_facets
        WHERE domain_key = %s
        """,
        (domain_key,),
    )
    if n:
        stats["intel.tracked_event_storyline_facets"] = n

    # Soft link is varchar "{schema}:{id}" — not a bare integer FK
    n = _safe_delete(
        cur,
        """
        UPDATE intelligence.tracked_events
        SET storyline_id = NULL
        WHERE storyline_id LIKE %s
        """,
        (f"{schema}:%",),
    )
    if n:
        stats["tracked_events_nulled"] = n
    # Also clear domain_key form used in some rows
    n2 = _safe_delete(
        cur,
        """
        UPDATE intelligence.tracked_events
        SET storyline_id = NULL
        WHERE storyline_id LIKE %s
        """,
        (f"{domain_key}:%",),
    )
    if n2:
        stats["tracked_events_nulled"] = int(stats.get("tracked_events_nulled") or 0) + n2

    n = _safe_delete(
        cur,
        "DELETE FROM public.storyline_article_suggestions WHERE domain_key = %s",
        (domain_key,),
    )
    if n:
        stats["public.storyline_article_suggestions"] = n

    for table in _DOMAIN_OPTIONAL:
        n = _safe_delete(cur, f"DELETE FROM {schema}.{table}")
        if n:
            stats[table] = n

    stats["story_entity_index"] = _safe_delete(
        cur, f"DELETE FROM {schema}.story_entity_index"
    )
    stats["storyline_articles"] = _safe_delete(
        cur, f"DELETE FROM {schema}.storyline_articles"
    )
    _safe_delete(
        cur,
        f"""
        UPDATE {schema}.storylines
        SET parent_storyline_id = NULL, merged_into_id = NULL
        """,
    )
    stats["storylines"] = _safe_delete(cur, f"DELETE FROM {schema}.storylines")

    # Topic rebuild path — TRUNCATE avoids cascade timeouts on large silos
    if dry_run:
        return stats
    for table in ("article_topic_clusters", "topic_clusters"):
        cur.execute("SAVEPOINT flush_trunc")
        try:
            cur.execute(f"TRUNCATE {schema}.{table} CASCADE")
            stats[table] = "truncate"
            cur.execute("RELEASE SAVEPOINT flush_trunc")
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT flush_trunc")
            logger.warning("truncate %s.%s: %s", schema, table, e)
            stats[table] = _safe_delete(cur, f"DELETE FROM {schema}.{table}")

    # Pass markers must die with the topic graph or Monitor queue_depth stays 0
    cur.execute("SAVEPOINT flush_tc_pass")
    try:
        cur.execute(
            f"""
            UPDATE {schema}.articles a
            SET metadata = jsonb_set(
                  COALESCE(a.metadata, '{{}}'::jsonb),
                  '{{pipeline,topic_clustering}}',
                  (
                    COALESCE(a.metadata->'pipeline'->'topic_clustering', '{{}}'::jsonb)
                    - 'last_pass_at'
                    - 'outcome'
                    - 'terminal_state'
                  ),
                  true
                ),
                updated_at = NOW()
            WHERE a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NOT NULL
              AND TRIM(COALESCE(
                a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', ''
              )) <> ''
            """
        )
        stats["topic_clustering_pass_markers_cleared"] = int(cur.rowcount or 0)
        cur.execute("RELEASE SAVEPOINT flush_tc_pass")
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT flush_tc_pass")
        logger.warning("clear topic_clustering pass markers %s: %s", schema, e)
        stats["topic_clustering_pass_markers_cleared"] = 0
    return stats


def flush_globals(cur, *, dry_run: bool) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    if dry_run:
        cur.execute("SELECT COUNT(*)::int FROM public.chronological_events")
        stats["chronological_events"] = int(cur.fetchone()[0] or 0)
        return stats
    try:
        cur.execute("TRUNCATE public.chronological_events CASCADE")
        stats["chronological_events"] = "truncated"
    except Exception as e:
        logger.warning("chronological_events truncate: %s", e)
        stats["chronological_events"] = _safe_delete(
            cur, "DELETE FROM public.chronological_events"
        )
    for table in ("watchlist", "storyline_insights", "storyline_correlations"):
        n = _safe_delete(cur, f"DELETE FROM public.{table}")
        if n:
            stats[table] = n
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete (default is dry-run counts only)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        help="Limit to domain key (repeatable). Default: all pipeline-active.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import (
        get_pipeline_active_domain_keys,
        resolve_domain_schema,
    )

    domains = args.domains or list(get_pipeline_active_domain_keys())
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "domains": {},
        "globals": {},
    }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            for dk in domains:
                schema = resolve_domain_schema(dk)
                logger.info(
                    "%s domain=%s schema=%s",
                    "DRY-RUN" if dry_run else "APPLY",
                    dk,
                    schema,
                )
                report["domains"][dk] = flush_domain(
                    cur, dk, schema, dry_run=dry_run
                )
            report["globals"] = flush_globals(cur, dry_run=dry_run)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        for dk, st in report["domains"].items():
            logger.info(
                "%s: storylines=%s memberships=%s deleted_storylines=%s",
                dk,
                st.get("storylines_before"),
                st.get("memberships_before"),
                st.get("storylines"),
            )
        logger.info("globals: %s", report["globals"])
        if dry_run:
            logger.info("Dry-run only. Re-run with --apply to flush.")
        else:
            logger.info("Flush applied. Restart topic clustering / storyline discovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
