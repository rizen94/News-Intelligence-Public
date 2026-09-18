#!/usr/bin/env python3
"""Detailed unified intake backlog breakdown (actionable vs legacy-already-processed)."""

from __future__ import annotations

from shared.article_processing_gates import sql_ml_ready_and_content_bounds
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_schema_names_active
from shared.pipeline_pass_marker import sql_article_pass_null
from shared.unified_intake_backlog import (
    get_unified_intake_backlog_stats,
    sql_actionable_unified_intake,
    sql_legacy_backfill_eligible,
    sql_legacy_intake_substantively_complete,
    unified_intake_legacy_aware_backlog_enabled,
)


def _base_where() -> str:
    ml_ready = sql_ml_ready_and_content_bounds("a")
    return f"""
        COALESCE(
            (a.metadata #>> '{{pipeline_skip,unified_intake_extraction_skip}}')::boolean,
            false
        ) = false
        AND a.content IS NOT NULL AND LENGTH(a.content) > 100
        AND ({ml_ready})
        AND (
            LENGTH(a.content) >= 500
            OR a.created_at < NOW() - INTERVAL '2 hours'
            OR COALESCE(a.enrichment_status, '') IN ('enriched', 'failed', 'inaccessible')
        )
    """


def main() -> None:
    from services.backlog_metrics import _count_unified_intake_extraction_pending
    from services.phase_work_queue_metrics import get_phase_work_queue

    stats = get_unified_intake_backlog_stats()
    print("unified_intake_backlog_stats:", stats)
    print("legacy_aware:", unified_intake_legacy_aware_backlog_enabled())
    print("Monitor pending (backlog_metrics):", _count_unified_intake_extraction_pending())
    print("phase_work_queue:", get_phase_work_queue("unified_intake_extraction"))

    pass_u = f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) "
    base = _base_where()
    totals = {
        "unified_pending": 0,
        "legacy_backfill_eligible": 0,
        "actionable_needs_llm": 0,
        "has_article_entities": 0,
        "legacy_entity_pass_cleared": 0,
        "legacy_event_pass_cleared": 0,
        "all_legacy_intake_pass_cleared": 0,
        "has_claims_on_linked_context": 0,
        "legacy_substantively_complete": 0,
    }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '180s'")
            for schema in get_pipeline_schema_names_active():
                dk = schema.replace("_", "-")
                legacy_complete = sql_legacy_intake_substantively_complete(schema, "a")
                backfill = sql_legacy_backfill_eligible(schema, "a")
                actionable = sql_actionable_unified_intake(schema, "a")
                cur.execute(
                    f"""
                    SELECT
                      COUNT(*) FILTER (WHERE TRUE {pass_u})::bigint,
                      COUNT(*) FILTER (WHERE {backfill})::bigint,
                      COUNT(*) FILTER (WHERE {actionable})::bigint,
                      COUNT(*) FILTER (WHERE TRUE {pass_u}
                        AND EXISTS (
                            SELECT 1 FROM {schema}.article_entities ae
                            WHERE ae.article_id = a.id))::bigint,
                      COUNT(*) FILTER (WHERE TRUE {pass_u}
                        AND NOT ({sql_article_pass_null('entity_extraction', 'a')}))::bigint,
                      COUNT(*) FILTER (WHERE TRUE {pass_u}
                        AND NOT ({sql_article_pass_null('event_extraction', 'a')}))::bigint,
                      COUNT(*) FILTER (WHERE TRUE {pass_u}
                        AND NOT ({sql_article_pass_null('entity_extraction', 'a')})
                        AND NOT ({sql_article_pass_null('event_extraction', 'a')})
                        AND NOT ({sql_article_pass_null('sentiment_analysis', 'a')})
                        AND NOT ({sql_article_pass_null('quality_scoring', 'a')}))::bigint,
                      COUNT(*) FILTER (WHERE TRUE {pass_u}
                        AND EXISTS (
                          SELECT 1 FROM intelligence.article_to_context atc
                          JOIN intelligence.extracted_claims ec ON ec.context_id = atc.context_id
                          WHERE atc.domain_key = %s AND atc.article_id = a.id
                        ))::bigint,
                      COUNT(*) FILTER (WHERE TRUE {pass_u}
                        AND ({legacy_complete}))::bigint
                    FROM {schema}.articles a
                    WHERE {base}
                    """,
                    (dk,),
                )
                row = cur.fetchone()
                print(f"\n{schema}:")
                print(f"  unified_pending (missing pass): {row[0]}")
                print(f"  legacy_backfill_eligible: {row[1]}")
                print(f"  actionable_needs_llm: {row[2]}")
                print(f"  with article_entities: {row[3]}")
                print(f"  legacy entity pass cleared: {row[4]}")
                print(f"  legacy event pass cleared: {row[5]}")
                print(f"  all legacy intake passes cleared: {row[6]}")
                print(f"  has claims on linked context: {row[7]}")
                print(f"  legacy substantively complete: {row[8]}")
                totals["unified_pending"] += int(row[0] or 0)
                totals["legacy_backfill_eligible"] += int(row[1] or 0)
                totals["actionable_needs_llm"] += int(row[2] or 0)
                totals["has_article_entities"] += int(row[3] or 0)
                totals["legacy_entity_pass_cleared"] += int(row[4] or 0)
                totals["legacy_event_pass_cleared"] += int(row[5] or 0)
                totals["all_legacy_intake_pass_cleared"] += int(row[6] or 0)
                totals["has_claims_on_linked_context"] += int(row[7] or 0)
                totals["legacy_substantively_complete"] += int(row[8] or 0)

    print("\n=== totals ===")
    for k, v in totals.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
