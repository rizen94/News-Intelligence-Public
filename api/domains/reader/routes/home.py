"""GET /api/reader/home — News / Current Events / One-offs StoryUnits."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from ..services.home_feed import build_reader_home

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/home")
async def reader_home(
    domain: str | None = Query(
        None,
        description="Optional domain filter (e.g. politics). Omit for all pipeline domains.",
    ),
    page: int = Query(1, ge=1, description="1-based page for the requested section(s)."),
    page_size: int = Query(12, ge=1, le=50, description="Items per page (max 50)."),
    section: str | None = Query(
        None,
        description="Optional: news | current_events | one_offs — returns one section + pagination.",
    ),
):
    """
    Broadsheet home feed.

    News requires a material ``updated_at`` / refinement within 48h and a non-empty dek.
    Membership-only ``last_article_added_at`` bumps are excluded.

    When ``section`` is set, response includes ``pagination`` and ``nav_ids`` for
    reader prev/next navigation.
    """
    try:
        return build_reader_home(
            domain=domain,
            page=page,
            page_size=page_size,
            section=section,
        )
    except Exception as exc:
        logger.exception("reader home failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
