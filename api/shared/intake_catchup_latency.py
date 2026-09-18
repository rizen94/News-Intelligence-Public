"""
Intake → full-process catchup latency (RSS created_at → core pipeline done).

v1 stages (6h SLA by default): enrichment, unified intake, context_sync,
topic_clustering, storyline link. Assembly / EPB / dossier are out of scope.

See docs/SIGNAL_FIRST_OPS.md and MONITOR_REPORTING_AND_METRICS.md.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_float, env_int, env_str

logger = logging.getLogger(__name__)

_STATE_KEY = "intake_catchup_latency_samples"
_cache: dict[str, Any] | None = None
_cache_mono: float = 0.0
_cache_lock = threading.Lock()


def catchup_sla_hours(override: float | None = None) -> float:
    if override is not None:
        return max(0.5, float(override))
    return max(0.5, env_float("CATCHUP_SLA_HOURS", 6.0))


def preprocess_sla_hours(override: float | None = None) -> float:
    """Enrich → UIE → context_sync only (steady-state intake target)."""
    if override is not None:
        return max(0.25, float(override))
    return max(0.25, env_float("PREPROCESS_SLA_HOURS", 1.0))


def catchup_window_hours(override: int | None = None) -> int:
    if override is not None:
        return max(1, int(override))
    try:
        from services.phase_work_queue_metrics import intake_window_hours

        return max(1, int(intake_window_hours()))
    except Exception:
        return max(1, env_int("MONITOR_INTAKE_WINDOW_HOURS", 72))


def catchup_cache_ttl_seconds() -> int:
    return max(15, env_int("CATCHUP_LATENCY_CACHE_TTL_SECONDS", 90))


def catchup_min_samples_for_sla() -> int:
    return max(1, env_int("CATCHUP_SLA_MIN_SAMPLES", 20))


def invalidate_intake_catchup_latency_cache() -> None:
    global _cache, _cache_mono
    with _cache_lock:
        _cache = None
        _cache_mono = 0.0


def _round_opt(v: Any, nd: int = 2) -> float | None:
    if v is None:
        return None
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


def _scored_cte_sql(schema: str, domain_key_literal: str) -> str:
    """Per-schema SELECT producing scored cohort rows (no params — domain key embedded)."""
    from shared.article_processing_gates import sql_context_sync_article_ready
    from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_article_pass_null
    from shared.unified_intake_backlog import sql_actionable_unified_intake

    # Domain keys are registry-controlled (safe identifiers); escape quotes only.
    dk = domain_key_literal.replace("'", "''")
    ready = sql_context_sync_article_ready("a")
    uie_pending = sql_actionable_unified_intake(schema, "a")

    try:
        from domains.content_analysis.services.topic_clustering_service import (
            TopicClusteringService,
        )

        topic_signal = TopicClusteringService._pending_signal_sql(
            schema, signal_full_only=True
        )
        topic_first = TopicClusteringService._pending_first_pass_where("a")
    except Exception:
        topic_signal = ""
        topic_first = """
            a.content IS NOT NULL
            AND LENGTH(a.content) > 100
            AND (
              a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NULL
              OR TRIM(COALESCE(
                  a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', ''
              )) = ''
            )
        """

    story_pass = ""
    if phase_backlog_uses_pass_marker("storyline_discovery"):
        story_pass = f" AND ({sql_article_pass_null('storyline_discovery', 'a')}) "

    return f"""
        SELECT
            '{dk}'::text AS domain_key,
            '{schema}'::text AS schema_name,
            a.id,
            a.created_at,
            (
                (a.enrichment_status IS NULL OR a.enrichment_status IN ('pending', 'failed'))
                AND COALESCE(a.enrichment_attempts, 0) < 3
            ) AS enrich_pending,
            ({uie_pending}) AS uie_pending,
            (
                atc.context_id IS NULL
                AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                AND ({ready})
            ) AS context_pending,
            (
                ({topic_first})
                {topic_signal}
            ) AS topic_pending,
            (
                NOT EXISTS (
                    SELECT 1 FROM {schema}.storyline_articles sa
                    WHERE sa.article_id = a.id
                )
                {story_pass}
            ) AS storyline_pending,
            EXTRACT(EPOCH FROM (NOW() - a.created_at)) / 3600.0 AS age_hours,
            (
                SELECT MAX(v)
                FROM (VALUES
                    (
                        CASE
                            WHEN a.enrichment_status IN ('enriched', 'failed', 'inaccessible')
                              OR COALESCE(a.enrichment_attempts, 0) >= 3
                            THEN a.updated_at
                            ELSE NULL
                        END
                    ),
                    (
                        (a.metadata #>> '{{pipeline,unified_intake_extraction,last_pass_at}}')
                            ::timestamptz
                    ),
                    (atc.created_at)
                ) AS t(v)
            ) AS preprocess_caught_up_at,
            (
                SELECT MAX(v)
                FROM (VALUES
                    (
                        CASE
                            WHEN a.enrichment_status IN ('enriched', 'failed', 'inaccessible')
                              OR COALESCE(a.enrichment_attempts, 0) >= 3
                            THEN a.updated_at
                            ELSE NULL
                        END
                    ),
                    (
                        (a.metadata #>> '{{pipeline,unified_intake_extraction,last_pass_at}}')
                            ::timestamptz
                    ),
                    (atc.created_at),
                    (
                        (a.metadata #>> '{{pipeline,topic_clustering,last_pass_at}}')
                            ::timestamptz
                    ),
                    (
                        (
                            SELECT MIN(sa.added_at)
                            FROM {schema}.storyline_articles sa
                            WHERE sa.article_id = a.id
                        )
                    )
                ) AS t(v)
            ) AS caught_up_at
        FROM {schema}.articles a
        LEFT JOIN intelligence.article_to_context atc
          ON atc.domain_key = '{dk}' AND atc.article_id = a.id
        WHERE a.created_at >= NOW() - (%s::text || ' hours')::interval
          AND a.url IS NOT NULL AND a.url != ''
          AND COALESCE(a.enrichment_status, '') NOT IN ('removed', 'pull_deferred')
    """


def compute_intake_catchup_latency(
    *,
    window_hours: int | None = None,
    sla_hours: float | None = None,
    preprocess_sla: float | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Aggregate catchup latency across pipeline-active domains."""
    global _cache, _cache_mono

    win = catchup_window_hours(window_hours)
    sla = catchup_sla_hours(sla_hours)
    pre_sla = preprocess_sla_hours(preprocess_sla)
    cache_key = f"{win}:{sla}:{pre_sla}"

    if use_cache:
        with _cache_lock:
            if (
                _cache is not None
                and _cache.get("_cache_key") == cache_key
                and (time.monotonic() - _cache_mono) < catchup_cache_ttl_seconds()
            ):
                out = dict(_cache)
                out.pop("_cache_key", None)
                return out

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import pipeline_url_schema_pairs

    pairs = list(pipeline_url_schema_pairs())
    empty_preprocess = {
        "sla_hours": pre_sla,
        "stages": [
            "content_enrichment",
            "unified_intake_extraction",
            "context_sync",
        ],
        "cohort_n": 0,
        "sample_n_completed": 0,
        "inflight_n": 0,
        "p50_hours": None,
        "p95_hours": None,
        "max_inflight_age_hours": None,
        "over_sla_n": 0,
        "ok_under_sla": False,
        "min_samples_for_sla": catchup_min_samples_for_sla(),
    }
    if not pairs:
        empty = {
            "window_hours": win,
            "sla_hours": sla,
            "stages": [
                "content_enrichment",
                "unified_intake_extraction",
                "context_sync",
                "topic_clustering",
                "storyline_discovery",
            ],
            "cohort_n": 0,
            "sample_n_completed": 0,
            "inflight_n": 0,
            "p50_hours": None,
            "p95_hours": None,
            "max_inflight_age_hours": None,
            "p95_inflight_age_hours": None,
            "over_sla_n": 0,
            "ok_under_sla": False,
            "min_samples_for_sla": catchup_min_samples_for_sla(),
            "per_domain": [],
            "preprocess": empty_preprocess,
            "computed_at_utc": datetime.now(timezone.utc).isoformat(),
            "note": (
                "Full-process = enrich + UIE + context_sync + topic_clustering + storyline link. "
                f"Preprocess band SLA = {pre_sla}h (enrich + UIE + context_sync). "
                "Assembly/EPB/dossier excluded."
            ),
        }
        return empty

    union_parts = [_scored_cte_sql(schema, dk) for dk, schema in pairs]
    # Each part has one %s for window_hours
    union_sql = " UNION ALL ".join(f"({p})" for p in union_parts)
    window_params = tuple(int(win) for _ in pairs)

    sql = f"""
        WITH scored AS (
            SELECT
                *,
                (
                    enrich_pending OR uie_pending OR context_pending
                    OR topic_pending OR storyline_pending
                ) AS any_pending,
                (
                    enrich_pending OR uie_pending OR context_pending
                ) AS preprocess_pending,
                CASE
                    WHEN caught_up_at IS NOT NULL AND caught_up_at >= created_at
                    THEN EXTRACT(EPOCH FROM (caught_up_at - created_at)) / 3600.0
                    ELSE NULL
                END AS catchup_hours,
                CASE
                    WHEN preprocess_caught_up_at IS NOT NULL
                     AND preprocess_caught_up_at >= created_at
                    THEN EXTRACT(EPOCH FROM (preprocess_caught_up_at - created_at)) / 3600.0
                    ELSE NULL
                END AS preprocess_hours
            FROM (
                {union_sql}
            ) raw
        )
        SELECT
            domain_key,
            schema_name,
            GROUPING(domain_key) AS is_global,
            COUNT(*)::bigint,
            COUNT(*) FILTER (WHERE any_pending)::bigint,
            COUNT(*) FILTER (WHERE NOT any_pending)::bigint,
            COALESCE(MAX(age_hours) FILTER (WHERE any_pending), 0)::float,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY age_hours)
                FILTER (WHERE any_pending),
            percentile_cont(0.50) WITHIN GROUP (ORDER BY catchup_hours)
                FILTER (WHERE NOT any_pending AND catchup_hours IS NOT NULL),
            percentile_cont(0.95) WITHIN GROUP (ORDER BY catchup_hours)
                FILTER (WHERE NOT any_pending AND catchup_hours IS NOT NULL),
            COUNT(*) FILTER (
                WHERE NOT any_pending
                  AND catchup_hours IS NOT NULL
                  AND catchup_hours > %s
            )::bigint,
            COUNT(*) FILTER (WHERE preprocess_pending)::bigint,
            COUNT(*) FILTER (WHERE NOT preprocess_pending)::bigint,
            COALESCE(MAX(age_hours) FILTER (WHERE preprocess_pending), 0)::float,
            percentile_cont(0.50) WITHIN GROUP (ORDER BY preprocess_hours)
                FILTER (WHERE NOT preprocess_pending AND preprocess_hours IS NOT NULL),
            percentile_cont(0.95) WITHIN GROUP (ORDER BY preprocess_hours)
                FILTER (WHERE NOT preprocess_pending AND preprocess_hours IS NOT NULL),
            COUNT(*) FILTER (
                WHERE NOT preprocess_pending
                  AND preprocess_hours IS NOT NULL
                  AND preprocess_hours > %s
            )::bigint
        FROM scored
        GROUP BY GROUPING SETS ((domain_key, schema_name), ())
        ORDER BY is_global DESC, domain_key NULLS LAST
    """

    errors: list[str] = []
    rows: list[tuple] = []

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SET LOCAL statement_timeout = '25s'")
            except Exception:
                pass
            try:
                cur.execute(sql, window_params + (float(sla), float(pre_sla)))
                rows = cur.fetchall()
            except Exception as e:
                errors.append(f"aggregate: {e}")
                logger.warning("intake_catchup_latency aggregate: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass

    min_n = catchup_min_samples_for_sla()
    per_domain: list[dict[str, Any]] = []
    cohort_n = inflight_n = completed_n = over_sla_n = 0
    max_inflight = p95_inflight = p50 = p95 = None
    pre_inflight = pre_completed = pre_over = 0
    pre_max_inf = pre_p50 = pre_p95 = None

    for r in rows:
        (
            dk,
            schema,
            is_global,
            d_cohort,
            d_inflight,
            d_completed,
            d_max_inf,
            d_p95_inf,
            d_p50,
            d_p95,
            d_over,
            d_pre_inflight,
            d_pre_completed,
            d_pre_max_inf,
            d_pre_p50,
            d_pre_p95,
            d_pre_over,
        ) = r
        d_completed_i = int(d_completed or 0)
        d_cohort_i = int(d_cohort or 0)
        d_inflight_i = int(d_inflight or 0)
        d_over_i = int(d_over or 0)
        d_pre_completed_i = int(d_pre_completed or 0)
        d_pre_inflight_i = int(d_pre_inflight or 0)
        d_pre_over_i = int(d_pre_over or 0)
        if int(is_global or 0) == 1:
            cohort_n = d_cohort_i
            inflight_n = d_inflight_i
            completed_n = d_completed_i
            over_sla_n = d_over_i
            max_inflight = d_max_inf
            p95_inflight = d_p95_inf
            p50 = d_p50
            p95 = d_p95
            pre_inflight = d_pre_inflight_i
            pre_completed = d_pre_completed_i
            pre_over = d_pre_over_i
            pre_max_inf = d_pre_max_inf
            pre_p50 = d_pre_p50
            pre_p95 = d_pre_p95
            continue
        d_ok = (
            d_p95 is not None
            and d_completed_i >= min_n
            and float(d_p95) <= sla
        )
        d_pre_ok = (
            d_pre_p95 is not None
            and d_pre_completed_i >= min_n
            and float(d_pre_p95) <= pre_sla
        )
        per_domain.append(
            {
                "domain_key": dk,
                "schema": schema,
                "cohort_n": d_cohort_i,
                "completed_n": d_completed_i,
                "inflight_n": d_inflight_i,
                "p50_hours": _round_opt(d_p50),
                "p95_hours": _round_opt(d_p95),
                "max_inflight_age_hours": _round_opt(d_max_inf),
                "p95_inflight_age_hours": _round_opt(d_p95_inf),
                "over_sla_n": d_over_i,
                "ok_under_sla": d_ok,
                "preprocess": {
                    "completed_n": d_pre_completed_i,
                    "inflight_n": d_pre_inflight_i,
                    "p50_hours": _round_opt(d_pre_p50),
                    "p95_hours": _round_opt(d_pre_p95),
                    "max_inflight_age_hours": _round_opt(d_pre_max_inf),
                    "over_sla_n": d_pre_over_i,
                    "ok_under_sla": d_pre_ok,
                },
            }
        )

    ok = p95 is not None and completed_n >= min_n and float(p95) <= sla
    pre_ok = pre_p95 is not None and pre_completed >= min_n and float(pre_p95) <= pre_sla

    payload: dict[str, Any] = {
        "window_hours": win,
        "sla_hours": sla,
        "stages": [
            "content_enrichment",
            "unified_intake_extraction",
            "context_sync",
            "topic_clustering",
            "storyline_discovery",
        ],
        "note": (
            "Full-process = enrich + UIE + context_sync + topic_clustering + storyline link. "
            f"Preprocess band SLA = {pre_sla}h (enrich + UIE + context_sync). "
            "Assembly/EPB/dossier excluded."
        ),
        "cohort_n": int(cohort_n or 0),
        "sample_n_completed": completed_n,
        "inflight_n": int(inflight_n or 0),
        "p50_hours": _round_opt(p50),
        "p95_hours": _round_opt(p95),
        "max_inflight_age_hours": _round_opt(max_inflight),
        "p95_inflight_age_hours": _round_opt(p95_inflight),
        "over_sla_n": int(over_sla_n or 0),
        "ok_under_sla": ok,
        "min_samples_for_sla": min_n,
        "per_domain": per_domain,
        "preprocess": {
            "sla_hours": pre_sla,
            "stages": [
                "content_enrichment",
                "unified_intake_extraction",
                "context_sync",
            ],
            "cohort_n": int(cohort_n or 0),
            "sample_n_completed": pre_completed,
            "inflight_n": pre_inflight,
            "p50_hours": _round_opt(pre_p50),
            "p95_hours": _round_opt(pre_p95),
            "max_inflight_age_hours": _round_opt(pre_max_inf),
            "over_sla_n": pre_over,
            "ok_under_sla": pre_ok,
            "min_samples_for_sla": min_n,
        },
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if errors:
        payload["errors"] = errors[:10]

    if use_cache:
        with _cache_lock:
            cached = dict(payload)
            cached["_cache_key"] = cache_key
            _cache = cached
            _cache_mono = time.monotonic()

    return payload



def record_intake_catchup_latency_sample(snapshot: dict[str, Any] | None = None) -> None:
    """Append a thin sample to automation_state (keep ~72 points). Skip during bulk catch-up."""
    if env_str("BULK_CATCHUP_ACTIVE", "").lower() in ("1", "true", "yes"):
        return
    try:
        snap = snapshot or compute_intake_catchup_latency(use_cache=True)
        point = {
            "ts": snap.get("computed_at_utc")
            or datetime.now(timezone.utc).isoformat(),
            "p95": snap.get("p95_hours"),
            "p50": snap.get("p50_hours"),
            "max_inflight": snap.get("max_inflight_age_hours"),
            "inflight_n": snap.get("inflight_n"),
            "over_sla": snap.get("over_sla_n"),
            "ok": snap.get("ok_under_sla"),
            "sla_hours": snap.get("sla_hours"),
            "preprocess_p95": (snap.get("preprocess") or {}).get("p95_hours"),
            "preprocess_ok": (snap.get("preprocess") or {}).get("ok_under_sla"),
            "preprocess_sla_hours": (snap.get("preprocess") or {}).get("sla_hours"),
        }
        from shared.database.connection import get_db_connection_context

        keep = max(24, env_int("CATCHUP_LATENCY_SAMPLE_KEEP", 72))
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (_STATE_KEY,),
                )
                row = cur.fetchone()
                hist: list[dict[str, Any]] = []
                if row and row[0]:
                    raw = row[0]
                    if isinstance(raw, list):
                        hist = list(raw)
                    elif isinstance(raw, str):
                        hist = json.loads(raw)
                    elif isinstance(raw, dict):
                        hist = raw.get("samples") or []
                hour_key = str(point["ts"])[:13]
                hist = [h for h in hist if str(h.get("ts", ""))[:13] != hour_key]
                hist.append(point)
                hist = hist[-keep:]
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_STATE_KEY, json.dumps(hist)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("record_intake_catchup_latency_sample: %s", e)
