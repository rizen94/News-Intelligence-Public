"""Politics routes — official U.S. government data + Quiver congress trades."""

from fastapi import APIRouter

from .official import router as official_router
from .quiver_trades import router as quiver_trades_router

router = APIRouter()
router.include_router(official_router)
router.include_router(quiver_trades_router)

__all__ = ["router"]
