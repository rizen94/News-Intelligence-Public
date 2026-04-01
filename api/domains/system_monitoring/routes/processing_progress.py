"""
Processing progress payload for Monitor (dimension throughput, phase_dashboard, hourly ticks).

The HTTP route is registered on ``resource_dashboard.router`` as ``GET /processing_progress``
(same prefix as ``/backlog_status``) so the path is always mounted with the rest of system monitoring.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_ui_db_connection as get_db_connection
from shared.domain_registry import get_schema_names_active, pipeline_url_schema_pairs

logger = logging.getLogger(__name__)

# Keep aligned with resource_dashboard.BACKLOG_WORKLOAD_WINDOW_DAYS (docstring note only).
_BACKLOG_WORKLOAD_WINDOW_DAYS = 4

# Orchestrator-only phase: omit from Processing pulse (still runs on schedule; history remains in DB).
_PROCESSING_PROGRESS_EXCLUDED_PHASES = frozenset({"nightly_enrichment_context"})


def _rollback_conn(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


def compute_processing_progress_response() -> dict[str, Any]:
    """
    Build JSON for GET /api/system_monitoring/processing_progress.

    See resource_dashboard route docstring / AGENTS.md for field meanings.
    """
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.warning("processing_progress: database unavailable: %s", e)
        return {"success": False, "error": str(e)[:200], "data": None}

    now_iso = datetime.now(timezone.utc).isoformat()
    dimensions: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    hourly_phase_ticks: list[dict[str, Any]] = []

    try:
        cur = conn.cursor()
        try:
            cur.execute("SET LOCAL statement_timeout = '8s'")
        except Exception:
            _rollback_conn(conn)

        article_backlog = 0
        enriched_1h = enriched_24h = enriched_7d = 0
        for schema in get_schema_names_active():
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    """
                )
                article_backlog += cur.fetchone()[0] or 0
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                        COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours'),
                        COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days')
                    FROM {schema}.articles
                    WHERE enrichment_status = 'enriched' AND url IS NOT NULL AND url != ''
                    """
                )
                r = cur.fetchone()
                if r:
                    enriched_1h += r[0] or 0
                    enriched_24h += r[1] or 0
                    enriched_7d += r[2] or 0
            except Exception:
                _rollback_conn(conn)

        dimensions.append(
            {
                "id": "articles_enriched",
                "label": "Articles enriched",
                "backlog": article_backlog,
                "last_1h": enriched_1h,
                "last_24h": enriched_24h,
                "last_7d": enriched_7d,
            }
        )

        context_backlog = 0
        ctx_claim_1h = ctx_claim_24h = ctx_claim_7d = 0
        ctx_created_1h = ctx_created_24h = ctx_created_7d = 0
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                """
            )
            context_backlog = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '24 hours'),
                    COUNT(DISTINCT context_id) FILTER (WHERE ec.created_at >= NOW() - INTERVAL '7 days')
                FROM intelligence.extracted_claims ec
                """
            )
            r = cur.fetchone()
            if r:
                ctx_claim_1h, ctx_claim_24h, ctx_claim_7d = (r[0] or 0), (r[1] or 0), (r[2] or 0)
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours'),
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')
                FROM intelligence.contexts
                """
            )
            r2 = cur.fetchone()
            if r2:
                ctx_created_1h, ctx_created_24h, ctx_created_7d = (
                    r2[0] or 0,
                    r2[1] or 0,
                    r2[2] or 0,
                )
        except Exception:
            _rollback_conn(conn)

        dimensions.append(
            {
                "id": "contexts_claimed",
                "label": "Contexts → claims",
                "backlog": context_backlog,
                "last_1h": ctx_claim_1h,
                "last_24h": ctx_claim_24h,
                "last_7d": ctx_claim_7d,
            }
        )
        dimensions.append(
            {
                "id": "contexts_created",
                "label": "Contexts created",
                "backlog": None,
                "last_1h": ctx_created_1h,
                "last_24h": ctx_created_24h,
                "last_7d": ctx_created_7d,
            }
        )

        ep_backlog = ep_any_1h = ep_any_24h = ep_any_7d = 0
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                WHERE ep.sections = '[]'::jsonb OR ep.sections IS NULL
                   OR ep.updated_at < NOW() - INTERVAL '7 days'
                """
            )
            ep_backlog = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days')
                FROM intelligence.entity_profiles
                """
            )
            r = cur.fetchone()
            if r:
                ep_any_1h, ep_any_24h, ep_any_7d = (r[0] or 0), (r[1] or 0), (r[2] or 0)
        except Exception:
            _rollback_conn(conn)

        dimensions.append(
            {
                "id": "entity_profiles_touched",
                "label": "Entity profiles updated",
                "backlog": ep_backlog,
                "last_1h": ep_any_1h,
                "last_24h": ep_any_24h,
                "last_7d": ep_any_7d,
            }
        )

        docs_backlog = docs_1h = docs_24h = docs_7d = 0
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.processed_documents
                WHERE (extracted_sections IS NULL OR extracted_sections = '[]')
                  AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
                """
            )
            docs_backlog = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '1 hour'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '24 hours'),
                    COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days')
                FROM intelligence.processed_documents
                WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]'::jsonb
                """
            )
            r = cur.fetchone()
            if r:
                docs_1h, docs_24h, docs_7d = (r[0] or 0), (r[1] or 0), (r[2] or 0)
        except Exception:
            _rollback_conn(conn)

        dimensions.append(
            {
                "id": "documents_extracted",
                "label": "PDFs / documents extracted",
                "backlog": docs_backlog,
                "last_1h": docs_1h,
                "last_24h": docs_24h,
                "last_7d": docs_7d,
            }
        )

        storyline_backlog = syn_1h = syn_24h = syn_7d = 0
        for _dk, schema in pipeline_url_schema_pairs():
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                      ON sa.storyline_id = s.id AND sa.c >= 3
                    WHERE s.synthesized_content IS NULL
                       OR EXISTS (
                         SELECT 1 FROM {schema}.storyline_articles sa2
                         JOIN {schema}.articles a ON a.id = sa2.article_id
                         WHERE sa2.storyline_id = s.id
                         AND a.created_at > COALESCE(s.synthesized_at, '1970-01-01'::timestamptz)
                       )
                    """
                )
                storyline_backlog += cur.fetchone()[0] or 0
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '1 hour'),
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '24 hours'),
                        COUNT(*) FILTER (WHERE synthesized_at >= NOW() - INTERVAL '7 days')
                    FROM {schema}.storylines
                    WHERE synthesized_at IS NOT NULL
                    """
                )
                r = cur.fetchone()
                if r:
                    syn_1h += r[0] or 0
                    syn_24h += r[1] or 0
                    syn_7d += r[2] or 0
            except Exception:
                _rollback_conn(conn)

        dimensions.append(
            {
                "id": "storylines_synthesized",
                "label": "Storylines synthesized",
                "backlog": storyline_backlog,
                "last_1h": syn_1h,
                "last_24h": syn_24h,
                "last_7d": syn_7d,
            }
        )

        try:
            cur.execute(
                """
                SELECT phase_name,
                    COUNT(*) FILTER (WHERE finished_at >= NOW() - INTERVAL '1 hour') AS r1h,
                    COUNT(*) FILTER (WHERE finished_at >= NOW() - INTERVAL '24 hours') AS r24h,
                    COUNT(*) FILTER (WHERE finished_at >= NOW() - INTERVAL '7 days') AS r7d,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours' AND success IS TRUE
                    ) AS s24h,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours' AND success IS NOT TRUE
                    ) AS f24h,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '7 days' AND success IS TRUE
                    ) AS s7d,
                    COUNT(*) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '7 days' AND success IS NOT TRUE
                    ) AS f7d,
                    AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (
                        WHERE finished_at >= NOW() - INTERVAL '24 hours'
                          AND started_at IS NOT NULL
                    ) AS avg_s
                FROM automation_run_history
                WHERE finished_at >= NOW() - INTERVAL '7 days'
                  AND NOT (phase_name = ANY(%s))
                GROUP BY phase_name
                ORDER BY r7d DESC NULLS LAST, phase_name
                """,
                (list(_PROCESSING_PROGRESS_EXCLUDED_PHASES),),
            )
            for row in cur.fetchall() or []:
                (
                    name,
                    r1h,
                    r24h,
                    r7d,
                    s24h,
                    f24h,
                    s7d,
                    f7d,
                    avg_s,
                ) = row[0], row[1] or 0, row[2] or 0, row[3] or 0, row[4] or 0, row[5] or 0, row[6] or 0, row[7] or 0, row[8]
                r24i, r7di = int(r24h), int(r7d)
                s24i, f24i, s7i, f7i = int(s24h), int(f24h), int(s7d), int(f7d)
                # Tri-valued success: TRUE / FALSE / NULL — (IS TRUE) and (IS NOT TRUE) partition rows.
                if s24i + f24i != r24i:
                    logger.warning(
                        "processing_progress: 24h run count mismatch for %s: successes+failures=%s runs=%s",
                        name,
                        s24i + f24i,
                        r24i,
                    )
                if s7i + f7i != r7di:
                    logger.warning(
                        "processing_progress: 7d run count mismatch for %s: successes+failures=%s runs=%s",
                        name,
                        s7i + f7i,
                        r7di,
                    )
                # Sample proportion of completions marked success (not a binomial CI).
                pr24 = round(100.0 * s24i / r24i, 1) if r24i > 0 else None
                pr7 = round(100.0 * s7i / r7di, 1) if r7di > 0 else None
                phases.append(
                    {
                        "phase_name": name,
                        "runs_1h": int(r1h),
                        "runs_24h": r24i,
                        "runs_7d": r7di,
                        "successes_24h": s24i,
                        "failures_24h": f24i,
                        "successes_7d": s7i,
                        "failures_7d": f7i,
                        "pass_rate_24h": pr24,
                        "pass_rate_7d": pr7,
                        "avg_duration_sec_24h": round(float(avg_s), 1) if avg_s is not None else None,
                    }
                )
        except Exception as e:
            logger.debug("processing_progress phase summary: %s", e)
            _rollback_conn(conn)

        try:
            cur.execute(
                """
                SELECT date_trunc('hour', finished_at) AS hr,
                       phase_name,
                       COUNT(*) AS runs,
                       SUM(CASE WHEN success IS TRUE THEN 0 ELSE 1 END) AS fails
                FROM automation_run_history
                WHERE finished_at >= NOW() - INTERVAL '72 hours'
                  AND NOT (phase_name = ANY(%s))
                GROUP BY hr, phase_name
                HAVING COUNT(*) > 0
                ORDER BY hr ASC, phase_name ASC
                LIMIT 4000
                """,
                (list(_PROCESSING_PROGRESS_EXCLUDED_PHASES),),
            )
            for row in cur.fetchall() or []:
                hr, pname, runs, fails = row[0], row[1], row[2] or 0, row[3] or 0
                hourly_phase_ticks.append(
                    {
                        "hour_utc": hr.isoformat() if hasattr(hr, "isoformat") else str(hr),
                        "phase_name": pname,
                        "runs": int(runs),
                        "failures": int(fails),
                    }
                )
        except Exception as e:
            logger.debug("processing_progress hourly: %s", e)
            _rollback_conn(conn)

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("processing_progress: failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:200], "data": None}

    phase_by_name = {p["phase_name"]: p for p in phases if p.get("phase_name")}
    pending_m: dict[str, int] = {}
    backlog_m: dict[str, int] = {}

    def _fallback_batch(_: str) -> int:
        return 1

    get_batch = _fallback_batch
    try:
        from services.backlog_metrics import (
            get_all_backlog_counts,
            get_all_pending_counts,
            get_per_run_batch_size_for_phase,
        )

        get_batch = get_per_run_batch_size_for_phase
        pending_m = {k: int(v) for k, v in get_all_pending_counts().items()}
        # Row-excess counts (for sort keys / parity with automation backlog_counts); not shown as batches.
        backlog_m = {k: int(v) for k, v in get_all_backlog_counts().items()}
    except Exception as e:
        logger.debug("processing_progress backlog_metrics merge: %s", e)

    all_names = sorted(
        (set(phase_by_name) | set(pending_m) | set(backlog_m))
        - _PROCESSING_PROGRESS_EXCLUDED_PHASES,
        key=lambda n: (
            -(pending_m.get(n, 0) + backlog_m.get(n, 0)),
            -(phase_by_name.get(n, {}).get("runs_7d", 0) or 0),
            n,
        ),
    )
    phase_dashboard: list[dict[str, Any]] = []
    for name in all_names:
        row = dict(phase_by_name.get(name, {}))
        if not row:
            row = {
                "phase_name": name,
                "runs_1h": 0,
                "runs_24h": 0,
                "runs_7d": 0,
                "successes_24h": 0,
                "failures_24h": 0,
                "successes_7d": 0,
                "failures_7d": 0,
                "pass_rate_24h": None,
                "pass_rate_7d": None,
                "avg_duration_sec_24h": None,
            }
        row["phase_name"] = name
        pend = int(pending_m.get(name, 0))
        row["pending_records"] = pend
        row["estimated_batch_per_run"] = int(get_batch(name))
        bsize = int(row["estimated_batch_per_run"])
        if pend <= 0:
            row["batches_to_drain"] = 0
        elif bsize > 0:
            row["batches_to_drain"] = int(math.ceil(pend / bsize))
        else:
            row["batches_to_drain"] = None
        phase_dashboard.append(row)

    reporting_definitions: dict[str, str] = {
        "pass_rate_24h_7d": (
            "Percentage = 100 × (completions with success=TRUE) ÷ (all completions in window). "
            "SQL uses success IS NOT TRUE for non-success, so FALSE and NULL both count as non-success. "
            "Denominator is finished runs only (no censoring of in-flight work). "
            "This is a sample proportion, not a confidence interval."
        ),
        "pending_records": (
            "Estimated work remaining for this phase: backlog_metrics counts rows that match the same "
            "eligibility filters the automation phase uses (not raw table sizes). Phases with rotating "
            "batches (e.g. storyline_automation) still show total eligible items; estimated_batch_per_run "
            "reflects typical throughput per scheduler run."
        ),
        "estimated_batch_per_run": (
            "Modeled rows consumed per scheduled run of the phase (backlog_metrics._per_run_batch_size); "
            "configuration estimate, not measured from automation_run_history."
        ),
        "batches_to_drain": (
            "Runs needed to clear the current queue: ceil(pending_records ÷ estimated_batch_per_run) "
            "when estimated_batch_per_run > 0; 0 if no pending; null if estimated_batch_per_run is 0 "
            "(no row-batch model for that phase). Values > 1 mean more than one run is needed to drain."
        ),
        "avg_duration_sec_24h": (
            "Unweighted arithmetic mean of (finished_at − started_at) in seconds over 24h completions; "
            "long runs skew the mean (median would be more robust but is not shown)."
        ),
        "runs_24h": (
            "Count of rows in automation_run_history for that phase in the window. For claim_extraction with "
            "CLAIM_EXTRACTION_DRAIN, one row is written per internal batch (not one per long-running scheduler task)."
        ),
        "dimension_throughput": (
            "Counts of rows updated or created in the stated intervals (SQL filters differ per dimension); "
            "not necessarily mutually exclusive across dimensions."
        ),
        "hourly_phase_ticks_failures": (
            "Per bucket, failures = completions where success is not TRUE (same rule as pass rate)."
        ),
    }

    return {
        "success": True,
        "data": {
            "generated_at_utc": now_iso,
            "workload_window_days_note": _BACKLOG_WORKLOAD_WINDOW_DAYS,
            "reporting_definitions": reporting_definitions,
            "dimensions": dimensions,
            "phase_dashboard": phase_dashboard,
            "phases": phase_dashboard,
            "hourly_phase_ticks": hourly_phase_ticks,
        },
    }
