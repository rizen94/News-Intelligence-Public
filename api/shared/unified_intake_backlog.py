"""
Unified intake backlog semantics: actionable LLM work vs legacy-complete marker backfill.

When unified intake replaced legacy per-phase extract, Monitor still counted every article
without a ``unified_intake_extraction`` pass marker (~64k) even though most already had
entities, events, and scores from legacy paths. Re-running unified LLM on those rows is
wasteful; this module aligns backlog counts, automation selection, and bulk backfill.
"""

from __future__ import annotations

import logging
import threading
import time

from config.runtime import env_str
from config.settings import unified_intake_legacy_aware_backlog_enabled
from shared.article_processing_gates import sql_ml_ready_and_content_bounds
from shared.domain_registry import get_pipeline_schema_names_active
from shared.pipeline_pass_marker import (
    TERMINAL_PROCESSED_WITH_OUTPUT,
    phase_backlog_uses_pass_marker,
    sql_article_pass_null,
)

logger = logging.getLogger(__name__)

LEGACY_INTAKE_BACKFILL_OUTCOME = "backfilled_from_legacy"

_stats_cache: dict[str, int] | None = None
_stats_cache_time: float = 0.0
_stats_cache_lock = threading.Lock()


def _unified_stats_cache_ttl_seconds() -> int:
    """Heavy cross-schema COUNT queries — default 5m, longer than backlog_metrics TTL."""
    raw = env_str("UNIFIED_INTAKE_BACKLOG_STATS_TTL_SECONDS", "300").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 300


def invalidate_unified_intake_backlog_stats_cache() -> None:
    """Force next get_unified_intake_backlog_stats() to re-query."""
    global _stats_cache, _stats_cache_time
    with _stats_cache_lock:
        _stats_cache = None
        _stats_cache_time = 0.0


def sql_unified_intake_base_eligible(alias: str = "a") -> str:
    """Articles eligible for unified intake (content / enrichment gates)."""
    ml_ready = sql_ml_ready_and_content_bounds(alias)
    return f"""
        COALESCE(
            ({alias}.metadata #>> '{{pipeline_skip,unified_intake_extraction_skip}}')::boolean,
            false
        ) = false
        AND {alias}.content IS NOT NULL
        AND LENGTH({alias}.content) > 100
        AND ({ml_ready})
        AND (
            LENGTH({alias}.content) >= 500
            OR {alias}.created_at < NOW() - INTERVAL '2 hours'
            OR COALESCE({alias}.enrichment_status, '') IN (
                'enriched', 'failed', 'inaccessible'
            )
        )
    """


def sql_legacy_intake_substantively_complete(schema: str, alias: str = "a") -> str:
    """
    Article already has legacy intake outputs — unified LLM would mostly duplicate work.

    Requires stored entities, event work (pass marker, timeline flag, or chronological row),
    and sentiment/quality scores (column values or cleared pass markers).
    """
    entity_ok = f"""
        EXISTS (
            SELECT 1 FROM {schema}.article_entities ae
            WHERE ae.article_id = {alias}.id
        )
        OR NOT ({sql_article_pass_null('entity_extraction', alias)})
    """
    event_ok = f"""
        NOT ({sql_article_pass_null('event_extraction', alias)})
        OR COALESCE({alias}.timeline_processed, false) = true
        OR EXISTS (
            SELECT 1 FROM public.chronological_events ce
            WHERE ce.source_article_id = {alias}.id
        )
    """
    scoring_ok = f"""
        (
            {alias}.sentiment_score IS NOT NULL
            AND {alias}.quality_score IS NOT NULL
        )
        OR (
            NOT ({sql_article_pass_null('sentiment_analysis', alias)})
            AND NOT ({sql_article_pass_null('quality_scoring', alias)})
        )
    """
    return f"(({entity_ok}) AND ({event_ok}) AND ({scoring_ok}))"


def sql_unified_pass_pending(alias: str = "a") -> str:
    if not phase_backlog_uses_pass_marker("unified_intake_extraction"):
        return "TRUE"
    return f"({sql_article_pass_null('unified_intake_extraction', alias)})"


def sql_actionable_unified_intake(schema: str, alias: str = "a") -> str:
    """Needs unified LLM (or retry) — not satisfied by legacy intake alone."""
    base = sql_unified_intake_base_eligible(alias)
    pending = sql_unified_pass_pending(alias)
    if not unified_intake_legacy_aware_backlog_enabled():
        return f"({base}) AND ({pending})"
    legacy = sql_legacy_intake_substantively_complete(schema, alias)
    return f"({base}) AND ({pending}) AND NOT ({legacy})"


def sql_legacy_backfill_eligible(schema: str, alias: str = "a") -> str:
    """Missing unified pass marker but legacy intake outputs already present."""
    if not unified_intake_legacy_aware_backlog_enabled():
        return "FALSE"
    base = sql_unified_intake_base_eligible(alias)
    pending = sql_unified_pass_pending(alias)
    legacy = sql_legacy_intake_substantively_complete(schema, alias)
    return f"({base}) AND ({pending}) AND ({legacy})"


def _query_unified_intake_backlog_stats() -> dict[str, int]:
    from shared.database.connection import get_db_connection

    out = {
        "total_missing_unified_pass": 0,
        "legacy_backfill_eligible": 0,
        "actionable_unified_intake": 0,
    }
    conn = get_db_connection()
    if not conn:
        return out
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '180s'")
            for schema in get_pipeline_schema_names_active():
                base = sql_unified_intake_base_eligible("a")
                pending = sql_unified_pass_pending("a")
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE ({base}) AND ({pending}))::bigint,
                        COUNT(*) FILTER (WHERE {sql_legacy_backfill_eligible(schema, 'a')})::bigint,
                        COUNT(*) FILTER (WHERE {sql_actionable_unified_intake(schema, 'a')})::bigint
                    FROM {schema}.articles a
                    """
                )
                row = cur.fetchone()
                if row:
                    out["total_missing_unified_pass"] += int(row[0] or 0)
                    out["legacy_backfill_eligible"] += int(row[1] or 0)
                    out["actionable_unified_intake"] += int(row[2] or 0)
    except Exception as e:
        logger.warning("get_unified_intake_backlog_stats: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out


def get_unified_intake_backlog_stats() -> dict[str, int]:
    """
    Break down unified intake inventory for Monitor vs automation.

    - total_missing_unified_pass: any eligible article without cleared unified pass
    - legacy_backfill_eligible: marker-only backfill (legacy outputs present)
    - actionable_unified_intake: matches automation / backlog_metrics pending count

    Cached separately (default 300s) — queries are heavier than per-phase backlog counts.
    """
    global _stats_cache, _stats_cache_time
    ttl = _unified_stats_cache_ttl_seconds()
    now = time.monotonic()
    if _stats_cache is not None and now - _stats_cache_time <= ttl:
        return dict(_stats_cache)

    with _stats_cache_lock:
        now = time.monotonic()
        if _stats_cache is not None and now - _stats_cache_time <= ttl:
            return dict(_stats_cache)
        out = _query_unified_intake_backlog_stats()
        _stats_cache = dict(out)
        _stats_cache_time = time.monotonic()
        return dict(out)


def backfill_unified_pass_from_legacy_batch(
    *,
    schema_name: str,
    limit: int = 500,
) -> list[int]:
    """
    Set unified_intake_extraction pass marker for legacy-complete articles (no LLM).
    Returns article ids backfilled.
    """
    from shared.database.connection import get_db_connection_context
    from shared.pipeline_pass_marker import bulk_record_article_phase_pass

    if not unified_intake_legacy_aware_backlog_enabled():
        return []
    limit = max(1, min(5000, int(limit)))
    where = sql_legacy_backfill_eligible(schema_name, "a")
    ids: list[int] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute(
                f"""
                SELECT a.id FROM {schema_name}.articles a
                WHERE {where}
                ORDER BY a.created_at ASC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            ids = [int(r[0]) for r in cur.fetchall()]
    if ids:
        bulk_record_article_phase_pass(
            schema_name,
            ids,
            "unified_intake_extraction",
            LEGACY_INTAKE_BACKFILL_OUTCOME,
            terminal_state=TERMINAL_PROCESSED_WITH_OUTPUT,
        )
        invalidate_unified_intake_backlog_stats_cache()
    return ids
