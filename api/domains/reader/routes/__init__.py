"""Reader route aggregation — prefix /api/reader."""

from fastapi import APIRouter

from .home import router as home_router
from .storylines import router as storylines_router

router = APIRouter(prefix="/api/reader", tags=["Reader"])
router.include_router(home_router)
router.include_router(storylines_router)

reader_router = router

__all__ = ["router", "reader_router"]
