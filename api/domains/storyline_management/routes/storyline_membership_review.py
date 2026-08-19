"""Storyline membership review routes — list/approve/reject + run review."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from shared.domain_registry import DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storyline Membership Review"])


async def validate_domain_dependency(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)) -> str:
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    return domain


class MembershipActionResolveBody(BaseModel):
    approve: bool = Field(..., description="True to apply, False to reject")


@router.get("/{domain}/storylines/membership-actions")
async def list_storyline_membership_actions(
    domain: str = Depends(validate_domain_dependency),
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    from services.storyline_membership_review_service import list_membership_actions

    if status not in ("pending", "applied", "rejected", "skipped"):
        raise HTTPException(status_code=400, detail="invalid status")
    data = list_membership_actions(domain, status=status, limit=limit, offset=offset)
    return {"success": True, "domain": domain, **data}


@router.post("/{domain}/storylines/membership-actions/{action_id}/resolve")
async def resolve_storyline_membership_action(
    domain: str = Depends(validate_domain_dependency),
    action_id: int = Path(..., ge=1),
    body: MembershipActionResolveBody = ...,
):
    from services.storyline_membership_review_service import apply_membership_action

    result = apply_membership_action(action_id, approve=body.approve)
    if not result.get("success") and result.get("error") in ("not_found",):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return {"success": bool(result.get("success")), "domain": domain, **result}


@router.post("/{domain}/storylines/{storyline_id}/membership-review")
async def run_storyline_membership_review(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., ge=1),
    dry_run: Optional[bool] = Query(None),
):
    from services.storyline_membership_review_service import review_storyline_membership

    stats = review_storyline_membership(domain, storyline_id, dry_run=dry_run)
    if stats.get("error") == "storyline_not_found":
        raise HTTPException(status_code=404, detail="Storyline not found")
    return {"success": "error" not in stats or stats.get("error") is None, "data": stats}


@router.post("/{domain}/storylines/membership-review/run")
async def run_domain_membership_review(
    domain: str = Depends(validate_domain_dependency),
    limit: int = Query(8, ge=1, le=50),
    dry_run: Optional[bool] = Query(None),
):
    from services.storyline_membership_review_service import (
        run_storyline_membership_review_for_domain,
    )

    data = run_storyline_membership_review_for_domain(domain, limit=limit, dry_run=dry_run)
    return {"success": True, "data": data}
