"""
News Intelligence System v3.0 - API Routes Package
FastAPI route modules for all API endpoints
"""

from . import health, dashboard, articles, stories, intelligence, ml, monitoring, rss, deduplication, entities, clusters, sources, search, rag, ml_management, automation

__all__ = [
    "health",
    "dashboard", 
    "articles",
    "stories",
    "intelligence",
    "ml",
    "monitoring",
    "rss",
    "deduplication",
    "entities",
    "clusters",
    "sources",
    "search",
    "rag",
    "ml_management",
    "automation"
]
