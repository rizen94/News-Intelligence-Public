"""Daily report API — GET /api/{domain}/daily + 72h intake brief."""

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


@router.get("/{domain}/daily/intake")
def get_intake_brief(
    domain: str = Path(..., description="Domain key (or 'all')"),
    hours: int = Query(72, ge=6, le=168),
    limit: int = Query(25, ge=5, le=60),
) -> dict[str, Any]:
    """Last-N-hour articles/events/topics — launch pad for POST /api/research/assemble."""
    from services.discovery_intake_brief_service import build_intake_brief

    dk = None if (domain or "").strip().lower() in ("all", "*", "global") else domain
    payload = build_intake_brief(hours=hours, domain_key=dk, limit_per_domain=limit)
    if not payload.get("ok"):
        return {"success": False, "data": None, "message": payload.get("error") or "failed"}
    return {"success": True, "data": payload}


@router.get("/daily/intake")
def get_global_intake_brief(
    hours: int = Query(72, ge=6, le=168),
    limit: int = Query(25, ge=5, le=60),
) -> dict[str, Any]:
    """Cross-domain 72h intake brief."""
    from services.discovery_intake_brief_service import build_intake_brief

    payload = build_intake_brief(hours=hours, domain_key=None, limit_per_domain=limit)
    if not payload.get("ok"):
        return {"success": False, "data": None, "message": payload.get("error") or "failed"}
    return {"success": True, "data": payload}
