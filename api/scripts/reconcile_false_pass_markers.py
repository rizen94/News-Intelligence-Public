#!/usr/bin/env python3
"""
Re-queue articles/contexts that were falsely marked processed (legacy outcomes without output).

Never deletes intelligence rows — only clears metadata.pipeline.<phase> markers.

  PYTHONPATH=api python3 api/scripts/reconcile_false_pass_markers.py --dry-run
  PYTHONPATH=api python3 api/scripts/reconcile_false_pass_markers.py --phase entity_extraction --limit 5000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.pipeline_pass_marker import (
    CLEARED_TERMINAL_STATES,
    LEGACY_FALSE_CLEAR_OUTCOMES,
    TERMINAL_FAILED_NEEDS_RETRY,
    TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
    bulk_record_article_phase_pass,
    clear_context_phase_pass,
)


def _preclear_entity_short_and_broken(dry_run: bool, limit: int) -> int:
    """Mark short / broken-enrichment articles empty-legitimate (no LLM)."""
    from config.runtime import env_str
    from shared.domain_registry import get_pipeline_schema_names_active

    short_max = int(env_str("ENTITY_EXTRACTION_LEGITIMATE_EMPTY_MAX_CHARS", "400"))
    phases = (
        "entity_extraction",
        "unified_intake_extraction",
        "event_extraction",
    )
    total = 0
    for schema in get_pipeline_schema_names_active():
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id
                    FROM {schema}.articles a
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.article_entities ae WHERE ae.article_id = a.id
                    )
                      AND COALESCE(
                          (a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean,
                          false
                      ) = false
                      AND a.content IS NOT NULL
                      AND (
                          LENGTH(a.content) < %s
                          OR COALESCE(a.enrichment_status, '') IN ('failed', 'inaccessible')
                      )
                      AND COALESCE(
                          a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state',
                          ''
                      ) != %s
                    ORDER BY a.id
                    LIMIT %s
                    """,
                    (short_max, TERMINAL_PROCESSED_EMPTY_LEGITIMATE, limit),
                )
                ids = [r[0] for r in cur.fetchall()]
        print(f"  {schema}: {len(ids)} short/broken articles to pre-clear")
        if dry_run:
            total += len(ids)
            continue
        if not ids:
            continue
        for phase in phases:
            bulk_record_article_phase_pass(
                schema,
                ids,
                phase,
                "no_entities_stored" if phase == "entity_extraction" else "preclear_skip",
                terminal_state=TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
            )
        total += len(ids)
    return total


def _reconcile_entity_false_with_output(dry_run: bool, limit: int) -> int:
    """Re-queue long articles marked processed_with_output but with zero entity rows."""
    from shared.domain_registry import get_pipeline_schema_names_active

    short_max = 400
    clear_phases = (
        "entity_extraction",
        "unified_intake_extraction",
        "event_extraction",
        "sentiment_analysis",
        "quality_scoring",
    )
    total = 0
    for schema in get_pipeline_schema_names_active():
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id
                    FROM {schema}.articles a
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.article_entities ae WHERE ae.article_id = a.id
                    )
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) >= %s
                      AND COALESCE(
                          a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state',
                          ''
                      ) = 'processed_with_output'
                    ORDER BY a.id
                    LIMIT %s
                    """,
                    (short_max, limit),
                )
                ids = [r[0] for r in cur.fetchall()]
        print(f"  {schema}: {len(ids)} false-with-output entity clears to re-queue")
        if dry_run:
            total += len(ids)
            continue
        if not ids:
            continue
        chunk = 50
        for offset in range(0, len(ids), chunk):
            batch = ids[offset : offset + chunk]
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '300s'")
                    cur.execute("SET LOCAL lock_timeout = '5s'")
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.articles
                        WHERE id = ANY(%s)
                        FOR UPDATE SKIP LOCKED
                        """,
                        (batch,),
                    )
                    locked = [r[0] for r in cur.fetchall()]
                    if not locked:
                        continue
                    meta_expr = "COALESCE(metadata, '{}'::jsonb)"
                    for phase in clear_phases:
                        meta_expr = f"({meta_expr} #- '{{pipeline,{phase}}}')"
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET metadata = {meta_expr}
                        WHERE id = ANY(%s)
                        """,
                        (locked,),
                    )
                conn.commit()
            total += len(locked)
    return total


def _reconcile_entity_extraction(dry_run: bool, limit: int) -> int:
    total = 0
    for domain_key in get_pipeline_active_domain_keys():
        schema = resolve_domain_schema(domain_key)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id
                    FROM {schema}.articles a
                    LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                    WHERE ae.id IS NULL
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 400
                      AND (
                        (a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_outcome') = 'no_entities_stored'
                        OR (
                            (a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_pass_at') IS NOT NULL
                            AND COALESCE(
                                a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state',
                                ''
                            ) NOT IN %s
                            AND COALESCE(
                                a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state',
                                ''
                            ) != 'failed_needs_retry'
                        )
                      )
                    ORDER BY a.id
                    LIMIT %s
                    """,
                    (tuple(CLEARED_TERMINAL_STATES), limit),
                )
                ids = [r[0] for r in cur.fetchall()]
        print(f"  {domain_key}: {len(ids)} articles to re-queue")
        if dry_run:
            total += len(ids)
            continue
        if not ids:
            continue
        phase = "entity_extraction"
        chunk = 50
        for offset in range(0, len(ids), chunk):
            batch = ids[offset : offset + chunk]
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '300s'")
                    cur.execute("SET LOCAL lock_timeout = '5s'")
                    cur.execute(
                        f"""
                        SELECT id
                        FROM {schema}.articles
                        WHERE id = ANY(%s)
                        FOR UPDATE SKIP LOCKED
                        """,
                        (batch,),
                    )
                    locked = [r[0] for r in cur.fetchall()]
                    if not locked:
                        continue
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET metadata = (COALESCE(metadata, '{{}}'::jsonb) #- '{{pipeline,{phase}}}')
                        WHERE id = ANY(%s)
                        """,
                        (locked,),
                    )
                conn.commit()
            total += len(locked)
    return total


def _reconcile_claim_extraction(dry_run: bool, limit: int) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id
                FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                  AND LENGTH(COALESCE(c.title, '') || COALESCE(c.content, '')) > 200
                  AND (
                    (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome')
                      = ANY(%s)
                    OR (
                        (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_pass_at') IS NOT NULL
                        AND COALESCE(
                            c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_terminal_state',
                            ''
                        ) NOT IN %s
                        AND COALESCE(
                            c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_terminal_state',
                            ''
                        ) != %s
                    )
                    OR (
                        (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_pass_at') IS NOT NULL
                        AND (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_terminal_state') IS NULL
                        AND (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome') IS NULL
                    )
                  )
                ORDER BY c.id
                LIMIT %s
                """,
                (
                    list(LEGACY_FALSE_CLEAR_OUTCOMES),
                    tuple(CLEARED_TERMINAL_STATES),
                    TERMINAL_FAILED_NEEDS_RETRY,
                    limit,
                ),
            )
            ids = [r[0] for r in cur.fetchall()]
    print(f"  claim_extraction: {len(ids)} contexts to re-queue")
    if dry_run:
        return len(ids)
    for cid in ids:
        clear_context_phase_pass(cid, "claim_extraction")
    return len(ids)


def _reconcile_event_extraction(dry_run: bool, limit: int) -> int:
    """Re-queue long articles marked processed with zero events (false clears)."""
    from shared.domain_registry import get_pipeline_schema_names_active

    total = 0
    min_len = 500
    phase = "event_extraction"
    for schema in get_pipeline_schema_names_active():
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id
                    FROM {schema}.articles a
                    WHERE a.timeline_processed = true
                      AND COALESCE(a.timeline_events_generated, 0) = 0
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > %s
                      AND COALESCE(
                          (a.metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean,
                          false
                      ) = false
                    ORDER BY a.id
                    LIMIT %s
                    """,
                    (min_len, limit),
                )
                ids = [r[0] for r in cur.fetchall()]
        print(f"  {schema}: {len(ids)} zero-event articles to re-queue")
        if dry_run:
            total += len(ids)
            continue
        if not ids:
            continue
        chunk = 25
        for offset in range(0, len(ids), chunk):
            batch = ids[offset : offset + chunk]
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '300s'")
                    cur.execute("SET LOCAL lock_timeout = '5s'")
                    cur.execute(
                        f"""
                        SELECT id
                        FROM {schema}.articles
                        WHERE id = ANY(%s)
                        FOR UPDATE SKIP LOCKED
                        """,
                        (batch,),
                    )
                    locked = [r[0] for r in cur.fetchall()]
                    if not locked:
                        continue
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET timeline_processed = false,
                            timeline_events_generated = 0,
                            metadata = (COALESCE(metadata, '{{}}'::jsonb) #- '{{pipeline,{phase}}}'),
                            updated_at = NOW()
                        WHERE id = ANY(%s)
                        """,
                        (locked,),
                    )
                conn.commit()
            total += len(locked)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile false pipeline pass markers")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--phase",
        choices=(
            "entity_extraction",
            "entity_false_output",
            "entity_preclear",
            "claim_extraction",
            "event_extraction",
            "all",
        ),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=10_000)
    args = parser.parse_args()

    total = 0
    if args.phase in ("entity_preclear", "all"):
        print("Entity pre-clear (short / failed enrichment):")
        total += _preclear_entity_short_and_broken(args.dry_run, args.limit)
    if args.phase in ("entity_false_output", "all"):
        print("Entity false-with-output reconciliation:")
        total += _reconcile_entity_false_with_output(args.dry_run, args.limit)
    if args.phase in ("entity_extraction", "all"):
        print("Entity extraction reconciliation (legacy incomplete markers):")
        total += _reconcile_entity_extraction(args.dry_run, args.limit)
    if args.phase in ("claim_extraction", "all"):
        print("Claim extraction reconciliation:")
        total += _reconcile_claim_extraction(args.dry_run, args.limit)
    if args.phase in ("event_extraction", "all"):
        print("Event extraction reconciliation (zero-event false clears):")
        total += _reconcile_event_extraction(args.dry_run, args.limit)

    action = "would re-queue" if args.dry_run else "re-queued"
    print(f"Done: {action} {total} item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
