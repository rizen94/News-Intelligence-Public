"""
Investigation API routes — /api/investigation/*
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Query

investigation_router = APIRouter(prefix="/api", tags=["investigation"])


@investigation_router.get("/investigation/health")
def investigation_health() -> dict:
    from nri_core.services.integration import get_investigation_health

    return get_investigation_health()


@investigation_router.get("/investigation/resolved_mentions")
def investigation_resolved_mentions(
    domain_key: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    from nri_core.services.integration import list_resolved_mentions

    return list_resolved_mentions(
        domain_key=domain_key, status=status, limit=limit, offset=offset
    )


@investigation_router.get("/investigation/parked")
def investigation_parked(
    domain_key: str | None = Query(None),
    review_status: str | None = Query("open"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    from nri_core.services.integration import list_parked_resolution

    return list_parked_resolution(
        domain_key=domain_key,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )


@investigation_router.patch("/investigation/parked/{parked_id}")
def investigation_review_parked(parked_id: int, body: dict = Body(...)) -> dict:
    from nri_core.services.integration import review_parked

    return review_parked(
        parked_id,
        review_status=str(body.get("review_status", "reviewed")),
        candidate_ftm_id=body.get("candidate_ftm_id"),
    )


@investigation_router.get("/investigation/entity_bridge/{entity_profile_id}")
def investigation_entity_bridge(entity_profile_id: int) -> dict:
    from nri_core.services.integration import get_entity_bridge

    return get_entity_bridge(entity_profile_id)


@investigation_router.get("/investigation/research_seeds")
def investigation_research_seeds(
    domains: list[str] | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    min_mentions: int = Query(3, ge=1, le=20),
) -> dict:
    from nri_core.services.integration import get_research_seeds

    return get_research_seeds(domains=domains, limit=limit, min_mentions=min_mentions)


@investigation_router.post("/investigation/research_seeds")
def investigation_set_research_seeds(
    body: dict = Body(...),
) -> dict:
    from nri_core.services.integration import set_research_seeds

    ftm_ids = body.get("ftm_ids", [])
    domains = body.get("domains", [])
    return set_research_seeds(ftm_ids=ftm_ids, domains=domains)


@investigation_router.get("/investigation/loop_summary")
def investigation_loop_summary(
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    from services.nri_loop_summarizer import build_vault_index

    # Build a comprehensive summary from recent loop runs
    index = build_vault_index(hypothesis_limit=500, tracking_days=30)
    return {"success": True, "summary": index}


@investigation_router.get("/investigation/vault_index")
def investigation_vault_index(
    hypothesis_limit: int = Query(200, ge=1, le=1000),
    tracking_days: int = Query(30, ge=1, le=90),
) -> dict:
    from services.nri_loop_summarizer import build_vault_index

    index = build_vault_index(hypothesis_limit=hypothesis_limit, tracking_days=tracking_days)
    return {"success": True, "index": index}


@investigation_router.get("/investigation/entity_claims")
def investigation_entity_claims(
    entity_profile_id: int = Query(..., ge=1),
    context_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    from nri_core.services.entity_claims import get_entity_claims_in_context

    return get_entity_claims_in_context(
        entity_profile_id=entity_profile_id, context_id=context_id, limit=limit
    )


@investigation_router.get("/investigation/context_intel/{context_id}")
def investigation_context_intel(
    context_id: int,
    claims_limit: int = Query(100, ge=1, le=300),
) -> dict:
    from nri_core.services.integration import get_context_intel

    return get_context_intel(context_id, claims_limit=claims_limit)


@investigation_router.get("/investigation/parked_cross_domain")
def investigation_parked_cross_domain(
    exclude_generic: bool = Query(True),
    min_domains: int = Query(2, ge=2, le=6),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    from nri_core.services.integration import list_parked_cross_domain

    return list_parked_cross_domain(
        exclude_generic=exclude_generic,
        min_domains=min_domains,
        limit=limit,
        offset=offset,
    )


@investigation_router.get("/investigation/hypotheses")
def investigation_hypotheses(
    status: str | None = Query(None),
    ftm_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    from nri_core.services.integration import list_hypotheses

    return list_hypotheses(status=status, ftm_id=ftm_id, limit=limit, offset=offset)


@investigation_router.get("/investigation/hypotheses/{hyp_id}")
def investigation_hypothesis_detail(hyp_id: str) -> dict:
    from nri_core.services.integration import get_hypothesis

    return get_hypothesis(hyp_id)


@investigation_router.get("/investigation/spine/entities")
def investigation_spine_entities(
    dataset: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from nri_core.services.integration import list_spine_entities

    return list_spine_entities(dataset=dataset, limit=limit)


@investigation_router.post("/investigation/spine/match")
def investigation_spine_match(body: dict = Body(...)) -> dict:
    from nri_core.services.integration import match_spine

    return match_spine(
        text=str(body.get("text", "")),
        schema_name=body.get("schema_name"),
    )


@investigation_router.get("/investigation/resolution_stats")
def investigation_resolution_stats(domain_key: str | None = Query(None)) -> dict:
    from nri_core.services.integration import get_resolution_stats

    return get_resolution_stats(domain_key=domain_key)


@investigation_router.get("/investigation/loop_runs")
def investigation_loop_runs(limit: int = Query(20, ge=1, le=100)) -> dict:
    from nri_core.services.integration import list_loop_runs

    return list_loop_runs(limit=limit)


@investigation_router.get("/investigation/graph_neighbors")
def investigation_graph_neighbors(
    seed_kind: str = Query(..., description="storyline|entity|tracked_event|topic|context"),
    seed_id: int = Query(..., ge=1),
    max_depth: int = Query(2, ge=1, le=5),
    max_nodes: int = Query(50, ge=5, le=200),
    domain_key: str | None = Query(None),
) -> dict:
    """Iterative BFS over graph_connection_links — seed entity/event → bounded expansion."""
    from services.graph_connection_queue_service import bfs_graph_neighbors

    return bfs_graph_neighbors(
        seed_kind=seed_kind,
        seed_id=seed_id,
        max_depth=max_depth,
        max_nodes=max_nodes,
        domain_key=domain_key,
    )


@investigation_router.get("/investigation/ftm_cache_stats")
def investigation_ftm_cache_stats() -> dict:
    from nri_core.services.integration import get_ftm_cache_dataset_counts

    return get_ftm_cache_dataset_counts()


@investigation_router.get("/investigation/bridge_qa/audit")
def investigation_bridge_qa_audit(
    domain_key: str | None = Query(None),
    qa_status: str | None = Query(
        None,
        description="Filter by QA status: suspect, mismatch, or omit for non-ok rows",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List entity↔FtM bridge links with bridge QA status for Investigation Ops."""
    from nri_core.services.integration import audit_bridge_qa

    return audit_bridge_qa(
        domain_key=domain_key,
        qa_status=qa_status,
        limit=limit,
        offset=offset,
    )
