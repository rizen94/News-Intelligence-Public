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


def after_story_continuation(automation: Any, *, linked: int = 0) -> None:
    """After event→storyline attaches, drain Research packages."""
    if int(linked or 0) <= 0:
        return
    _safe_request(automation, "editorial_research_pass")


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
    _safe_request(automation, "editorial_reduction_pass")


def after_editorial_narrative(
    automation: Any,
    *,
    processed: int = 0,
    routed_to_reduction: int = 0,
) -> None:
    """Wake Reduction only when Narrative actually routed packages there."""
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
        _safe_request(automation, "editorial_research_pass")
    if int(routed_to_narrative or 0) > 0:
        _safe_request(automation, "editorial_narrative_pass")


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
