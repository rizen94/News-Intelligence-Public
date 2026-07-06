"""Backward-compatible shim — use nri_core.services.integration."""

from nri_core.services.integration import (  # noqa: F401
    audit_bridge_qa,
    get_context_intel,
    get_entity_bridge,
    get_ftm_cache_dataset_counts,
    get_hypothesis,
    get_investigation_health,
    get_nri_health,
    get_resolution_stats,
    list_hypotheses,
    list_loop_runs,
    list_parked_cross_domain,
    list_parked_resolution,
    list_resolved_mentions,
    list_spine_entities,
    match_spine,
    review_parked,
)

__all__ = [
    "audit_bridge_qa",
    "get_context_intel",
    "get_entity_bridge",
    "get_ftm_cache_dataset_counts",
    "get_hypothesis",
    "get_investigation_health",
    "get_nri_health",
    "get_resolution_stats",
    "list_hypotheses",
    "list_loop_runs",
    "list_parked_cross_domain",
    "list_parked_resolution",
    "list_resolved_mentions",
    "list_spine_entities",
    "match_spine",
    "review_parked",
]
