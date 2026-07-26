"""
Critical-path phase handoffs — request the next owner after a batch succeeds.

Scheduling is primarily backlog-polled; ``depends_on`` is advisory. These helpers
push work down the assembly rail so stages do not wait solely on the next interval:

  UIE / CE catchup → event_deduplication → story_continuation → editorial_* 

Do not expand chemistry beaker kicks here; keep matching → storyline → packages.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _safe_request(automation: Any, phase: str) -> None:
    if automation is None or not phase:
        return
    try:
        skip = getattr(automation, "_should_skip_redundant_phase_request", None)
        if callable(skip) and skip(phase):
            return
        automation.request_phase(phase)
    except Exception as e:
        logger.debug("pipeline_handoff request %s: %s", phase, e)


def after_unified_intake(automation: Any, *, articles_processed: int = 0) -> None:
    """After a UIE batch: restore missing CE if needed, then coreference."""
    if int(articles_processed or 0) <= 0:
        return
    try:
        from services.chronological_events_catchup_service import (
            count_uie_without_chrono,
            is_enabled as catchup_enabled,
        )

        if catchup_enabled():
            wd = count_uie_without_chrono()
            if int((wd or {}).get("total") or 0) > 0:
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


def after_editorial_research(automation: Any, *, processed: int = 0) -> None:
    """Research may route packages into Reduction — wake that drain."""
    if int(processed or 0) <= 0:
        return
    _safe_request(automation, "editorial_reduction_pass")


def after_editorial_narrative(automation: Any, *, processed: int = 0) -> None:
    """Narrative may route packages into Reduction — wake that drain."""
    if int(processed or 0) <= 0:
        return
    _safe_request(automation, "editorial_reduction_pass")


def after_editorial_reduction(automation: Any, *, processed: int = 0) -> None:
    """Reduction routes back to Research/Narrative — wake both drains."""
    if int(processed or 0) <= 0:
        return
    _safe_request(automation, "editorial_research_pass")
    _safe_request(automation, "editorial_narrative_pass")
