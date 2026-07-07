"""
Monitor dimension backlog — delegates to phase queue_depth SSOT.

Dimension chips show throughput windows separately; backlog fields must match
phase_dashboard queue_depth for the mapped automation phase.
"""

from __future__ import annotations

from typing import Any

# Monitor dimension id → automation phase key (queue_depth SSOT)
DIMENSION_PHASE_MAP: dict[str, str] = {
    "articles_enriched": "content_enrichment",
    "contexts_claimed": "claim_extraction",
    "entity_profiles_touched": "entity_profile_build",
    "documents_extracted": "document_processing",
    "storylines_synthesized": "storyline_synthesis",
}


def get_dimension_backlog(dimension_id: str, queue_depths: dict[str, int] | None = None) -> int:
    """Backlog for a Monitor dimension chip (matches phase queue_depth)."""
    phase = DIMENSION_PHASE_MAP.get(dimension_id)
    if not phase:
        return 0
    if queue_depths is None:
        from shared.pipeline_queue_counts import get_all_phase_queue_depths

        queue_depths = get_all_phase_queue_depths()
    return int(queue_depths.get(phase) or 0)


def get_all_dimension_backlogs(queue_depths: dict[str, int] | None = None) -> dict[str, int]:
    """Backlog per dimension id."""
    if queue_depths is None:
        from shared.pipeline_queue_counts import get_all_phase_queue_depths

        queue_depths = get_all_phase_queue_depths()
    return {
        dim_id: int(queue_depths.get(phase) or 0)
        for dim_id, phase in DIMENSION_PHASE_MAP.items()
    }


def apply_dimension_backlogs(dimensions: list[dict[str, Any]], queue_depths: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """Set dimension backlog from phase queue_depth kernel (mutates copies)."""
    backlogs = get_all_dimension_backlogs(queue_depths)
    out: list[dict[str, Any]] = []
    for dim in dimensions:
        d = dict(dim)
        dim_id = str(d.get("id") or "")
        if dim_id in backlogs:
            d["backlog"] = backlogs[dim_id]
            d["backlog_phase"] = DIMENSION_PHASE_MAP.get(dim_id)
        out.append(d)
    return out
