"""Connection discovery API — agent-friendly canned queries."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services import connection_query_service as cq
from services import event_reconciliation_service as reconciliation
from services.linkage_coverage_service import get_linkage_coverage

router = APIRouter(prefix="/api/connections", tags=["Connection discovery"])


@router.get("/coverage")
async def get_connections_coverage() -> dict[str, Any]:
    """Linkage coverage: EEL %, orphan clusters, TE bridge %, dup-title groups."""
    return get_linkage_coverage()


@router.get("/orphan_summary")
async def get_orphan_summary() -> dict[str, Any]:
    """Compact orphan / linkage gap summary for agents."""
    return cq.orphan_summary()


@router.get("/events/{event_id}")
async def get_event_connections(event_id: int) -> dict[str, Any]:
    """Chronological event → EEL → episode → narrative thread + cluster peers."""
    return cq.event_connections(event_id)


@router.get("/entities/{entity_profile_id}")
async def get_entity_graph(
    entity_profile_id: int,
    limit: int = Query(40, ge=5, le=100),
) -> dict[str, Any]:
    """Entity profile → facts, storylines (SEI), graph edges."""
    return cq.entity_graph(entity_profile_id, limit=limit)


@router.get("/chains/tracked_events/{tracked_event_id}")
async def get_tracked_event_connection_chain(tracked_event_id: int) -> dict[str, Any]:
    """TE → CE cluster → episode (EEL) → narrative thread."""
    row = reconciliation.get_connection_chain_for_tracked_event(tracked_event_id)
    if not row:
        return {"found": False, "tracked_event_id": tracked_event_id}
    return row


@router.post("/graph/refresh")
async def refresh_graph_projection(
    domain_key: str | None = Query(None),
    limit: int = Query(500, ge=10, le=5000),
    dry_run: bool = Query(False),
) -> dict[str, Any]:
    """Project EEL + narrative_threads + SEI into graph_connection_links."""
    return cq.refresh_assembly_graph_edges(
        domain_key=domain_key,
        limit=limit,
        apply=not dry_run,
    )
