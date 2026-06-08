"""
Longitudinal intelligence API — arcs, reports, citations, spine, heatmap (Phases 4–5).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from schemas.response_schemas import APIResponse

from services.arc_catalog_service import (
    get_arc_definition,
    list_active_arcs,
    resolve_current_chapter,
    sync_arc_definitions_from_yaml,
)
from services.arc_historical_context_service import build_arc_historical_context
from services.arc_feedback_service import (
    get_arc_feedback_summary,
    submit_arc_report_feedback,
)
from services.reference_event_curation_service import (
    create_reference_event,
    flag_reference_event,
    list_reference_event_flags,
    supersede_reference_event,
)
from services.reference_events_loader import list_reference_events
from services.arc_analogue_service import (
    load_arc_cross_domain_correlations,
    load_arc_pattern_discoveries,
)
from services.slow_report_service import (
    generate_slow_report_async,
    get_citation_provenance,
    get_latest_arc_report,
)
from services.wikidata_review_service import list_entities_missing_wikidata_qid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["Longitudinal Intelligence"])


class GenerateReportRequest(BaseModel):
    report_type: str = Field(default="weekly_brief")
    as_of_date: str | None = None
    retrieval_query: str | None = None


class ReferenceEventCreate(BaseModel):
    event_date: str
    title: str
    summary: str
    date_precision: str = "day"
    end_date: str | None = None
    category: str | None = None
    entity_qids: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    arc_ids: list[str] = Field(default_factory=list)
    curator: str = "operator"


class ReferenceEventSupersede(BaseModel):
    title: str | None = None
    summary: str | None = None
    event_date: str | None = None
    end_date: str | None = None
    notes: str | None = None
    curator: str = "operator"


class ReferenceEventFlag(BaseModel):
    flag_type: str = "missed_coverage"
    notes: str | None = None
    curator: str = "operator"


class ArcReportFeedback(BaseModel):
    report_id: int | None = None
    section_key: str = "overall"
    rating: int | None = Field(default=None, ge=1, le=5)
    useful: bool | None = None
    notes: str | None = None
    curator: str = "operator"


@router.get("/arcs")
async def list_arcs():
    return APIResponse(success=True, data=list_active_arcs(), message="Active arcs")


@router.get("/arcs/{arc_id}")
async def get_arc(arc_id: str):
    arc = get_arc_definition(arc_id)
    if not arc:
        raise HTTPException(status_code=404, detail="Arc not found")
    chapter = resolve_current_chapter(arc_id)
    return APIResponse(
        success=True,
        data={"arc": arc, "current_chapter": chapter},
        message=f"Arc {arc_id}",
    )


@router.post("/arcs/sync")
async def sync_arcs():
    result = sync_arc_definitions_from_yaml()
    return APIResponse(success=True, data=result, message="Arc definitions synced from YAML")


@router.get("/arcs/{arc_id}/context")
async def arc_context(
    arc_id: str,
    as_of: str | None = Query(None, description="ISO UTC cutoff for point-in-time query"),
):
    as_of_dt = None
    if as_of:
        try:
            as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid as_of: {e}") from e
    bundle = build_arc_historical_context(arc_id, as_of_dt)
    if not bundle.get("success"):
        raise HTTPException(status_code=404, detail=bundle.get("error", "Not found"))
    return APIResponse(success=True, data=bundle, message="Arc historical context")


@router.get("/arcs/{arc_id}/spine")
async def arc_spine(arc_id: str):
    arc = get_arc_definition(arc_id)
    if not arc:
        raise HTTPException(status_code=404, detail="Arc not found")
    events = list_reference_events(arc_id=arc_id, limit=500)
    chapter = resolve_current_chapter(arc_id)
    macro_ids = arc.get("primary_macro_series_ids") or []
    macro: list[dict[str, Any]] = []
    if macro_ids:
        from services.macro_series_service import get_macro_series_for_arc

        macro = get_macro_series_for_arc(macro_ids, limit=300)
    return APIResponse(
        success=True,
        data={
            "arc": arc,
            "reference_events": events,
            "current_chapter": chapter,
            "macro_series": macro,
        },
        message="Arc spine data",
    )


@router.get("/arcs/{arc_id}/heatmap")
async def tension_heatmap(arc_id: str, months: int = Query(24, ge=6, le=60)):
    arc = get_arc_definition(arc_id)
    macro_ids = (arc or {}).get("primary_macro_series_ids") or []
    gpr_series = next(
        (s for s in macro_ids if str(s).upper().startswith("GPR")),
        "GPRHICU",
    )
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT month_start, region_key, source, event_count, fatalities_sum
                FROM intelligence.mv_tension_heatmap_monthly
                WHERE month_start >= (date_trunc('month', NOW()) - (%s || ' months')::interval)::date
                ORDER BY month_start DESC, region_key
                """,
                (months,),
            )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get("month_start"):
                    d["month_start"] = d["month_start"].isoformat()
                rows.append(d)

            gpr_by_month: dict[str, float] = {}
            try:
                cur.execute(
                    """
                    SELECT date_trunc('month', observation_date AT TIME ZONE 'UTC')::date AS month_start,
                           AVG(value)::float AS gpr_avg
                    FROM intelligence.macro_series_observations
                    WHERE series_id = %s
                      AND observation_date >= (date_trunc('month', NOW()) - (%s || ' months')::interval)
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    (gpr_series, months),
                )
                for month_start, gpr_avg in cur.fetchall():
                    gpr_by_month[month_start.isoformat()] = float(gpr_avg or 0)
            except Exception as e:
                logger.debug("heatmap GPR join skipped: %s", e)

    # Aggregate per month/region; composite = normalized events + GPR z-score proxy
    month_totals: dict[str, int] = {}
    for cell in rows:
        mk = str(cell.get("month_start", ""))[:10]
        month_totals[mk] = month_totals.get(mk, 0) + int(cell.get("event_count") or 0)
    max_events = max(month_totals.values()) if month_totals else 1
    max_gpr = max(gpr_by_month.values()) if gpr_by_month else 1.0

    aggregated: dict[str, dict[str, Any]] = {}
    for cell in rows:
        mk = str(cell.get("month_start", ""))[:10]
        rk = str(cell.get("region_key") or "XX")
        key = f"{mk}|{rk}"
        agg = aggregated.setdefault(
            key,
            {
                "month_start": cell.get("month_start"),
                "region_key": rk,
                "event_count": 0,
                "fatalities_sum": 0,
                "sources": [],
            },
        )
        agg["event_count"] += int(cell.get("event_count") or 0)
        agg["fatalities_sum"] += int(cell.get("fatalities_sum") or 0)
        src = cell.get("source")
        if src and src not in agg["sources"]:
            agg["sources"].append(src)

    composite_cells = []
    for agg in aggregated.values():
        mk = str(agg.get("month_start", ""))[:10]
        event_norm = (agg["event_count"] / max_events) if max_events else 0
        gpr_norm = (gpr_by_month.get(mk, 0) / max_gpr) if max_gpr else 0
        agg["gpr_index"] = round(gpr_by_month.get(mk, 0), 4)
        agg["composite_score"] = round(0.65 * event_norm + 0.35 * gpr_norm, 4)
        composite_cells.append(agg)

    return APIResponse(
        success=True,
        data={
            "arc_id": arc_id,
            "months": months,
            "cells": composite_cells,
            "raw_cells": rows,
            "gpr_series_id": gpr_series,
        },
        message="Tension heatmap with GPR composite (refresh mat view after external_events ingest)",
    )


@router.get("/arc_report/{arc_id}/latest")
async def latest_arc_report(arc_id: str):
    report = get_latest_arc_report(arc_id)
    if not report:
        raise HTTPException(status_code=404, detail="No report generated yet")
    return APIResponse(success=True, data=report, message="Latest arc report")


@router.post("/arc_report/{arc_id}/generate")
async def trigger_arc_report(arc_id: str, body: GenerateReportRequest | None = None):
    body = body or GenerateReportRequest()
    sync_arc_definitions_from_yaml()
    as_of_dt = None
    if body.as_of_date:
        as_of_dt = datetime.fromisoformat(body.as_of_date.replace("Z", "+00:00"))
    result = await generate_slow_report_async(
        arc_id,
        report_type=body.report_type,
        as_of_date=as_of_dt,
        retrieval_query=body.retrieval_query,
    )
    if not result.get("success"):
        detail = result.get("error", "Generation failed")
        if result.get("validation"):
            detail = {"error": detail, "validation": result["validation"]}
        raise HTTPException(status_code=400, detail=detail)
    return APIResponse(success=True, data=result, message="Arc report generated")


@router.get("/citation/{citation_id}")
async def citation_detail(citation_id: str):
    prov = get_citation_provenance(citation_id)
    if not prov:
        raise HTTPException(status_code=404, detail="Citation not found")
    return APIResponse(success=True, data=prov, message="Citation provenance")


@router.get("/analogues/{arc_id}")
async def arc_analogues(arc_id: str, limit: int = Query(4, ge=1, le=10)):
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            patterns = load_arc_pattern_discoveries(cur, arc_id, limit=limit)
            correlations = load_arc_cross_domain_correlations(cur, arc_id, limit=limit)
    return APIResponse(
        success=True,
        data={"patterns": patterns, "correlations": correlations},
        message="Prior analogues (rhymes-with, not predictive)",
    )


@router.get("/reference_events")
async def get_reference_events(
    arc_id: str | None = None,
    limit: int = Query(200, ge=1, le=500),
):
    events = list_reference_events(arc_id=arc_id, limit=limit)
    return APIResponse(success=True, data=events, message="Reference events")


@router.post("/reference_events")
async def post_reference_event(body: ReferenceEventCreate):
    result = create_reference_event(body.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return APIResponse(success=True, data=result, message="Reference event created")


@router.post("/reference_events/{event_id}/supersede")
async def post_supersede_reference_event(event_id: int, body: ReferenceEventSupersede):
    result = supersede_reference_event(event_id, body.model_dump(exclude_unset=True))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return APIResponse(success=True, data=result, message="Reference event superseded")


@router.post("/reference_events/{event_id}/flag")
async def post_flag_reference_event(event_id: int, body: ReferenceEventFlag):
    result = flag_reference_event(
        event_id,
        flag_type=body.flag_type,
        notes=body.notes,
        curator=body.curator,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return APIResponse(success=True, data=result, message="Flag recorded")


@router.get("/reference_events/flags")
async def get_reference_event_flags(limit: int = Query(100, ge=1, le=200)):
    flags = list_reference_event_flags(limit=limit)
    return APIResponse(success=True, data=flags, message="Reference event flags")


@router.post("/arc_report/{arc_id}/feedback")
async def post_arc_report_feedback(arc_id: str, body: ArcReportFeedback):
    result = submit_arc_report_feedback(
        arc_id,
        report_id=body.report_id,
        section_key=body.section_key,
        rating=body.rating,
        useful=body.useful,
        notes=body.notes,
        curator=body.curator,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return APIResponse(success=True, data=result, message="Arc feedback recorded")


@router.get("/wikidata/review_queue")
async def get_wikidata_review_queue(
    domain: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    data = list_entities_missing_wikidata_qid(domain_key=domain, limit=limit)
    return APIResponse(success=True, data=data, message="Entities missing Wikidata QID")


@router.get("/arc_report/{arc_id}/feedback")
async def get_arc_report_feedback(arc_id: str):
    summary = get_arc_feedback_summary(arc_id)
    return APIResponse(success=True, data=summary, message="Arc feedback summary")
