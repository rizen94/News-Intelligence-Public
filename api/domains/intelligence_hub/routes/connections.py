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


@router.get("/findings")
async def list_connection_findings(
    status: str | None = Query("open"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Discovery queue rows (open / queued / dismissed)."""
    from services.connection_discovery_service import list_findings

    return list_findings(status=status, limit=limit, offset=offset)


@router.post("/findings/bridge")
async def bridge_findings_to_research(
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    """Manually queue high-confidence open findings into packages (opt-in).

    Unsupervised discovery no longer auto-bridges; prefer POST /api/research/assemble
    for idea-driven research packages.
    """
    from services.discovery_research_bridge_service import bridge_open_findings_to_research
    from config.runtime import env_bool

    # Explicit API call forces a one-shot bridge even when the env default is off.
    if not env_bool("DISCOVERY_RESEARCH_BRIDGE_ENABLED", False):
        # Temporarily allow via direct call path used by operators.
        import os

        prev = os.environ.get("DISCOVERY_RESEARCH_BRIDGE_ENABLED")
        os.environ["DISCOVERY_RESEARCH_BRIDGE_ENABLED"] = "true"
        try:
            return bridge_open_findings_to_research(limit=limit)
        finally:
            if prev is None:
                os.environ.pop("DISCOVERY_RESEARCH_BRIDGE_ENABLED", None)
            else:
                os.environ["DISCOVERY_RESEARCH_BRIDGE_ENABLED"] = prev
    return bridge_open_findings_to_research(limit=limit)


@router.get("/intake_brief")
async def get_discovery_intake_brief(
    hours: int = Query(72, ge=6, le=168),
    domain_key: str | None = Query(None),
    limit: int = Query(25, ge=5, le=60),
) -> dict[str, Any]:
    """72h articles/events/topics brief — launch pad for research assemble."""
    from services.discovery_intake_brief_service import build_intake_brief

    return build_intake_brief(hours=hours, domain_key=domain_key, limit_per_domain=limit)


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
