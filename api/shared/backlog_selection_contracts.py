"""
Phase backlog ↔ selection contracts (Bucket A measurement).

Each entry documents the shared predicate that backlog counts and phase selection
must both use. ``assert_backlog_contracts()`` is a static check (no DB): it fails
when a count helper drifts off the shared eligibility module.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BacklogSelectionContract:
    phase: str
    """Human-readable predicate ownership."""
    selection_predicate: str
    """Module:function that computes Monitor/automation pending."""
    pending_counter: str
    """Substrings that must appear in the pending_counter source (shared gate)."""
    required_source_markers: tuple[str, ...]
    """Value-tier keys this phase can expose (subset of hot/actionable/long_tail/deferred)."""
    value_tiers: tuple[str, ...] = ("actionable",)


# High-fan-out / phantom-debt phases first — extend as more predicates are shared.
BACKLOG_SELECTION_CONTRACTS: tuple[BacklogSelectionContract, ...] = (
    BacklogSelectionContract(
        phase="entity_profile_build",
        selection_predicate="shared.entity_profile_eligibility.sql_entity_profile_selectable_for_build",
        pending_counter="services.backlog_metrics._count_entity_profile_build_backlog",
        required_source_markers=(
            "sql_entity_profile_selectable_for_build",
            "pipeline_domain_any_sql",
        ),
        value_tiers=("hot", "actionable", "long_tail"),
    ),
    BacklogSelectionContract(
        phase="claim_extraction",
        selection_predicate="services.claim_extraction_service.sql_claim_extraction_eligible",
        pending_counter="services.backlog_metrics._count_claim_extraction_backlog",
        required_source_markers=("sql_claim_extraction_eligible",),
        value_tiers=("actionable", "deferred", "inventory"),
    ),
    BacklogSelectionContract(
        phase="entity_extraction",
        selection_predicate="shared.article_signal_gate.sql_article_signal_full_lane_and",
        pending_counter="services.backlog_metrics._count_entity_extraction_pending",
        required_source_markers=(
            "sql_article_signal_full_lane_and",
            "sql_article_pass_null",
        ),
        value_tiers=("actionable", "deferred"),
    ),
    BacklogSelectionContract(
        phase="event_extraction",
        selection_predicate="shared.article_signal_gate.sql_article_signal_full_lane_and",
        pending_counter="services.backlog_metrics._count_event_extraction_pending",
        required_source_markers=(
            "sql_article_signal_full_lane_and",
            "timeline_processed",
        ),
        value_tiers=("actionable", "deferred"),
    ),
    BacklogSelectionContract(
        phase="storyline_discovery",
        selection_predicate="shared.article_signal_gate.sql_article_signal_full_lane_and",
        pending_counter="services.backlog_metrics._count_storyline_discovery_pending",
        required_source_markers=(
            "sql_article_signal_full_lane_and",
            "storyline_articles",
        ),
        value_tiers=("actionable",),
    ),
    BacklogSelectionContract(
        phase="proactive_detection",
        selection_predicate="shared.article_signal_gate.sql_article_signal_full_lane_and",
        pending_counter="services.backlog_metrics._count_proactive_detection_pending",
        required_source_markers=(
            "sql_article_signal_full_lane_and",
            "72 hours",
        ),
        value_tiers=("actionable",),
    ),
    BacklogSelectionContract(
        phase="storyline_assembly",
        selection_predicate="services.storyline_assembly_service.count_unlinked_articles",
        pending_counter="services.backlog_metrics._count_storyline_assembly_pending",
        required_source_markers=("count_unlinked_articles",),
        value_tiers=("actionable",),
    ),
    BacklogSelectionContract(
        phase="content_refinement_queue",
        selection_predicate="shared.content_refinement_queue_eligibility.sql_content_refinement_queue_pending",
        pending_counter="services.backlog_metrics._count_content_refinement_queue_pending",
        required_source_markers=("sql_content_refinement_queue_pending",),
        value_tiers=("actionable",),
    ),
    BacklogSelectionContract(
        phase="story_continuation",
        selection_predicate="services.story_continuation_service.continuation_recheck_due_sql",
        pending_counter="services.backlog_metrics._count_story_continuation_pending",
        required_source_markers=(
            "continuation_recheck_due_sql",
            "public.chronological_events",
        ),
        value_tiers=("actionable",),
    ),
)


def _resolve_attr(dotted: str) -> Callable[..., object]:
    mod_name, _, attr = dotted.rpartition(".")
    mod = __import__(mod_name, fromlist=[attr])
    return getattr(mod, attr)


def assert_backlog_contracts() -> list[str]:
    """
    Return list of failure messages (empty = all contracts pass).
    Safe for unit tests — does not open the database.
    """
    failures: list[str] = []
    for c in BACKLOG_SELECTION_CONTRACTS:
        try:
            fn = _resolve_attr(c.pending_counter)
        except Exception as e:
            failures.append(f"{c.phase}: cannot import {c.pending_counter}: {e}")
            continue
        try:
            src = inspect.getsource(fn)
        except OSError as e:
            failures.append(f"{c.phase}: cannot read source for {c.pending_counter}: {e}")
            continue
        for marker in c.required_source_markers:
            if marker not in src:
                failures.append(
                    f"{c.phase}: {c.pending_counter} missing marker {marker!r} "
                    f"(expected shared selection via {c.selection_predicate})"
                )
    return failures


def contract_catalog() -> list[dict[str, object]]:
    """JSON-serializable catalog for Monitor / ops docs."""
    return [
        {
            "phase": c.phase,
            "selection_predicate": c.selection_predicate,
            "pending_counter": c.pending_counter,
            "value_tiers": list(c.value_tiers),
            "required_source_markers": list(c.required_source_markers),
        }
        for c in BACKLOG_SELECTION_CONTRACTS
    ]
