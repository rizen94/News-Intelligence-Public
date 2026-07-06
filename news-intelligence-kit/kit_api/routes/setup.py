"""Kit setup API routes."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config.runtime import env_str
from kit_api.services import provision_service, setup_agent_service
from kit_api.services.opml_parser import merge_opml_into_domains
from kit_api.services.provision_service import apply_setup_plan
from kit_api.services.setup_state import (
    get_setup_draft,
    is_setup_complete,
    save_setup_draft,
    set_setup_complete,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["Kit Setup"])


class TopicsBody(BaseModel):
    interests: str = Field(..., min_length=1, max_length=2000)


class FeedsBody(BaseModel):
    domain_key: str
    query: str = ""


class ValidateFeedBody(BaseModel):
    url: str


class DomainsBody(BaseModel):
    domains: list[dict[str, Any]]


class OpmlBody(BaseModel):
    opml: str = Field(..., min_length=1)
    domain_key: str = ""


@router.get("/status")
async def setup_status() -> dict[str, Any]:
    ollama_ok = False
    db_ok = False
    try:
        host = env_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{host}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = cur.fetchone()[0] == 1
    except Exception:
        pass
    return {
        "setup_complete": is_setup_complete(),
        "ollama_ok": ollama_ok,
        "db_ok": db_ok,
        "hardware_tier": env_str("KIT_HARDWARE_TIER", "standard"),
        "kit_mode": env_str("NEWS_INTEL_KIT_MODE", "true").lower() in ("1", "true", "yes"),
    }


@router.post("/topics")
async def setup_topics(body: TopicsBody) -> dict[str, Any]:
    draft = get_setup_draft()
    draft["interests"] = body.interests
    domains = await setup_agent_service.propose_domains_from_interests(body.interests)
    draft["domains"] = domains
    save_setup_draft(draft)
    return {"domains": domains}


@router.post("/propose_domains")
async def propose_domains(body: TopicsBody) -> dict[str, Any]:
    domains = await setup_agent_service.propose_domains_from_interests(body.interests)
    draft = get_setup_draft()
    draft["interests"] = body.interests
    draft["domains"] = domains
    save_setup_draft(draft)
    return {"domains": domains}


@router.post("/suggest_feeds")
async def suggest_feeds(body: FeedsBody) -> dict[str, Any]:
    feeds = await setup_agent_service.suggest_feeds(body.domain_key, body.query)
    return {"feeds": feeds}


@router.post("/validate_feed")
async def validate_feed(body: ValidateFeedBody) -> dict[str, Any]:
    return provision_service.validate_feed_url(body.url)


@router.post("/import_opml")
async def import_opml(body: OpmlBody) -> dict[str, Any]:
    draft = get_setup_draft()
    domains = draft.get("domains") or []
    feeds = merge_opml_into_domains(body.opml, domains)
    if body.domain_key:
        for f in feeds:
            f["domain_key"] = body.domain_key
    return {"feeds": feeds, "count": len(feeds)}


@router.get("/plan")
async def get_plan() -> dict[str, Any]:
    return get_setup_draft()


@router.put("/plan")
async def update_plan(body: DomainsBody) -> dict[str, Any]:
    draft = get_setup_draft()
    draft["domains"] = body.domains
    save_setup_draft(draft)
    return draft


@router.post("/apply")
async def apply_setup() -> dict[str, Any]:
    draft = get_setup_draft()
    if not draft.get("domains"):
        raise HTTPException(status_code=400, detail="No domains in plan")
    result = provision_service.apply_setup_plan(draft)
    if result["errors"] and not result["provisioned"]:
        raise HTTPException(status_code=500, detail=result)
    if result["provisioned"]:
        set_setup_complete(True)
    result["next_steps"] = [
        "Run ./scripts/enable_automation.sh on the host to start the pipeline",
        "Run ./scripts/pull_ollama_models.sh if models are missing",
    ]
    return result


@router.post("/add_domain")
async def add_domain(domain: dict[str, Any]) -> dict[str, Any]:
    r = provision_service.provision_domain(domain)
    return r
