# Content Analysis — consolidated router
from fastapi import APIRouter

from .article_deduplication import router as article_dedup_router
from .content_analysis import router as content_router
from .deduplication_api import router as deduplication_api_router
from .llm_activity_monitoring import router as llm_activity_router
from .topic_management import router as topic_router
from .topic_queue_management import router as topic_queue_router

router = APIRouter(tags=["Content Analysis"])
router.include_router(content_router)
router.include_router(topic_router)
router.include_router(topic_queue_router)
router.include_router(article_dedup_router)
router.include_router(llm_activity_router)
router.include_router(deduplication_api_router)

__all__ = ["router"]
