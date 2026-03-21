"""
Cross-domain and relationship intelligence API (P1 + P2).
Routes: cross_domain_synthesis, correlations, unified_timeline, meta_storylines;
  extract_relationships, network_graph.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

from typing import Any

from fastapi import APIRouter, Body, Path, Query
from services.cross_domain_service import (
    get_cross_domain_correlations,
    get_meta_storylines,
    get_unified_timeline,
    run_cross_domain_synthesis,
)
from services.relationship_extraction_service import (
    extract_relationships_from_contexts,
    get_network_subgraph,
)
from services.trend_predictions_service import get_predictions, get_trend_analysis

router = APIRouter(prefix="/api/intelligence", tags=["Cross-domain & relationships"])


@router.post("/cross_domain_synthesis")
def post_cross_domain_synthesis(
    domains: list[str] | None = Body(None, embed=True),
    time_window_days: int = Body(7, embed=True),
    correlation_threshold: float = Body(0.8, embed=True),
) -> dict[str, Any]:
    """Run cross-domain correlation job; persist to cross_domain_correlations. Returns correlation_id and correlations."""
    result = run_cross_domain_synthesis(
        domains=domains,
        time_window_days=time_window_days,
        correlation_threshold=correlation_threshold,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "correlation_id": result.get("correlation_id"),
            "correlations": result.get("correlations", []),
            "meta_storylines": result.get("meta_storylines", []),
        },
        "message": None,
    }


@router.get("/cross_domain_correlations")
def get_intelligence_cross_domain_correlations(
    domain_1: str | None = Query(None),
    domain_2: str | None = Query(None),
    since: int | None = Query(None, description="Only correlations discovered in last N days"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List cross-domain correlation rows with optional filters."""
    result = get_cross_domain_correlations(
        domain_1=domain_1,
        domain_2=domain_2,
        since_days=since,
        limit=limit,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {"correlations": result.get("correlations", [])},
        "message": None,
    }


@router.get("/meta_storylines")
def get_intelligence_meta_storylines(
    domain_1: str | None = Query(None),
    domain_2: str | None = Query(None),
    since: int | None = Query(None, description="Only storylines discovered in last N days"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Meta-storylines that span or correlate multiple domains (from cross_domain_correlations)."""
    result = get_meta_storylines(
        domain_1=domain_1,
        domain_2=domain_2,
        since_days=since,
        limit=limit,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {"meta_storylines": result.get("meta_storylines", [])},
        "message": None,
    }


@router.get("/unified_timeline")
def get_intelligence_unified_timeline(
    domains: str | None = Query(
        None, description="Comma-separated domain keys, e.g. politics,finance"
    ),
    since: int | None = Query(None, description="Only events since N days ago"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Chronological events across domains with domain_key, event_type, entity links."""
    domain_list = [d.strip() for d in domains.split(",")] if domains else None
    result = get_unified_timeline(domains=domain_list, since_days=since, limit=limit)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {"success": True, "data": {"events": result.get("events", [])}, "message": None}


@router.post("/extract_relationships")
def post_extract_relationships(
    context_ids: list[int] | None = Body(None, embed=True),
    domain: str | None = Body(None, embed=True),
    limit: int = Body(50, embed=True),
) -> dict[str, Any]:
    """Extract entity relationships from contexts (co-mentions -> entity_relationships). Returns extracted count and relationship_ids."""
    result = extract_relationships_from_contexts(
        context_ids=context_ids,
        domain_key=domain,
        limit=limit,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "extracted": result.get("extracted", 0),
            "relationship_ids": result.get("relationship_ids", []),
        },
        "message": None,
    }


@router.post("/trend_analysis")
def post_trend_analysis(
    domain: str | None = Body(None, embed=True),
    time_window_days: int = Body(14, embed=True),
    indicators: list[str] | None = Body(None, embed=True),
) -> dict[str, Any]:
    """Trend detection over context/event data; returns trends and leading_indicators (P3)."""
    result = get_trend_analysis(
        domain=domain, time_window_days=time_window_days, indicators=indicators
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "trends": result.get("trends", []),
            "leading_indicators": result.get("leading_indicators", []),
        },
        "message": None,
    }


@router.get("/predictions/{domain}")
def get_intelligence_predictions(
    domain: str = Path(..., description="politics, finance, or science-tech"),
    entity_id: int | None = Query(None),
    horizon_days: int | None = Query(None),
) -> dict[str, Any]:
    """Predictions for domain (and optionally entity). Stub extended by Learning Governor (P3)."""
    result = get_predictions(domain=domain, entity_id=entity_id, horizon_days=horizon_days)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "predictions": result.get("predictions", []),
            "confidence": result.get("confidence", 0),
            "based_on": result.get("based_on", []),
            "domain": result.get("domain"),
        },
        "message": None,
    }


@router.get("/network_graph/{domain}/{entity_id}")
def get_network_graph(
    domain: str = Path(..., description="Domain of the entity (e.g. politics, finance)"),
    entity_id: int = Path(..., description="entity_canonical id in that domain"),
    depth: int = Query(2, ge=1, le=5),
    relationship_types: str | None = Query(None, description="Comma-separated types or 'all'"),
    limit_per_layer: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Subgraph around entity: nodes = (domain, entity_id), edges = entity_relationships."""
    types_list = [t.strip() for t in relationship_types.split(",")] if relationship_types else None
    result = get_network_subgraph(
        domain=domain,
        entity_id=entity_id,
        depth=depth,
        relationship_types=types_list,
        limit_per_layer=limit_per_layer,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {"nodes": result.get("nodes", []), "edges": result.get("edges", [])},
        "message": None,
    }
