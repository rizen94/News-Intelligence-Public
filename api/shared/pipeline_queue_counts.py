"""
Phase queue depth kernel — single entry for actionable per-phase counts.

Wraps backlog_metrics eligibility SQL; spine queue depth is exposed separately
(never folded into queue_depth). See pipeline_queue_vocabulary.py.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.pipeline_queue_vocabulary import (
    UnifiedIntakeBreakdown,
    unified_intake_breakdown_from_stats,
)

logger = logging.getLogger(__name__)

_SPINE_QUEUE_PHASES = frozenset({"content_enrichment", "unified_intake_extraction"})


def get_all_phase_queue_depths_uncached() -> dict[str, int]:
    """Uncached actionable queue depths per phase (same semantics as get_all_pending_counts)."""
    from services.backlog_metrics import _get_raw_pending_counts

    return dict(_get_raw_pending_counts())


def get_all_phase_queue_depths() -> dict[str, int]:
    """Cached actionable queue depths (delegates to backlog_metrics cache)."""
    from services.backlog_metrics import get_all_pending_counts

    return dict(get_all_pending_counts())


def get_phase_queue_depth(phase: str) -> int:
    """Actionable queue depth for one automation phase."""
    return int(get_all_phase_queue_depths().get(phase) or 0)


def get_spine_queue_depth(phase: str) -> int:
    """Spine work-queue table pending rows (operational; not operator ETA)."""
    if phase not in _SPINE_QUEUE_PHASES:
        return 0
    try:
        from services.spine_work_queue_service import count_all_pending, spine_work_queues_enabled

        if not spine_work_queues_enabled():
            return 0
        return int(count_all_pending(phase) or 0)
    except Exception as exc:
        logger.debug("get_spine_queue_depth %s: %s", phase, exc)
        return 0


def get_unified_intake_breakdown() -> UnifiedIntakeBreakdown:
    """Unified intake actionable vs inventory vs spine queue depth."""
    from shared.unified_intake_backlog import get_unified_intake_backlog_stats

    stats = get_unified_intake_backlog_stats()
    spine = get_spine_queue_depth("unified_intake_extraction")
    return unified_intake_breakdown_from_stats(stats, spine_queue=spine)


def verify_unified_intake_alignment(pending: dict[str, int] | None = None) -> dict[str, Any]:
    """
    Return alignment check for unified intake queue_depth vs actionable SQL.
    Used by queue_audit and CI verify script.
    """
    if pending is None:
        pending = get_all_phase_queue_depths()
    breakdown = get_unified_intake_breakdown()
    queue_depth = int(pending.get("unified_intake_extraction") or 0)
    actionable = int(breakdown["actionable_unified_intake"])
    return {
        "queue_depth": queue_depth,
        "actionable_unified_intake": actionable,
        "inventory_missing_pass": breakdown["inventory_missing_pass"],
        "legacy_backfill_eligible": breakdown["legacy_backfill_eligible"],
        "spine_queue_depth": breakdown["spine_queue_depth"],
        "matches_actionable_sql": queue_depth == actionable,
    }
