"""Hub facet browse API — who/what/where lenses across domains."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from schemas.response_schemas import APIResponse
from services.hub_facets_service import (
    list_hub_articles,
    list_hub_facets,
    list_hub_storylines,
)

router = APIRouter(prefix="/api/intelligence/hub_facets", tags=["Hub Facets"])


def _require_domain(domain: str) -> str:
    key = (domain or "").strip().lower().replace("_", "-")
    known = {
        "legal",
        "medicine",
        "artificial-intelligence",
        "politics",
        "finance",
        "neurodiversity",
    }
    try:
        from shared.domain_registry import is_valid_domain_key

        if is_valid_domain_key(key):
            return key
    except Exception:
        pass
    if key in known:
        return key
    raise HTTPException(status_code=404, detail=f"Unknown domain: {domain}")


@router.get("/{domain}")
def get_hub_facets(domain: str):
    """List configured hub facets (who/what/where) for a domain."""
    key = _require_domain(domain)
    return APIResponse(
        success=True,
        data={"domain_key": key, "hub_facets": list_hub_facets(key)},
        message="ok",
    )


@router.get("/{domain}/{hub_key}/articles")
def get_hub_articles(
    domain: str,
    hub_key: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    key = _require_domain(domain)
    try:
        payload = list_hub_articles(key, hub_key, limit=limit, offset=offset)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return APIResponse(success=True, data=payload, message="ok")


@router.get("/{domain}/{hub_key}/storylines")
def get_hub_storylines(
    domain: str,
    hub_key: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    key = _require_domain(domain)
    try:
        payload = list_hub_storylines(key, hub_key, limit=limit, offset=offset)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return APIResponse(success=True, data=payload, message="ok")
