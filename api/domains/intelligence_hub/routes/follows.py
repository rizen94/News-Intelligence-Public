"""Follow registry API — mutating routes 403 on public demo (by design)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query

logger = logging.getLogger(__name__)

from services.follow_service import (
    follow,
    get_follow_by_id,
    list_followed,
    mark_read,
    patch_follow,
    unfollow,
)
from services.living_story_service import demote_to_quiet, promote_to_living
from services.pulse_service import get_followed_movement

router = APIRouter(prefix="/api/follows", tags=["Follows"])


@router.post("")
def api_follow(
    object_kind: str = Body(..., embed=True),
    domain_key: str | None = Body(None, embed=True),
    object_id: int = Body(..., embed=True),
    tier: str = Body("quiet", embed=True),
    user_key: str = Body("operator", embed=True),
    notify_on: str = Body("any_movement", embed=True),
) -> dict[str, Any]:
    try:
        row = follow(
            object_kind,
            domain_key,
            object_id,
            tier=tier,
            user_key=user_key,
            notify_on=notify_on,
        )
        if tier == "living":
            try:
                promote_to_living(int(row["id"]), user_key=user_key)
            except LookupError as e:
                patch_follow(int(row["id"]), user_key=user_key, tier="quiet")
                raise HTTPException(status_code=404, detail=str(e)) from e
            except ValueError as e:
                patch_follow(int(row["id"]), user_key=user_key, tier="quiet")
                raise HTTPException(status_code=400, detail=str(e)) from e
            except Exception as e:
                patch_follow(int(row["id"]), user_key=user_key, tier="quiet")
                logger.exception("follow+living promote failed follow_id=%s", row.get("id"))
                raise HTTPException(status_code=500, detail="living promotion failed") from e
            row = get_follow_by_id(int(row["id"]), user_key=user_key) or row
        return {"success": True, "data": row}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("")
def api_list_follows(
    user_key: str = Query("operator"),
    tier: str | None = Query(None),
    include_archived: bool = Query(False),
) -> dict[str, Any]:
    rows = list_followed(user_key, include_archived=include_archived, tier=tier)
    return {"success": True, "data": rows}


@router.get("/movement")
def api_follows_movement(
    user_key: str = Query("operator"),
    window_hours: int = Query(48, ge=1, le=168),
) -> dict[str, Any]:
    rows = get_followed_movement(user_key, window_hours=window_hours)
    return {"success": True, "data": rows}


@router.delete("/{follow_id}")
def api_unfollow(
    follow_id: int = Path(...),
    user_key: str = Query("operator"),
) -> dict[str, Any]:
    try:
        row = unfollow(follow_id, user_key=user_key)
        return {"success": True, "data": row}
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{follow_id}/read")
def api_mark_read(
    follow_id: int = Path(...),
    user_key: str = Query("operator"),
) -> dict[str, Any]:
    try:
        row = mark_read(follow_id, user_key=user_key)
        return {"success": True, "data": row}
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{follow_id}")
def api_patch_follow(
    follow_id: int = Path(...),
    user_key: str = Query("operator"),
    tier: str | None = Body(None, embed=True),
    notify_on: str | None = Body(None, embed=True),
    status: str | None = Body(None, embed=True),
    promote_living: bool = Body(False, embed=True),
    demote_quiet: bool = Body(False, embed=True),
) -> dict[str, Any]:
    try:
        if promote_living:
            data = promote_to_living(follow_id, user_key=user_key)
            return {"success": True, "data": data}
        if demote_quiet:
            data = demote_to_quiet(follow_id, user_key=user_key)
            return {"success": True, "data": data}
        row = patch_follow(
            follow_id,
            user_key=user_key,
            tier=tier,
            notify_on=notify_on,
            status=status,
        )
        return {"success": True, "data": row}
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("patch follow failed follow_id=%s", follow_id)
        raise HTTPException(status_code=500, detail="follow update failed") from e
