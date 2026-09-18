#!/usr/bin/env python3
"""
Clear topic_clustering pass markers when topic links were wiped but markers remain.

After flush_all_storylines (or TRUNCATE of topic_clusters / article_topic_clusters),
articles still carry metadata.pipeline.topic_clustering.last_pass_at, so Monitor
queue_depth stays ~0 and PopOS idle-gates the phase.

  PYTHONPATH=api python3 api/scripts/clear_topic_clustering_pass_markers.py --dry-run
  PYTHONPATH=api python3 api/scripts/clear_topic_clustering_pass_markers.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("clear_tc_pass_markers")


def clear_domain(cur, schema: str, *, dry_run: bool, only_unlinked: bool) -> dict:
    where_unlinked = ""
    if only_unlinked:
        where_unlinked = f"""
          AND NOT EXISTS (
            SELECT 1 FROM {schema}.article_topic_clusters atc
            WHERE atc.article_id = a.id
          )
        """
    cur.execute(
        f"""
        SELECT COUNT(*)::bigint
        FROM {schema}.articles a
        WHERE a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NOT NULL
          AND TRIM(COALESCE(
            a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', ''
          )) <> ''
          {where_unlinked}
        """
    )
    candidates = int(cur.fetchone()[0] or 0)
    if dry_run or candidates == 0:
        return {"schema": schema, "candidates": candidates, "cleared": 0}
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
          {where_unlinked}
        """
    )
    return {"schema": schema, "candidates": candidates, "cleared": int(cur.rowcount or 0)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--all-marked",
        action="store_true",
        help="Clear all last_pass_at markers, even if article still has topic links",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply
    only_unlinked = not args.all_marked

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import (
        get_pipeline_active_domain_keys,
        resolve_domain_schema,
    )
    from services.backlog_metrics import _count_topic_clustering_pending

    before = _count_topic_clustering_pending()

    report = {"dry_run": dry_run, "only_unlinked": only_unlinked, "domains": [], "before": before}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            for dk in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(dk)
                st = clear_domain(
                    cur, schema, dry_run=dry_run, only_unlinked=only_unlinked
                )
                st["domain"] = dk
                report["domains"].append(st)
                logger.info("%s %s", "DRY" if dry_run else "CLEARED", st)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()

    after = _count_topic_clustering_pending()
    report["after"] = after
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        logger.info("pending before=%s after=%s", before, after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
