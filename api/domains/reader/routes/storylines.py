"""GET /api/reader/storylines/{id} — longform reader pack."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path, Query

from shared.domain_registry import DOMAIN_PATH_PATTERN

from ..services.storyline_pack import build_storyline_reader_pack

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/storylines/{storyline_id}")
async def reader_storyline_pack(
    storyline_id: int = Path(..., ge=1),
    domain: str = Query(..., pattern=DOMAIN_PATH_PATTERN, description="Domain key"),
):
    try:
        return build_storyline_reader_pack(domain=domain, storyline_id=storyline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("reader pack failed for %s/%s", domain, storyline_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
