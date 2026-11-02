"""
Nightly sequential drain — definitive idle detection per automation phase.

* **Backlog-backed phases** — ``phase_has_pending_work`` reads ``get_all_pending_counts()`` (same\
  source as the daytime scheduler). When a phase’s raw count is 0, that phase is done for this drain.
* **Formerly single-pass phases** — once ran exactly one shot per sweep. They now also loop on their own\
  backlog metric until zero, so all phases share the same drain-to-zero semantics regardless of category.
  ``is_single_pass_phase()`` remains for backward compatibility with phase categorization; it no longer\
  implies "runs once."

"""

from __future__ import annotations

import os
from typing import Any

_DEFAULT_SINGLE_PASS = (
    "pattern_recognition",
    "pattern_matching",
    "fact_verification",
    "event_deduplication",
    "event_coherence_review",
    "cross_domain_synthesis",
    "entity_organizer",
    "narrative_thread_build",
    "story_continuation",
    "watchlist_alerts",
    "storyline_enrichment",
)


def _single_pass_phases() -> frozenset[str]:
    raw = os.environ.get(
        "NIGHTLY_SEQUENTIAL_SINGLE_PASS_PHASES",
        ",".join(_DEFAULT_SINGLE_PASS),
    )
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def is_single_pass_phase(phase_name: str) -> bool:
    """Phases formerly categorized as single-pass. Now drain to zero like all other phases."""
    return phase_name in _single_pass_phases()


def phase_has_pending_work(phase_name: str) -> bool:
    """
    True when backlog metrics indicate this phase still has pending items.

    Unknown phase names return False so the drain does not loop forever.\
    This function is now used for ALL phases (including formerly single-pass).
    """
    from services.backlog_metrics import get_all_pending_counts, invalidate_backlog_metrics_cache

    invalidate_backlog_metrics_cache()
    counts = get_all_pending_counts()
    if phase_name not in counts:
        return False
    return int(counts[phase_name] or 0) > 0


def sequential_metric_backlog(phase_names: list[str], pending: dict[str, Any]) -> bool:
    """True if any non-single-pass sequential phase has pending work in ``pending`` snapshot."""
    for ph in phase_names:
        if is_single_pass_phase(ph):
            continue
        if int(pending.get(ph) or 0) > 0:
            return True
    return False
