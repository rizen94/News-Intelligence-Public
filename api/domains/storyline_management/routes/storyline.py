"""
Unified Storyline API Endpoints
Consolidates all storyline-related endpoints into a single router with modular sub-routers
for CRUD operations, article management, and automation controls.
"""

from fastapi import APIRouter

# Sub-routers for different aspects of storyline management
router_crud = APIRouter(tags=["Storyline CRUD"])
router_articles = APIRouter(tags=["Storyline Articles"])
router_automation = APIRouter(tags=["Storyline Automation"])

# Import and register CRUD routes
from .storyline_crud import router as crud_router
router_crud.include_router(crud_router)

# Import and register articles routes
from .storyline_articles import router as articles_router
router_articles.include_router(articles_router)

# Import and register automation routes
from .automation import router as automation_router
router_automation.include_router(automation_router)

# Main router that includes all sub-routers
main_router = APIRouter(prefix="/storylines", tags=["Storylines"])
main_router.include_router(router_crud)
main_router.include_router(router_articles)
main_router.include_router(router_automation)

# For backward compatibility, also expose individual routers
__all__ = ["main_router", "router_crud", "router_articles", "router_automation"]