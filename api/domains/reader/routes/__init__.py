"""Reader route aggregation — prefix /api/reader."""

from fastapi import APIRouter

from .home import router as home_router
from .storylines import router as storylines_router
from .vault_notes import router as vault_notes_router
from .vault_hubs import router as vault_hubs_router
from .articles import router as articles_router
from .research_subjects import router as research_subjects_router

router = APIRouter(prefix="/api/reader", tags=["Reader"])
router.include_router(home_router)
router.include_router(storylines_router)
router.include_router(vault_notes_router)
router.include_router(vault_hubs_router)
router.include_router(articles_router)
router.include_router(research_subjects_router)

reader_router = router

__all__ = ["router", "reader_router"]
