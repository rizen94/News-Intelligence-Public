"""Narrative enhancement UX APIs (Phases 5–6 scaffolding)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Narrative Enhancement"])


@router.get("/expectations", response_model=dict[str, Any])
async def get_expectations(
    status: str | None = Query(None),
    domain_key: str | None = Query(None),
    overdue_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    from services.expectation_tracking_service import list_expectations

    rows = list_expectations(
        status=status,
        domain_key=domain_key,
        overdue_only=overdue_only,
        limit=limit,
    )
    return {"success": True, "count": len(rows), "expectations": rows}


@router.get("/source_disagreement/{event_id}", response_model=dict[str, Any])
async def get_source_disagreement(event_id: int = Path(..., ge=1)):
    from services.source_disagreement_service import summarize_claim_variants_for_event

    data = summarize_claim_variants_for_event(event_id)
    return {"success": True, **data}


@router.get("/entity_dossier_diff/{entity_profile_id}", response_model=dict[str, Any])
async def get_entity_dossier_diff(
    entity_profile_id: int = Path(..., ge=1),
    window_days: int = Query(7, ge=1, le=90),
):
    from services.entity_dossier_diff_service import weekly_dossier_diff

    data = weekly_dossier_diff(entity_profile_id, window_days=window_days)
    return {"success": True, **data}


@router.get("/hyperedge_meta_storylines", response_model=dict[str, Any])
async def get_hyperedge_meta_storylines(
    domain_key: str | None = Query(None),
    status: str = Query("pending"),
    limit: int = Query(30, ge=1, le=100),
):
    from services.hyperedge_meta_storyline_service import list_hyperedge_meta_storylines

    rows = list_hyperedge_meta_storylines(
        domain_key=domain_key, status=status, limit=limit
    )
    return {"success": True, "count": len(rows), "hyperedges": rows}


@router.get("/hyperedge_meta_storylines/{proposal_id}", response_model=dict[str, Any])
async def get_hyperedge_meta_detail(proposal_id: int = Path(..., ge=1)):
    from services.hyperedge_meta_storyline_service import get_hyperedge_meta_storyline

    row = get_hyperedge_meta_storyline(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail="hyperedge not found")
    return {"success": True, "hyperedge": row}


@router.get("/storylines/{domain}/{storyline_id}/lifecycle", response_model=dict[str, Any])
async def get_lifecycle(
    domain: str = Path(...),
    storyline_id: int = Path(..., ge=1),
):
    from services.storyline_lifecycle_service import get_storyline_lifecycle

    data = get_storyline_lifecycle(domain, storyline_id)
    if data.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="storyline not found")
    return {"success": True, **data}


@router.get("/storylines/{domain}/{storyline_id}/arc_stage", response_model=dict[str, Any])
async def get_arc_stage(
    domain: str = Path(...),
    storyline_id: int = Path(..., ge=1),
    persist: bool = Query(False),
):
    from services.arc_stage_service import infer_arc_stage

    data = infer_arc_stage(domain, storyline_id, persist=persist)
    return {"success": True, **data}
