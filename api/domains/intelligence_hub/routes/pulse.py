"""Pulse digest API — GET /api/pulse (read-only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services.pulse_service import compute_pulse

router = APIRouter(prefix="/api", tags=["Pulse"])


@router.get("/pulse")
def get_pulse(
    window_hours: int = Query(48, ge=1, le=168),
    limit: int = Query(20, ge=1, le=100),
    domain: str | None = Query(None, description="Optional domain_key filter"),
) -> dict[str, Any]:
    payload = compute_pulse(window_hours=window_hours, limit=limit, domain_filter=domain)
    return {"success": True, "data": payload, "message": None}
