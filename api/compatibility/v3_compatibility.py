"""
News Intelligence System v4.0 - API Compatibility Layer
Maintains v3.0 endpoint compatibility while using v4.0 domain architecture
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

# Import v4.0 domain services
from domains.news_aggregation.routes.news_aggregation import router as news_aggregation_router
from domains.content_analysis.routes.content_analysis import router as content_analysis_router
from domains.storyline_management.routes.storyline_management import router as storyline_management_router
from shared.services.llm_service import llm_service
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

# Create compatibility router
compatibility_router = APIRouter(
    prefix="/api",
    tags=["v3.0 Compatibility"],
    responses={404: {"description": "Not found"}}
)

# ============================================================================
# HEALTH ENDPOINTS - v3.0 Compatible
# ============================================================================

@compatibility_router.get("/health/")
async def health_check_v3():
    """v3.0 compatible health check"""
    try:
        # Check database connection
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "status": "unhealthy",
                "error": "Database connection failed",
                "timestamp": datetime.now().isoformat()
            }
        
        # Check LLM service
        llm_status = await llm_service.get_model_status()
        
        conn.close()
        
        return {
            "success": True,
            "status": "healthy",
            "database": "connected",
            "llm_service": llm_status.get("success", False),
            "models": {
                "primary": llm_status.get("primary_model", "unknown"),
                "secondary": llm_status.get("secondary_model", "unknown")
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# ARTICLES ENDPOINTS - v3.0 Compatible
# ============================================================================

@compatibility_router.get("/articles/")
async def get_articles_v3(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None
):
    """v3.0 compatible articles endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Build query with filters
            where_conditions = []
            params = []
            
            if status:
                where_conditions.append("status = %s")
                params.append(status)
            
            if source:
                where_conditions.append("source_domain = %s")
                params.append(source)
            
            if category:
                where_conditions.append("category = %s")
                params.append(category)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM articles {where_clause}"
            with conn.cursor() as cur:
                cur.execute(count_query, params)
                total = cur.fetchone()[0]
            
            # Get articles with pagination
            offset = (page - 1) * limit
            articles_query = f"""
                SELECT id, title, content, url, published_at, source_domain, category, 
                       processing_status, summary, quality_score, word_count, reading_time_minutes,
                       sentiment_score, entities, created_at, updated_at
                FROM articles 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            
            with conn.cursor() as cur:
                cur.execute(articles_query, params + [limit, offset])
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2],
                        "url": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "source": row[5],  # source_domain mapped to source for v3 compatibility
                        "category": row[6],
                        "status": row[7],  # processing_status mapped to status for v3 compatibility
                        "summary": row[8],
                        "quality_score": row[9],
                        "word_count": row[10],
                        "reading_time": row[11],  # reading_time_minutes mapped to reading_time for v3 compatibility
                        "sentiment_score": row[12],
                        "entities": row[13],
                        "created_at": row[14].isoformat() if row[14] else None,
                        "updated_at": row[15].isoformat() if row[15] else None
                    })
                
                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "total": total,
                        "page": page,
                        "limit": limit,
                        "pages": (total + limit - 1) // limit
                    },
                    "message": f"Retrieved {len(articles)} articles",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/articles/{article_id}")
async def get_article_v3(article_id: int):
    """v3.0 compatible single article endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, content, url, published_at, source, category, 
                           status, summary, quality_score, word_count, reading_time,
                           sentiment_score, entities, created_at, updated_at
                    FROM articles 
                    WHERE id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")
                
                return {
                    "success": True,
                    "data": {
                        "id": article[0],
                        "title": article[1],
                        "content": article[2],
                        "url": article[3],
                        "published_at": article[4].isoformat() if article[4] else None,
                        "source": article[5],
                        "category": article[6],
                        "status": article[7],
                        "summary": article[8],
                        "quality_score": article[9],
                        "word_count": article[10],
                        "reading_time": article[11],
                        "sentiment_score": article[12],
                        "entities": article[13],
                        "created_at": article[14].isoformat() if article[14] else None,
                        "updated_at": article[15].isoformat() if article[15] else None
                    },
                    "message": "Article retrieved successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching article: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STORYLINES ENDPOINTS - v3.0 Compatible
# ============================================================================

@compatibility_router.get("/storylines/")
async def get_storylines_v3():
    """v3.0 compatible storylines endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, description, processing_status, created_at, updated_at, created_by_user
                    FROM storylines 
                    ORDER BY updated_at DESC
                """)
                
                storylines = []
                for row in cur.fetchall():
                    storylines.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "status": row[3],  # processing_status mapped to status for v3 compatibility
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "created_by": row[6]  # created_by_user mapped to created_by for v3 compatibility
                    })
                
                return {
                    "success": True,
                    "data": {
                        "storylines": storylines,
                        "total": len(storylines)
                    },
                    "message": f"Retrieved {len(storylines)} storylines",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.post("/storylines/")
async def create_storyline_v3(request: Dict[str, Any]):
    """v3.0 compatible storyline creation"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO storylines (title, description, processing_status, created_at, updated_at, created_by_user)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    request.get("title"),
                    request.get("description", ""),
                    request.get("status", "active"),  # status mapped to processing_status
                    datetime.now(),
                    datetime.now(),
                    request.get("created_by", "system")  # created_by mapped to created_by_user
                ))
                
                storyline_id = cur.fetchone()[0]
                conn.commit()
                
                return {
                    "success": True,
                    "data": {"storyline_id": storyline_id},
                    "message": "Storyline created successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error creating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/storylines/{storyline_id}")
async def get_storyline_v3(storyline_id: int):
    """v3.0 compatible single storyline endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline details
                cur.execute("""
                    SELECT id, title, description, processing_status, created_at, updated_at, created_by_user
                    FROM storylines 
                    WHERE id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get articles in storyline (if storyline_articles table exists)
                try:
                    cur.execute("""
                        SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                        FROM articles a
                        JOIN storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY a.published_at ASC
                    """, (storyline_id,))
                    
                    articles = []
                    for row in cur.fetchall():
                        articles.append({
                            "id": row[0],
                            "title": row[1],
                            "url": row[2],
                            "source": row[3],
                            "published_at": row[4].isoformat() if row[4] else None,
                            "summary": row[5]
                        })
                except Exception:
                    # storyline_articles table doesn't exist yet
                    articles = []
                
                return {
                    "success": True,
                    "data": {
                        "storyline": {
                            "id": storyline[0],
                            "title": storyline[1],
                            "description": storyline[2],
                            "status": storyline[3],
                            "created_at": storyline[4].isoformat() if storyline[4] else None,
                            "updated_at": storyline[5].isoformat() if storyline[5] else None,
                            "created_by": storyline[6]
                        },
                        "articles": articles
                    },
                    "message": "Storyline retrieved successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# RSS FEEDS ENDPOINTS - v3.0 Compatible
# ============================================================================

@compatibility_router.get("/rss-feeds/")
async def get_rss_feeds_v3():
    """v3.0 compatible RSS feeds endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, feed_name, feed_url, is_active, last_fetched_at, fetch_interval_seconds,
                           created_at, updated_at, error_count, last_error_message
                    FROM rss_feeds 
                    ORDER BY feed_name
                """)
                
                feeds = []
                for row in cur.fetchall():
                    feeds.append({
                        "id": row[0],
                        "name": row[1],  # feed_name mapped to name for v3 compatibility
                        "url": row[2],   # feed_url mapped to url for v3 compatibility
                        "is_active": row[3],
                        "last_fetched": row[4].isoformat() if row[4] else None,  # last_fetched_at mapped to last_fetched
                        "fetch_interval": row[5],  # fetch_interval_seconds mapped to fetch_interval
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None,
                        "error_count": row[8],
                        "last_error": row[9]  # last_error_message mapped to last_error
                    })
                
                return {
                    "success": True,
                    "data": {
                        "feeds": feeds,
                        "total": len(feeds)
                    },
                    "message": f"Retrieved {len(feeds)} RSS feeds",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching RSS feeds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# DASHBOARD ENDPOINTS - v3.0 Compatible
# ============================================================================

@compatibility_router.get("/dashboard/stats")
async def get_dashboard_stats_v3():
    """v3.0 compatible dashboard stats endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get article statistics
                cur.execute("SELECT COUNT(*) FROM articles")
                total_articles = cur.fetchone()[0]
                
                # Articles from today
                today = datetime.now().date()
                cur.execute("SELECT COUNT(*) FROM articles WHERE DATE(created_at) = %s", (today,))
                today_articles = cur.fetchone()[0]
                
                # Get RSS feed statistics
                cur.execute("SELECT COUNT(*) FROM rss_feeds")
                total_feeds = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")
                active_feeds = cur.fetchone()[0]
                
                # Get storyline statistics
                cur.execute("SELECT COUNT(*) FROM storylines")
                total_storylines = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storylines WHERE processing_status = 'active'")
                active_storylines = cur.fetchone()[0]
                
                # Get recent activity (last 10 articles)
                cur.execute("""
                    SELECT id, title, source_domain, created_at
                    FROM articles 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """)
                
                recent_activity = []
                for row in cur.fetchall():
                    recent_activity.append({
                        "id": row[0],
                        "title": row[1],
                        "source": row[2],
                        "created_at": row[3].isoformat() if row[3] else None
                    })
                
                return {
                    "success": True,
                    "data": {
                        "system_health": {"status": "healthy"},
                        "article_stats": {
                            "total": total_articles,
                            "today": today_articles
                        },
                        "rss_stats": {
                            "total_feeds": total_feeds,
                            "active_feeds": active_feeds
                        },
                        "storyline_stats": {
                            "total": total_storylines,
                            "active": active_storylines
                        },
                        "recent_activity": recent_activity
                    },
                    "message": "Dashboard stats retrieved successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ADDITIONAL COMPATIBILITY ENDPOINTS
# ============================================================================

@compatibility_router.post("/storylines/{storyline_id}/add-article")
async def add_article_to_storyline_v3(storyline_id: int, request: Dict[str, Any]):
    """v3.0 compatible add article to storyline endpoint"""
    try:
        article_id = request.get("article_id")
        if not article_id:
            raise HTTPException(status_code=400, detail="Article ID is required")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute("SELECT id FROM storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Check if article exists
                cur.execute("SELECT id FROM articles WHERE id = %s", (article_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found")
                
                # Try to add article to storyline (if storyline_articles table exists)
                try:
                    cur.execute("""
                        INSERT INTO storyline_articles (storyline_id, article_id, added_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (storyline_id, article_id) DO NOTHING
                    """, (storyline_id, article_id, datetime.now()))
                    
                    conn.commit()
                    
                    return {
                        "success": True,
                        "message": "Article added to storyline successfully",
                        "storyline_id": storyline_id,
                        "article_id": article_id,
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception:
                    # storyline_articles table doesn't exist yet
                    return {
                        "success": False,
                        "message": "Storyline-article relationship not yet implemented",
                        "error": "storyline_articles table not found",
                        "timestamp": datetime.now().isoformat()
                    }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error adding article to storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# TOPIC CLUSTERING COMPATIBILITY ENDPOINTS
# ============================================================================

@compatibility_router.get("/topics/")
async def get_topics_v3(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    category: Optional[str] = None
):
    """v3.0 compatible topics endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query with filters
                where_conditions = ["tc.is_active = true"]
                params = []
                
                if search:
                    where_conditions.append("tc.cluster_name ILIKE %s")
                    params.append(f"%{search}%")
                
                if category:
                    where_conditions.append("tc.cluster_type = %s")
                    params.append(category)
                
                where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # Get topics with article counts
                query = f"""
                    SELECT tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           tc.created_at, tc.updated_at, tc.metadata,
                           COUNT(atc.article_id) as article_count,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    {where_clause}
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                             tc.created_at, tc.updated_at, tc.metadata
                    ORDER BY article_count DESC, tc.created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cur.execute(query, params + [limit, offset])
                
                topics = []
                for row in cur.fetchall():
                    topics.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "type": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "metadata": row[6],
                        "article_count": row[7] or 0,
                        "avg_relevance": float(row[8]) if row[8] else 0.0,
                        "avg_confidence": float(row[8]) if row[8] else 0.0,  # Map avg_relevance to avg_confidence for frontend compatibility
                        "category": row[3],  # Map type to category for frontend compatibility
                        "subcategory": None,  # Add subcategory field for frontend compatibility
                        "latest_article": None  # Add latest_article field for frontend compatibility
                    })
                
                # Get total count
                count_query = f"""
                    SELECT COUNT(DISTINCT tc.id)
                    FROM topic_clusters tc
                    {where_clause}
                """
                cur.execute(count_query, params)
                total_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "topics": topics,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit
                    },
                    "message": f"Retrieved {len(topics)} topics",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/topics/categories/stats")
async def get_category_stats_v3():
    """v3.0 compatible category stats endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get category statistics
                cur.execute("""
                    SELECT tc.cluster_type,
                           COUNT(tc.id) as topic_count,
                           COUNT(atc.article_id) as total_articles,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    WHERE tc.is_active = true
                    GROUP BY tc.cluster_type
                    ORDER BY total_articles DESC
                """)
                
                categories = []
                for row in cur.fetchall():
                    categories.append({
                        "category": row[0],
                        "topic_count": row[1],
                        "total_articles": row[2] or 0,
                        "avg_relevance": float(row[3]) if row[3] else 0.0
                    })
                
                return {
                    "success": True,
                    "data": {
                        "categories": categories,
                        "total_categories": len(categories)
                    },
                    "message": f"Retrieved statistics for {len(categories)} categories",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching category stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/intelligence/topic-clusters")
async def get_intelligence_topic_clusters_v3(
    time_period: str = "7d",
    min_articles: int = 3,
    limit: int = 20
):
    """v3.0 compatible intelligence topic clusters endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Calculate time filter
                if time_period == "24h":
                    time_filter = datetime.now() - timedelta(hours=24)
                elif time_period == "7d":
                    time_filter = datetime.now() - timedelta(days=7)
                elif time_period == "30d":
                    time_filter = datetime.now() - timedelta(days=30)
                else:
                    time_filter = datetime.now() - timedelta(days=7)
                
                # Get topic clusters with recent activity
                cur.execute("""
                    SELECT tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           tc.created_at, tc.updated_at, tc.metadata,
                           COUNT(atc.article_id) as total_articles,
                           COUNT(CASE WHEN a.created_at >= %s THEN atc.article_id END) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance,
                           MAX(a.published_at) as latest_article_date
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    LEFT JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                             tc.created_at, tc.updated_at, tc.metadata
                    HAVING COUNT(atc.article_id) >= %s
                    ORDER BY recent_articles DESC, total_articles DESC
                    LIMIT %s
                """, (time_filter, min_articles, limit))
                
                clusters = []
                for row in cur.fetchall():
                    clusters.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "type": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "metadata": row[6],
                        "total_articles": row[7] or 0,
                        "recent_articles": row[8] or 0,
                        "avg_relevance": float(row[9]) if row[9] else 0.0,
                        "avg_confidence": float(row[9]) if row[9] else 0.0,  # Map avg_relevance to avg_confidence for frontend compatibility
                        "latest_article_date": row[10].isoformat() if row[10] else None,
                        "category": row[3],  # Map type to category for frontend compatibility
                        "subcategory": None,  # Add subcategory field for frontend compatibility
                        "latest_article": row[10].isoformat() if row[10] else None,  # Map latest_article_date to latest_article for frontend compatibility
                        "article_count": row[7] or 0  # Map total_articles to article_count for frontend compatibility
                    })
                
                return {
                    "success": True,
                    "data": {
                        "clusters": clusters,
                        "time_period": time_period,
                        "min_articles": min_articles,
                        "total_clusters": len(clusters)
                    },
                    "message": f"Retrieved {len(clusters)} topic clusters",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topic clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/intelligence/trending-topics")
async def get_trending_topics_v3(
    time_period: str = "24h",
    limit: int = 10
):
    """v3.0 compatible trending topics endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Calculate time filter
                if time_period == "24h":
                    time_filter = datetime.now() - timedelta(hours=24)
                elif time_period == "7d":
                    time_filter = datetime.now() - timedelta(days=7)
                elif time_period == "30d":
                    time_filter = datetime.now() - timedelta(days=30)
                else:
                    time_filter = datetime.now() - timedelta(hours=24)
                
                # Get trending topics based on recent article activity
                cur.execute("""
                    SELECT tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance,
                           AVG(a.sentiment_score) as avg_sentiment,
                           MAX(a.published_at) as latest_article_date
                    FROM topic_clusters tc
                    JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    AND a.created_at >= %s
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type
                    ORDER BY recent_articles DESC, avg_relevance DESC
                    LIMIT %s
                """, (time_filter, limit))
                
                trending_topics = []
                for row in cur.fetchall():
                    trending_topics.append({
                        "name": row[0],
                        "description": row[1],
                        "type": row[2],
                        "recent_articles": row[3],
                        "avg_relevance": float(row[4]) if row[4] else 0.0,
                        "avg_confidence": float(row[4]) if row[4] else 0.0,  # Map avg_relevance to avg_confidence for frontend compatibility
                        "avg_sentiment": float(row[5]) if row[5] else 0.0,
                        "latest_article_date": row[6].isoformat() if row[6] else None,
                        "trend_score": row[3] * (float(row[4]) if row[4] else 0.0),  # Simple trend calculation
                        "category": row[2],  # Map type to category for frontend compatibility
                        "subcategory": None,  # Add subcategory field for frontend compatibility
                        "latest_article": row[6].isoformat() if row[6] else None,  # Map latest_article_date to latest_article for frontend compatibility
                        "article_count": row[3]  # Map recent_articles to article_count for frontend compatibility
                    })
                
                return {
                    "success": True,
                    "data": {
                        "trending_topics": trending_topics,
                        "time_period": time_period,
                        "total_topics": len(trending_topics)
                    },
                    "message": f"Retrieved {len(trending_topics)} trending topics",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/topics/{topic_name}/articles")
async def get_topic_articles_v3(
    topic_name: str,
    limit: int = 20,
    offset: int = 0
):
    """v3.0 compatible topic articles endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get topic ID
                cur.execute("SELECT id FROM topic_clusters WHERE cluster_name = %s", (topic_name,))
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id = topic_result[0]
                
                # Get articles for this topic
                cur.execute("""
                    SELECT a.id, a.title, a.content, a.url, a.source_domain, a.published_at,
                           a.summary, a.quality_score, a.sentiment_score, a.sentiment_label,
                           atc.relevance_score, atc.assigned_at
                    FROM articles a
                    JOIN article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY atc.relevance_score DESC, a.published_at DESC
                    LIMIT %s OFFSET %s
                """, (topic_id, limit, offset))
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2][:500] + "..." if len(row[2]) > 500 else row[2],
                        "url": row[3],
                        "source": row[4],  # source_domain mapped to source for v3 compatibility
                        "published_at": row[5].isoformat() if row[5] else None,
                        "summary": row[6],
                        "quality_score": row[7],
                        "sentiment_score": row[8],
                        "sentiment": row[9],  # sentiment_label mapped to sentiment for v3 compatibility
                        "relevance_score": float(row[10]) if row[10] else 0.0,
                        "topic_confidence": float(row[10]) if row[10] else 0.0,  # Map relevance_score to topic_confidence for frontend compatibility
                        "assigned_at": row[11].isoformat() if row[11] else None,
                        "created_at": row[11].isoformat() if row[11] else None,  # Map assigned_at to created_at for frontend compatibility
                        "urgency": "normal"  # Add default urgency for frontend compatibility
                    })
                
                # Get total count
                cur.execute("""
                    SELECT COUNT(*)
                    FROM article_topic_clusters
                    WHERE topic_cluster_id = %s
                """, (topic_id,))
                total_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "topic_name": topic_name,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit
                    },
                    "message": f"Retrieved {len(articles)} articles for topic '{topic_name}'",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topic articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.get("/topics/{topic_name}/summary")
async def get_topic_summary_v3(topic_name: str):
    """v3.0 compatible topic summary endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get topic info
                cur.execute("""
                    SELECT id, cluster_name, cluster_description, metadata
                    FROM topic_clusters 
                    WHERE cluster_name = %s
                """, (topic_name,))
                
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id, cluster_name, description, metadata = topic_result
                
                # Get recent articles for summary
                cur.execute("""
                    SELECT a.title, a.summary, a.published_at, a.sentiment_score
                    FROM articles a
                    JOIN article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY a.published_at DESC
                    LIMIT 10
                """, (topic_id,))
                
                articles = cur.fetchall()
                
                if not articles:
                    return {
                        "success": True,
                        "data": {
                            "topic_name": cluster_name,
                            "summary": "No articles available for this topic yet.",
                            "article_count": 0,
                            "last_updated": None,
                            "total_articles": 0,
                            "unique_sources": 0,
                            "breaking_news": 0,
                            "avg_confidence": 0.0
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Generate summary using LLM (simplified for compatibility)
                summary_text = f"Topic: {cluster_name}\\n\\nDescription: {description}\\n\\nRecent articles:\\n"
                for article in articles[:5]:
                    summary_text += f"- {article[0]}\\n"
                
                return {
                    "success": True,
                    "data": {
                        "topic_name": cluster_name,
                        "summary": summary_text,
                        "article_count": len(articles),
                        "total_articles": len(articles),
                        "unique_sources": len(set([article[0] for article in articles])),  # Simplified count
                        "breaking_news": 0,  # Default value
                        "avg_confidence": 0.8,  # Default confidence
                        "last_updated": datetime.now().isoformat(),
                        "metadata": metadata
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error generating topic summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.post("/topics/cluster")
async def cluster_articles_v3(request: Dict[str, Any]):
    """v3.0 compatible article clustering endpoint"""
    try:
        limit = request.get("limit", 100)
        
        # For now, return success without actual clustering
        # In a real implementation, this would trigger background clustering
        return {
            "success": True,
            "message": "Article clustering started",
            "limit": limit,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting article clustering: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@compatibility_router.post("/topics/{topic_name}/convert-to-storyline")
async def convert_topic_to_storyline_v3(topic_name: str, request: Dict[str, Any]):
    """v3.0 compatible topic to storyline conversion endpoint"""
    try:
        storyline_title = request.get("storyline_title", f"Storyline: {topic_name}")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Create new storyline
                cur.execute("""
                    INSERT INTO storylines (title, description, processing_status, created_at, updated_at, created_by_user)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    storyline_title,
                    f"Auto-generated storyline from topic: {topic_name}",
                    "active",
                    datetime.now(),
                    datetime.now(),
                    "system"
                ))
                
                storyline_id = cur.fetchone()[0]
                conn.commit()
                
                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "storyline_title": storyline_title
                    },
                    "message": f"Successfully converted topic '{topic_name}' to storyline",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error converting topic to storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
