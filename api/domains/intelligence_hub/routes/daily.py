"""Daily report API — GET /api/{domain}/daily."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Query

from services.daily_report_service import assemble_daily

router = APIRouter(prefix="/api", tags=["Daily"])


@router.get("/{domain}/daily")
def get_daily_report(
    domain: str = Path(..., description="Domain key"),
    date: str | None = Query(None, description="ISO date YYYY-MM-DD (default today)"),
    since: str | None = Query(None, description="Optional ISO timestamp for incremental moved_today"),
    limit: int = Query(40, ge=1, le=80),
) -> dict[str, Any]:
    payload = assemble_daily(domain, day=date, since=since, limit=limit)
    if not payload.get("ok"):
        return {"success": False, "data": None, "message": payload.get("error") or "failed"}
    return {"success": True, "data": payload}
