"""
News Intelligence System v3.0 - API Routes Package
FastAPI route modules for all API endpoints
"""

from . import health, articles, rss_feeds, fallback_logging

__all__ = [
    "health",
    "articles", 
    "rss_feeds",
    "fallback_logging"
]
