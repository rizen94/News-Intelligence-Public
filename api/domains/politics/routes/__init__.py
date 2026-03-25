"""Politics routes — official U.S. government data (Congress.gov, etc.)."""

from fastapi import APIRouter

from .official import router as official_router

router = APIRouter()
router.include_router(official_router)

__all__ = ["router"]
