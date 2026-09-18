"""Episode / container timeline browse APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from schemas.response_schemas import APIResponse
from services.container_projection_service import (
    hub_context_feed,
    project_episode_to_containers,
)
from services.episode_container_timeline_service import (
    container_timeline,
    dossier_projection_stub,
    episode_timeline,
)
from services.episode_lifecycle_service import (
    apply_bifurcation_split,
    grow_signature_from_coanchors,
    propose_bifurcation_split,
    transition_episode_state,
)

router = APIRouter(prefix="/api/intelligence", tags=["Episodes & Containers"])


def _require_domain(domain: str) -> str:
    key = (domain or "").strip().lower().replace("_", "-")
    try:
        from shared.domain_registry import is_valid_domain_key

        if is_valid_domain_key(key):
            return key
    except Exception:
        pass
    known = {
        "legal",
        "medicine",
        "artificial-intelligence",
        "politics",
        "finance",
        "neurodiversity",
    }
    if key in known:
        return key
    raise HTTPException(status_code=404, detail=f"Unknown domain: {domain}")


@router.get("/episodes/{domain}/{episode_id}/timeline")
def get_episode_timeline(
    domain: str,
    episode_id: int,
    limit: int = Query(100, ge=1, le=500),
):
    key = _require_domain(domain)
    data = episode_timeline(key, int(episode_id), limit=limit)
    if not data.get("episode"):
        raise HTTPException(status_code=404, detail="Episode not found")
    return APIResponse(success=True, data=data, message="ok")


@router.post("/episodes/{domain}/{episode_id}/project_containers")
def post_project_containers(domain: str, episode_id: int):
    key = _require_domain(domain)
    data = project_episode_to_containers(key, int(episode_id), apply=True)
    return APIResponse(success=True, data=data, message="ok")


@router.post("/episodes/{domain}/{episode_id}/state")
def post_episode_state(domain: str, episode_id: int, new_state: str = Query(...), reason: str = ""):
    key = _require_domain(domain)
    ok = transition_episode_state(key, int(episode_id), new_state, reason=reason)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid transition or episode missing")
    return APIResponse(success=True, data={"episode_id": episode_id, "state": new_state}, message="ok")


@router.post("/episodes/{domain}/{episode_id}/grow_signature")
def post_grow_signature(
    domain: str,
    episode_id: int,
    apply: bool = Query(False),
    min_cooccurring_events: int = Query(3, ge=2, le=20),
):
    key = _require_domain(domain)
    data = grow_signature_from_coanchors(
        key,
        int(episode_id),
        min_cooccurring_events=min_cooccurring_events,
        apply=apply,
    )
    return APIResponse(success=True, data=data, message="ok")


@router.get("/episodes/{domain}/{episode_id}/bifurcation")
def get_bifurcation_proposals(domain: str, episode_id: int):
    key = _require_domain(domain)
    proposals = propose_bifurcation_split(key, int(episode_id))
    return APIResponse(success=True, data={"proposals": proposals}, message="ok")


@router.post("/episodes/{domain}/{episode_id}/bifurcation/apply")
def post_bifurcation_apply(
    domain: str,
    episode_id: int,
    group_a: str = Query(..., description="Comma-separated identity anchors for source"),
    group_b: str = Query(..., description="Comma-separated identity anchors for new episode"),
):
    key = _require_domain(domain)
    ga = [x.strip() for x in group_a.split(",") if x.strip()]
    gb = [x.strip() for x in group_b.split(",") if x.strip()]
    if not ga or not gb:
        raise HTTPException(status_code=400, detail="group_a and group_b required")
    data = apply_bifurcation_split(key, int(episode_id), ga, gb)
    return APIResponse(success=True, data=data, message="ok")


@router.get("/containers/{domain}/{tracked_event_id}/timeline")
def get_container_timeline(
    domain: str,
    tracked_event_id: int,
    limit: int = Query(150, ge=1, le=500),
):
    key = _require_domain(domain)
    data = container_timeline(key, int(tracked_event_id), limit=limit)
    if not data.get("container"):
        raise HTTPException(status_code=404, detail="Container not found")
    return APIResponse(success=True, data=data, message="ok")


@router.get("/containers/{domain}/hub/{hub_key}/context")
def get_hub_container_context(
    domain: str,
    hub_key: str,
    limit: int = Query(50, ge=1, le=200),
):
    """Hub context feed — not membership."""
    key = _require_domain(domain)
    items = hub_context_feed(key, hub_key, limit=limit)
    return APIResponse(
        success=True,
        data={
            "domain_key": key,
            "hub_key": hub_key,
            "articles": items,
            "owns_articles": False,
        },
        message="ok",
    )


@router.get("/dossiers/{domain}/projection")
def get_dossier_projection(
    domain: str,
    canonical_entity_id: int | None = Query(None),
    entity_name: str | None = Query(None),
):
    key = _require_domain(domain)
    data = dossier_projection_stub(
        key,
        canonical_entity_id=canonical_entity_id,
        entity_name=entity_name,
    )
    return APIResponse(success=True, data=data, message="ok")
