#!/usr/bin/env python3
"""
Storyline Management Routes
Consolidated router including all storyline route modules
"""

from fastapi import APIRouter
from .storyline_discovery import router as discovery_router
from .storyline_consolidation import router as consolidation_router
from .storyline_automation import router as automation_router
from .storyline_crud import router as crud_router
from .storyline_articles import router as articles_router
from .storyline_evolution import router as evolution_router
from .storyline_analysis import router as analysis_router
from .storyline_helpers import router as helpers_router
from .storyline_timeline import router as timeline_router
from .storyline_watchlist import router as watchlist_router

# Import background tasks from main management file
from .storyline_management import (
    trigger_storyline_evolution,
    perform_rag_analysis_background,
    process_storyline_rag_analysis
)

# Create main router
router = APIRouter(
    prefix="/api",
    tags=["Storyline Management"]
)

# Include all sub-routers (discovery/consolidation/automation first for route ordering)
router.include_router(discovery_router)
router.include_router(consolidation_router)
router.include_router(automation_router)
router.include_router(crud_router)
router.include_router(articles_router)
router.include_router(evolution_router)
router.include_router(analysis_router)
router.include_router(helpers_router)
router.include_router(timeline_router)
router.include_router(watchlist_router)

# Export background tasks for use in other modules
__all__ = [
    'router',
    'trigger_storyline_evolution',
    'perform_rag_analysis_background'
]

