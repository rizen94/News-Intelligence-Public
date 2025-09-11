"""
RSS Management API Routes for News Intelligence System v3.0
Comprehensive feed management, filtering, and monitoring endpoints
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks
from pydantic import BaseModel, Field

from services.enhanced_rss_service import EnhancedRSSService, FeedConfig
from services.rss_fetcher_service import RSSFetcherService, fetch_all_rss_feeds
from services.nlp_classifier_service import get_classifier
from services.deduplication_service import get_deduplication_service
from services.metadata_enrichment_service import get_enrichment_service
from services.monitoring_service import get_monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for request/response
class FeedCreateRequest(BaseModel):
    name: str = Field(..., description="Feed name")
    url: str = Field(..., description="RSS feed URL")
    description: Optional[str] = Field(None, description="Feed description")
    tier: int = Field(2, ge=1, le=3, description="Feed tier: 1=wire services, 2=institutions, 3=specialized")
    priority: int = Field(5, ge=1, le=10, description="Processing priority: 1=highest, 10=lowest")
    language: str = Field("en", description="Feed language")
    country: Optional[str] = Field(None, description="Feed country")
    category: str = Field(..., description="Feed category")
    subcategory: Optional[str] = Field(None, description="Feed subcategory")
    update_frequency: int = Field(30, ge=5, le=1440, description="Update frequency in minutes")
    max_articles: int = Field(50, ge=1, le=1000, description="Maximum articles per update")
    tags: List[str] = Field(default_factory=list, description="Feed tags")
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Content filtering rules")

class FeedUpdateRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    tier: Optional[int] = Field(None, ge=1, le=3)
    priority: Optional[int] = Field(None, ge=1, le=10)
    language: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    update_frequency: Optional[int] = Field(None, ge=5, le=1440)
    max_articles: Optional[int] = Field(None, ge=1, le=1000)
    is_active: Optional[bool] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_headers: Optional[Dict[str, str]] = None
    filters: Optional[Dict[str, Any]] = None

class FilteringConfigRequest(BaseModel):
    config_name: str = Field(..., description="Configuration name")
    config_data: Dict[str, Any] = Field(..., description="Configuration data")

class ArticleQueryRequest(BaseModel):
    limit: int = Field(50, ge=1, le=1000, description="Number of articles to return")
    offset: int = Field(0, ge=0, description="Number of articles to skip")
    category: Optional[str] = Field(None, description="Filter by category")
    source_tier: Optional[int] = Field(None, ge=1, le=3, description="Filter by source tier")
    language: Optional[str] = Field(None, description="Filter by language")
    is_duplicate: Optional[bool] = Field(None, description="Filter by duplicate status")
    enrichment_status: Optional[str] = Field(None, description="Filter by enrichment status")
    date_from: Optional[datetime] = Field(None, description="Filter articles from date")
    date_to: Optional[datetime] = Field(None, description="Filter articles to date")
    search_query: Optional[str] = Field(None, description="Search in title and content")

# Initialize services
rss_service = EnhancedRSSService()

@router.get("/feeds", response_model=Dict[str, Any])
async def get_feeds(
    active_only: bool = Query(False, description="Only return active feeds"),
    tier: Optional[int] = Query(None, ge=1, le=3, description="Filter by tier"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=1000, description="Number of feeds to return"),
    offset: int = Query(0, ge=0, description="Number of feeds to skip")
):
    """Get RSS feeds with filtering options"""
    try:
        result = await rss_service.get_feeds(
            active_only=active_only,
            tier=tier,
            category=category,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        logger.error(f"Error getting feeds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feeds", response_model=Dict[str, Any])
async def create_feed(feed_request: FeedCreateRequest):
    """Create a new RSS feed"""
    try:
        feed_config = FeedConfig(
            name=feed_request.name,
            url=feed_request.url,
            description=feed_request.description,
            tier=feed_request.tier,
            priority=feed_request.priority,
            language=feed_request.language,
            country=feed_request.country,
            category=feed_request.category,
            subcategory=feed_request.subcategory,
            update_frequency=feed_request.update_frequency,
            max_articles=feed_request.max_articles,
            tags=feed_request.tags,
            custom_headers=feed_request.custom_headers,
            filters=feed_request.filters
        )
        
        result = await rss_service.create_feed(feed_config)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/feeds/{feed_id}", response_model=Dict[str, Any])
async def update_feed(
    feed_id: int = Path(..., description="Feed ID"),
    feed_request: FeedUpdateRequest = None
):
    """Update RSS feed configuration"""
    try:
        updates = feed_request.dict(exclude_unset=True)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        result = await rss_service.update_feed(feed_id, updates)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feed {feed_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/feeds/{feed_id}", response_model=Dict[str, Any])
async def delete_feed(feed_id: int = Path(..., description="Feed ID")):
    """Delete RSS feed and associated data"""
    try:
        result = await rss_service.delete_feed(feed_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feed {feed_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feeds/{feed_id}/stats", response_model=Dict[str, Any])
async def get_feed_stats(feed_id: int = Path(..., description="Feed ID")):
    """Get detailed statistics for a specific feed"""
    try:
        result = await rss_service.get_feed_stats(feed_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feed stats for {feed_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feeds/stats/overview", response_model=Dict[str, Any])
async def get_feeds_overview():
    """Get overview statistics for all feeds"""
    try:
        result = await rss_service.get_feed_stats()
        return result
    except Exception as e:
        logger.error(f"Error getting feeds overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feeds/fetch", response_model=Dict[str, Any])
async def fetch_all_feeds_endpoint(
    background_tasks: BackgroundTasks,
    max_concurrent: int = Query(5, ge=1, le=20, description="Maximum concurrent feeds to process")
):
    """Trigger fetching of all active RSS feeds"""
    try:
        # Run in background
        background_tasks.add_task(fetch_all_rss_feeds, max_concurrent)
        
        return {
            "message": "RSS feed fetching started in background",
            "max_concurrent": max_concurrent,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting feed fetching: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feeds/{feed_id}/fetch", response_model=Dict[str, Any])
async def fetch_single_feed(
    feed_id: int = Path(..., description="Feed ID"),
    background_tasks: BackgroundTasks = None
):
    """Trigger fetching of a specific RSS feed"""
    try:
        # Get feed details
        feeds_result = await rss_service.get_feeds()
        feed = None
        for f in feeds_result.get("feeds", []):
            if f["id"] == feed_id:
                feed = f
                break
        
        if not feed:
            raise HTTPException(status_code=404, detail="Feed not found")
        
        # Run in background
        async def fetch_single():
            async with RSSFetcherService() as fetcher:
                return await fetcher.fetch_single_feed(feed)
        
        background_tasks.add_task(fetch_single)
        
        return {
            "message": f"RSS feed '{feed['name']}' fetching started in background",
            "feed_id": feed_id,
            "status": "started"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting single feed fetching: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles", response_model=Dict[str, Any])
async def get_articles(query: ArticleQueryRequest = None):
    """Get articles with filtering and pagination"""
    try:
        if query is None:
            query = ArticleQueryRequest()
        
        # Build query parameters
        params = {
            "limit": query.limit,
            "offset": query.offset
        }
        
        where_conditions = []
        
        if query.category:
            where_conditions.append("a.categories::text ILIKE :category")
            params["category"] = f"%{query.category}%"
        
        if query.source_tier:
            where_conditions.append("a.source_tier = :source_tier")
            params["source_tier"] = query.source_tier
        
        if query.language:
            where_conditions.append("a.language = :language")
            params["language"] = query.language
        
        if query.is_duplicate is not None:
            where_conditions.append("a.is_duplicate = :is_duplicate")
            params["is_duplicate"] = query.is_duplicate
        
        if query.enrichment_status:
            where_conditions.append("a.enrichment_status = :enrichment_status")
            params["enrichment_status"] = query.enrichment_status
        
        if query.date_from:
            where_conditions.append("a.created_at >= :date_from")
            params["date_from"] = query.date_from
        
        if query.date_to:
            where_conditions.append("a.created_at <= :date_to")
            params["date_to"] = query.date_to
        
        if query.search_query:
            where_conditions.append("(a.title ILIKE :search_query OR a.content ILIKE :search_query)")
            params["search_query"] = f"%{query.search_query}%"
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Execute query
        from config.database import get_db
        db_gen = get_db()
        db = next(db_gen)
        try:
            query_sql = f"""
                SELECT a.id, a.title, a.url, a.content, a.summary, a.published_at,
                       a.created_at, a.source, a.source_tier, a.source_priority,
                       a.language, a.detected_language, a.is_translated,
                       a.categories, a.geography, a.entities, a.sentiment_score,
                       a.quality_score, a.is_duplicate, a.cluster_id,
                       a.canonical_article_id, a.enrichment_status
                FROM articles a
                WHERE {where_clause}
                ORDER BY a.created_at DESC
                LIMIT :limit OFFSET :offset
            """
            
            result = db.execute(query_sql, params).fetchall()
            
            articles = []
            for row in result:
                articles.append({
                    "id": row[0],
                    "title": row[1],
                    "url": row[2],
                    "content": row[3],
                    "summary": row[4],
                    "published_at": row[5].isoformat() if row[5] else None,
                    "created_at": row[6].isoformat() if row[6] else None,
                    "source": row[7],
                    "source_tier": row[8],
                    "source_priority": row[9],
                    "language": row[10],
                    "detected_language": row[11],
                    "is_translated": row[12],
                    "categories": json.loads(row[13]) if row[13] else [],
                    "geography": json.loads(row[14]) if row[14] else [],
                    "entities": json.loads(row[15]) if row[15] else [],
                    "sentiment_score": float(row[16]) if row[16] else None,
                    "quality_score": float(row[17]) if row[17] else None,
                    "is_duplicate": row[18],
                    "cluster_id": row[19],
                    "canonical_article_id": row[20],
                    "enrichment_status": row[21]
                })
            
            # Get total count
            count_query = f"""
                SELECT COUNT(*) FROM articles a WHERE {where_clause}
            """
            total_count = db.execute(count_query, params).fetchone()[0]
            
            return {
                "articles": articles,
                "total_count": total_count,
                "limit": query.limit,
                "offset": query.offset
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filtering/config", response_model=Dict[str, Any])
async def get_filtering_config():
    """Get current filtering configuration"""
    try:
        result = await rss_service.get_filtering_config()
        return result
    except Exception as e:
        logger.error(f"Error getting filtering config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/filtering/config", response_model=Dict[str, Any])
async def update_filtering_config(config_request: FilteringConfigRequest):
    """Update global filtering configuration"""
    try:
        result = await rss_service.update_filtering_config(
            config_request.config_name,
            config_request.config_data
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating filtering config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deduplication/detect", response_model=Dict[str, Any])
async def detect_duplicates(
    background_tasks: BackgroundTasks,
    time_window_hours: int = Query(24, ge=1, le=168, description="Time window for duplicate detection in hours")
):
    """Trigger duplicate detection process"""
    try:
        dedup_service = await get_deduplication_service()
        
        # Run in background
        background_tasks.add_task(dedup_service.detect_duplicates, None, time_window_hours)
        
        return {
            "message": "Duplicate detection started in background",
            "time_window_hours": time_window_hours,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting duplicate detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deduplication/stats", response_model=Dict[str, Any])
async def get_deduplication_stats():
    """Get duplicate detection statistics"""
    try:
        dedup_service = await get_deduplication_service()
        result = await dedup_service.get_deduplication_stats()
        return result
    except Exception as e:
        logger.error(f"Error getting deduplication stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enrichment/batch", response_model=Dict[str, Any])
async def enrich_articles_batch(
    background_tasks: BackgroundTasks,
    article_ids: List[int] = Query(..., description="List of article IDs to enrich")
):
    """Trigger metadata enrichment for multiple articles"""
    try:
        enrichment_service = await get_enrichment_service()
        
        # Run in background
        background_tasks.add_task(enrichment_service.batch_enrich_articles, article_ids)
        
        return {
            "message": f"Metadata enrichment started for {len(article_ids)} articles",
            "article_count": len(article_ids),
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting batch enrichment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitoring/metrics", response_model=Dict[str, Any])
async def get_monitoring_metrics():
    """Get comprehensive monitoring metrics"""
    try:
        monitoring_service = await get_monitoring_service()
        result = await monitoring_service.get_metrics_summary()
        return result
    except Exception as e:
        logger.error(f"Error getting monitoring metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitoring/prometheus")
async def get_prometheus_metrics():
    """Get Prometheus metrics in text format"""
    try:
        monitoring_service = await get_monitoring_service()
        result = await monitoring_service.get_prometheus_metrics()
        return result
    except Exception as e:
        logger.error(f"Error getting Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        from config.database import get_db
        db_gen = get_db()
        db = next(db_gen)
        try:
            db.execute("SELECT 1").fetchone()
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
        finally:
            db.close()
        
        # Check services
        services_status = {
            "rss_service": "available",
            "nlp_classifier": "available" if await get_classifier() else "unavailable",
            "deduplication": "available" if await get_deduplication_service() else "unavailable",
            "enrichment": "available" if await get_enrichment_service() else "unavailable",
            "monitoring": "available" if await get_monitoring_service() else "unavailable"
        }
        
        return {
            "status": "healthy" if db_status == "healthy" else "unhealthy",
            "database": db_status,
            "services": services_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }




