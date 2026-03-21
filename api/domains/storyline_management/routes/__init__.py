#!/usr/bin/env python3
"""
Storyline management — aggregated FastAPI router (pattern for other domains).

Mounts sub-routers under ``prefix="/api"`` so paths align with the flat ``/api/...``
convention. **Include order matters** where two routes could match the same path
(e.g. timeline_router before helpers_router — see comments below).

Each ``storyline_*.py`` module defines endpoints for one concern (CRUD, discovery,
automation, articles, timeline, watchlist, …). For domain terminology, see repo
``AGENTS.md`` (``storylines`` not ``stories``).
"""

from fastapi import APIRouter

from .storyline_analysis import router as analysis_router
from .storyline_articles import router as articles_router
from .storyline_automation import router as automation_router
from .storyline_consolidation import router as consolidation_router
from .storyline_crud import router as crud_router
from .storyline_discovery import router as discovery_router
from .storyline_evolution import router as evolution_router
from .storyline_helpers import router as helpers_router

# Import background tasks from main management file
from .storyline_management import (
    perform_rag_analysis_background,
    process_storyline_rag_analysis,
    trigger_storyline_evolution,
)
from .storyline_timeline import router as timeline_router
from .storyline_watchlist import router as watchlist_router

# Create main router
router = APIRouter(prefix="/api", tags=["Storyline Management"])

# Include all sub-routers (discovery/consolidation/automation first for route ordering)
router.include_router(discovery_router)
router.include_router(consolidation_router)
router.include_router(automation_router)
router.include_router(crud_router)
router.include_router(articles_router)
router.include_router(evolution_router)
router.include_router(analysis_router)
# Chronological timeline (public.chronological_events) must register before helpers_router,
# which also defines GET .../timeline (legacy domain.timeline_events) — first match wins.
router.include_router(timeline_router)
router.include_router(helpers_router)
router.include_router(watchlist_router)

# Export background tasks for use in other modules
__all__ = ["router", "trigger_storyline_evolution", "perform_rag_analysis_background"]
