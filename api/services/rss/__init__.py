"""
RSS Service - Consolidated RSS Feed Management
Combines feed management, async fetching, and pipeline processing

This service consolidates:
- rss_service.py (basic CRUD)
- enhanced_rss_service.py (enhanced management)
- rss_fetcher_service.py (async fetching)
- rss_processing_service.py (pipeline processing)

All functionality is now available through a single RSSService class.
"""

import logging

from .base import BaseRSSService, FeedConfig, FeedStatus, FeedTier
from .fetching import ArticleData, RSSFetchingModule
from .processing import RSSProcessingModule

logger = logging.getLogger(__name__)


class RSSService(BaseRSSService):
    """
    Consolidated RSS Service

    Provides all RSS feed functionality:
    - Feed management (CRUD, stats, configuration)
    - Async feed fetching with filtering
    - Pipeline-integrated processing

    Usage:
        from services.rss import RSSService

        service = RSSService()

        # Management operations
        feeds = await service.get_feeds(active_only=True)
        stats = await service.get_feed_stats()

        # Async fetching
        async with service.fetching as fetcher:
            result = await fetcher.fetch_all_feeds(max_concurrent=5)

        # Pipeline processing
        result = await service.processing.process_all_feeds()
    """

    def __init__(self):
        """Initialize consolidated RSS service"""
        super().__init__()
        self._fetching_module = None
        self._processing_module = None

    @property
    def fetching(self) -> RSSFetchingModule:
        """Get fetching module (lazy initialization)"""
        if self._fetching_module is None:
            self._fetching_module = RSSFetchingModule(self)
        return self._fetching_module

    @property
    def processing(self) -> RSSProcessingModule:
        """Get processing module (lazy initialization)"""
        if self._processing_module is None:
            self._processing_module = RSSProcessingModule(self)
        return self._processing_module


# Global instance for backward compatibility
_rss_service_instance = None


def get_rss_service() -> RSSService:
    """Get global RSS service instance (backward compatibility)"""
    global _rss_service_instance
    if _rss_service_instance is None:
        _rss_service_instance = RSSService()
    return _rss_service_instance


def get_rss_processor() -> RSSProcessingModule:
    """
    Get RSS processor instance (backward compatibility)

    Note: This maintains compatibility with code that uses:
    from services.rss_processing_service import get_rss_processor
    """
    service = get_rss_service()
    return service.processing


# Convenience function for async fetching (backward compatibility)
async def fetch_all_rss_feeds(max_concurrent: int = 5) -> dict:
    """
    Fetch all RSS feeds with concurrency control (backward compatibility)

    Note: This maintains compatibility with code that uses:
    from services.rss_fetcher_service import fetch_all_rss_feeds
    """
    service = get_rss_service()
    async with service.fetching as fetcher:
        return await fetcher.fetch_all_feeds(max_concurrent)


# Export all public classes and functions
__all__ = [
    "RSSService",
    "BaseRSSService",
    "RSSFetchingModule",
    "RSSProcessingModule",
    "FeedTier",
    "FeedStatus",
    "FeedConfig",
    "ArticleData",
    "get_rss_service",
    "get_rss_processor",
    "fetch_all_rss_feeds",
]
