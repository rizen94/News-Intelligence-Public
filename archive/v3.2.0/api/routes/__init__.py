"""
News Intelligence System v3.0 - API Routes Package
FastAPI route modules for all API endpoints
"""

from . import health, dashboard, articles, story_management, intelligence, monitoring, rss, entities, clusters, sources, search, rag, automation, advanced_ml, sentiment, readability, story_consolidation, ai_processing

__all__ = [
    "health",
    "dashboard",
    "articles",
    "story_management",
    "intelligence",
    "monitoring",
    "rss",
    "entities",
    "clusters",
    "sources",
    "search",
    "rag",
    "automation",
    "advanced_ml",
    "sentiment",
    "readability",
    "story_consolidation",
    "ai_processing"
]
