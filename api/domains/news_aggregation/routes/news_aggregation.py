"""
Domain 1: News Aggregation Routes
Handles RSS feed processing, article ingestion, and content quality assessment
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Path, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from domains.news_aggregation.services.article_service import ArticleService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4",
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

@router.get("/{domain}/rss-feeds")
async def get_domain_rss_feeds(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """Get all configured RSS feeds for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        # Get schema name
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT schema_name FROM domains WHERE domain_key = %s", (domain,))
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=400, detail=f"Domain {domain} not found")
                schema_name = result[0]
            
            # Get feeds from domain schema
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, feed_name, feed_url, is_active, last_fetched_at, 
                           fetch_interval_seconds, created_at
                    FROM {schema_name}.rss_feeds 
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
                        "created_at": row[6].isoformat() if row[6] else None
                    })
                
                return {
                    "success": True,
                    "data": {"feeds": feeds, "domain": domain},
                    "count": len(feeds),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching RSS feeds for domain {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rss-feeds")
async def create_rss_feed(feed_data: Dict[str, Any]):
    """Create a new RSS feed with duplicate prevention"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            feed_url = feed_data.get("feed_url")
            feed_name = feed_data.get("feed_name")
            
            # Check for existing feed with same URL
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, feed_name, is_active 
                    FROM rss_feeds 
                    WHERE feed_url = %s
                """, (feed_url,))
                
                existing_feed = cur.fetchone()
                
                if existing_feed:
                    existing_id, existing_name, existing_active = existing_feed
                    return {
                        "success": False,
                        "error": "duplicate_url",
                        "data": {
                            "existing_feed": {
                                "id": existing_id,
                                "name": existing_name,
                                "is_active": existing_active
                            }
                        },
                        "message": f"RSS feed with URL '{feed_url}' already exists (ID: {existing_id}, Name: '{existing_name}')"
                    }
                
                # Check for similar feed names
                cur.execute("""
                    SELECT id, feed_name, feed_url 
                    FROM rss_feeds 
                    WHERE LOWER(feed_name) = LOWER(%s)
                """, (feed_name,))
                
                similar_feed = cur.fetchone()
                
                if similar_feed:
                    similar_id, similar_name, similar_url = similar_feed
                    return {
                        "success": False,
                        "error": "similar_name",
                        "data": {
                            "similar_feed": {
                                "id": similar_id,
                                "name": similar_name,
                                "url": similar_url
                            }
                        },
                        "message": f"RSS feed with similar name '{feed_name}' already exists (ID: {similar_id}, URL: '{similar_url}')"
                    }
                
                # Create new feed
                cur.execute("""
                    INSERT INTO rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    feed_name,
                    feed_url,
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

@router.post("/{domain}/rss-feeds/collect-now")
async def collect_rss_feeds_now(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """Trigger immediate RSS feed collection and wait for completion"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        # Import collector function
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        from collectors.rss_collector import collect_rss_feeds
        
        logger.info(f"Starting RSS feed collection via API for domain: {domain}")
        
        # Run collection synchronously (collects from all domains)
        articles_added = collect_rss_feeds()
        
        return {
            "success": True,
            "message": "RSS feed collection completed",
            "articles_added": articles_added,
            "domain": domain,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error collecting RSS feeds: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "RSS feed collection failed",
            "timestamp": datetime.now().isoformat()
        }

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

@router.get("/{domain}/articles")
async def get_domain_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$", description="Domain key"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of articles"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    hours: Optional[int] = Query(None, ge=1, description="Filter articles from last N hours"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    source_domain: Optional[str] = Query(None, description="Filter by source domain"),
    processing_status: Optional[str] = Query(None, description="Filter by processing status")
):
    """
    Get articles for a specific domain with optional filtering and pagination.
    
    Domain-aware endpoint that returns articles from the specified domain schema.
    """
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        # Create domain-aware service
        article_service = ArticleService(domain=domain)
        
        # Build filters
        filters = {}
        if source_domain:
            filters['source_domain'] = source_domain
        if processing_status:
            filters['processing_status'] = processing_status
        if hours:
            from datetime import datetime, timedelta
            filters['published_after'] = datetime.now() - timedelta(hours=hours)
        
        # Get articles
        result = article_service.get_articles(limit=limit, offset=offset, filters=filters)
        
        # Apply search filter if provided (post-query for now, can be optimized)
        if search:
            articles = result['data']['articles']
            search_lower = search.lower()
            filtered_articles = [
                a for a in articles
                if search_lower in (a.get('title', '') or '').lower() or 
                   search_lower in (a.get('content', '') or '').lower()
            ]
            result['data']['articles'] = filtered_articles
            result['data']['count'] = len(filtered_articles)
        
        return result
            
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching articles for domain {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/articles/{article_id}")
async def get_domain_article(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    article_id: int = Path(..., description="Article ID")
):
    """Get a single article by ID from a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        
        # Create domain-aware service
        article_service = ArticleService(domain=domain)
        
        # Get article
        article = article_service.get_article(article_id)
        
        if not article:
            raise HTTPException(status_code=404, detail=f"Article {article_id} not found in domain {domain}")
        
        return {
            'success': True,
            'data': article,
            'domain': domain
        }
            
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching article {article_id} from domain {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Legacy endpoint for backward compatibility (redirects to politics domain)
@router.get("/articles/recent")
async def get_recent_articles_legacy(
    limit: int = 50,
    hours: Optional[int] = None,
    page: Optional[int] = None,
    offset: Optional[int] = None,
    search: Optional[str] = None,
    source_domain: Optional[str] = None,
    sort: Optional[str] = None
):
    """
    Legacy endpoint - redirects to politics domain.
    Use /api/v4/{domain}/articles instead.
    """
    # Redirect to politics domain
    return await get_domain_articles(
        domain='politics',
        limit=limit,
        offset=offset if offset is not None else ((page - 1) * limit if page else 0),
        hours=hours,
        search=search,
        source_domain=source_domain,
        processing_status=None
    )

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
                cur.execute("SELECT AVG(LENGTH(content)) FROM articles WHERE quality_score IS NOT NULL")
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
    
    try:
        import feedparser
        import requests
        from urllib.parse import urlparse
        
        processed_count = 0
        error_count = 0
        
        for feed_data in feeds:
            feed_id, feed_name, feed_url, fetch_interval, last_fetched_at = feed_data
            
            # Get a fresh database connection for each feed
            conn = get_db_connection()
            if not conn:
                logger.error(f"Database connection failed for feed: {feed_name}")
                error_count += 1
                continue
                
            try:
                logger.info(f"Processing feed: {feed_name} ({feed_url})")
                
                # Fetch RSS feed with better error handling
                try:
                    response = requests.get(feed_url, timeout=30, headers={
                        'User-Agent': 'Mozilla/5.0 (compatible; News Intelligence Bot/1.0)'
                    })
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"Error fetching feed {feed_name}: {e}")
                    error_count += 1
                    continue
                
                # Parse RSS feed
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    logger.warning(f"No entries found in feed: {feed_name}")
                    continue
                
                # Process each entry
                for entry in feed.entries[:10]:  # Limit to 10 most recent articles
                    try:
                        # Extract article data
                        title = entry.get('title', 'No Title')
                        link = entry.get('link', '')
                        description = entry.get('description', '')
                        published = entry.get('published_parsed')
                        
                        # Convert published date
                        published_at = None
                        if published:
                            from datetime import datetime
                            published_at = datetime(*published[:6])
                        
                        # Extract domain from URL
                        domain = urlparse(link).netloc if link else 'unknown'
                        
                        # Check if article already exists and insert new article
                        with conn.cursor() as cur:
                            # Check for duplicates
                            cur.execute("""
                                SELECT id FROM articles 
                                WHERE url = %s OR (title = %s AND source_domain = %s)
                            """, (link, title, domain))
                            
                            if cur.fetchone():
                                continue  # Skip duplicate
                            
                            # Insert new article with proper error handling
                            try:
                                cur.execute("""
                                    INSERT INTO articles (
                                        title, url, content, content, source_domain,
                                        published_at,  processing_status,
                                        created_at, updated_at
                                    ) VALUES (
                                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                                    )
                                """, (
                                    title,
                                    link,
                                    description,
                                    description[:500] + "..." if len(description) > 500 else description,
                                    domain,
                                    published_at,
                                    len(description.split()) if description else 0,
                                    'pending',
                                    datetime.now(),
                                    datetime.now()
                                ))
                                
                                processed_count += 1
                                logger.info(f"Added article: {title[:50]}...")
                                
                            except Exception as db_error:
                                logger.error(f"Database error inserting article '{title[:30]}...': {db_error}")
                                conn.rollback()  # Rollback the transaction
                                error_count += 1
                                continue
                    
                    except Exception as e:
                        logger.error(f"Error processing article from {feed_name}: {e}")
                        error_count += 1
                
                # Update feed timestamp
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE rss_feeds 
                            SET last_fetched_at = %s 
                            WHERE id = %s
                        """, (datetime.now(), feed_id))
                    conn.commit()
                except Exception as e:
                    logger.error(f"Error updating feed timestamp for {feed_name}: {e}")
                    conn.rollback()
                
            except Exception as e:
                logger.error(f"Error processing feed {feed_name}: {e}")
                error_count += 1
            finally:
                conn.close()
        
        logger.info(f"RSS processing completed: {processed_count} articles processed, {error_count} errors")
        
    except Exception as e:
        logger.error(f"RSS processing failed: {e}")

async def process_article_quality(article: tuple):
    """Background task to analyze article quality using LLM"""
    try:
        article_id, title, content, url, source_domain = article
        
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
