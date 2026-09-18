"""Phase A/B/C API: causal edges, reasoning chains, rolling arcs, trading signals."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Narrative Inference"])


class CausalEdgeIn(BaseModel):
    cause_kind: str
    cause_id: int
    effect_kind: str
    effect_id: int
    relation: str = "contributes_to"
    confidence: float = 0.5
    evidence_grade: str = "weak"
    evidence_context_ids: list[int] = Field(default_factory=list)
    reasoning_steps: list[Any] = Field(default_factory=list)
    domain_key: str | None = None
    source: str = "api"


class SignalReviewIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    reason: str = ""
    reviewed_by: str = "operator"


class ReasoningPersistIn(BaseModel):
    domain_key: str
    storyline_id: int | None = None
    tracked_event_id: int | None = None
    steps: list[Any] = Field(default_factory=list)
    narrative: str | None = None
    edge_ids: list[int] = Field(default_factory=list)


@router.get("/causal_edges", response_model=dict[str, Any])
async def get_causal_edges(
    domain_key: str | None = Query(None),
    cause_kind: str | None = Query(None),
    cause_id: int | None = Query(None),
    effect_kind: str | None = Query(None),
    effect_id: int | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
):
    from services.causal_edges_service import list_causal_edges

    edges = list_causal_edges(
        domain_key=domain_key,
        cause_kind=cause_kind,
        cause_id=cause_id,
        effect_kind=effect_kind,
        effect_id=effect_id,
        min_confidence=min_confidence,
        limit=limit,
    )
    return {"success": True, "count": len(edges), "edges": edges}


@router.post("/causal_edges", response_model=dict[str, Any])
async def post_causal_edge(body: CausalEdgeIn):
    from services.causal_edges_service import upsert_causal_edge

    try:
        eid = upsert_causal_edge(**body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not eid:
        raise HTTPException(status_code=500, detail="failed to upsert causal edge")
    return {"success": True, "id": eid}


@router.get("/reasoning/{domain}/{storyline_id}", response_model=dict[str, Any])
async def get_storyline_reasoning(
    domain: str = Path(...),
    storyline_id: int = Path(..., ge=1),
):
    from services.narrative_reasoning_service import get_reasoning_chain

    data = get_reasoning_chain(domain_key=domain, storyline_id=storyline_id)
    return {"success": True, "reasoning": data}


@router.get("/reasoning/event/{event_id}", response_model=dict[str, Any])
async def get_event_reasoning(event_id: int = Path(..., ge=1)):
    from services.narrative_reasoning_service import get_reasoning_chain

    data = get_reasoning_chain(tracked_event_id=event_id)
    return {"success": True, "reasoning": data}


@router.post("/reasoning", response_model=dict[str, Any])
async def persist_reasoning(body: ReasoningPersistIn):
    from services.narrative_reasoning_service import persist_reasoning_chain

    ok = persist_reasoning_chain(**body.model_dump())
    return {"success": ok}


@router.get("/rolling_arcs", response_model=dict[str, Any])
async def get_rolling_arcs(
    domain_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from services.rolling_arc_service import list_rolling_arcs

    arcs = list_rolling_arcs(domain_key=domain_key, limit=limit)
    return {"success": True, "count": len(arcs), "arcs": arcs}


@router.get("/rolling_arcs/{arc_id}", response_model=dict[str, Any])
async def get_rolling_arc_detail(arc_id: int = Path(..., ge=1)):
    from services.rolling_arc_service import get_rolling_arc

    arc = get_rolling_arc(arc_id)
    if not arc:
        raise HTTPException(status_code=404, detail="rolling arc not found")
    return {"success": True, "arc": arc}


@router.post("/rolling_arcs/refresh", response_model=dict[str, Any])
async def refresh_rolling_arcs():
    from services.rolling_arc_service import refresh_default_rolling_arcs

    result = refresh_default_rolling_arcs()
    return {"success": True, **result}


@router.get("/signals", response_model=dict[str, Any])
async def get_signals(
    review_status: str | None = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
):
    from services.trading_signals_service import list_signals

    rows = list_signals(review_status=review_status, limit=limit)
    return {"success": True, "count": len(rows), "signals": rows}


@router.post("/signals/{signal_id}/review", response_model=dict[str, Any])
async def review_trading_signal(signal_id: int = Path(..., ge=1), body: SignalReviewIn = ...):
    from services.trading_signals_service import review_signal

    ok = review_signal(
        signal_id,
        decision=body.decision,
        reason=body.reason,
        reviewed_by=body.reviewed_by,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="signal not found or update failed")
    return {"success": True, "id": signal_id, "review_status": body.decision}


@router.post("/signals/generate", response_model=dict[str, Any])
async def generate_signals(
    days: int = Query(14, ge=1, le=90),
    limit: int = Query(15, ge=1, le=50),
):
    from services.trading_signals_service import generate_signals_from_recent_events

    result = generate_signals_from_recent_events(days=days, limit=limit)
    return {"success": True, **result}
