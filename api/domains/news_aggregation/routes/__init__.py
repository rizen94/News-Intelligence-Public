# News Aggregation — consolidated router
from fastapi import APIRouter

from .news_aggregation import router as news_router

router = APIRouter(tags=["News Aggregation"])
router.include_router(news_router)

__all__ = ["router"]
