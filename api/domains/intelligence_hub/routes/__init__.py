# Intelligence Hub — consolidated router
from fastapi import APIRouter
from .intelligence_hub import router as hub_router
from .intelligence_analysis import router as analysis_router
from .rag_queries import router as rag_router
from .content_synthesis import router as synthesis_router
from .context_centric import router as context_centric_router
from .quality import router as quality_router
from .cross_domain import router as cross_domain_router
from .products import router as products_router
from .enrichment import router as enrichment_router

router = APIRouter(tags=["Intelligence Hub"])
router.include_router(hub_router)
router.include_router(analysis_router)
router.include_router(rag_router)
router.include_router(synthesis_router)
router.include_router(context_centric_router)
router.include_router(quality_router)
router.include_router(cross_domain_router)
router.include_router(products_router)
router.include_router(enrichment_router)

__all__ = ["router"]
