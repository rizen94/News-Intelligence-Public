"""
Tracking discovery + vault automation API routes.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from services import event_reconciliation_service as reconciliation
from services import tracking_discovery_service as discovery

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Tracking & reconciliation"])


@router.get("/tracking/discovery")
async def get_tracking_discovery(
    since: str | None = Query(None, description="ISO timestamp; defaults to vault cursor or 7d"),
    domain_keys: str | None = Query(None, description="Comma-separated domain keys"),
    include_vault_reconcile: bool = Query(True),
) -> dict[str, Any]:
    """Deterministic tracking discovery (ports news-tracking-discovery.md passes 1–5)."""
    keys = [k.strip() for k in domain_keys.split(",") if k.strip()] if domain_keys else None
    return discovery.run_tracking_discovery(
        since=since,
        domain_keys=keys,
        include_vault_reconcile=include_vault_reconcile,
    )


@router.get("/event_reconciliation")
async def get_event_reconciliation(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    domain_key: str | None = Query(None),
    since_days: int = Query(14, ge=1, le=365),
) -> dict[str, Any]:
    """Read-only tracked_events ↔ chronological_events ↔ storyline reconciliation."""
    return reconciliation.list_event_reconciliation(
        limit=limit,
        offset=offset,
        domain_key=domain_key,
        since_days=since_days,
    )


@router.get("/event_reconciliation/tracked_events/{tracked_event_id}")
async def get_event_reconciliation_for_tracked(tracked_event_id: int) -> dict[str, Any]:
    row = reconciliation.get_reconciliation_for_tracked_event(tracked_event_id)
    if not row:
        return {"found": False, "tracked_event_id": tracked_event_id}
    return {"found": True, **row}


@router.get("/event_reconciliation/storylines/{domain_key}/{storyline_id}")
async def get_event_reconciliation_for_storyline(domain_key: str, storyline_id: int) -> dict[str, Any]:
    return reconciliation.get_reconciliation_for_storyline(domain_key, storyline_id)
