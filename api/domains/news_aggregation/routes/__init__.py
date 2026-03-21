# News Aggregation — consolidated router
from fastapi import APIRouter

from .news_aggregation import router as news_router
from .rss_duplicate_management import router as rss_dup_router

router = APIRouter(tags=["News Aggregation"])
router.include_router(news_router)
router.include_router(rss_dup_router)

__all__ = ["router"]
