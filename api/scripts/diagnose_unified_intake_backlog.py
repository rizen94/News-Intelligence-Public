#!/usr/bin/env python3
"""Compare unified_intake_extraction Monitor backlog vs legacy intake clearance."""

from __future__ import annotations

from shared.article_processing_gates import sql_ml_ready_and_content_bounds
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_schema_names_active
from shared.pipeline_pass_marker import sql_article_pass_null
from shared.pipeline_resource_policy import intake_extraction_suppressed


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
    from config.runtime import env_str
    from services.backlog_metrics import _get_raw_pending_counts
    from services.phase_work_queue_metrics import get_phase_work_queue
    from shared.pipeline_queue_counts import get_unified_intake_breakdown, verify_unified_intake_alignment
    from shared.queue_audit import build_queue_audit

    print("UNIFIED_INTAKE_EXTRACTION_ENABLED=", env_str("UNIFIED_INTAKE_EXTRACTION_ENABLED", "(unset)"))
    print("intake_extraction_suppressed (unified active)=", intake_extraction_suppressed())
    masked = _get_raw_pending_counts()
    print("queue_depth (masked):", masked.get("unified_intake_extraction"))
    breakdown = get_unified_intake_breakdown()
    print("actionable_unified_intake:", breakdown.get("actionable_unified_intake"))
    print("inventory_missing_pass:", breakdown.get("inventory_missing_pass"))
    print("legacy_backfill_eligible:", breakdown.get("legacy_backfill_eligible"))
    print("spine_queue_depth:", breakdown.get("spine_queue_depth"))
    alignment = verify_unified_intake_alignment(masked)
    print("matches_actionable_sql:", alignment.get("matches_actionable_sql"))
    audit = build_queue_audit(masked)
    print("queue_audit:", audit.get("phases", {}).get("unified_intake_extraction"))
    print("phase_work_queue (masked):", get_phase_work_queue("unified_intake_extraction"))
    for ph in ("entity_extraction", "event_extraction", "sentiment_analysis", "quality_scoring"):
        print(f"Monitor pending {ph}:", masked.get(ph))

    pass_u = f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) "
    pass_entity = f" AND ({sql_article_pass_null('entity_extraction', 'a')}) "
    pass_event = f" AND ({sql_article_pass_null('event_extraction', 'a')}) "
    base = _base_where()

    totals = {
        "unified_pending": 0,
        "has_article_entities": 0,
        "entity_pass_cleared": 0,
        "event_pass_cleared": 0,
        "legacy_fully_cleared": 0,
    }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")
            for schema in get_pipeline_schema_names_active():
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE TRUE {pass_u})::bigint,
                        COUNT(*) FILTER (
                            WHERE TRUE {pass_u}
                              AND EXISTS (
                                  SELECT 1 FROM {schema}.article_entities ae
                                  WHERE ae.article_id = a.id
                              )
                        )::bigint,
                        COUNT(*) FILTER (
                            WHERE TRUE {pass_u}
                              AND NOT ({sql_article_pass_null('entity_extraction', 'a')})
                        )::bigint,
                        COUNT(*) FILTER (
                            WHERE TRUE {pass_u}
                              AND NOT ({sql_article_pass_null('event_extraction', 'a')})
                        )::bigint,
                        COUNT(*) FILTER (
                            WHERE TRUE {pass_u}
                              AND NOT ({sql_article_pass_null('entity_extraction', 'a')})
                              AND NOT ({sql_article_pass_null('event_extraction', 'a')})
                              AND NOT ({sql_article_pass_null('sentiment_analysis', 'a')})
                              AND NOT ({sql_article_pass_null('quality_scoring', 'a')})
                        )::bigint
                    FROM {schema}.articles a
                    WHERE {base}
                    """
                )
                row = cur.fetchone()
                print(f"\n{schema}:")
                print(f"  unified_pending (no unified pass): {row[0]}")
                print(f"  ...with article_entities rows:     {row[1]}")
                print(f"  ...entity_extraction pass cleared: {row[2]}")
                print(f"  ...event_extraction pass cleared:  {row[3]}")
                print(f"  ...all legacy intake passes clear: {row[4]}")
                totals["unified_pending"] += int(row[0] or 0)
                totals["has_article_entities"] += int(row[1] or 0)
                totals["entity_pass_cleared"] += int(row[2] or 0)
                totals["event_pass_cleared"] += int(row[3] or 0)
                totals["legacy_fully_cleared"] += int(row[4] or 0)

    print("\n=== totals ===")
    for k, v in totals.items():
        print(f"{k}: {v}")
    if not intake_extraction_suppressed():
        print(
            "\nNote: unified intake is DISABLED — Monitor pending for unified_intake_extraction "
            "is 0; legacy phases own intake (~"
            f"{sum(int(masked.get(p, 0) or 0) for p in ('entity_extraction','event_extraction','sentiment_analysis','quality_scoring'))} "
            "combined on masked counts)."
        )
        print(
            f"Inventory (would-be unified queue if enabled): {totals['unified_pending']} articles "
            "without unified pass marker."
        )
    else:
        print(
            f"\nUnified intake ACTIVE — Monitor pending should match eligible articles "
            f"({totals['unified_pending']} without unified pass marker)."
        )


if __name__ == "__main__":
    main()
