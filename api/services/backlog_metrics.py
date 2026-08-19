"""
Backlog metrics — pending work counts per automation phase for orchestrator priority.
Counts are defined to match each phase’s real eligibility (what automation would select),
not coarse table totals, so Monitor ``pending_records`` reflects actionable backlog.

**topic_clustering (default):** ``pending`` = articles with no ``metadata.pipeline.topic_clustering.last_pass_at``
that have sufficient body text **and** pass the same signal-first full-lane gate the worker uses
(when ``ARTICLE_SIGNAL_ENABLED``). Light-lane / low-quality pass-null inventory is excluded so
Monitor and residual scheduling do not thrash empty cycles. Legacy “churn” counting (low average
confidence after assignments) is available via ``TOPIC_CLUSTERING_BACKLOG_USE_PASS_MARKER=false``.

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

import asyncio
import logging
import os
import threading
import time
from contextvars import ContextVar
from typing import Any, Dict, Optional

from shared.article_processing_gates import (
    sql_context_sync_article_ready,
    sql_ml_ready_and_content_bounds,
)
from shared.domain_registry import (
    get_pipeline_schema_names_active,
    pipeline_url_schema_pairs,
)
from shared.pipeline_pass_marker import (
    phase_backlog_uses_pass_marker,
    sql_article_pass_null,
    sql_context_pass_null,
)
from shared.pipeline_article_selection import sql_order_created_at
from shared.phase_spec import overlay_batch_size_per_task, overlay_skip_when_empty
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

# One shared DB session for a full pending-count refresh (avoids N pool checkouts).
_shared_backlog_conn: ContextVar[Any] = ContextVar("shared_backlog_conn", default=None)


def _domain_keys_for_phase(phase: str) -> list[str]:
    """Domains that may run/count ``phase`` (corpus/research gate).

    Skipping the drain but still counting backlog causes phantom backlog
    (same class of bug as CTF / membership miscounts).
    """
    from shared.pipeline_domain_sql import pipeline_domain_keys_for_phase

    return pipeline_domain_keys_for_phase(phase)


def _schemas_for_phase(phase: str) -> list[str]:
    """Schemas for domains that may run/count ``phase``."""
    from shared.pipeline_domain_sql import pipeline_schema_names_for_phase

    return pipeline_schema_names_for_phase(phase)


def _pairs_for_phase(phase: str) -> list[tuple[str, str]]:
    from shared.pipeline_domain_sql import pipeline_url_schema_pairs_for_phase

    return pipeline_url_schema_pairs_for_phase(phase)


class _SharedBacklogConn:
    """Proxy around a live connection whose ``close()`` is a no-op during batch refresh."""

    __slots__ = ("_conn",)

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def close(self) -> None:
        return None

    def cursor(self, *args: Any, **kwargs: Any):
        return self._conn.cursor(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def _ensure_shared_backlog_conn_healthy() -> None:
    """
    Rollback an aborted shared backlog transaction so later phase COUNTs are not
    false-zeroed (e.g. claims_to_facts timeout poisoning collision/embedding).
    """
    shared = _shared_backlog_conn.get()
    if shared is None:
        return
    try:
        with shared.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception:
        try:
            shared.rollback()
        except Exception:
            pass


def _capped_count_probe(
    cur,
    sql: str,
    params: tuple | list | None = None,
    *,
    cap: int = 10_001,
    cache_key: str | None = None,
) -> int:
    """
    COUNT(*) over a ``LIMIT cap`` subquery so heavy scans cannot run unbounded.

    When the probe hits ``cap``, return max(cached, cap) so Monitor still shows
    non-zero backlog instead of a false zero or a multi-minute COUNT.
    """
    cap = max(1, int(cap))
    wrapped = f"SELECT COUNT(*)::bigint FROM ({sql.rstrip().rstrip(';')} LIMIT %s) AS _probe"
    args: list[Any] = list(params or [])
    args.append(cap)
    cur.execute(wrapped, tuple(args))
    n = int(cur.fetchone()[0] or 0)
    if n >= cap and cache_key:
        try:
            prev = int(_backlog_cache.get(cache_key, 0) or 0)
        except Exception:
            prev = 0
        return max(prev, cap)
    return n


def _rollback_quiet(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass


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
    "unified_intake_extraction": 6,
    "sentiment_analysis": 300,  # 100 × 3
    "quality_scoring": 150,  # 50 × 3
    "storyline_processing": 24,  # ~8 storylines worth of summary work per full pass
    "topic_clustering": 60,  # ~20 × 3 standard domains (approximates automation)
    "timeline_generation": 36,  # 12 × 3
    "storyline_discovery": 50,  # unlinked-in-newest-N proxy (see _count_storyline_discovery_pending)
    "storyline_assembly": 60,  # ~automation_batch_per_assembly (20) × active domains
    "proactive_detection": 1000,  # proactive candidate pool cap per domain
    "storyline_automation": 5,  # automation_manager LIMIT storylines per domain per tick
    "storyline_review_agent": 60,  # suggestions reviewed per domain batch (score + LLM mid-band)
    "storyline_membership_review": 100,  # adaptive floor; catch-up may raise further
    "storyline_hygiene": 25,  # storylines pruned per domain per tick
    "rag_enhancement": 5,  # top-N hot per domain (see RAG_ENHANCEMENT_TOP_N_PER_DOMAIN)
    "event_extraction": 90,  # 30 × 3
    "claims_to_facts": 200,  # adaptive 50–500; chunked by CLAIMS_TO_FACTS_CHUNK_SIZE (default 50)
    "legislative_references": 8,  # articles scanned per domain per run (Congress.gov rate limits)
    "entity_profile_sync": 40,  # canonical rows mapped per domain batch (approx)
    "entity_enrichment": 20,  # run_enrichment_batch limit
    "entity_dossier_compile": 20,  # _run_scheduled_dossier_compiles max per run
    "story_enhancement": 50,  # fact_change_log + story_update_queue proxy per cycle
    "storyline_synthesis": 16,  # ~4 storylines × active domains per _execute_storyline_synthesis tick
    "graph_connection_distillation": 50,  # GRAPH_CONNECTION_DISTILLATION_BATCH proposals per run
    "embedding_link_candidates": 12,
    "collision_sampling": 8,
    "stimulus_rag": 20,
    "protein_harden": 40,
    "graph_link_drift_review": 40,
    "mention_resolution": 500,  # NRI_MENTION_RESOLVE_BATCH_LIMIT default
    "entity_organizer": 100,
    "event_deduplication": 100,
    "story_continuation": 30,
    "pending_db_flush": 200,  # rough lines replayed per successful flush (order-of-magnitude)
}

# High-churn phases: PhaseSpec overlays batch defaults (spec wins).
BATCH_SIZE_PER_TASK = overlay_batch_size_per_task(BATCH_SIZE_PER_TASK)

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
        "storyline_review_agent",
        "storyline_membership_review",
        "storyline_hygiene",
        "embedding_link_candidates",
        "collision_sampling",
        "stimulus_rag",
        "protein_harden",
        "graph_link_drift_review",
        "claims_to_facts",
        "legislative_references",
        "entity_profile_sync",
        "entity_enrichment",
        "entity_dossier_compile",
        "story_enhancement",
        "storyline_synthesis",
        "graph_connection_distillation",
        "mention_resolution",
        "nightly_enrichment_context",
        "entity_organizer",
        "event_deduplication",
        "story_continuation",
        "chronological_events_catchup",
        "editorial_research_pass",
        "editorial_narrative_pass",
        "editorial_evidence_expand_pass",
        "editorial_reduction_pass",
        "claim_evidence_appraisal",
    }
)


def _get_raw_pending_counts() -> Dict[str, int]:
    """Query all raw pending-work counts (not cached — called by the cached wrapper)."""
    raw: Dict[str, int] = {}

    def _set(phase: str, value) -> None:
        # Skip expensive COUNT SQL for retired/suppressed phases (evaluate callables lazily).
        if _should_skip_backlog_count(phase):
            raw[phase] = 0
            return
        _ensure_shared_backlog_conn_healthy()
        try:
            raw[phase] = int(value() if callable(value) else (value or 0))
        except Exception as e:
            logger.debug("backlog_metrics _set %s: %s", phase, e)
            raw[phase] = 0
        finally:
            _ensure_shared_backlog_conn_healthy()

    shared_conn = None
    shared_token = None
    try:
        shared_conn = _acquire_raw_backlog_conn()
        if shared_conn is not None:
            shared_token = _shared_backlog_conn.set(shared_conn)

        hot: dict[str, int] = {}
        if shared_conn is not None:
            try:
                hot = _hot_path_pending_counts(shared_conn)
            except Exception as e:
                logger.debug("backlog hot_path via shared conn: %s", e)
                try:
                    shared_conn.rollback()
                except Exception:
                    pass
        _set(
            "content_enrichment",
            hot.get("content_enrichment", 0) if hot else _count_content_enrichment_backlog(),
        )
        _set(
            "context_sync",
            hot.get("context_sync", 0) if hot else _count_context_sync_backlog(),
        )
        _set("event_tracking", _count_event_tracking_backlog())
        _set("claim_extraction", _count_claim_extraction_backlog())
        _set("entity_profile_build", _count_entity_profile_build_backlog())
        _set("investigation_report_refresh", _count_investigation_report_backlog)
        _set(
            "document_processing",
            hot.get("document_processing", 0) if hot else _count_document_processing_backlog(),
        )
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
        _set("storyline_processing", _count_storyline_processing_pending)
        _set("topic_clustering", _count_topic_clustering_pending())
        _set("timeline_generation", _count_timeline_generation_pending)
        _set("storyline_discovery", _count_storyline_discovery_pending)
        _set("rag_enhancement", _count_rag_enhancement_pending)
        _set("event_extraction", _count_event_extraction_pending())
        _set("proactive_detection", _count_proactive_detection_pending)
        _set("storyline_assembly", _count_storyline_assembly_pending())
        _set("storyline_automation", _count_storyline_automation_pending())
        _set("storyline_review_agent", get_storyline_review_queue_pending())
        _set("storyline_membership_review", _count_storyline_membership_review_pending())
        _set("storyline_hygiene", _count_storyline_hygiene_pending)
        # Prefer callables so _set can recover a poisoned shared txn before each COUNT.
        _set("claims_to_facts", _count_claims_to_facts_pending)
        _set("claim_evidence_appraisal", _count_claim_evidence_appraisal_pending)
        _set("legislative_references", _count_legislative_references_backlog)
        _set("entity_profile_sync", _count_entity_profile_sync_pending)
        _set("entity_enrichment", _count_entity_enrichment_pending)
        _set("entity_dossier_compile", _count_entity_dossier_compile_pending)
        _set("story_enhancement", _count_story_enhancement_pending)
        _set("storyline_synthesis", _count_storyline_synthesis_pending)
        _set("graph_connection_distillation", _count_graph_connection_distillation_pending)
        _set("embedding_link_candidates", _count_embedding_link_candidates_pending)
        _set("collision_sampling", _count_collision_sampling_pending)
        _set("stimulus_rag", _count_stimulus_rag_pending)
        _set("protein_harden", _count_protein_harden_pending)
        _set("graph_link_drift_review", _count_graph_link_drift_pending)
        _set("mention_resolution", _count_mention_resolution_pending)
        _set("entity_organizer", _count_entity_organizer_pending)
        _set("event_deduplication", _count_event_deduplication_pending)
        _set("story_continuation", _count_story_continuation_pending)
        _set("chronological_events_catchup", _count_chronological_events_catchup_pending)
        _set("editorial_research_pass", _count_editorial_research_pending)
        _set("editorial_narrative_pass", _count_editorial_narrative_pending)
        _set("editorial_evidence_expand_pass", _count_editorial_evidence_expand_pending)
        _set("editorial_reduction_pass", _count_editorial_reduction_pending)
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
    finally:
        if shared_token is not None:
            _shared_backlog_conn.reset(shared_token)
        if shared_conn is not None:
            try:
                shared_conn.close()
            except Exception:
                pass
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


def _called_from_asyncio_loop_thread() -> bool:
    """True when invoked (possibly nested) on the thread running an asyncio event loop."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


_backlog_invalidate_last_mono: float = 0.0


def invalidate_backlog_metrics_cache() -> None:
    """Force the next get_all_pending_counts / get_all_backlog_counts to re-query the DB."""
    global _backlog_cache_time, _pending_cache_time, _backlog_cache, _pending_cache
    global _backlog_invalidate_last_mono
    _backlog_cache_time = 0.0
    _pending_cache_time = 0.0
    _backlog_cache.clear()
    _pending_cache.clear()
    _backlog_invalidate_last_mono = time.monotonic()
    try:
        from shared.unified_intake_backlog import invalidate_unified_intake_backlog_stats_cache

        invalidate_unified_intake_backlog_stats_cache()
    except Exception:
        pass


def invalidate_backlog_metrics_cache_throttled(*, min_interval_seconds: float = 60.0) -> bool:
    """
    Invalidate backlog caches at most once per ``min_interval_seconds``.

    UIE/enrich drains used to call full invalidate every round (~100 COUNT scans).
    Prefer this for high-frequency callers; use ``invalidate_backlog_metrics_cache`` for
    operator/nightly forced refresh.
    """
    global _backlog_invalidate_last_mono
    now = time.monotonic()
    gap = max(0.0, float(min_interval_seconds))
    if gap > 0 and (now - _backlog_invalidate_last_mono) < gap:
        return False
    invalidate_backlog_metrics_cache()
    return True

def _per_run_batch_size(task: str) -> int:
    """Align backlog subtraction with actual automation batch sizes (env-tunable for claim phases)."""
    if task == "content_enrichment":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("content_enrichment")
            if adaptive is not None:
                return max(1, min(120, int(adaptive)))
        except Exception:
            pass
    if task in NO_BACKLOG_BATCH_SUBTRACT_PHASES:
        return 0
    if task == "entity_extraction":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            n = int(env_str("ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN", "40"))
            n = max(5, min(120, n))
            adaptive = get_persisted_adaptive_batch("entity_extraction")
            if adaptive is not None:
                n = max(5, min(120, int(adaptive)))
            doms = len(get_pipeline_schema_names_active()) or 1
            return n * doms
        except Exception:
            pass
    if task == "claim_extraction":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("claim_extraction")
            if adaptive is not None:
                return max(1, int(adaptive))
            from services.claim_extraction_service import get_claim_extraction_batch_limit

            return int(get_claim_extraction_batch_limit())
        except Exception:
            pass
    if task == "claims_to_facts":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("claims_to_facts")
            if adaptive is not None:
                # Keep Monitor ETA aligned with adaptive max (50–500).
                return max(1, min(500, int(adaptive)))
            from services.claim_extraction_service import get_claims_to_facts_batch_limit

            return int(get_claims_to_facts_batch_limit())
        except Exception:
            pass
    if task == "topic_clustering":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            per = 20
            adaptive = get_persisted_adaptive_batch("topic_clustering")
            if adaptive is not None:
                per = max(5, int(adaptive))
            else:
                try:
                    per = max(5, int(env_str("TOPIC_CLUSTERING_BATCH_SIZE", "20")))
                except (TypeError, ValueError):
                    per = 20
            doms = len(get_pipeline_schema_names_active()) or 1
            return per * doms
        except Exception:
            pass
    if task == "mention_resolution":
        try:
            from config.runtime import mention_resolve_batch_limit

            return int(mention_resolve_batch_limit())
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
            from services.storyline_assembly_service import storyline_assembly_rows_per_run

            return int(storyline_assembly_rows_per_run())
        except Exception:
            pass
    if task == "storyline_review_agent":
        # Per-domain adaptive limit (not × domains). Prefer persisted autotune size.
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("storyline_review_agent")
            if adaptive is not None:
                return max(20, int(adaptive))
            return max(20, int(BATCH_SIZE_PER_TASK.get("storyline_review_agent", 60)))
        except Exception:
            return int(BATCH_SIZE_PER_TASK.get("storyline_review_agent", 60))
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
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("entity_profile_build")
            if adaptive is not None:
                return max(1, min(150, int(adaptive)))
            return max(1, min(150, int(env_str("ENTITY_PROFILE_BUILD_LIMIT", "25"))))
        except Exception:
            pass
    if task == "entity_dossier_compile":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("entity_dossier_compile")
            if adaptive is not None:
                return max(1, min(100, int(adaptive)))
            return max(1, min(100, int(env_str("ENTITY_DOSSIER_COMPILE_MAX", "20"))))
        except Exception:
            pass
    if task == "event_tracking":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("event_tracking")
            batch_max = max(25, min(300, int(env_str("EVENT_TRACKING_ASSEMBLY_BATCH_MAX", "300"))))
            if adaptive is not None:
                return max(1, min(batch_max, int(adaptive)))
            return max(1, min(batch_max, int(env_str("EVENT_TRACKING_ASSEMBLY_BATCH_LIMIT", "25"))))
        except Exception:
            pass
    if task == "graph_connection_distillation":
        try:
            from shared.adaptive_batch_policy import get_persisted_adaptive_batch

            adaptive = get_persisted_adaptive_batch("graph_connection_distillation")
            default = max(1, int(env_str("GRAPH_CONNECTION_DISTILLATION_BATCH", "50")))
            if adaptive is not None:
                return max(1, int(adaptive))
            return default
        except Exception:
            pass
    # Generic: any phase with adaptive bounds + persisted batch
    try:
        from shared.adaptive_batch_policy import (
            get_persisted_adaptive_batch,
            is_adaptive_batch_phase,
            is_per_domain_adaptive_batch,
        )

        if is_adaptive_batch_phase(task):
            adaptive = get_persisted_adaptive_batch(task)
            if adaptive is not None:
                n = max(1, int(adaptive))
                if is_per_domain_adaptive_batch(task):
                    doms = len(get_pipeline_schema_names_active()) or 1
                    if task == "storyline_automation":
                        from shared.domain_registry import get_pipeline_active_domain_keys

                        doms = len(get_pipeline_active_domain_keys()) or 1
                    return n * doms
                return n
    except Exception:
        pass
    if task in BATCH_SIZE_PER_TASK:
        return int(BATCH_SIZE_PER_TASK[task])
    return _default_batch_for_unknown_phase()


def get_per_run_batch_size_for_phase(phase_name: str) -> int:
    """Rows/items assumed processed in one automation run of ``phase_name`` (for Monitor / processing_progress)."""
    return _per_run_batch_size(phase_name)


def _refresh_cache() -> None:
    """Refresh both pending and backlog caches (single-flight under lock).

    Goal: one DB session per refresh via shared contextvar in ``_get_raw_pending_counts``.

    Never block the uvicorn event loop behind another refresh: serve stale caches when
    available, and skip waiting on the asyncio thread when the cache is still empty
    (callers that need fresh counts should use ``asyncio.to_thread``).
    """
    global _backlog_cache, _backlog_cache_time, _pending_cache, _pending_cache_time
    now = time.monotonic()
    if now - _backlog_cache_time <= BACKLOG_CACHE_TTL and _backlog_cache and _pending_cache:
        return

    acquired = _refresh_cache_lock.acquire(blocking=False)
    if not acquired:
        # Stale caches are safe to serve without waiting.
        if _pending_cache and _backlog_cache:
            return
        # No cache yet: wait for the in-flight refresh — but never on the asyncio
        # loop thread (that freezes Monitor HTTP for the full SQL duration).
        if _called_from_asyncio_loop_thread():
            return
        _refresh_cache_lock.acquire(blocking=True)
        acquired = True

    try:
        now = time.monotonic()
        if now - _backlog_cache_time <= BACKLOG_CACHE_TTL and _backlog_cache and _pending_cache:
            return

        raw = _get_raw_pending_counts()
        # Never clobber a good cache with an empty refresh (pool/conn failure → Monitor zeros).
        if not raw:
            logger.warning(
                "backlog_metrics refresh returned 0 phases — keeping prior cache "
                "(pending=%d backlog=%d)",
                len(_pending_cache),
                len(_backlog_cache),
            )
            return

        _pending_cache = raw.copy()
        _pending_cache_time = now

        out: Dict[str, int] = {}
        for task, pending in raw.items():
            batch = _per_run_batch_size(task)
            out[task] = max(pending - batch, 0)
        _backlog_cache = out
        _backlog_cache_time = now
    finally:
        if acquired:
            _refresh_cache_lock.release()

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

    During ``_get_raw_pending_counts`` a shared session is installed via contextvar so each
    ``_count_*`` helper reuses one checkout instead of opening dozens of connections.
    """
    shared = _shared_backlog_conn.get()
    if shared is not None:
        return _SharedBacklogConn(shared)
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


def _acquire_raw_backlog_conn():
    """Open a real connection for a full pending-count refresh (never the shared proxy)."""
    try:
        from shared.database.connection import get_db_connection

        return get_db_connection()
    except Exception:
        try:
            from shared.database.connection import get_ui_db_connection

            return get_ui_db_connection()
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
    """Articles pending enrichment (eligibility SQL — not spine queue table depth)."""
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


def _hot_path_pending_counts(conn) -> dict[str, int]:
    """Batch ingest hot-path COUNTs on one DB session (content_enrichment, context_sync, document_processing)."""
    out = {"content_enrichment": 0, "context_sync": 0, "document_processing": 0}
    probe_cap = env_int("BACKLOG_HOT_PATH_PROBE_CAP", 5001)
    try:
        for schema in get_pipeline_schema_names_active():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                try:
                    out["content_enrichment"] += _capped_count_probe(
                        cur,
                        f"""
                        SELECT 1 FROM {schema}.articles
                        WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                          AND COALESCE(enrichment_attempts, 0) < 3
                          AND url IS NOT NULL AND url != ''
                        """,
                        cap=probe_cap,
                        cache_key="content_enrichment",
                    )
                except Exception:
                    _rollback_quiet(conn)
        ready = sql_context_sync_article_ready("a")
        for domain_key, schema in pipeline_url_schema_pairs():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3s'")
                try:
                    out["context_sync"] += _capped_count_probe(
                        cur,
                        f"""
                        SELECT 1 FROM {schema}.articles a
                        LEFT JOIN intelligence.article_to_context atc
                          ON atc.domain_key = %s AND atc.article_id = a.id
                        WHERE atc.context_id IS NULL
                          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                          AND ({ready})
                        """,
                        (domain_key,),
                        cap=probe_cap,
                        cache_key="context_sync",
                    )
                except Exception:
                    _rollback_quiet(conn)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            try:
                out["document_processing"] = _capped_count_probe(
                    cur,
                    """
                    SELECT 1 FROM intelligence.processed_documents
                    WHERE source_url IS NOT NULL AND source_url != ''
                      AND (extracted_sections IS NULL OR extracted_sections = '[]'::jsonb)
                      AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
                    """,
                    cap=probe_cap,
                    cache_key="document_processing",
                )
            except Exception:
                _rollback_quiet(conn)
    except Exception as e:
        logger.debug("backlog hot_path counts: %s", e)
        _rollback_quiet(conn)
    return out


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
    """Contexts the ``event_tracking`` phase can select: same window, min length, pipeline
    domains only (``run_event_tracking_batch`` / ``discover_events_from_contexts``), and
    ``NOT EXISTS`` chronicle link predicate — not orphan rows like ``documents``."""
    max_age_days, min_len = _event_tracking_scan_window_params()
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    # Exclude corpus domains — drain skips them; counting them is phantom backlog.
    domain_sql, domain_keys = pipeline_domain_any_sql(
        "c.domain_key", phase="event_tracking"
    )
    if not domain_keys:
        return 0
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
                  AND {domain_sql}
                  AND NOT EXISTS (
                      SELECT 1 FROM intelligence.event_chronicle_contexts ecc
                      WHERE ecc.context_id = c.id
                  )
                  {pass_sql}
                """,
                (max_age_days, min_len, domain_keys),
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
    try:
        from services.claim_extraction_service import sql_claim_extraction_eligible

        eligible = sql_claim_extraction_eligible("c")
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '60s'")
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.contexts c
                WHERE {eligible}
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.warning("backlog claim_extraction count failed (using eligible capped probe): %s", e)
        _rollback_quiet(conn)
        # Prefer the same eligibility SQL as the worker; never fall back to a looser
        # "no claims + min text" probe (phantom backlog / CTF-class mismatch).
        try:
            from services.claim_extraction_service import sql_claim_extraction_eligible

            eligible = sql_claim_extraction_eligible("c")
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '15s'")
                n = _capped_count_probe(
                    cur,
                    f"""
                    SELECT 1 FROM intelligence.contexts c
                    WHERE {eligible}
                    """,
                    (),
                    cap=env_int("BACKLOG_CLAIM_EXTRACTION_PROBE_CAP", 5001),
                    cache_key="claim_extraction",
                )
                if n > 0:
                    return n
        except Exception as e2:
            logger.debug("backlog claim_extraction capped probe: %s", e2)
            _rollback_quiet(conn)
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
        _entity_profile_upstream_gate_for_select,
        _profile_build_db_timeout_ms,
    )
    from shared.entity_profile_eligibility import sql_entity_profile_needs_build
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    conn = _get_conn()
    if not conn:
        raise RuntimeError("entity_profile_build backlog count: no DB connection")
    # Corpus domains never run entity_profile_build — exclude to avoid phantom backlog.
    domain_sql, domain_keys = pipeline_domain_any_sql(
        "ep.domain_key", phase="entity_profile_build"
    )
    if not domain_keys:
        return 0
    upstream_sql = ""
    if _entity_profile_upstream_gate_for_select():
        upstream_sql = f" AND {sql_entity_profile_upstream_cleared_exists()} "
    needs_build = sql_entity_profile_needs_build("ep")
    timeout_ms = _profile_build_db_timeout_ms()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = %s", (str(timeout_ms),))
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
    finally:
        try:
            conn.close()
        except Exception:
            pass


def count_entity_profile_build_backlog_safe() -> int | None:
    """Like _count_entity_profile_build_backlog but returns None when count fails."""
    try:
        return _count_entity_profile_build_backlog()
    except Exception as e:
        logger.warning("entity_profile_build backlog count failed: %s", e)
        return None


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
    """Articles awaiting topic_clustering that the worker would actually select.

    Uses ``TopicClusteringService.count_pending_articles`` (same predicates as
    ``select_pending_article_ids`` / PopOS idle gate). Default first-pass-only
    mode does not inflate queue_depth with retry rows.
    Per-schema timeouts keep a partial total instead of zeroing the whole phase.
    Shared-connection failures roll back so later backlog counts are not poisoned.
    """
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        from config.settings import (
            topic_clustering_backlog_uses_pass_marker,
            topic_clustering_graduation_confidence,
            topic_clustering_iterative_refinement_enabled,
        )
        from domains.content_analysis.services.topic_clustering_service import (
            TopicClusteringService,
        )

        use_pass = topic_clustering_backlog_uses_pass_marker()
        iterative = topic_clustering_iterative_refinement_enabled()
        conf = float(topic_clustering_graduation_confidence())
    except Exception:
        use_pass = True
        iterative = False
        conf = 0.88
        TopicClusteringService = None  # type: ignore[misc, assignment]

    for schema in get_pipeline_schema_names_active():
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '8s'")
                if TopicClusteringService is not None:
                    total += int(
                        TopicClusteringService.count_pending_articles(
                            cur,
                            schema,
                            use_pass_marker=use_pass,
                            iterative=iterative,
                            confidence_threshold=conf,
                        )
                        or 0
                    )
                else:
                    # Fallback first-pass-only if import failed mid-path
                    cur.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM {schema}.articles a
                        WHERE a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (
                            a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NULL
                            OR TRIM(COALESCE(
                                a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', ''
                            )) = ''
                          )
                        """
                    )
                    total += int(cur.fetchone()[0] or 0)
        except Exception as e:
            logger.debug("backlog topic_clustering count schema=%s: %s", schema, e)
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        conn.close()
    except Exception:
        pass
    return total


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
        for schema in _schemas_for_phase("storyline_discovery"):
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
    """Domains above assembly threshold only — matches PopOS idle gate / drain."""
    try:
        from services.storyline_assembly_service import (
            count_unlinked_articles,
            domains_needing_assembly,
        )

        # Gate: corpus domains must not contribute research backlog.
        allowed = set(_domain_keys_for_phase("storyline_assembly"))
        return sum(
            count_unlinked_articles(dk)
            for dk in domains_needing_assembly()
            if dk in allowed
        )
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
        for schema in _schemas_for_phase("proactive_detection"):
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
        for schema in _schemas_for_phase("storyline_automation"):
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


def _count_storyline_hygiene_pending() -> int:
    """Active oversized storylines eligible for hygiene prune/merge."""
    try:
        from services.storyline_hygiene_service import count_storyline_hygiene_pending

        return int(count_storyline_hygiene_pending() or 0)
    except Exception:
        return 0


def _count_storyline_membership_review_pending() -> int:
    """
    Megas the membership drain will actually pick (fingerprint / never-reviewed SSOT).

    Pending operator actions are *not* this phase's queue_depth — automation runs
    ``_pick_storylines`` / review, not ``apply_membership_action``.
    """
    try:
        from services.storyline_membership_review_service import (
            count_storylines_needing_membership_review,
            membership_review_enabled,
        )

        if not membership_review_enabled():
            return 0
        # Sum only research domains — corpus backlog here is phantom.
        total = 0
        for dk in _domain_keys_for_phase("storyline_membership_review"):
            total += int(count_storylines_needing_membership_review(domain_key=dk) or 0)
        return total
    except Exception as e:
        logger.debug("backlog storyline_membership_review count: %s", e)
        return 0


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

        if not _domain_keys_for_phase("rag_enhancement"):
            return 0
        return int(count_rag_enhancement_pending() or 0)
    except Exception as e:
        logger.debug("backlog rag_enhancement count: %s", e)
        return 0


def _count_claims_to_facts_pending() -> int:
    """Unpromoted high-confidence claims for Monitor (see ``build_claims_to_facts_backlog_where_suffix``).

    Default ``CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE=batch_candidate``: same WHERE as
    ``promote_claims_to_versioned_facts`` (queue_depth SSOT). Opt into
    ``promotable_hint`` only for exploratory Monitor views.
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
        # Timeout/error aborts the txn — must rollback or shared-batch COUNTs false-zero.
        _rollback_quiet(conn)
        # Cheaper fallback: unpromoted high-confidence claims (no resolvable-hint joins).
        # Still exclude promotion_skip / deferred so Monitor does not show ~deferred+gap as actionable.
        try:
            from services.claim_extraction_service import claim_promotion_deferred_exclude_sql

            defer_sql = claim_promotion_deferred_exclude_sql()
        except Exception:
            defer_sql = """
                      AND COALESCE(ec.metadata->>'promotion_skip', '') = ''
"""
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '10s'")
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.extracted_claims ec
                    WHERE ec.confidence >= %s
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.versioned_facts vf
                        WHERE vf.metadata->>'source_claim_id' = ec.id::text
                      )
                    """
                    + defer_sql,
                    (min_conf,),
                )
                return int(cur.fetchone()[0] or 0)
        except Exception as e2:
            logger.debug("backlog claims_to_facts fallback count: %s", e2)
            _rollback_quiet(conn)
            # Last resort: capped probe — never leave Monitor at false zero if work exists.
            try:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '5s'")
                    return _capped_count_probe(
                        cur,
                        """
                        SELECT 1 FROM intelligence.extracted_claims ec
                        WHERE ec.confidence >= %s
                          AND NOT EXISTS (
                            SELECT 1 FROM intelligence.versioned_facts vf
                            WHERE vf.metadata->>'source_claim_id' = ec.id::text
                          )
                        """
                        + defer_sql,
                        (min_conf,),
                        cap=env_int("BACKLOG_CLAIMS_TO_FACTS_PROBE_CAP", 10001),
                        cache_key="claims_to_facts",
                    )
            except Exception as e3:
                logger.debug("backlog claims_to_facts capped probe: %s", e3)
                _rollback_quiet(conn)
                return int(_backlog_cache.get("claims_to_facts", 0) or 0)
    finally:
        try:
            conn.close()
        except Exception:
            pass



def _count_claim_evidence_appraisal_pending() -> int:
    """SSOT: documents/articles due for corpus evidence appraisal.

    Skip drain but still counting here would create phantom backlog for research
    domains — counter is scoped to corpus domains inside the service.
    """
    try:
        from services.claim_evidence_appraisal_service import count_claim_evidence_appraisal_due

        return int(count_claim_evidence_appraisal_due() or 0)
    except Exception as e:
        logger.debug("backlog claim_evidence_appraisal count: %s", e)
        return 0



def _count_entity_profile_sync_pending() -> int:
    """entity_canonical rows without intelligence.old_entity_to_new mapping (per domain).

    Completion is structural (mapping row exists); there is no separate pass marker."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    try:
        # Research-band phase — exclude corpus to avoid phantom backlog.
        for domain_key, schema in _pairs_for_phase("entity_profile_sync"):
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
    domain_sql, domain_keys = pipeline_domain_any_sql(
        "ep.domain_key", phase="entity_dossier_compile"
    )
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
    """Actionable pending rows in intelligence.graph_connection_proposals.

    Excludes entity-merge rows the drain deliberately holds for editorial
    review (below GRAPH_CONNECTION_ENTITY_MERGE_MIN); counting those made the
    backlog look flat once drainable rows cleared, falsely stalling the phase
    into auto-silence.
    """
    try:
        from services.graph_connection_queue_service import count_pending_graph_connection_proposals

        allowed = _domain_keys_for_phase("graph_connection_distillation")
        if not allowed:
            return 0
        return int(
            count_pending_graph_connection_proposals(
                actionable_only=True, domain_keys=allowed
            )
        )
    except Exception as e:
        logger.debug("backlog graph_connection_distillation count: %s", e)
        return 0


def _count_embedding_link_candidates_pending() -> int:
    """Storylines due for embedding-link scan (same due SQL as the drain)."""
    try:
        from services.embedding_link_candidate_service import (
            count_embedding_link_candidates_due,
        )

        total = 0
        for dk in _domain_keys_for_phase("embedding_link_candidates"):
            total += int(count_embedding_link_candidates_due(domain_key=dk) or 0)
        return total
    except Exception as e:
        logger.debug("backlog embedding_link_candidates count: %s", e)
        return 0


def _count_collision_sampling_pending() -> int:
    """Domains with a samplable collision pool (≥2 storylines) — not proposal inventory."""
    try:
        from services.embedding_link_candidate_service import (
            count_collision_sampling_actionable,
        )

        if not _domain_keys_for_phase("collision_sampling"):
            return 0
        return int(count_collision_sampling_actionable() or 0)
    except Exception as e:
        logger.debug("backlog collision_sampling count: %s", e)
        return 0


def _count_event_deduplication_pending() -> int:
    """
    Chronological events still needing a coreference pass (capped probe).

    Soft-cluster roots already have ``event_cluster_id`` and must not inflate
    Monitor backlog — only hard-merge members leave ``canonical_event_id`` null
    while still being "done" for soft linking.
    """
    conn = _get_conn()
    if not conn:
        return 0
    cap = max(100, env_int("EVENT_DEDUP_PENDING_PROBE_CAP", 5000))
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(
                """
                SELECT COUNT(*)::int FROM (
                    SELECT 1 FROM public.chronological_events
                    WHERE canonical_event_id IS NULL
                      AND event_cluster_id IS NULL
                    LIMIT %s
                ) t
                """,
                (cap,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog event_deduplication count: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_story_continuation_pending() -> int:
    """Events still due for a continuation pass (capped probe).

    Matches the idle probe / ``process_recent_events`` due predicate so Monitor
    does not treat backoff-deferred unlinked events as actionable backlog.
    """
    conn = _get_conn()
    if not conn:
        return 0
    cap = max(100, env_int("STORY_CONTINUATION_PENDING_PROBE_CAP", 5000))
    try:
        from services.story_continuation_service import continuation_recheck_due_sql

        due_sql, due_params = continuation_recheck_due_sql("ce")
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM (
                    SELECT 1 FROM public.chronological_events ce
                    WHERE (ce.storyline_id IS NULL OR ce.storyline_id = '')
                      AND ce.canonical_event_id IS NULL
                      AND {due_sql}
                    LIMIT %s
                ) t
                """,
                (*due_params, cap),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog story_continuation count: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_chronological_events_catchup_pending() -> int:
    """UIE-complete articles missing chronological_events (CE restore backlog)."""
    try:
        from services.chronological_events_catchup_service import (
            count_uie_without_chrono,
            is_enabled,
        )

        if not is_enabled():
            return 0
        stats = count_uie_without_chrono()
        return int((stats or {}).get("missing_ce_total") or (stats or {}).get("total") or 0)
    except Exception as e:
        logger.debug("backlog chronological_events_catchup count: %s", e)
        return 0


def _count_editorial_research_pending() -> int:
    """Packages waiting on Research modal drain (capped probe)."""
    try:
        from services.editorial_package_research_service import is_enabled, list_research_due

        if not is_enabled():
            return 0
        return len(list_research_due(limit=50))
    except Exception as e:
        logger.debug("backlog editorial_research_pass count: %s", e)
        return 0


def _count_editorial_narrative_pending() -> int:
    """Packages waiting on Narrative modal drain (capped probe)."""
    try:
        from services.editorial_package_narrative_service import is_enabled, list_narrative_due

        if not is_enabled():
            return 0
        return len(list_narrative_due(limit=50))
    except Exception as e:
        logger.debug("backlog editorial_narrative_pass count: %s", e)
        return 0


def _count_editorial_evidence_expand_pending() -> int:
    """Packages waiting on Narrative evidence-expand (capped probe)."""
    try:
        from services.editorial_package_evidence_expand_service import (
            is_enabled,
            list_evidence_expand_due,
        )

        if not is_enabled():
            return 0
        return len(list_evidence_expand_due(limit=50))
    except Exception as e:
        logger.debug("backlog editorial_evidence_expand_pass count: %s", e)
        return 0


def _count_editorial_reduction_pending() -> int:
    """Packages waiting on Reduction modal drain (capped probe)."""
    try:
        from services.editorial_package_reduction_service import is_enabled, list_reduction_due

        if not is_enabled():
            return 0
        return len(list_reduction_due(limit=50))
    except Exception as e:
        logger.debug("backlog editorial_reduction_pass count: %s", e)
        return 0


def _count_entity_organizer_pending() -> int:
    """Articles past unified intake with no link_indexer pass (organizer relationship work)."""
    conn = _get_conn()
    if not conn:
        return 0
    total = 0
    cap_per = max(50, env_int("ENTITY_ORGANIZER_PENDING_PROBE_CAP", 2000))
    try:
        from shared.pipeline_pass_marker import sql_article_pass_cleared

        for schema in _schemas_for_phase("entity_organizer"):
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM (
                        SELECT 1
                        FROM {schema}.articles a
                        WHERE ({sql_article_pass_cleared("unified_intake_extraction", "a")})
                          AND COALESCE(
                              (a.metadata #>> '{{pipeline,link_indexer,last_pass_at}}')::text,
                              ''
                          ) = ''
                        LIMIT %s
                    ) t
                    """,
                    (cap_per,),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("backlog entity_organizer count: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_stimulus_rag_pending() -> int:
    try:
        from services.rag_evidence_pull_service import count_evidence_pull_pending

        if not _domain_keys_for_phase("stimulus_rag"):
            return 0
        return int(count_evidence_pull_pending() or 0)
    except Exception:
        return 0


def _count_protein_harden_pending() -> int:
    try:
        from services.protein_harden_service import count_protein_harden_pending

        if not _domain_keys_for_phase("protein_harden"):
            return 0
        return int(count_protein_harden_pending() or 0)
    except Exception:
        return 0


def _count_graph_link_drift_pending() -> int:
    """Active links due for drift re-score when flag on."""
    try:
        from services.graph_link_drift_service import graph_link_drift_enabled

        if not graph_link_drift_enabled():
            return 0
    except Exception:
        return 0
    conn = _get_conn()
    if not conn:
        return 0
    try:
        from config.runtime import env_int, env_str

        conf_max = float(env_str("GRAPH_LINK_DRIFT_CONF_MAX", "0.70") or 0.70)
        days = max(1, env_int("GRAPH_LINK_DRIFT_DAYS", 14))
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.graph_connection_links
                WHERE status = 'active'
                  AND (
                    COALESCE(confidence, 0) < %s
                    OR last_scored_at IS NULL
                    OR last_scored_at < NOW() - (%s || ' days')::interval
                  )
                """,
                (conf_max, days),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("backlog graph_link_drift count: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _count_mention_resolution_pending() -> int:
    """CEM rows still past the mention_resolver watermark (actionable automation drain).

    Uses a dedicated connection so an aborted shared backlog transaction (earlier
    phase COUNT timeouts) cannot zero this metric.
    """
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
    except Exception:
        conn = None
    if not conn:
        return 0
    try:
        from config.investigation_tables import T_CONTEXT_ENTITY_MENTIONS, T_WATERMARKS

        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '15s'")
            cur.execute(
                f"SELECT last_value FROM {T_WATERMARKS} WHERE name = %s",
                ("mention_resolver",),
            )
            row = cur.fetchone()
            watermark = int(row[0]) if row and row[0] is not None else 0
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::bigint
                    FROM {T_CONTEXT_ENTITY_MENTIONS}
                    WHERE id > %s
                    """,
                    (watermark,),
                )
                return int(cur.fetchone()[0] or 0)
            except Exception:
                _rollback_quiet(conn)
                cur.execute("SET LOCAL statement_timeout = '5s'")
                return _capped_count_probe(
                    cur,
                    f"""
                    SELECT 1
                    FROM {T_CONTEXT_ENTITY_MENTIONS}
                    WHERE id > %s
                    """,
                    (watermark,),
                    cap=env_int("BACKLOG_MENTION_RESOLUTION_PROBE_CAP", 50001),
                    cache_key="mention_resolution",
                )
    except Exception as e:
        logger.debug("backlog mention_resolution count: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
    "storyline_review_agent",
    "storyline_membership_review",
    "storyline_hygiene",
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
    "embedding_link_candidates",
    "collision_sampling",
    "stimulus_rag",
    "protein_harden",
    "graph_link_drift_review",
    "mention_resolution",
    "entity_organizer",
    "event_deduplication",
    "story_continuation",
    "chronological_events_catchup",
    "editorial_research_pass",
    "editorial_narrative_pass",
    "editorial_evidence_expand_pass",
    "editorial_reduction_pass",
    "claim_evidence_appraisal",
})

# PhaseSpec high-churn phases union into skip set (keeps specs from drifting off SKIP_WHEN_EMPTY).
SKIP_WHEN_EMPTY = overlay_skip_when_empty(SKIP_WHEN_EMPTY)

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
    """Structural DB health signals for Monitor (entity graph size, claims/facts ratio, context orphans).

    Also surfaces the connection quality-loop queues: pending proposals, contested facts,
    and quarantined/refused patterns (count + oldest age in hours).
    """
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    out: dict = {
        "entity_relationships_estimate": 0,
        "extracted_claims_total": 0,
        "versioned_facts_total": 0,
        "claims_to_facts_ratio": 0.0,
        "claims_unpromoted": 0,
        "context_orphans": {},
        "pending_graph_proposals": 0,
        "pending_graph_proposals_oldest_hours": None,
        "contested_facts": 0,
        "contested_facts_oldest_hours": None,
        "quarantined_patterns": 0,
        "quarantined_patterns_oldest_hours": None,
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

            try:
                cur.execute(
                    """
                    SELECT COUNT(*)::int,
                           EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) / 3600.0
                    FROM intelligence.graph_connection_proposals
                    WHERE status = 'pending'
                    """
                )
                prow = cur.fetchone()
                out["pending_graph_proposals"] = int((prow[0] if prow else 0) or 0)
                if prow and prow[1] is not None and out["pending_graph_proposals"] > 0:
                    out["pending_graph_proposals_oldest_hours"] = round(float(prow[1]), 2)
            except Exception:
                pass

            try:
                cur.execute(
                    """
                    SELECT COUNT(*)::int,
                           EXTRACT(EPOCH FROM (NOW() - MIN(updated_at))) / 3600.0
                    FROM intelligence.versioned_facts
                    WHERE (metadata->>'verification_status') IN (
                        'contested', 'unverified', 'partially_verified'
                    )
                      AND (metadata->>'superseded_by_fact_id') IS NULL
                    """
                )
                crow = cur.fetchone()
                out["contested_facts"] = int((crow[0] if crow else 0) or 0)
                if crow and crow[1] is not None and out["contested_facts"] > 0:
                    out["contested_facts_oldest_hours"] = round(float(crow[1]), 2)
            except Exception:
                pass

            try:
                cur.execute(
                    """
                    SELECT COUNT(*)::int,
                           EXTRACT(EPOCH FROM (NOW() - MIN(updated_at))) / 3600.0
                    FROM intelligence.graph_pattern_refusals
                    WHERE status IN ('refuse', 'quarantine')
                    """
                )
                qrow = cur.fetchone()
                out["quarantined_patterns"] = int((qrow[0] if qrow else 0) or 0)
                if qrow and qrow[1] is not None and out["quarantined_patterns"] > 0:
                    out["quarantined_patterns_oldest_hours"] = round(float(qrow[1]), 2)
            except Exception:
                # Table may not exist until migration 263.
                try:
                    from services.graph_connection_queue_service import count_quarantined_patterns

                    out["quarantined_patterns"] = int(count_quarantined_patterns())
                except Exception:
                    pass

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
