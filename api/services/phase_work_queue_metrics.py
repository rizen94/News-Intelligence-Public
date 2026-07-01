"""
Per-phase work queue breakdown for Monitor: first pass vs retry vs intake-window backlog.

``total_pending`` matches ``backlog_metrics.get_all_pending_counts()`` (scheduler eligibility).
``first_pass`` = never completed a successful/cleared pass for that phase.
``retry_pending`` = attempted but still needs another pass (failed / legacy false-clear).
``intake_first_pass`` = first-pass items created within the intake window (grows with RSS, shrinks on catch-up).
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from config.runtime import env_str
from shared.article_processing_gates import sql_ml_ready_and_content_bounds
from shared.domain_registry import get_pipeline_active_domain_keys, get_pipeline_schema_names_active
from shared.pipeline_pass_marker import (
    phase_backlog_uses_pass_marker,
    sql_article_first_pass_only,
    sql_article_pass_null,
    sql_article_retry_pending,
    sql_context_first_pass_only,
    sql_context_pass_null,
    sql_context_retry_pending,
)

logger = logging.getLogger(__name__)


class PhaseWorkQueue(TypedDict, total=False):
    total_pending: int
    first_pass: int
    retry_pending: int
    intake_first_pass: int
    metric_kind: str
    intake_window_hours: int


def intake_window_hours() -> int:
    try:
        return max(1, int(env_str("MONITOR_INTAKE_WINDOW_HOURS", "72")))
    except ValueError:
        return 72


def _empty_queue(kind: str = "unknown") -> PhaseWorkQueue:
    h = intake_window_hours()
    return {
        "total_pending": 0,
        "first_pass": 0,
        "retry_pending": 0,
        "intake_first_pass": 0,
        "metric_kind": kind,
        "intake_window_hours": h,
    }


def _merge_queues(a: PhaseWorkQueue, b: PhaseWorkQueue) -> PhaseWorkQueue:
    return {
        "total_pending": int(a.get("total_pending", 0)) + int(b.get("total_pending", 0)),
        "first_pass": int(a.get("first_pass", 0)) + int(b.get("first_pass", 0)),
        "retry_pending": int(a.get("retry_pending", 0)) + int(b.get("retry_pending", 0)),
        "intake_first_pass": int(a.get("intake_first_pass", 0)) + int(b.get("intake_first_pass", 0)),
        "metric_kind": a.get("metric_kind") or b.get("metric_kind") or "unknown",
        "intake_window_hours": a.get("intake_window_hours") or intake_window_hours(),
    }


def _get_conn():
    try:
        from services.backlog_metrics import _get_conn as bm_get_conn

        return bm_get_conn()
    except Exception:
        return None


def _count_article_breakdown(
    phase: str,
    *,
    base_where: str,
    use_pass_markers: bool | None = None,
) -> PhaseWorkQueue:
    """COUNT with FILTER for article rows matching ``base_where`` (no leading AND)."""
    conn = _get_conn()
    if not conn:
        return _empty_queue("article")
    use_pass = (
        phase_backlog_uses_pass_marker(phase)
        if use_pass_markers is None
        else use_pass_markers
    )
    hours = intake_window_hours()
    out = _empty_queue("article_pass_marker" if use_pass else "article")
    out["intake_window_hours"] = hours
    try:
        for schema in get_pipeline_schema_names_active():
            pass_total = f" AND ({sql_article_pass_null(phase, 'a')}) " if use_pass else ""
            first_expr = (
                f"({sql_article_first_pass_only(phase, 'a')})"
                if use_pass
                else "TRUE"
            )
            retry_expr = (
                f"({sql_article_retry_pending(phase, 'a')})"
                if use_pass
                else "FALSE"
            )
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '8s'")
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE TRUE {pass_total})::bigint AS total_pending,
                        COUNT(*) FILTER (WHERE ({first_expr}) {pass_total})::bigint AS first_pass,
                        COUNT(*) FILTER (WHERE ({retry_expr}) {pass_total})::bigint AS retry_pending,
                        COUNT(*) FILTER (
                            WHERE ({first_expr}) {pass_total}
                              AND a.created_at >= NOW() - (%s || ' hours')::interval
                        )::bigint AS intake_first_pass
                    FROM {schema}.articles a
                    WHERE {base_where}
                    """,
                    (hours,),
                )
                row = cur.fetchone()
                if row:
                    partial: PhaseWorkQueue = {
                        "total_pending": int(row[0] or 0),
                        "first_pass": int(row[1] or 0),
                        "retry_pending": int(row[2] or 0),
                        "intake_first_pass": int(row[3] or 0),
                        "metric_kind": out["metric_kind"],
                        "intake_window_hours": hours,
                    }
                    out = _merge_queues(out, partial)
        if not use_pass:
            out["first_pass"] = out["total_pending"]
            out["retry_pending"] = 0
            # intake_first_pass already counted with first_expr=TRUE → equals intake total eligible
        return out
    except Exception as e:
        logger.debug("phase_work_queue article %s: %s", phase, e)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_context_breakdown(phase: str, *, base_where: str) -> PhaseWorkQueue:
    conn = _get_conn()
    if not conn:
        return _empty_queue("context")
    use_pass = phase_backlog_uses_pass_marker(phase)
    hours = intake_window_hours()
    out = _empty_queue("context_pass_marker" if use_pass else "context")
    out["intake_window_hours"] = hours
    pass_total = f" AND ({sql_context_pass_null(phase, 'c')}) " if use_pass else ""
    first_expr = (
        f"({sql_context_first_pass_only(phase, 'c')})" if use_pass else "TRUE"
    )
    retry_expr = (
        f"({sql_context_retry_pending(phase, 'c')})" if use_pass else "FALSE"
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE TRUE {pass_total})::bigint,
                    COUNT(*) FILTER (WHERE ({first_expr}) {pass_total})::bigint,
                    COUNT(*) FILTER (WHERE ({retry_expr}) {pass_total})::bigint,
                    COUNT(*) FILTER (
                        WHERE ({first_expr}) {pass_total}
                          AND c.created_at >= NOW() - (%s || ' hours')::interval
                    )::bigint
                FROM intelligence.contexts c
                WHERE {base_where}
                """,
                (hours,),
            )
            row = cur.fetchone()
            if row:
                out = {
                    "total_pending": int(row[0] or 0),
                    "first_pass": int(row[1] or 0),
                    "retry_pending": int(row[2] or 0),
                    "intake_first_pass": int(row[3] or 0),
                    "metric_kind": out["metric_kind"],
                    "intake_window_hours": hours,
                }
        if not use_pass:
            out["first_pass"] = out["total_pending"]
            out["retry_pending"] = 0
        return out
    except Exception as e:
        logger.debug("phase_work_queue context %s: %s", phase, e)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _queue_topic_clustering() -> PhaseWorkQueue:
    from config.settings import topic_clustering_backlog_uses_pass_marker

    use_pass = topic_clustering_backlog_uses_pass_marker()
    base = "a.content IS NOT NULL AND LENGTH(a.content) > 100"
    return _count_article_breakdown("topic_clustering", base_where=base, use_pass_markers=use_pass)


def _queue_entity_extraction() -> PhaseWorkQueue:
    base = """
        NOT EXISTS (SELECT 1 FROM {schema}.article_entities ae WHERE ae.article_id = a.id)
        AND COALESCE((a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean, false) = false
        AND a.content IS NOT NULL AND LENGTH(a.content) > 100
        AND (
            LENGTH(a.content) >= 500
            OR a.created_at < NOW() - INTERVAL '2 hours'
            OR COALESCE(a.enrichment_status, '') IN ('enriched', 'failed', 'inaccessible')
        )
    """
    conn = _get_conn()
    if not conn:
        return _empty_queue("article")
    hours = intake_window_hours()
    out = _empty_queue("article_pass_marker")
    out["intake_window_hours"] = hours
    use_pass = phase_backlog_uses_pass_marker("entity_extraction")
    pass_total = (
        f" AND ({sql_article_pass_null('entity_extraction', 'a')}) " if use_pass else ""
    )
    try:
        for schema in get_pipeline_schema_names_active():
            where = base.format(schema=schema)
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '8s'")
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE TRUE {pass_total})::bigint,
                        COUNT(*) FILTER (WHERE ({sql_article_first_pass_only('entity_extraction', 'a')}) {pass_total})::bigint,
                        COUNT(*) FILTER (WHERE ({sql_article_retry_pending('entity_extraction', 'a')}) {pass_total})::bigint,
                        COUNT(*) FILTER (
                            WHERE ({sql_article_first_pass_only('entity_extraction', 'a')}) {pass_total}
                              AND a.created_at >= NOW() - (%s || ' hours')::interval
                        )::bigint
                    FROM {schema}.articles a
                    WHERE {where}
                    """,
                    (hours,),
                )
                row = cur.fetchone()
                if row:
                    out = _merge_queues(
                        out,
                        {
                            "total_pending": int(row[0] or 0),
                            "first_pass": int(row[1] or 0),
                            "retry_pending": int(row[2] or 0),
                            "intake_first_pass": int(row[3] or 0),
                            "metric_kind": "article_pass_marker",
                            "intake_window_hours": hours,
                        },
                    )
        return out
    except Exception as e:
        logger.debug("phase_work_queue entity_extraction: %s", e)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _queue_unified_intake_extraction() -> PhaseWorkQueue:
    from shared.unified_intake_backlog import (
        sql_actionable_unified_intake,
        unified_intake_legacy_aware_backlog_enabled,
    )

    ml_ready = sql_ml_ready_and_content_bounds("a")
    if unified_intake_legacy_aware_backlog_enabled():
        conn = _get_conn()
        if not conn:
            return _empty_queue("article_pass_marker")
        hours = intake_window_hours()
        out = _empty_queue("article_pass_marker")
        out["intake_window_hours"] = hours
        use_pass = phase_backlog_uses_pass_marker("unified_intake_extraction")
        pass_total = (
            f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) " if use_pass else ""
        )
        try:
            for schema in get_pipeline_schema_names_active():
                where = sql_actionable_unified_intake(schema, "a")
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '8s'")
                    cur.execute(
                        f"""
                        SELECT
                            COUNT(*) FILTER (WHERE TRUE {pass_total})::bigint,
                            COUNT(*) FILTER (WHERE ({sql_article_first_pass_only('unified_intake_extraction', 'a')}) {pass_total})::bigint,
                            COUNT(*) FILTER (WHERE ({sql_article_retry_pending('unified_intake_extraction', 'a')}) {pass_total})::bigint,
                            COUNT(*) FILTER (
                                WHERE ({sql_article_first_pass_only('unified_intake_extraction', 'a')}) {pass_total}
                                  AND a.created_at >= NOW() - (%s || ' hours')::interval
                            )::bigint
                        FROM {schema}.articles a
                        WHERE {where}
                        """,
                        (hours,),
                    )
                    row = cur.fetchone()
                    if row:
                        out = _merge_queues(
                            out,
                            {
                                "total_pending": int(row[0] or 0),
                                "first_pass": int(row[1] or 0),
                                "retry_pending": int(row[2] or 0),
                                "intake_first_pass": int(row[3] or 0),
                                "metric_kind": "article_pass_marker",
                                "intake_window_hours": hours,
                            },
                        )
            return out
        except Exception as e:
            logger.debug("phase_work_queue unified_intake_extraction: %s", e)
            return out
        finally:
            try:
                conn.close()
            except Exception:
                pass

    base = f"""
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
    return _count_article_breakdown("unified_intake_extraction", base_where=base)


def _queue_storyline_assembly() -> PhaseWorkQueue:
    from services.storyline_assembly_service import count_unlinked_articles

    hours = intake_window_hours()
    total = 0
    intake = 0
    for dk in get_pipeline_active_domain_keys():
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config

            lookback = get_domain_synthesis_config(
                dk
            ).storyline_development.proactive.lookback_hours
        except Exception:
            lookback = 72
        n = count_unlinked_articles(dk, lookback_hours=lookback)
        total += n
        ni = count_unlinked_articles(dk, lookback_hours=min(lookback, hours))
        intake += ni
    return {
        "total_pending": total,
        "first_pass": total,
        "retry_pending": 0,
        "intake_first_pass": intake,
        "metric_kind": "storyline_unlinked",
        "intake_window_hours": hours,
    }


def _queue_story_enhancement() -> PhaseWorkQueue:
    conn = _get_conn()
    if not conn:
        return _empty_queue("queue_table")
    hours = intake_window_hours()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                """
                SELECT
                  COALESCE((SELECT COUNT(*) FROM intelligence.fact_change_log
                            WHERE processed = FALSE), 0)::bigint,
                  COALESCE((SELECT COUNT(*) FROM intelligence.fact_change_log
                            WHERE processed = FALSE
                              AND changed_at >= NOW() - (%s || ' hours')::interval), 0)::bigint,
                  COALESCE((SELECT COUNT(*) FROM intelligence.story_update_queue
                            WHERE processed = FALSE), 0)::bigint,
                  COALESCE((SELECT COUNT(*) FROM intelligence.story_update_queue
                            WHERE processed = FALSE
                              AND created_at >= NOW() - (%s || ' hours')::interval), 0)::bigint
                """,
                (hours, hours),
            )
            row = cur.fetchone()
            if not row:
                return _empty_queue("queue_table")
            fc_total, fc_intake, su_total, su_intake = [int(x or 0) for x in row]
            total = fc_total + su_total
            return {
                "total_pending": total,
                "first_pass": total,
                "retry_pending": 0,
                "intake_first_pass": fc_intake + su_intake,
                "metric_kind": "queue_table",
                "intake_window_hours": hours,
            }
    except Exception as e:
        logger.debug("phase_work_queue story_enhancement: %s", e)
        return _empty_queue("queue_table")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _queue_entity_dossier_compile() -> PhaseWorkQueue:
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    conn = _get_conn()
    if not conn:
        return _empty_queue("entity_dossier")
    domain_sql, domain_keys = pipeline_domain_any_sql("ep.domain_key")
    if not domain_keys:
        return _empty_queue("entity_dossier")
    hours = intake_window_hours()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE ed.id IS NULL)::bigint,
                  COUNT(*) FILTER (WHERE ed.id IS NOT NULL
                    AND ed.compilation_date < CURRENT_DATE - INTERVAL '7 days')::bigint,
                  COUNT(*) FILTER (WHERE ed.id IS NULL
                    AND ep.created_at >= NOW() - (%s || ' hours')::interval)::bigint
                FROM intelligence.entity_profiles ep
                LEFT JOIN intelligence.entity_dossiers ed
                  ON ed.domain_key = ep.domain_key AND ed.entity_id = ep.canonical_entity_id
                WHERE ep.canonical_entity_id IS NOT NULL
                  AND {domain_sql}
                """,
                (hours, list(domain_keys)),
            )
            row = cur.fetchone()
            if not row:
                return _empty_queue("entity_dossier")
            first_pass, retry, intake = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
            return {
                "total_pending": first_pass + retry,
                "first_pass": first_pass,
                "retry_pending": retry,
                "intake_first_pass": intake,
                "metric_kind": "entity_dossier",
                "intake_window_hours": hours,
            }
    except Exception as e:
        logger.debug("phase_work_queue entity_dossier_compile: %s", e)
        return _empty_queue("entity_dossier")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _queue_from_pending_total(phase: str, total: int) -> PhaseWorkQueue:
    """Phases without bespoke breakdown: treat all pending as first-pass work."""
    q = _empty_queue("pending_total")
    q["total_pending"] = int(total or 0)
    q["first_pass"] = q["total_pending"]
    q["intake_first_pass"] = 0
    return q


def _queue_metadata_enrichment() -> PhaseWorkQueue:
    base = """a.content IS NOT NULL AND LENGTH(a.content) > 50
        AND (a.metadata IS NULL OR (a.metadata->>'enrichment_done') IS NULL)"""
    return _count_article_breakdown("metadata_enrichment", base_where=base)


def _queue_sentiment_analysis() -> PhaseWorkQueue:
    ml_ready = sql_ml_ready_and_content_bounds()
    base = f"""a.sentiment_score IS NULL
        AND COALESCE((a.metadata #>> '{{pipeline_skip,sentiment_analysis_skip}}')::boolean, false) = false
        AND ({ml_ready})"""
    return _count_article_breakdown("sentiment_analysis", base_where=base)


def _queue_event_extraction() -> PhaseWorkQueue:
    base = """a.timeline_processed = false
        AND COALESCE((a.metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean, false) = false
        AND a.content IS NOT NULL
        AND LENGTH(a.content) > 100
        AND (
            a.processing_status = 'completed'
            OR a.enrichment_status IN ('completed', 'enriched')
        )"""
    return _count_article_breakdown("event_extraction", base_where=base)


_PHASE_HANDLERS: dict[str, Any] = {
    "topic_clustering": _queue_topic_clustering,
    "entity_extraction": _queue_entity_extraction,
    "unified_intake_extraction": _queue_unified_intake_extraction,
    "metadata_enrichment": _queue_metadata_enrichment,
    "sentiment_analysis": _queue_sentiment_analysis,
    "event_extraction": _queue_event_extraction,
    "storyline_assembly": _queue_storyline_assembly,
    "story_enhancement": _queue_story_enhancement,
    "entity_dossier_compile": _queue_entity_dossier_compile,
}


def get_phase_work_queue(phase_name: str, *, pending_total: int | None = None) -> PhaseWorkQueue:
    from shared.pipeline_resource_policy import intake_phase_scheduled

    if not intake_phase_scheduled(phase_name):
        return _empty_queue("inactive_intake_mode")
    handler = _PHASE_HANDLERS.get(phase_name)
    if handler:
        return handler()
    if pending_total is not None:
        return _queue_from_pending_total(phase_name, pending_total)
    try:
        from services.backlog_metrics import get_all_pending_counts

        total = int(get_all_pending_counts().get(phase_name, 0) or 0)
    except Exception:
        total = 0
    return _queue_from_pending_total(phase_name, total)


def get_all_phase_work_queues(
    pending_totals: dict[str, int] | None = None,
) -> dict[str, PhaseWorkQueue]:
    """
    Breakdown for all phases in ``pending_totals`` (or fresh ``get_all_pending_counts()``).
    Handlers run for phases with specific SQL; others inherit totals-only breakdown.
    """
    if pending_totals is None:
        try:
            from services.backlog_metrics import get_all_pending_counts

            pending_totals = {
                k: int(v) for k, v in get_all_pending_counts().items()
            }
        except Exception:
            pending_totals = {}
    out: dict[str, PhaseWorkQueue] = {}
    for phase, total in pending_totals.items():
        if phase in _PHASE_HANDLERS:
            try:
                q = _PHASE_HANDLERS[phase]()
            except Exception as e:
                logger.debug("work queue handler %s: %s", phase, e)
                q = _queue_from_pending_total(phase, total)
        else:
            q = _queue_from_pending_total(phase, total)
        out[phase] = q
    return out


def get_signal_lane_counts_24h(cur=None) -> dict[str, int]:
    """Count unified_intake signal_deferred vs full-lane completions in last 24h."""
    from shared.domain_registry import get_pipeline_schema_names_active

    deferred = 0
    full_lane = 0
    close_conn = False
    conn = None
    if cur is None:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return {"signal_deferred_24h": 0, "signal_full_24h": 0}
        cur = conn.cursor()
        close_conn = True

    try:
        for schema in get_pipeline_schema_names_active():
            try:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (
                            WHERE a.metadata->'pipeline'->'unified_intake_extraction'->>'last_outcome'
                                  = 'signal_deferred'
                              AND (a.metadata->'pipeline'->'unified_intake_extraction'->>'last_pass_at')::timestamptz
                                  >= NOW() - INTERVAL '24 hours'
                        )::bigint,
                        COUNT(*) FILTER (
                            WHERE a.metadata->'pipeline'->'unified_intake_extraction'->>'last_outcome'
                                  IS DISTINCT FROM 'signal_deferred'
                              AND COALESCE(
                                  a.metadata->'pipeline'->'unified_intake_extraction'->>'last_terminal_state',
                                  ''
                              ) IN ('processed_with_output', 'processed_empty_legitimate')
                              AND (a.metadata->'pipeline'->'unified_intake_extraction'->>'last_pass_at')::timestamptz
                                  >= NOW() - INTERVAL '24 hours'
                        )::bigint
                    FROM {schema}.articles a
                    """
                )
                row = cur.fetchone()
                if row:
                    deferred += int(row[0] or 0)
                    full_lane += int(row[1] or 0)
            except Exception as exc:
                logger.debug("signal_lane_counts %s: %s", schema, exc)
    finally:
        if close_conn and conn:
            try:
                conn.close()
            except Exception:
                pass

    return {"signal_deferred_24h": deferred, "signal_full_24h": full_lane}
