"""Agent investigation loop API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from kit_api.services.investigation_loop_service import run_investigation_loop

router = APIRouter(prefix="/api/agent", tags=["Kit Agent"])


class InvestigateBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    domain_key: str | None = None
    entity_id: int | None = None
    event_id: int | None = None


@router.post("/investigate")
async def investigate(body: InvestigateBody) -> dict[str, Any]:
    return await run_investigation_loop(
        query=body.query,
        domain_key=body.domain_key,
        entity_id=body.entity_id,
        event_id=body.event_id,
    )
