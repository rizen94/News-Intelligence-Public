# Intelligence Hub — consolidated router
from fastapi import APIRouter
from .intelligence_hub import router as hub_router
from .intelligence_analysis import router as analysis_router
from .rag_queries import router as rag_router
from .content_synthesis import router as synthesis_router

router = APIRouter(tags=["Intelligence Hub"])
router.include_router(hub_router)
router.include_router(analysis_router)
router.include_router(rag_router)
router.include_router(synthesis_router)

__all__ = ["router"]
