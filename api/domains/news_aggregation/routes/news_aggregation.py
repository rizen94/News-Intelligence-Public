"""
Domain 1: News Aggregation Routes
Handles RSS feed processing, article ingestion, and content quality assessment
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/news-aggregation",
    tags=["News Aggregation"],
    responses={404: {"description": "Not found"}}
)

@router.get("/health")
async def health_check():
    """Health check for News Aggregation domain"""
    try:
        # Check database connection
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "domain": "news_aggregation",
                "status": "unhealthy",
                "error": "Database connection failed"
            }
        
        # Check LLM service
        llm_status = await llm_service.get_model_status()
        
        conn.close()
        
        return {
            "success": True,
            "domain": "news_aggregation",
            "status": "healthy",
            "llm_service": llm_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "news_aggregation",
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/rss-feeds")
async def get_rss_feeds():
    """Get all configured RSS feeds"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, feed_name, feed_url, is_active, last_fetched_at, 
                           fetch_interval_seconds, quality_score, created_at
                    FROM rss_feeds 
                    ORDER BY feed_name
                """)
                
                feeds = []
                for row in cur.fetchall():
                    feeds.append({
                        "id": row[0],
                        "feed_name": row[1],
                        "feed_url": row[2],
                        "is_active": row[3],
                        "last_fetched_at": row[4].isoformat() if row[4] else None,
                        "fetch_interval_seconds": row[5],
                        "quality_score": row[6],
                        "created_at": row[7].isoformat() if row[7] else None
                    })
                
                return {
                    "success": True,
                    "data": {"feeds": feeds},
                    "count": len(feeds),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching RSS feeds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rss-feeds")
async def create_rss_feed(feed_data: Dict[str, Any]):
    """Create a new RSS feed"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    feed_data.get("feed_name"),
                    feed_data.get("feed_url"),
                    feed_data.get("is_active", True),
                    feed_data.get("fetch_interval_seconds", 3600),  # 1 hour default
                    datetime.now()
                ))
                
                feed_id = cur.fetchone()[0]
                conn.commit()
                
                return {
                    "success": True,
                    "data": {"feed_id": feed_id},
                    "message": "RSS feed created successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error creating RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fetch-articles")
async def fetch_articles_from_feeds(background_tasks: BackgroundTasks):
    """Fetch articles from all active RSS feeds"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, feed_name, feed_url, fetch_interval_seconds, last_fetched_at
                    FROM rss_feeds 
                    WHERE is_active = true
                """)
                
                feeds = cur.fetchall()
                
                # Start background task for fetching
                background_tasks.add_task(process_rss_feeds, feeds)
                
                return {
                    "success": True,
                    "message": f"Started fetching from {len(feeds)} RSS feeds",
                    "feeds_count": len(feeds),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting RSS fetch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles/recent")
async def get_recent_articles(limit: int = 50, hours: int = 24):
    """Get recently ingested articles"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, url, source_domain, published_at, 
                           summary, quality_score, word_count, created_at
                    FROM articles 
                    WHERE created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (cutoff_time, limit))
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "url": row[2],
                        "source_domain": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "summary": row[5],
                        "quality_score": row[6],
                        "word_count": row[7],
                        "created_at": row[8].isoformat() if row[8] else None
                    })
                
                return {
                    "success": True,
                    "data": {"articles": articles},
                    "count": len(articles),
                    "timeframe_hours": hours,
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching recent articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/articles/{article_id}/analyze-quality")
async def analyze_article_quality(article_id: int, background_tasks: BackgroundTasks):
    """Analyze article quality using LLM"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, content, url, source_domain
                    FROM articles 
                    WHERE id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")
                
                # Start background quality analysis
                background_tasks.add_task(process_article_quality, article)
                
                return {
                    "success": True,
                    "message": "Quality analysis started",
                    "article_id": article_id,
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting quality analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_aggregation_statistics():
    """Get news aggregation statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Total articles
                cur.execute("SELECT COUNT(*) FROM articles")
                total_articles = cur.fetchone()[0]
                
                # Articles last 24 hours
                yesterday = datetime.now() - timedelta(days=1)
                cur.execute("SELECT COUNT(*) FROM articles WHERE created_at >= %s", (yesterday,))
                recent_articles = cur.fetchone()[0]
                
                # Active RSS feeds
                cur.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")
                active_feeds = cur.fetchone()[0]
                
                # Average quality score
                cur.execute("SELECT AVG(quality_score) FROM articles WHERE quality_score IS NOT NULL")
                avg_quality = cur.fetchone()[0] or 0
                
                return {
                    "success": True,
                    "data": {
                        "total_articles": total_articles,
                        "recent_articles_24h": recent_articles,
                        "active_rss_feeds": active_feeds,
                        "average_quality_score": round(avg_quality, 2)
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def process_rss_feeds(feeds: List[tuple]):
    """Background task to process RSS feeds"""
    logger.info(f"Processing {len(feeds)} RSS feeds")
    # Implementation would go here - RSS parsing, article extraction, etc.
    pass

async def process_article_quality(article: tuple):
    """Background task to analyze article quality using LLM"""
    try:
        article_id, title, content, url, source = article
        
        # Use LLM to analyze quality
        quality_analysis = await llm_service.generate_summary(
            content, 
            TaskType.COMPREHENSIVE_ANALYSIS
        )
        
        if quality_analysis["success"]:
            # Update article with quality analysis
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE articles 
                            SET quality_score = %s, 
                                summary = %s,
                                updated_at = %s
                            WHERE id = %s
                        """, (
                            85,  # Placeholder quality score
                            quality_analysis["summary"],
                            datetime.now(),
                            article_id
                        ))
                        conn.commit()
                        logger.info(f"Updated quality analysis for article {article_id}")
                finally:
                    conn.close()
        
    except Exception as e:
        logger.error(f"Error processing article quality: {e}")
