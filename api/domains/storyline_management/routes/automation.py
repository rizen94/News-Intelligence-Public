"""
Unified Storyline Automation API Endpoints
Consolidates all storyline automation-related endpoints into a single router.
"""

from fastapi import APIRouter

# Main router for automation
router = APIRouter(tags=["Storyline Automation"])

# Import and register the original automation routes
from .storyline_automation import router as automation_router
router.include_router(automation_router)

# Import and register bulk automation routes
from .storyline_automation_bulk import register_bulk_routes
register_bulk_routes(router)