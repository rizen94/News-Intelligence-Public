"""
Backlog metrics — pending work counts per automation phase for orchestrator priority.
Counts are defined to match each phase’s real eligibility (what automation would select),
not coarse table totals, so Monitor ``pending_records`` reflects actionable backlog.

**topic_clustering (default):** ``pending`` = articles with no ``metadata.pipeline.topic_clustering.last_pass_at``
that have sufficient body text — i.e. never completed a successful clustering pass (including
``no_topics_extracted`` outcomes). Legacy “churn” counting (low average confidence after assignments)
is available via ``TOPIC_CLUSTERING_BACKLOG_USE_PASS_MARKER=false``.

**Other phases:** ``PIPELINE_BACKLOG_USE_PASS_MARKERS`` (default true) and per-phase
``<PHASE>_BACKLOG_USE_PASS_MARKER`` gate the same ``metadata.pipeline.<phase>.last_pass_at`` pattern for
entity_extraction, metadata_enrichment, storyline_discovery, event_extraction, sentiment_analysis,
claim_extraction, and event_tracking. ``entity_profile_sync`` uses ``old_entity_to_new`` as the completion
signal (no separate pass field).

Used by the automation manager to: skip empty cycles, run backlog mode (shorter interval),
and queue tasks by amount of work (most first). When workload-driven scheduling is on,
phases listed here are eligible every tick (subject to cooldown) when they have work;
phases not listed still use interval-based scheduling. Adding more phases to
_get_raw_pending_counts and BATCH_SIZE_PER_TASK makes more of the pipeline workload-driven.
"""

import logging
import os
import threading
import time
from typing import Dict, Optional

from shared.article_processing_gates import (
    sql_context_sync_article_ready,
    sql_ml_ready_and_content_bounds,
)
from shared.domain_registry import get_pipeline_schema_names_active, pipeline_url_schema_pairs
from shared.pipeline_pass_marker import (
    phase_backlog_uses_pass_marker,
    sql_article_pass_null,
    sql_context_pass_null,
)
from shared.pipeline_article_selection import sql_order_created_at
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

def _backlog_cache_ttl_seconds() -> int:
    """Cache TTL for pending/backlog counts; override via BACKLOG_CACHE_TTL_SECONDS."""
    raw = env_str("BACKLOG_CACHE_TTL_SECONDS", "90").strip()
    try:
        return max(15, int(raw))
    except ValueError:
        return 90


# Cache TTL seconds; scheduler runs every 5s, default refresh every 90s
BACKLOG_CACHE_TTL = _backlog_cache_ttl_seconds()
_backlog_cache: Dict[str, int] = {}
_backlog_cache_time: float = 0

# How many items each task processes per run.  Pending counts at or below this
# are normal throughput, not a backlog.  Anything above triggers backlog mode.
BATCH_SIZE_PER_TASK: Dict[str, int] = {
    "content_enrichment": 60,
    "context_sync": 100,
    "event_tracking": 300,
    "claim_extraction": 50,
    "entity_profile_build": 25,  # v8
    "investigation_report_refresh": 8,
    "document_processing": 10,
    "content_refinement_queue": 4,
    # Unified nightly phase: enrichment + context_sync + refinement queue
    "nightly_enrichment_context": 0,
    # Per-run throughput (automation_manager batch limits × domain count where applicable)
    "metadata_enrichment": 15,  # order-of-magnitude per domain batch
    "ml_processing": 150,  # 50 × 3 schemas
    "entity_extraction": 60,  # 20 × 3
    "unified_intake_extraction": 90,
    "sentiment_analysis": 300,  # 100 × 3
    "quality_scoring": 150,  # 50 × 3
    "storyline_processing": 24,  # ~8 storylines worth of summary work per full pass
    "topic_clustering": 60,  # ~20 × 3 standard domains (approximates automation)
    "timeline_generation": 36,  # 12 × 3
    "storyline_discovery": 50,  # unlinked-in-newest-N proxy (see _count_storyline_discovery_pending)
    "storyline_assembly": 60,  # ~automation_batch_per_assembly (20) × active domains
    "proactive_detection": 1000,  # proactive candidate pool cap per domain
    "storyline_automation": 5,  # automation_manager LIMIT storylines per domain per tick
    "rag_enhancement": 9,  # few storylines enhanced per tick per domain
    "event_extraction": 90,  # 30 × 3
    "claims_to_facts": 10_000,  # overridden by get_claims_to_facts_batch_limit() when available
    "legislative_references": 8,  # articles scanned per domain per run (Congress.gov rate limits)
    "entity_profile_sync": 40,  # canonical rows mapped per domain batch (approx)
    "entity_enrichment": 20,  # run_enrichment_batch limit
    "entity_dossier_compile": 20,  # _run_scheduled_dossier_compiles max per run
    "story_enhancement": 50,  # fact_change_log + story_update_queue proxy per cycle
    "storyline_synthesis": 16,  # ~4 storylines × active domains per _execute_storyline_synthesis tick
    "graph_connection_distillation": 12,  # GRAPH_CONNECTION_DISTILLATION_BATCH proposals per run
    "pending_db_flush": 200,  # rough lines replayed per successful flush (order-of-magnitude)
}

# Phases where backlog = pending (orchestrator / not row-batched in this model).
NO_BACKLOG_BATCH_SUBTRACT_PHASES = frozenset({"nightly_enrichment_context"})

LEGACY_INTAKE_BACKLOG_KEYS = frozenset(
    {
        "metadata_enrichment",
        "ml_processing",
        "entity_extraction",
        "sentiment_analysis",
        "quality_scoring",
        "event_extraction",
    }
)


def _should_skip_backlog_count(phase: str) -> bool:
    """Skip expensive scans for archived phases under v10.1 defaults."""
    if phase in LEGACY_INTAKE_BACKLOG_KEYS:
        from config.settings import legacy_intake_extraction_enabled

        if not legacy_intake_extraction_enabled():
            return True
    try:
        from shared.assembly_phase_order import post_spine_scheduling_suppressed

        if post_spine_scheduling_suppressed(phase):
            return True
    except Exception:
        pass
    return False


def _default_batch_for_unknown_phase() -> int:
    """When a phase has pending counts but no BATCH_SIZE_PER_TASK entry, subtract at least this many rows per run so row-excess backlog != pending (scheduler); Monitor shows ceil(pending/batch) as batches_to_drain."""
    try:
        v = int(env_str("BACKLOG_METRICS_DEFAULT_BATCH_SIZE", "1"))
    except (TypeError, ValueError):
        v = 1
    return max(1, min(v, 50_000))


# Keys assigned in _get_raw_pending_counts (keep in sync with that function).
# Invariant: SKIP_WHEN_EMPTY must be a subset — otherwise AutomationManager never schedules those phases
# (pending defaults to 0). Validated at import below after SKIP_WHEN_EMPTY is defined.
RAW_PENDING_COUNT_KEYS = frozenset(
    {
        "content_enrichment",
        "context_sync",
        "event_tracking",
        "claim_extraction",
        "entity_profile_build",
        "investigation_report_refresh",
        "document_processing",
        "pending_db_flush",
        "content_refinement_queue",
        "metadata_enrichment",
        "ml_processing",
        "entity_extraction",
        "unified_intake_extraction",
        "sentiment_analysis",
        "quality_scoring",
        "storyline_processing",
        "topic_clustering",
        "timeline_generation",
        "storyline_discovery",
        "proactive_detection",
        "storyline_assembly",
        "rag_enhancement",
        "event_extraction",
        "storyline_automation",
        "claims_to_facts",
        "legislative_references",
        "entity_profile_sync",
        "entity_enrichment",
        "entity_dossier_compile",
        "story_enhancement",
        "storyline_synthesis",
        "graph_connection_distillation",
        "nightly_enrichment_context",
    }
)


def _get_raw_pending_counts() -> Dict[str, int]:
    """Query all raw pending-work counts (not cached — called by the cached wrapper)."""
    raw: Dict[str, int] = {}

    def _set(phase: str, value: int) -> None:
        raw[phase] = 0 if _should_skip_backlog_count(phase) else value

    try:
        _set("content_enrichment", _count_content_enrichment_backlog())
        _set("context_sync", _count_context_sync_backlog())
        _set("event_tracking", _count_event_tracking_backlog())
        _set("claim_extraction", _count_claim_extraction_backlog())
        _set("entity_profile_build", _count_entity_profile_build_backlog())
        _set("investigation_report_refresh", _count_investigation_report_backlog())
        _set("document_processing", _count_document_processing_backlog())
        try:
            from shared.database.pending_db_writes import pending_line_count

            raw["pending_db_flush"] = pending_line_count()
        except Exception:
            raw["pending_db_flush"] = 0
        _set("content_refinement_queue", _count_content_refinement_queue_pending())
        _set("metadata_enrichment", _count_metadata_enrichment_pending())
        _set("ml_processing", _count_ml_processing_pending())
        _set("entity_extraction", _count_entity_extraction_pending())
        _set("unified_intake_extraction", _count_unified_intake_extraction_pending())
        _set("sentiment_analysis", _count_sentiment_analysis_pending())
        _set("quality_scoring", _count_quality_scoring_pending())
        _set("storyline_processing", _count_storyline_processing_pending())
        _set("topic_clustering", _count_topic_clustering_pending())
        _set("timeline_generation", _count_timeline_generation_pending())
        _set("storyline_discovery", _count_storyline_discovery_pending())
        _set("rag_enhancement", _count_rag_enhancement_pending())
        _set("event_extraction", _count_event_extraction_pending())
        _set("proactive_detection", _count_proactive_detection_pending())
        _set("storyline_assembly", _count_storyline_assembly_pending())
        _set("storyline_automation", _count_storyline_automation_pending())
        _set("claims_to_facts", _count_claims_to_facts_pending())
        _set("legislative_references", _count_legislative_references_backlog())
        _set("entity_profile_sync", _count_entity_profile_sync_pending())
        _set("entity_enrichment", _count_entity_enrichment_pending())
        _set("entity_dossier_compile", _count_entity_dossier_compile_pending())
        _set("story_enhancement", _count_story_enhancement_pending())
        _set("storyline_synthesis", _count_storyline_synthesis_pending())
        _set("graph_connection_distillation", _count_graph_connection_distillation_pending())
        nightly_base = (
            int(raw.get("content_enrichment", 0) or 0)
            + int(raw.get("context_sync", 0) or 0)
            + int(raw.get("content_refinement_queue", 0) or 0)
        )
        try:
            from services.nightly_ingest_window_service import nightly_sequential_phases
            from services.nightly_phase_idle import sequential_metric_backlog

            seq_work = sequential_metric_backlog(nightly_sequential_phases(), raw)
        except Exception:
            seq_work = False
        # Nightly drain must schedule when sequential phases (e.g. topic_clustering) have backlog
        # even if enrichment/context/refinement queues are empty.
        raw["nightly_enrichment_context"] = max(nightly_base, 1 if seq_work else 0)
    except Exception as e:
        logger.warning("backlog_metrics _get_raw_pending_counts: %s", e)
        return raw
    built = frozenset(raw.keys())
    if built != RAW_PENDING_COUNT_KEYS:
        raise RuntimeError(
            "backlog_metrics: _get_raw_pending_counts keys drifted from RAW_PENDING_COUNT_KEYS — "
            f"extra={sorted(built - RAW_PENDING_COUNT_KEYS)} "
            f"missing={sorted(RAW_PENDING_COUNT_KEYS - built)}"
        )
    from shared.pipeline_resource_policy import apply_intake_mode_pending_mask

    return apply_intake_mode_pending_mask(raw)


# Two cached dicts: raw pending (for SKIP_WHEN_EMPTY) and true backlog (for priority/interval)
_pending_cache: Dict[str, int] = {}
_pending_cache_time: float = 0
_refresh_cache_lock = threading.Lock()


def invalidate_backlog_metrics_cache() -> None:
    """Force the next get_all_pending_counts / get_all_backlog_counts to re-query the DB."""
    global _backlog_cache_time, _pending_cache_time, _backlog_cache, _pending_cache
    _backlog_cache_time = 0.0
    _pending_cache_time = 0.0
    _backlog_cache.clear()
    _pending_cache.clear()
    try:
        from shared.unified_intake_backlog import invalidate_unified_intake_backlog_stats_cache

        invalidate_unified_intake_backlog_stats_cache()
    except Exception:
        pass


def _per_run_batch_size(task: str) -> int:
    """Align backlog subtraction with actual automation batch sizes (env-tunable for claim phases)."""
    if task in NO_BACKLOG_BATCH_SUBTRACT_PHASES:
        return 0
    if task == "entity_extraction":
        try:
            n = int(env_str("ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN", "40"))
            n = max(5, min(120, n))
            doms = len(get_pipeline_schema_names_active()) or 1
            return n * doms
        except Exception:
            pass
    if task == "claim_extraction":
        try:
            from services.claim_extraction_service import get_claim_extraction_batch_limit

            return int(get_claim_extraction_batch_limit())
        except Exception:
            pass
    if task == "claims_to_facts":
        try:
            from services.claim_extraction_service import get_claims_to_facts_batch_limit

            return int(get_claims_to_facts_batch_limit())
        except Exception:
            pass
    if task == "topic_clustering":
        try:
            doms = len(get_pipeline_schema_names_active()) or 1
            return 20 * doms
        except Exception:
            pass
    if task == "storyline_automation":
        try:
            from shared.domain_registry import get_pipeline_active_domain_keys

            doms = len(get_pipeline_active_domain_keys()) or 1
            return 5 * doms
        except Exception:
            pass
    if task == "storyline_assembly":
        try:
            from shared.domain_registry import get_pipeline_active_domain_keys

            doms = len(get_pipeline_active_domain_keys()) or 1
            return 20 * doms
        except Exception:
            pass
    if task == "story_enhancement":
        try:
            import os

            fact = max(10, min(500, int(env_str("STORY_ENHANCEMENT_FACT_BATCH", "100"))))
            queue = max(1, min(50, int(env_str("STORY_ENHANCEMENT_QUEUE_BATCH", "10"))))
            enrich = max(1, min(50, int(env_str("STORY_ENHANCEMENT_ENRICH_LIMIT", "10"))))
            build = max(1, min(50, int(env_str("STORY_ENHANCEMENT_BUILD_LIMIT", "10"))))
            return fact + queue + enrich + build
        except Exception:
            return int(BATCH_SIZE_PER_TASK["story_enhancement"])
    if task == "unified_intake_extraction":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch
            from shared.pipeline_batch_drain import phase_batch_limit

            per_domain = phase_batch_limit("unified_intake_extraction", 40)
            adaptive_pd = get_persisted_adaptive_batch("unified_intake_extraction")
            if adaptive_pd is not None:
                per_domain = adaptive_pd
            doms = len(get_pipeline_schema_names_active()) or 1
            return max(1, per_domain * doms)
        except Exception:
            pass
    if task == "entity_profile_build":
        try:
            return max(1, min(150, int(env_str("ENTITY_PROFILE_BUILD_LIMIT", "25"))))
        except Exception:
            pass
    if task == "entity_dossier_compile":
        try:
            return max(1, min(100, int(env_str("ENTITY_DOSSIER_COMPILE_MAX", "20"))))
        except Exception:
            pass
    if task == "event_tracking":
        try:
            batch_max = max(25, min(300, int(env_str("EVENT_TRACKING_ASSEMBLY_BATCH_MAX", "300"))))
            return max(1, min(batch_max, int(env_str("EVENT_TRACKING_ASSEMBLY_BATCH_LIMIT", "25"))))
        except Exception:
            pass
    if task in BATCH_SIZE_PER_TASK:
        return int(BATCH_SIZE_PER_TASK[task])
    return _default_batch_for_unknown_phase()


def get_per_run_batch_size_for_phase(phase_name: str) -> int:
    """Rows/items assumed processed in one automation run of ``phase_name`` (for Monitor / processing_progress)."""
    return _per_run_batch_size(phase_name)


def _refresh_cache() -> None:
    """Refresh both pending and backlog caches (single-flight under lock)."""
    global _backlog_cache, _backlog_cache_time, _pending_cache, _pending_cache_time
    now = time.monotonic()
    if now - _backlog_cache_time <= BACKLOG_CACHE_TTL and _backlog_cache and _pending_cache:
        return

    with _refresh_cache_lock:
        now = time.monotonic()
        if now - _backlog_cache_time <= BACKLOG_CACHE_TTL and _backlog_cache and _pending_cache:
            return

        raw = _get_raw_pending_counts()
        _pending_cache = raw.copy()
        _pending_cache_time = now

        out: Dict[str, int] = {}
        for task, pending in raw.items():
            batch = _per_run_batch_size(task)
            out[task] = max(pending - batch, 0)
        _backlog_cache = out
        _backlog_cache_time = now


def get_all_backlog_counts() -> Dict[str, int]:
    """
    Return current **backlog** count per phase — pending work *exceeding* one batch.
    Cached for BACKLOG_CACHE_TTL.  Values > 0 mean genuine backlog (more work than
    one run can handle); 0 means the task is keeping up or idle.
    Used for priority boosting and interval shortening.
    """
    _refresh_cache()
    return _backlog_cache.copy()


def get_all_pending_counts() -> Dict[str, int]:
    """
    Return raw pending-work counts per phase (items waiting, regardless of batch size).
    Used by SKIP_WHEN_EMPTY — a task with *any* pending work (even 1 item) should still run.
    """
    _refresh_cache()
    return _pending_cache.copy()


def get_backlog_count(task_name: str) -> Optional[int]:
    """Return backlog for one task; uses cache. Returns None if task has no backlog metric."""
    counts = get_all_backlog_counts()
    if task_name in counts:
        return counts[task_name]
    return None


def _get_conn():
    """
    Read-only COUNT queries for backlog / Monitor.

    Prefer the **worker** pool (same as automation). When that pool is saturated or times out,
    fall back to the **UI** pool so ``processing_progress`` (which already uses the UI pool for
    its main query block) can still show ``pending_records`` instead of silent all-zeros.
    """
    try:
        from shared.database.connection import get_db_connection

        return get_db_connection()
    except Exception:
        try:
            from shared.database.connection import get_ui_db_connection

            conn = get_ui_db_connection()
            logger.debug(
                "backlog_metrics: worker pool connection failed; using UI pool for pending counts"
            )
            return conn
        except Exception:
            return None


def _event_tracking_scan_window_params() -> tuple[int, int]:
    """Max age (days) and min content length — must match ``discover_events_from_contexts``."""
    try:
        from config.settings import event_tracking_max_age_days, event_tracking_min_content_len

        return int(event_tracking_max_age_days()), int(event_tracking_min_content_len())
    except Exception:
        d = int(env_str("EVENT_TRACKING_MAX_AGE_DAYS", "14") or 14)
        n = int(env_str("EVENT_TRACKING_MIN_CONTENT_LEN", "180") or 180)
        return max(1, min(d, 365)), max(1, min(n, 50_000))


def _claim_extraction_min_text_length() -> int:
    """Matches ``extract_claims_for_context`` (title+body strip length gate)."""
    try:
        n = int(env_str("CLAIM_EXTRACTION_MIN_TEXT_LEN", "80"))
    except (TypeError, ValueError):
        n = 80
    return max(40, min(n, 2000))


def _count_content_enrichment_backlog() -> int:
    """Articles pending enrichment; uses queue COUNT when SPINE_USE_WORK_QUEUES."""
    try:
        from services.spine_work_queue_service import count_all_pending, spine_work_queues_enabled

        if spine_work_queues_enabled():
            q = count_all_pending("content_enrichment")
            if q > 0:
                return q
    except Exception:
        pass
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    """
                )
                total += cur.fetchone()[0] or 0
        return total
    except Exception as e:
        logger.debug("backlog content_enrichment count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_context_sync_backlog() -> int:
    """Articles not yet in article_to_context — matches ``sync_domain_articles_to_contexts`` (excludes removed)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ready = sql_context_sync_article_ready("a")
    try:
        for domain_key, schema in pipeline_url_schema_pairs():
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN intelligence.article_to_context atc
                      ON atc.domain_key = %s AND atc.article_id = a.id
                    WHERE atc.context_id IS NULL
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      AND ({ready})
                    """,
                    (domain_key,),
                )
                total += cur.fetchone()[0] or 0
        return total
    except Exception as e:
        logger.debug("backlog context_sync count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_event_tracking_backlog() -> int:
    """Contexts the ``event_tracking`` phase can select: same window, min length, and
    ``NOT EXISTS`` chronicle link predicate as ``discover_events_from_contexts`` (not
    ``COUNT(contexts) - COUNT(event_chronicles)``, which is not meaningful work remaining)."""
    max_age_days, min_len = _event_tracking_scan_window_params()
    conn = _get_conn()
    if not conn:
        return 0
    pass_sql = ""
    if phase_backlog_uses_pass_marker("event_tracking"):
        pass_sql = f" AND ({sql_context_pass_null('event_tracking', 'c')}) "
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.contexts c
                WHERE c.created_at >= NOW() - (%s * INTERVAL '1 day')
                  AND LENGTH(COALESCE(c.content, '')) >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM intelligence.event_chronicles ec,
                      LATERAL jsonb_array_elements(ec.developments) AS dev
                      WHERE (dev->>'context_id')::int = c.id
                  )
                  {pass_sql}
                """,
                (max_age_days, min_len),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.warning("backlog event_tracking count failed (showing 0): %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_claim_extraction_backlog() -> int:
    """Contexts with no extracted_claims and enough text for extraction (matches batch gate)."""
    conn = _get_conn()
    if not conn:
        return 0
    min_text = _claim_extraction_min_text_length()
    pass_sql = ""
    if phase_backlog_uses_pass_marker("claim_extraction"):
        pass_sql = f" AND ({sql_context_pass_null('claim_extraction', 'c')}) "
    gap_sql = ""
    try:
        from services.claim_extraction_service import claim_extraction_gap_fill_sql

        gap_sql = claim_extraction_gap_fill_sql()
    except Exception:
        pass
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '60s'")
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.contexts c
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.extracted_claims ec
                    WHERE ec.context_id = c.id
                )
                  AND (
                      LENGTH(COALESCE(c.content, '')) + LENGTH(COALESCE(c.title, ''))
                  ) >= %s
                  {pass_sql}
                  {gap_sql}
                """,
                (min_text,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.warning("backlog claim_extraction count failed (using pending probe): %s", e)
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '15s'")
                cur.execute(
                    f"""
                    SELECT 1 FROM intelligence.contexts c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM intelligence.extracted_claims ec
                        WHERE ec.context_id = c.id
                    )
                      AND (
                          LENGTH(COALESCE(c.content, '')) + LENGTH(COALESCE(c.title, ''))
                      ) >= %s
                      {pass_sql}
                    LIMIT 1
                    """,
                    (min_text,),
                )
                if cur.fetchone():
                    return max(_backlog_cache.get("claim_extraction", 1), 1)
        except Exception:
            pass
        return int(_backlog_cache.get("claim_extraction", 0) or 0)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_profile_build_backlog() -> int:
    """Profiles matching ``get_entity_profile_ids_to_build`` that also have at least one
    context mention (``build_profile_sections`` no-ops without mentions)."""
    from services.entity_profile_builder_service import (
        sql_entity_profile_upstream_cleared_exists,
        _entity_profile_upstream_gate_enabled,
    )
    from shared.entity_profile_eligibility import sql_entity_profile_needs_build
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    conn = _get_conn()
    if not conn:
        return 0
    domain_sql, domain_keys = pipeline_domain_any_sql("ep.domain_key")
    if not domain_keys:
        return 0
    upstream_sql = ""
    if _entity_profile_upstream_gate_enabled():
        upstream_sql = f" AND {sql_entity_profile_upstream_cleared_exists()} "
    needs_build = sql_entity_profile_needs_build("ep")
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '12s'")
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                WHERE {domain_sql}
                  AND {needs_build}
                  AND EXISTS (
                      SELECT 1 FROM intelligence.context_entity_mentions cem
                      WHERE cem.entity_profile_id = ep.id
                  )
                  {upstream_sql}
                """,
                (domain_keys,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog entity_profile_build count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_investigation_report_backlog() -> int:
    """Tracked events without an event_report (new reports needed)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.tracked_events te
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.event_reports er WHERE er.event_id = te.id
                )
                """
            )
            return cur.fetchone()[0] or 0
    except Exception as e:
        logger.debug("backlog investigation_report count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_content_refinement_queue_pending() -> int:
    """Rows in intelligence.content_refinement_queue waiting for workers (migration 181)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.content_refinement_queue
                WHERE status = 'pending'
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog content_refinement_queue count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_document_processing_backlog() -> int:
    """Documents with source_url but not yet extracted (PDF download + section/entity extraction)."""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.processed_documents
                WHERE source_url IS NOT NULL AND source_url != ''
                  AND (extracted_sections IS NULL OR extracted_sections = '[]'::jsonb)
                  AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
                """
            )
            return cur.fetchone()[0] or 0
    except Exception as e:
        logger.debug("backlog document_processing count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_metadata_enrichment_pending() -> int:
    """Articles pending metadata batch (matches run_metadata_enrichment_batch_for_domains)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    pass_sql = ""
    if phase_backlog_uses_pass_marker("metadata_enrichment"):
        pass_sql = f" AND ({sql_article_pass_null('metadata_enrichment', 'a')}) "
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE a.content IS NOT NULL AND LENGTH(a.content) > 50
                      AND (a.metadata IS NULL OR (a.metadata->>'enrichment_done') IS NULL)
                      {pass_sql}
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog metadata_enrichment count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_ml_processing_pending() -> int:
    """Articles not yet through ML background queue (ml_processed)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ml_ready = sql_ml_ready_and_content_bounds()
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE ml_processed = FALSE
                      AND ({ml_ready})
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog ml_processing count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_extraction_pending() -> int:
    """Articles eligible for entity extraction (matches automation_manager join filter)."""
    from shared.pipeline_resource_policy import intake_extraction_suppressed

    if intake_extraction_suppressed():
        return 0
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    pass_sql = ""
    if phase_backlog_uses_pass_marker("entity_extraction"):
        pass_sql = f" AND ({sql_article_pass_null('entity_extraction', 'a')}) "
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                    WHERE ae.id IS NULL
                      AND COALESCE((a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean, false) = false
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 100
                      AND (
                          LENGTH(a.content) >= 500
                          OR a.created_at < NOW() - INTERVAL '2 hours'
                          OR COALESCE(a.enrichment_status, '') IN (
                              'enriched', 'failed', 'inaccessible'
                          )
                      )
                      {pass_sql}
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog entity_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_unified_intake_extraction_pending() -> int:
    """Articles needing unified LLM (excludes legacy-complete marker backfill)."""
    try:
        from services.spine_work_queue_service import count_all_pending, spine_work_queues_enabled

        if spine_work_queues_enabled():
            q = count_all_pending("unified_intake_extraction")
            if q > 0:
                return q
    except Exception:
        pass
    from config.settings import unified_intake_extraction_enabled
    from shared.pipeline_resource_policy import intake_extraction_suppressed
    from shared.unified_intake_backlog import (
        get_unified_intake_backlog_stats,
        sql_actionable_unified_intake,
        unified_intake_legacy_aware_backlog_enabled,
    )

    if not intake_extraction_suppressed() or not unified_intake_extraction_enabled():
        return 0
    if unified_intake_legacy_aware_backlog_enabled():
        try:
            return int(get_unified_intake_backlog_stats().get("actionable_unified_intake", 0) or 0)
        except Exception as e:
            logger.debug("backlog unified_intake_extraction stats: %s", e)

    from shared.article_processing_gates import sql_ml_ready_and_content_bounds

    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    pass_sql = ""
    if phase_backlog_uses_pass_marker("unified_intake_extraction"):
        pass_sql = f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) "
    ml_ready = sql_ml_ready_and_content_bounds("a")
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                if unified_intake_legacy_aware_backlog_enabled():
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.articles a
                        WHERE {sql_actionable_unified_intake(schema, 'a')}
                        """
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.articles a
                        WHERE COALESCE(
                            (a.metadata #>> '{{pipeline_skip,unified_intake_extraction_skip}}')::boolean,
                            false
                        ) = false
                          AND a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND ({ml_ready})
                          AND (
                              LENGTH(a.content) >= 500
                              OR a.created_at < NOW() - INTERVAL '2 hours'
                              OR COALESCE(a.enrichment_status, '') IN (
                                  'enriched', 'failed', 'inaccessible'
                              )
                          )
                          {pass_sql}
                        """
                    )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog unified_intake_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_sentiment_analysis_pending() -> int:
    from shared.pipeline_resource_policy import intake_extraction_suppressed

    if intake_extraction_suppressed():
        return 0
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ml_ready = sql_ml_ready_and_content_bounds()
    pass_sql = ""
    if phase_backlog_uses_pass_marker("sentiment_analysis"):
        pass_sql = f" AND ({sql_article_pass_null('sentiment_analysis', 'a')}) "
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE a.sentiment_score IS NULL
                      AND COALESCE((a.metadata #>> '{{pipeline_skip,sentiment_analysis_skip}}')::boolean, false) = false
                      AND ({ml_ready})
                      {pass_sql}
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog sentiment_analysis count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_quality_scoring_pending() -> int:
    from shared.pipeline_resource_policy import intake_extraction_suppressed

    if intake_extraction_suppressed():
        return 0
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    ml_ready = sql_ml_ready_and_content_bounds()
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE quality_score IS NULL
                      AND COALESCE((metadata #>> '{{pipeline_skip,quality_scoring_skip}}')::boolean, false) = false
                      AND ({ml_ready})
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog quality_scoring count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_processing_pending() -> int:
    """Active storylines with articles but short/absent analysis summary (matches storyline_processing)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    WHERE s.status = 'active'
                      AND EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.storyline_id = s.id
                      )
                      AND LENGTH(
                          TRIM(COALESCE(s.analysis_summary, '') || COALESCE(s.master_summary, ''))
                      ) < 100
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_processing count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_topic_clustering_pending() -> int:
    """Articles awaiting a first successful topic_clustering pass (or legacy graduation backlog)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        from config.settings import (
            topic_clustering_backlog_uses_pass_marker,
            topic_clustering_graduation_confidence,
        )

        use_pass = topic_clustering_backlog_uses_pass_marker()
        conf = float(topic_clustering_graduation_confidence())
    except Exception:
        use_pass = True
        conf = 0.88
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                if use_pass:
                    cur.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM {schema}.articles a
                        WHERE a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at') IS NULL
                        """
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM (
                            SELECT a.id
                            FROM {schema}.articles a
                            LEFT JOIN {schema}.article_topic_assignments ata
                              ON a.id = ata.article_id
                            WHERE a.content IS NOT NULL
                              AND LENGTH(a.content) > 100
                            GROUP BY a.id
                            HAVING COUNT(ata.id) = 0
                                OR COALESCE(AVG(ata.confidence_score), 0) < %s
                        ) t
                        """,
                        (conf,),
                    )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog topic_clustering count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_timeline_generation_pending() -> int:
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines s
                    WHERE s.status = 'active'
                      AND EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.storyline_id = s.id
                      )
                      AND (
                          s.timeline_summary IS NULL
                          OR LENGTH(COALESCE(s.timeline_summary, '')) < 100
                      )
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog timeline_generation count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_discovery_pending() -> int:
    """Newest-N articles per schema (same cap as discovery fetch) that are not on any storyline — linkage backlog."""
    try:
        from services.ai_storyline_discovery import STORYLINE_DISCOVERY_ARTICLE_LIMIT as cap
    except Exception:
        cap = 10000
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    pass_sql = ""
    if phase_backlog_uses_pass_marker("storyline_discovery"):
        pass_sql = f" AND ({sql_article_pass_null('storyline_discovery', 'a')}) "
    _ord = sql_order_created_at()
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    WITH cand AS (
                        SELECT id FROM {schema}.articles
                        ORDER BY created_at {_ord}
                        LIMIT %s
                    )
                    SELECT COUNT(*) FROM {schema}.articles a
                    INNER JOIN cand ON cand.id = a.id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.storyline_articles sa
                        WHERE sa.article_id = a.id
                    )
                    {pass_sql}
                    """,
                    (cap,),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_discovery count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_assembly_pending() -> int:
    """Unlinked recent articles across pipeline domains — assembly ties detection + discovery + automation."""
    try:
        from services.storyline_assembly_service import count_unlinked_articles
        from shared.domain_registry import get_pipeline_active_domain_keys

        return sum(count_unlinked_articles(dk) for dk in get_pipeline_active_domain_keys())
    except Exception as e:
        logger.debug("backlog storyline_assembly count: %s", e)
        return 0


def _count_proactive_detection_pending() -> int:
    """Recent articles (72h) with no storyline_articles row — matches proactive_detection candidate query."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN {schema}.storyline_articles sa ON sa.article_id = a.id
                    WHERE COALESCE(a.published_at, a.created_at) >= NOW() - INTERVAL '72 hours'
                      AND sa.article_id IS NULL
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog proactive_detection count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_automation_pending() -> int:
    """Storylines with ``automation_enabled`` (recurring pool the phase rotates through, not one-shot work)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.storylines
                    WHERE automation_enabled = true
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_automation count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_storyline_review_queue_pending() -> int:
    """Pending rows in public.storyline_article_suggestions (operator curation pressure)."""
    by_domain = get_storyline_review_queue_pending_by_domain()
    return sum(by_domain.values())


def get_storyline_review_queue_pending_by_domain() -> Dict[str, int]:
    """Pending suggestion rows grouped by domain_key (operator curation pressure)."""
    conn = _get_conn()
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT domain_key, COUNT(*) FROM public.storyline_article_suggestions
                WHERE status = 'pending'
                GROUP BY domain_key
                """
            )
            return {str(row[0]): int(row[1] or 0) for row in cur.fetchall() if row[0]}
    except Exception as e:
        logger.debug("backlog storyline_review_queue count: %s", e)
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_rag_enhancement_pending() -> int:
    """Storylines due for RAG (first pass or new articles since last enhance)."""
    try:
        from shared.rag_enhancement_eligibility import count_rag_enhancement_pending

        return int(count_rag_enhancement_pending() or 0)
    except Exception as e:
        logger.debug("backlog rag_enhancement count: %s", e)
        return 0


def _count_claims_to_facts_pending() -> int:
    """Unpromoted high-confidence claims for Monitor (see ``build_claims_to_facts_backlog_where_suffix``).

    Default ``CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE=promotable_hint``: excludes generic subjects and requires
    an exact-resolution signal (context mention, profile canonical/display, or article_entities name),
    so the number tracks work closer to what can promote without fuzzy/trgm. Use ``batch_candidate``
    for the larger SQL-candidate pool (pre-resolution, still excludes generic subjects and uses merged-id
    guard when ``CLAIMS_TO_FACTS_CHECK_MERGED_SOURCE_IDS`` is on).
    """
    try:
        from services.claim_extraction_service import (
            build_claims_to_facts_backlog_where_suffix,
            get_claims_to_facts_min_confidence,
        )

        min_conf = float(get_claims_to_facts_min_confidence())
        suffix = build_claims_to_facts_backlog_where_suffix()
    except Exception:
        min_conf = 0.75
        suffix = """
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.versioned_facts vf
    WHERE vf.metadata->>'source_claim_id' = ec.id::text
  )
"""
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= %s
                """
                + suffix,
                (min_conf,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog claims_to_facts count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_profile_sync_pending() -> int:
    """entity_canonical rows without intelligence.old_entity_to_new mapping (per domain).

    Completion is structural (mapping row exists); there is no separate pass marker."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for domain_key, schema in pipeline_url_schema_pairs():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.entity_canonical ec
                    WHERE NOT EXISTS (
                        SELECT 1 FROM intelligence.old_entity_to_new o
                        WHERE o.domain_key = %s AND o.old_entity_id = ec.id
                    )
                    """,
                    (domain_key,),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog entity_profile_sync count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_enrichment_pending() -> int:
    """1 if get_entity_profile_ids_to_enrich finds work, else 0 (cheap presence check)."""
    try:
        from services.entity_enrichment_service import get_entity_profile_ids_to_enrich

        ids = get_entity_profile_ids_to_enrich(limit=1)
        return 1 if ids else 0
    except Exception as e:
        logger.debug("backlog entity_enrichment count: %s", e)
        return 0


def _count_event_extraction_pending() -> int:
    """Articles eligible for v5 event extraction (timeline_processed)."""
    from shared.pipeline_resource_policy import intake_extraction_suppressed

    if intake_extraction_suppressed():
        return 0
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    pass_sql = ""
    if phase_backlog_uses_pass_marker("event_extraction"):
        pass_sql = f" AND ({sql_article_pass_null('event_extraction', 'a')}) "
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE a.timeline_processed = false
                      AND COALESCE((a.metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean, false) = false
                      AND a.content IS NOT NULL
                      AND LENGTH(a.content) > 100
                      AND (
                          a.processing_status = 'completed'
                          OR a.enrichment_status IN ('completed', 'enriched')
                      )
                      {pass_sql}
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog event_extraction count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_entity_dossier_compile_pending() -> int:
    """Profiles missing dossier or with upstream changes since compile (matches dossier_compiler)."""
    from shared.entity_dossier_eligibility import sql_entity_dossier_needs_compile
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    conn = _get_conn()
    if not conn:
        return 0
    domain_sql, domain_keys = pipeline_domain_any_sql("ep.domain_key")
    if not domain_keys:
        return 0
    needs_compile = sql_entity_dossier_needs_compile("ep", "ed")
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '12s'")
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                LEFT JOIN intelligence.entity_dossiers ed
                  ON ed.domain_key = ep.domain_key AND ed.entity_id = ep.canonical_entity_id
                WHERE ep.canonical_entity_id IS NOT NULL
                  AND {domain_sql}
                  AND {needs_compile}
                """,
                (domain_keys,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog entity_dossier_compile count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_story_enhancement_pending() -> int:
    """Hot-queue depth for ``run_enhancement_cycle`` (fact_change_log + story_update_queue only).

    This is **not** storyline historical memory completeness — long arcs live in
    versioned_facts, chronological_events, and story_entity_index (see storyline_historical_context_service).
    Entity enrichment and profile-build backlog are separate phases.
    """
    conn = _get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(
                """
                SELECT
                  COALESCE((SELECT COUNT(*) FROM intelligence.fact_change_log WHERE processed = FALSE), 0)
                + COALESCE((SELECT COUNT(*) FROM intelligence.story_update_queue WHERE processed = FALSE), 0)
                AS n
                """
            )
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
    except Exception as e:
        logger.debug("backlog story_enhancement queues: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_storyline_synthesis_pending() -> int:
    """Storylines with 3+ articles needing first synthesis or re-synthesis (matches _execute_storyline_synthesis)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.storylines s
                        INNER JOIN (
                            SELECT storyline_id FROM {schema}.storyline_articles
                            GROUP BY storyline_id HAVING COUNT(*) >= 3
                        ) sa ON sa.storyline_id = s.id
                        WHERE s.synthesized_content IS NULL
                           OR EXISTS (
                             SELECT 1 FROM {schema}.storyline_articles sa2
                             JOIN {schema}.articles a ON a.id = sa2.article_id
                             WHERE sa2.storyline_id = s.id
                               AND a.created_at > COALESCE(s.synthesized_at, '1970-01-01'::timestamptz)
                           )
                        """
                    )
                    total += int(cur.fetchone()[0] or 0)
                except Exception:
                    try:
                        cur.execute(
                            f"""
                            SELECT COUNT(*) FROM {schema}.storylines s
                            INNER JOIN (
                                SELECT storyline_id FROM {schema}.storyline_articles
                                GROUP BY storyline_id HAVING COUNT(*) >= 3
                            ) sa ON sa.storyline_id = s.id
                            WHERE s.synthesized_content IS NULL
                            """
                        )
                        total += int(cur.fetchone()[0] or 0)
                    except Exception as e2:
                        logger.debug(
                            "backlog storyline_synthesis count schema=%s: %s", schema, e2
                        )
        return total
    except Exception as e:
        logger.debug("backlog storyline_synthesis count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_legislative_references_backlog() -> int:
    """Politics/legal articles without a legislative_article_scans row (bill-citation pass)."""
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import is_valid_domain_key, resolve_domain_schema
        from services.legislative_reference_service import (
            LEGISLATIVE_SCAN_DOMAIN_KEYS,
            SCAN_ARTICLE_DAYS,
        )
    except Exception as e:
        logger.debug("legislative_references backlog import: %s", e)
        return 0
    total = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for dk in LEGISLATIVE_SCAN_DOMAIN_KEYS:
                    if not is_valid_domain_key(dk):
                        continue
                    schema = resolve_domain_schema(dk)
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.articles a
                        WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                          AND a.created_at > NOW() - INTERVAL '{int(SCAN_ARTICLE_DAYS)} days'
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.legislative_article_scans s
                              WHERE s.domain_key = %s AND s.article_id = a.id
                          )
                        """,
                        (dk,),
                    )
                    total += int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("legislative_references backlog query: %s", e)
        return 0
    return total


def _count_graph_connection_distillation_pending() -> int:
    """Pending rows in intelligence.graph_connection_proposals (merge / associate / hyperedge)."""
    try:
        from services.graph_connection_queue_service import count_pending_graph_connection_proposals

        return int(count_pending_graph_connection_proposals())
    except Exception as e:
        logger.debug("backlog graph_connection_distillation count: %s", e)
        return 0


# Phases that should be skipped when backlog is 0 (avoid empty cycles).
# Every phase in RAW_PENDING_COUNT_KEYS belongs here so workload scheduling never ticks on interval at zero.
SKIP_WHEN_EMPTY = frozenset({
    "content_enrichment",
    "context_sync",
    "event_tracking",
    "claim_extraction",
    "entity_profile_build",
    "investigation_report_refresh",
    "document_processing",
    "content_refinement_queue",
    "pending_db_flush",
    "nightly_enrichment_context",
    "metadata_enrichment",
    "ml_processing",
    "entity_extraction",
    "unified_intake_extraction",
    "sentiment_analysis",
    "quality_scoring",
    "storyline_processing",
    "topic_clustering",
    "timeline_generation",
    "storyline_discovery",
    "proactive_detection",
    "storyline_assembly",
    "storyline_automation",
    "rag_enhancement",
    "event_extraction",
    "claims_to_facts",
    "legislative_references",
    "entity_profile_sync",
    "entity_enrichment",
    "entity_dossier_compile",
    "story_enhancement",
    "storyline_synthesis",
    "graph_connection_distillation",
})

_missing_skip_pending = SKIP_WHEN_EMPTY - RAW_PENDING_COUNT_KEYS
if _missing_skip_pending:
    raise RuntimeError(
        "backlog_metrics: SKIP_WHEN_EMPTY contains phases not in RAW_PENDING_COUNT_KEYS "
        f"(scheduler would starve them): {sorted(_missing_skip_pending)}. "
        "Add counts to _get_raw_pending_counts and extend RAW_PENDING_COUNT_KEYS."
    )

_missing_skip_raw = RAW_PENDING_COUNT_KEYS - SKIP_WHEN_EMPTY
if _missing_skip_raw:
    raise RuntimeError(
        "backlog_metrics: RAW_PENDING_COUNT_KEYS phases missing from SKIP_WHEN_EMPTY "
        f"(empty cycles at interval): {sorted(_missing_skip_raw)}. "
        "Add each phase to SKIP_WHEN_EMPTY."
    )

# When backlog exceeds this, use backlog-mode interval so we run more often
BACKLOG_HIGH_THRESHOLD = 200
# Effective min interval (seconds) when in backlog mode (high backlog)
BACKLOG_MODE_INTERVAL = 300
# When any backlog > 0, use this so we don't wait full interval between runs (run as soon as eligible)
BACKLOG_ANY_INTERVAL = 30


def get_data_quality_metrics() -> dict:
    """Structural DB health signals for Monitor (entity graph size, claims/facts ratio, context orphans)."""
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    out: dict = {
        "entity_relationships_estimate": 0,
        "extracted_claims_total": 0,
        "versioned_facts_total": 0,
        "claims_to_facts_ratio": 0.0,
        "claims_unpromoted": 0,
        "context_orphans": {},
    }
    conn = _get_conn()
    if not conn:
        return out
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                """
                SELECT reltuples::bigint FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'intelligence' AND c.relname = 'entity_relationships'
                """
            )
            row = cur.fetchone()
            out["entity_relationships_estimate"] = int(row[0] or 0) if row else 0

            cur.execute("SELECT COUNT(*)::bigint FROM intelligence.extracted_claims")
            claims = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*)::bigint FROM intelligence.versioned_facts")
            facts = int(cur.fetchone()[0] or 0)
            out["extracted_claims_total"] = claims
            out["versioned_facts_total"] = facts
            out["claims_to_facts_ratio"] = round(claims / facts, 2) if facts else float(claims)
            out["claims_unpromoted"] = _count_claims_to_facts_pending()

            for domain_key in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(domain_key)
                cur.execute(f"SELECT COUNT(*)::int FROM {schema}.articles")
                articles = int(cur.fetchone()[0] or 0)
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT atc.article_id)::int
                    FROM intelligence.article_to_context atc
                    JOIN intelligence.contexts c ON c.id = atc.context_id
                    WHERE c.domain_key = %s
                    """,
                    (domain_key,),
                )
                linked = int(cur.fetchone()[0] or 0)
                orphans = max(0, articles - linked)
                pct = round(orphans / articles * 100, 2) if articles else 0.0
                out["context_orphans"][domain_key] = {
                    "articles": articles,
                    "linked": linked,
                    "orphans": orphans,
                    "orphan_pct": pct,
                }
    except Exception as e:
        logger.debug("get_data_quality_metrics: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out
