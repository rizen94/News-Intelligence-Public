"""
Critical-path phase handoffs — request the next owner after a batch succeeds.

Scheduling is primarily backlog-polled; ``depends_on`` is advisory. These helpers
push work down the assembly rail so stages do not wait solely on the next interval:

  UIE / CE catchup → event_deduplication → story_continuation → editorial_*

Do not expand chemistry beaker kicks here; keep matching → storyline → packages.

When UIE runs on the PopOS remote worker (``REMOTE_PHASE_WORKER_OWNED_PHASES``),
Widow never executes ``_execute_unified_intake_extraction`` — use
``nudge_event_rail_after_uie`` (HTTP trigger) from the worker instead.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Prevent modal handoffs from stacking while a drain is already in flight.
_HANDOFF_DEDUP_PHASES = frozenset(
    {
        "chronological_events_catchup",
        "event_deduplication",
        "story_continuation",
        "editorial_research_pass",
        "editorial_narrative_pass",
        "editorial_reduction_pass",
    }
)


def _safe_request(automation: Any, phase: str) -> None:
    if automation is None or not phase:
        return
    try:
        skip = getattr(automation, "_should_skip_redundant_phase_request", None)
        if callable(skip) and skip(phase):
            return
        if phase in _HANDOFF_DEDUP_PHASES:
            inflight = getattr(automation, "_phase_pipeline_inflight", None)
            if callable(inflight) and int(inflight(phase) or 0) > 0:
                return
        automation.request_phase(phase)
    except Exception as e:
        logger.debug("pipeline_handoff request %s: %s", phase, e)


def _safe_request_editorial(automation: Any, phase: str, *, reason: str = "pipeline_handoff") -> None:
    """Route editorial drains to PopOS when Widow schedule is remote-owned."""
    if automation is None or not phase:
        return
    try:
        from shared.remote_phase_worker import phase_owned_by_remote_worker

        if phase_owned_by_remote_worker(phase):
            from shared.popos_editorial_wake import request_popos_editorial_wake

            request_popos_editorial_wake([phase], reason=reason)
            logger.info("PopOS editorial wake requested: %s (%s)", phase, reason)
            return
    except Exception as e:
        logger.debug("editorial remote handoff %s: %s", phase, e)
    _safe_request(automation, phase)


def route_target_counts(stats: dict[str, Any] | None) -> dict[str, int]:
    """Count per-result route_target from editorial batch stats."""
    out = {"reduction": 0, "research": 0, "narrative": 0, "editor": 0, "stay": 0}
    if not isinstance(stats, dict):
        return out
    for row in stats.get("results") or []:
        if not isinstance(row, dict):
            continue
        t = str(row.get("route_target") or "").strip().lower()
        if t in out:
            out[t] += 1
    return out


def after_unified_intake(automation: Any, *, articles_processed: int = 0) -> None:
    """After a UIE batch on Widow: restore missing CE if needed, then coreference."""
    if int(articles_processed or 0) <= 0:
        return
    try:
        from services.chronological_events_catchup_service import (
            count_uie_without_chrono,
            is_enabled as catchup_enabled,
        )

        if catchup_enabled():
            wd = count_uie_without_chrono()
            if int((wd or {}).get("missing_ce_total") or (wd or {}).get("total") or 0) > 0:
                _safe_request(automation, "chronological_events_catchup")
    except Exception as e:
        logger.debug("after_unified_intake catchup probe: %s", e)
    _safe_request(automation, "event_deduplication")
    # Drain vault note queue after extract fan-out
    try:
        from services.vault_notes_fanout_service import vault_notes_pipeline_enabled
        from services.vault_update_queue_service import count_vault_update_pending

        if vault_notes_pipeline_enabled():
            pending = count_vault_update_pending()
            if int(pending.get("pending") or 0) > 0:
                _safe_request(automation, "vault_notes_writer")
    except Exception as e:
        logger.debug("after_unified_intake vault_notes_writer: %s", e)


def after_chronological_events_catchup(automation: Any, *, saved_total: int = 0) -> None:
    """After CE restore writes rows, stir coreference."""
    if int(saved_total or 0) <= 0:
        return
    _safe_request(automation, "event_deduplication")


def after_event_deduplication(
    automation: Any,
    *,
    merged: int = 0,
    soft_links: int = 0,
    hard_merges: int = 0,
) -> None:
    """After coref merges/links, run storyline continuation attach."""
    if int(merged or 0) + int(soft_links or 0) + int(hard_merges or 0) <= 0:
        return
    _safe_request(automation, "story_continuation")


def _stale_morning_slate_needs_wake(*, min_novel: int = 3, max_age_hours: int = 36) -> bool:
    """True when living expansions are missing/stale and novel episode work exists."""
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    except Exception:
        return False
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXTRACT(EPOCH FROM (NOW() - MAX(note_updated_at)))/3600.0
                    FROM intelligence.vault_notes
                    WHERE note_type = 'expansion'
                      AND COALESCE(lifecycle, 'living') = 'living'
                      AND note_updated_at >= NOW() - INTERVAL '7 days'
                    """
                )
                row = cur.fetchone()
                max_age = float(row[0]) if row and row[0] is not None else 999.0
                stale = max_age >= float(max_age_hours)
                if not stale:
                    cur.execute(
                        """
                        SELECT COUNT(*)::int FROM intelligence.vault_notes
                        WHERE note_type = 'expansion'
                          AND COALESCE(lifecycle, 'living') = 'living'
                          AND note_updated_at >= NOW() - INTERVAL '7 days'
                        """
                    )
                    if int((cur.fetchone() or [0])[0] or 0) > 0:
                        return False
                    stale = True
                novel = 0
                for dk in get_pipeline_active_domain_keys():
                    sch = resolve_domain_schema(dk)
                    # Novelty: recent bag articles OR recent EEL admits on active episodes.
                    cur.execute(
                        f"""
                        SELECT COUNT(*)::int
                        FROM {sch}.storylines s
                        WHERE s.merged_into_id IS NULL
                          AND COALESCE(s.status, '') = 'active'
                          AND (
                            EXISTS (
                              SELECT 1 FROM {sch}.storyline_articles sa
                              JOIN {sch}.articles a ON a.id = sa.article_id
                              WHERE sa.storyline_id = s.id
                                AND COALESCE(a.published_at, a.created_at)
                                    >= NOW() - INTERVAL '2 days'
                            )
                            OR EXISTS (
                              SELECT 1 FROM intelligence.event_episode_links eel
                              WHERE eel.episode_id = s.id
                                AND eel.domain_key = %s
                                AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                                AND eel.created_at >= NOW() - INTERVAL '2 days'
                            )
                          )
                        """,
                        (dk,),
                    )
                    novel += int((cur.fetchone() or [0])[0] or 0)
                    if novel >= int(min_novel):
                        break
                # Hard freshness floor: if slate is >72h cold, nudge even with novel=0
                # (prime itself remains SKIP_WHEN-compatible / no on-read LLM).
                if stale and max_age >= 72.0:
                    return True
                return bool(stale and novel >= int(min_novel))
    except Exception as e:
        logger.debug("stale_morning_slate_needs_wake: %s", e)
        return False


def after_story_continuation(automation: Any, *, linked: int = 0) -> None:
    """After event→storyline attaches, drain Research packages; nudge stale morning prime."""
    if int(linked or 0) > 0:
        _safe_request_editorial(
            automation, "editorial_research_pass", reason="after_story_continuation"
        )
    # A2: cache-first stale-slate wake even when this pass linked 0 (SKIP_WHEN inside prime).
    try:
        if _stale_morning_slate_needs_wake():
            _safe_request(automation, "vault_morning_prime")
            logger.info("pipeline_handoff vault_morning_prime (stale slate after story_continuation)")
    except Exception as e:
        logger.debug("after_story_continuation morning wake: %s", e)


def after_connection_discovery(
    automation: Any,
    *,
    bridged: int = 0,
    research_queued: int = 0,
    narrative_queued: int = 0,
) -> None:
    """After discovery bridge queues packages, wake PopOS editorial drains."""
    if (
        int(bridged or 0) <= 0
        and int(research_queued or 0) <= 0
        and int(narrative_queued or 0) <= 0
    ):
        return
    if int(research_queued or 0) > 0:
        _safe_request_editorial(
            automation, "editorial_research_pass", reason="after_connection_discovery"
        )
    if int(narrative_queued or 0) > 0:
        _safe_request_editorial(
            automation, "editorial_narrative_pass", reason="after_connection_discovery"
        )
    if int(research_queued or 0) <= 0 and int(narrative_queued or 0) <= 0:
        from shared.popos_editorial_wake import request_popos_editorial_wake

        request_popos_editorial_wake(
            ["editorial_research_pass", "editorial_narrative_pass"],
            reason="after_connection_discovery",
        )


def after_editorial_research(
    automation: Any,
    *,
    processed: int = 0,
    routed_to_reduction: int = 0,
) -> None:
    """Wake Reduction only when Research actually routed packages there."""
    del processed  # kept for call-site compatibility
    if int(routed_to_reduction or 0) <= 0:
        return
    _safe_request_editorial(automation, "editorial_reduction_pass", reason="after_editorial_research")


def after_editorial_narrative(
    automation: Any,
    *,
    processed: int = 0,
    routed_to_reduction: int = 0,
) -> None:
    """Wake evidence-expand (when enabled) then Reduction for Narrative routes."""
    del processed
    if int(routed_to_reduction or 0) <= 0:
        return
    try:
        from services.editorial_package_evidence_expand_service import is_enabled as expand_on

        if expand_on():
            _safe_request_editorial(
                automation, "editorial_evidence_expand_pass", reason="after_editorial_narrative"
            )
            return
    except Exception:
        pass
    _safe_request_editorial(automation, "editorial_reduction_pass", reason="after_editorial_narrative")


def after_editorial_evidence_expand(
    automation: Any,
    *,
    processed: int = 0,
    routed_to_reduction: int = 0,
) -> None:
    """Wake Reduction after evidence-expand attaches/synthesizes."""
    del processed
    if int(routed_to_reduction or 0) <= 0:
        return
    _safe_request(automation, "editorial_reduction_pass")


def after_editorial_reduction(
    automation: Any,
    *,
    processed: int = 0,
    routed_to_research: int = 0,
    routed_to_narrative: int = 0,
) -> None:
    """Wake Research/Narrative only for packages Reduction routed back."""
    del processed
    if int(routed_to_research or 0) > 0:
        _safe_request_editorial(automation, "editorial_research_pass", reason="after_editorial_reduction")
    if int(routed_to_narrative or 0) > 0:
        _safe_request_editorial(automation, "editorial_narrative_pass", reason="after_editorial_reduction")


def nudge_widow_phases(phases: list[str], *, reason: str = "remote_handoff") -> int:
    """HTTP-trigger Widow AutomationManager phases (PopOS worker → Widow API).

    Returns number of phases that accepted the trigger (2xx). Soft-fails on errors.
    """
    from config.runtime import env_str

    base = (env_str("WIDOW_API_BASE", "") or env_str("NI_API_BASE", "") or "").strip().rstrip("/")
    if not base:
        base = "http://192.168.93.101:8000"
    url = f"{base}/api/system_monitoring/monitoring/trigger_phase"
    ok = 0
    try:
        import urllib.error
        import urllib.request
        import json as _json
    except Exception as e:
        logger.debug("nudge_widow_phases import: %s", e)
        return 0
    for phase in phases:
        name = (phase or "").strip()
        if not name:
            continue
        body = _json.dumps({"phase": name, "reason": reason}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                if 200 <= int(getattr(resp, "status", 200) or 200) < 300:
                    ok += 1
        except Exception as e:
            logger.debug("nudge_widow_phases %s: %s", name, e)
    return ok


def nudge_event_rail_after_uie(*, articles_processed: int = 0) -> int:
    """PopOS UIE completion → wake CE catchup + coreference on Widow."""
    if int(articles_processed or 0) <= 0:
        return 0
    phases = ["event_deduplication"]
    try:
        from services.chronological_events_catchup_service import (
            count_uie_without_chrono,
            is_enabled as catchup_enabled,
        )

        if catchup_enabled():
            wd = count_uie_without_chrono()
            if int((wd or {}).get("missing_ce_total") or (wd or {}).get("total") or 0) > 0:
                phases.insert(0, "chronological_events_catchup")
    except Exception as e:
        logger.debug("nudge_event_rail catchup probe: %s", e)
    return nudge_widow_phases(phases, reason="after_unified_intake_remote")
