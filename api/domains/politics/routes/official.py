"""
Politics — official government sources (Congress.gov bill API).

Paths: ``/api/politics/official/...`` — global read-only; API key stays server-side.
"""

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from shared.services.congress_gov_client import (
    fetch_bill,
    fetch_bill_summaries,
    fetch_bill_text_versions,
    is_congress_gov_configured,
    search_bills,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/politics/official",
    tags=["Politics — official sources"],
    responses={404: {"description": "Not found"}},
)

_BILL_TYPE_RE = re.compile(r"^[a-z]{1,8}$")


def _bill_type_norm(bill_type: str) -> str:
    bt = (bill_type or "").strip().lower()
    if not _BILL_TYPE_RE.match(bt):
        raise HTTPException(
            status_code=400,
            detail="bill_type must be a short lowercase code (e.g. hr, s, hjres, sconres)",
        )
    return bt


def _require_congress_gov() -> None:
    if not is_congress_gov_configured():
        raise HTTPException(
            status_code=503,
            detail="Congress.gov is not configured. Set CONGRESS_GOV_API_KEY in the API environment.",
        )


def _wrap(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("success"):
        return {
            "success": True,
            "data": result.get("data"),
            "message": "ok",
            "source": "congress.gov",
        }
    err = result.get("error") or "Congress.gov request failed"
    code = result.get("status_code")
    if code == 404:
        raise HTTPException(status_code=404, detail=err)
    if code == 401 or code == 403:
        raise HTTPException(status_code=502, detail=err)
    raise HTTPException(status_code=502, detail=err)


@router.get("/congress_gov/status")
async def congress_gov_status() -> dict[str, Any]:
    """Whether Congress.gov credentials are configured (does not expose the key)."""
    return {
        "success": True,
        "data": {"configured": is_congress_gov_configured()},
        "message": "ok",
    }


@router.get("/congress_gov/bill/{congress}/{bill_type}/{bill_number}/summaries")
async def get_bill_summaries(
    congress: int = Path(..., ge=1, le=999),
    bill_type: str = Path(..., min_length=1, max_length=12),
    bill_number: int = Path(..., ge=1),
) -> dict[str, Any]:
    bt = _bill_type_norm(bill_type)
    return _wrap(fetch_bill_summaries(congress, bt, bill_number))


@router.get("/congress_gov/bill/{congress}/{bill_type}/{bill_number}/text")
async def get_bill_text_versions(
    congress: int = Path(..., ge=1, le=999),
    bill_type: str = Path(..., min_length=1, max_length=12),
    bill_number: int = Path(..., ge=1),
) -> dict[str, Any]:
    _require_congress_gov()
    bt = _bill_type_norm(bill_type)
    return _wrap(fetch_bill_text_versions(congress, bt, bill_number))


@router.get("/congress_gov/bill/{congress}/{bill_type}/{bill_number}")
async def get_bill(
    congress: int = Path(..., ge=1, le=999),
    bill_type: str = Path(..., min_length=1, max_length=12),
    bill_number: int = Path(..., ge=1),
) -> dict[str, Any]:
    bt = _bill_type_norm(bill_type)
    return _wrap(fetch_bill(congress, bt, bill_number))


@router.get("/congress_gov/bills/search")
async def search_bills_endpoint(
    congress: int = Query(..., ge=1, le=999, description="Congress session (e.g. 118)"),
    q: str | None = Query(None, description="Optional filter (Congress.gov q parameter)"),
    limit: int = Query(20, ge=1, le=250),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    _require_congress_gov()
    return _wrap(search_bills(congress, query=q, limit=limit, offset=offset))
