"""
Cheap per-phase "has work?" probes + exponential idle backoff for PopOS workers.

Why: PopOS phase workers used to call drain_phase() every cycle even when
eligibility SQL returned zero rows, which polluted Monitor run history and
burned DB/CPU. Widow's PipelineController already uses queue_depth; this module
gives remote workers the same idle-awareness without paying full COUNT(*) cost.

``phase_has_work(phase)`` uses LIMIT 1 / EXISTS probes that match backlog
eligibility SQL (same gates as ``backlog_metrics`` / drain selectors).
Fail-open on probe errors so a broken probe never permanently stalls a phase.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from config.runtime import env_float, env_str

logger = logging.getLogger(__name__)


def idle_gate_enabled() -> bool:
    return env_str("POPOS_IDLE_GATE_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def idle_backoff_base_seconds() -> float:
    try:
        return max(5.0, float(env_float("POPOS_IDLE_BACKOFF_BASE_SEC", 30.0)))
    except (TypeError, ValueError):
        return 30.0


def idle_backoff_max_seconds() -> float:
    try:
        return max(
            idle_backoff_base_seconds(),
            float(env_float("POPOS_IDLE_BACKOFF_MAX_SEC", 300.0)),
        )
    except (TypeError, ValueError):
        return 300.0


def idle_backoff_factor() -> float:
    try:
        return max(1.5, float(env_float("POPOS_IDLE_BACKOFF_FACTOR", 2.0)))
    except (TypeError, ValueError):
        return 2.0


def _probe_claim_extraction() -> bool:
    from services.claim_extraction_service import get_context_ids_without_claims

    return bool(get_context_ids_without_claims(limit=1))


def _probe_unified_intake_extraction() -> bool:
    from config.settings import unified_intake_extraction_enabled
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_schema_names_active
    from shared.pipeline_resource_policy import intake_extraction_suppressed
    from shared.unified_intake_backlog import (
        sql_actionable_unified_intake,
        sql_unified_intake_base_eligible,
        unified_intake_legacy_aware_backlog_enabled,
    )

    if not intake_extraction_suppressed() or not unified_intake_extraction_enabled():
        return False
    # Spine queue fast path
    try:
        from services.spine_work_queue_service import count_all_pending, spine_work_queues_enabled

        if spine_work_queues_enabled() and int(count_all_pending("unified_intake_extraction") or 0) > 0:
            return True
    except Exception:
        pass

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            for schema in get_pipeline_schema_names_active():
                if unified_intake_legacy_aware_backlog_enabled():
                    where = sql_actionable_unified_intake(schema, "a")
                else:
                    where = sql_unified_intake_base_eligible("a")
                cur.execute(
                    f"""
                    SELECT 1 FROM {schema}.articles a
                    WHERE {where}
                    LIMIT 1
                    """
                )
                if cur.fetchone():
                    return True
    return False


def _probe_topic_clustering() -> bool:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_schema_names_active

    try:
        from config.settings import topic_clustering_backlog_uses_pass_marker
        from domains.content_analysis.services.topic_clustering_service import (
            TopicClusteringService,
        )

        use_pass = bool(topic_clustering_backlog_uses_pass_marker())
    except Exception:
        use_pass = True
        TopicClusteringService = None  # type: ignore[misc, assignment]

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            for schema in get_pipeline_schema_names_active():
                if TopicClusteringService is not None:
                    ids = TopicClusteringService.select_pending_article_ids(
                        cur,
                        schema,
                        batch_size=1,
                        use_pass_marker=use_pass,
                    )
                    if ids:
                        return True
                else:
                    cur.execute(
                        f"""
                        SELECT 1 FROM {schema}.articles a
                        WHERE a.content IS NOT NULL
                          AND LENGTH(a.content) > 100
                          AND (
                            a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at' IS NULL
                            OR TRIM(COALESCE(
                                a.metadata->'pipeline'->'topic_clustering'->>'last_pass_at', ''
                            )) = ''
                          )
                        LIMIT 1
                        """
                    )
                    if cur.fetchone():
                        return True
    return False


def _probe_storyline_assembly() -> bool:
    from services.storyline_assembly_service import domains_needing_assembly

    return bool(domains_needing_assembly())


def _probe_content_enrichment() -> bool:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_schema_names_active

    try:
        from services.spine_work_queue_service import count_all_pending, spine_work_queues_enabled

        if spine_work_queues_enabled() and int(count_all_pending("content_enrichment") or 0) > 0:
            return True
    except Exception:
        pass

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            for schema in get_pipeline_schema_names_active():
                cur.execute(
                    f"""
                    SELECT 1 FROM {schema}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    LIMIT 1
                    """
                )
                if cur.fetchone():
                    return True
    return False


def _probe_entity_profile_build() -> bool:
    from services.entity_profile_builder_service import (
        _entity_profile_upstream_gate_for_select,
        sql_entity_profile_upstream_cleared_exists,
    )
    from shared.database.connection import get_db_connection_context
    from shared.entity_profile_eligibility import sql_entity_profile_needs_build
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    domain_sql, domain_keys = pipeline_domain_any_sql(
        "ep.domain_key", phase="entity_profile_build"
    )
    if not domain_keys:
        return False
    upstream_sql = ""
    if _entity_profile_upstream_gate_for_select():
        upstream_sql = f" AND {sql_entity_profile_upstream_cleared_exists()} "
    needs_build = sql_entity_profile_needs_build("ep")
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(
                f"""
                SELECT 1 FROM intelligence.entity_profiles ep
                WHERE {domain_sql}
                  AND {needs_build}
                  AND EXISTS (
                      SELECT 1 FROM intelligence.context_entity_mentions cem
                      WHERE cem.entity_profile_id = ep.id
                  )
                  {upstream_sql}
                LIMIT 1
                """,
                (domain_keys,),
            )
            return bool(cur.fetchone())


def _probe_spine_sql_tail() -> bool:
    """Prefer spine_tail_queue depth; fall back to True (fail-open) if unavailable."""
    try:
        from services.spine_work_queue_service import count_all_pending, spine_work_queues_enabled

        if spine_work_queues_enabled():
            return int(count_all_pending("spine_sql_tail") or 0) > 0
    except Exception:
        pass
    try:
        from shared.pipeline_queue_counts import get_phase_queue_depth

        return int(get_phase_queue_depth("spine_sql_tail") or 0) > 0
    except Exception:
        return True


def _probe_editorial_research() -> bool:
    from services.editorial_package_research_service import is_enabled, list_research_due

    return bool(is_enabled() and list_research_due(limit=1))


def _probe_editorial_narrative() -> bool:
    from services.editorial_package_narrative_service import is_enabled, list_narrative_due

    return bool(is_enabled() and list_narrative_due(limit=1))


def _probe_editorial_reduction() -> bool:
    from services.editorial_package_reduction_service import is_enabled, list_reduction_due

    return bool(is_enabled() and list_reduction_due(limit=1))


def _probe_chronological_events_catchup() -> bool:
    from services.chronological_events_catchup_service import (
        count_uie_without_chrono,
        is_enabled,
    )

    if not is_enabled():
        return False
    stats = count_uie_without_chrono()
    return int((stats or {}).get("missing_ce_total") or (stats or {}).get("total") or 0) > 0


def _probe_story_continuation() -> bool:
    from shared.database.connection import get_db_connection
    from shared.domain_processing_mode import domain_runs_phase
    from shared.domain_registry import pipeline_url_schema_pairs

    schemas = [
        sch
        for dk, sch in pipeline_url_schema_pairs()
        if domain_runs_phase(dk, "story_continuation")
    ]
    if not schemas:
        return False
    conn = get_db_connection()
    if not conn:
        return True
    from services.story_continuation_service import continuation_recheck_due_sql

    due_sql, due_params = continuation_recheck_due_sql("ce")
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            # Any schema-scoped unlinked CE that is off recheck backoff counts as work;
            # mirrors process_recent_events, else the probe reports work every cycle.
            for schema in schemas:
                cur.execute(
                    f"""
                    SELECT 1
                    FROM public.chronological_events ce
                    WHERE (ce.storyline_id IS NULL OR ce.storyline_id = '')
                      AND ce.canonical_event_id IS NULL
                      AND ce.source_article_id IS NOT NULL
                      AND {due_sql}
                      AND EXISTS (
                            SELECT 1 FROM {schema}.articles a
                            WHERE a.id = ce.source_article_id
                      )
                    LIMIT 1
                    """,
                    due_params,
                )
                if cur.fetchone() is not None:
                    return True
            return False
    except Exception:
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _probe_content_refinement_queue() -> bool:
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return True
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '3s'")
            cur.execute(
                """
                SELECT 1 FROM intelligence.content_refinement_queue
                WHERE status = 'pending'
                LIMIT 1
                """
            )
            return cur.fetchone() is not None
    except Exception:
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass


_PROBES: dict[str, Callable[[], bool]] = {
    "claim_extraction": _probe_claim_extraction,
    "unified_intake_extraction": _probe_unified_intake_extraction,
    "topic_clustering": _probe_topic_clustering,
    "storyline_assembly": _probe_storyline_assembly,
    "content_enrichment": _probe_content_enrichment,
    "entity_profile_build": _probe_entity_profile_build,
    "spine_sql_tail": _probe_spine_sql_tail,
    "editorial_research_pass": _probe_editorial_research,
    "editorial_narrative_pass": _probe_editorial_narrative,
    "editorial_reduction_pass": _probe_editorial_reduction,
    "chronological_events_catchup": _probe_chronological_events_catchup,
    "story_continuation": _probe_story_continuation,
    "content_refinement_queue": _probe_content_refinement_queue,
}


def phase_has_work(phase: str) -> bool:
    """
    Return True if ``phase`` has at least one actionable row (cheap probe).

    Unknown phases fail-open (True) so new drains are not silently skipped.
    Probe exceptions also fail-open.
    """
    name = (phase or "").strip()
    if not name:
        return False
    probe = _PROBES.get(name)
    if probe is None:
        return True
    try:
        return bool(probe())
    except Exception as exc:
        logger.warning("phase_has_work(%s) probe failed (fail-open): %s", name, exc)
        return True


def drain_result_had_work(result: object) -> bool:
    """True when a drain_phase return payload indicates real work."""
    if not isinstance(result, dict):
        return False
    if result.get("skipped") in ("idle", "backoff", "no_domains_above_unlinked_threshold"):
        return False
    if result.get("frequency_skip_only"):
        return False
    if result.get("error"):
        return False
    for key in (
        "processed",
        "claims_inserted",
        "profiles_updated",
        "articles_processed",
        "articles_linked",
        "llm_processed",
        "legacy_backfilled",
        "batches",
        "saved_total",
        "changed_total",
        "linked",
        "checked",
    ):
        val = result.get(key)
        if isinstance(val, int) and val > 0:
            # batches alone is not enough if claims_inserted is 0 — handled below
            if key == "batches":
                continue
            return True
    # Nested storyline_assembly domains payload
    domains = result.get("domains")
    if isinstance(domains, dict) and domains:
        linked = 0
        for payload in domains.values():
            if isinstance(payload, dict):
                linked += int(payload.get("articles_linked") or 0)
        return linked > 0
    # Explicit zero-work drain with batches=0 / claims_inserted=0
    if "claims_inserted" in result and int(result.get("claims_inserted") or 0) == 0:
        return False
    if "processed" in result and int(result.get("processed") or 0) == 0:
        return False
    return False


class PhaseIdleBackoff:
    """
    Per-phase exponential backoff after idle probes / empty drains.

    Empty → wait base * factor^(streak-1), capped at max.
    Work found → reset streak so the next idle starts at base again.
    """

    def __init__(
        self,
        *,
        base_seconds: float | None = None,
        max_seconds: float | None = None,
        factor: float | None = None,
    ) -> None:
        self.base = float(base_seconds if base_seconds is not None else idle_backoff_base_seconds())
        self.max = float(max_seconds if max_seconds is not None else idle_backoff_max_seconds())
        self.factor = float(factor if factor is not None else idle_backoff_factor())
        self._until_mono: dict[str, float] = {}
        self._streak: dict[str, int] = {}

    def remaining_seconds(self, phase: str, *, now: float | None = None) -> float:
        mono = time.monotonic() if now is None else now
        until = self._until_mono.get(phase, 0.0)
        return max(0.0, until - mono)

    def should_skip(self, phase: str, *, now: float | None = None) -> tuple[bool, float]:
        rem = self.remaining_seconds(phase, now=now)
        return rem > 0.0, rem

    def mark_idle(
        self,
        phase: str,
        *,
        now: float | None = None,
        delay_seconds: float | None = None,
    ) -> float:
        mono = time.monotonic() if now is None else now
        streak = int(self._streak.get(phase, 0) or 0) + 1
        self._streak[phase] = streak
        if delay_seconds is not None and float(delay_seconds) > 0:
            # Phase-hinted delays (assembly freq window) may exceed default max.
            delay = max(self.base, float(delay_seconds))
        else:
            delay = min(self.max, self.base * (self.factor ** (streak - 1)))
        self._until_mono[phase] = mono + delay
        return delay

    def mark_work(self, phase: str) -> None:
        self._streak.pop(phase, None)
        self._until_mono.pop(phase, None)

    def streak(self, phase: str) -> int:
        return int(self._streak.get(phase, 0) or 0)


def decide_phase_action(
    phase: str,
    backoff: PhaseIdleBackoff,
    *,
    enabled: bool | None = None,
) -> dict[str, object]:
    """
    Decide whether to drain, skip (backoff), or skip (idle probe).

    Returns dict with keys: action ('drain'|'skip_backoff'|'skip_idle'),
    delay_sec, has_work (optional).
    """
    if enabled is None:
        enabled = idle_gate_enabled()
    if not enabled:
        return {"action": "drain", "delay_sec": 0.0}

    skip_bo, rem = backoff.should_skip(phase)
    if skip_bo:
        return {"action": "skip_backoff", "delay_sec": rem, "has_work": False}

    has = phase_has_work(phase)
    if not has:
        delay = backoff.mark_idle(phase)
        return {"action": "skip_idle", "delay_sec": delay, "has_work": False}

    backoff.mark_work(phase)
    return {"action": "drain", "delay_sec": 0.0, "has_work": True}
