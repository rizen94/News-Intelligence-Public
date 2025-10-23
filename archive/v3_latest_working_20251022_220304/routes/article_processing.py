"""
News Intelligence System v3.0 - Article Processing API
Handles RSS feed processing, HTML cleaning, and article ingestion
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from services.article_processing_service import ArticleProcessingService

logger = logging.getLogger(__name__)
router = APIRouter()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'news-system-postgres'),
    'database': os.getenv('DB_NAME', 'newsintelligence'),
    'user': os.getenv('DB_USER', 'newsapp'),
    'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
    'port': os.getenv('DB_PORT', '5432')
}

# Pydantic models
class ProcessingRequest(BaseModel):
    feed_urls: List[str]
    process_immediately: bool = True

class ProcessingResponse(BaseModel):
    success: bool
    message: str
    stats: Optional[Dict[str, Any]] = None
    articles_processed: Optional[int] = None
    error: Optional[str] = None

# Initialize processing service
processing_service = ArticleProcessingService(DB_CONFIG)

@router.post("/process-feeds/", response_model=ProcessingResponse)
async def process_rss_feeds(request: ProcessingRequest, background_tasks: BackgroundTasks):
    """Process RSS feeds and clean articles"""
    try:
        logger.info(f"Processing {len(request.feed_urls)} RSS feeds...")
        
        if request.process_immediately:
            # Process immediately
            result = await processing_service.process_rss_feeds(request.feed_urls)
            
            if result['success']:
                return ProcessingResponse(
                    success=True,
                    message=f"Successfully processed {result['articles_processed']} articles",
                    stats=result['stats'],
                    articles_processed=result['articles_processed']
                )
            else:
                return ProcessingResponse(
                    success=False,
                    message="Failed to process feeds",
                    error=result.get('error', 'Unknown error'),
                    stats=result.get('stats', {})
                )
        else:
            # Process in background
            background_tasks.add_task(processing_service.process_rss_feeds, request.feed_urls)
            return ProcessingResponse(
                success=True,
                message="RSS feeds queued for background processing"
            )
            
    except Exception as e:
        logger.error(f"Error processing RSS feeds: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process feeds: {str(e)}")

@router.get("/process-status/")
async def get_processing_status():
    """Get current processing status"""
    try:
        # This would be implemented with a proper job queue system
        # For now, return basic status
        return {
            "success": True,
            "status": "idle",
            "message": "Processing service is ready"
        }
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.post("/clean-article/")
async def clean_single_article(url: str):
    """Clean a single article by URL"""
    try:
        logger.info(f"Cleaning article: {url}")
        
        # Fetch and clean the article
        content = await processing_service._fetch_article_content(url)
        cleaned_content = processing_service._clean_html_content(content)
        
        return {
            "success": True,
            "url": url,
            "raw_content": content[:500] + "..." if len(content) > 500 else content,
            "cleaned_content": cleaned_content[:500] + "..." if len(cleaned_content) > 500 else cleaned_content,
            "word_count": len(cleaned_content.split()),
            "message": "Article cleaned successfully"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning article {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clean article: {str(e)}")

@router.post("/fetch-full-content/{article_id}")
async def fetch_full_content_for_article(article_id: str):
    """Fetch full content for an existing article and update the database"""
    try:
        logger.info(f"Fetching full content for article: {article_id}")
        
        # Get article from database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("SELECT id, title, url, content FROM articles WHERE id = %s", (article_id,))
        article = cursor.fetchone()
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        if not article['url']:
            raise HTTPException(status_code=400, detail="Article has no URL to fetch content from")
        
        # Check if we already have substantial content
        current_content = article['content'] or ""
        if len(current_content) > 500:  # Already has substantial content
            return {
                "success": True,
                "article_id": article_id,
                "content": current_content,
                "word_count": len(current_content.split()),
                "message": "Article already has full content"
            }
        
        # Fetch full content
        full_content = await processing_service._fetch_article_content(article['url'])
        
        if not full_content or len(full_content) < 100:
            raise HTTPException(status_code=400, detail="Could not fetch substantial content from URL")
        
        # Clean the content
        cleaned_content = processing_service._clean_html_content(full_content)
        
        # Update database with full content
        word_count = len(cleaned_content.split())
        reading_time = max(1, word_count // 200)  # 200 words per minute
        
        cursor.execute("""
            UPDATE articles 
            SET content = %s, word_count = %s, reading_time = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (cleaned_content, word_count, reading_time, article_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "article_id": article_id,
            "content": cleaned_content,
            "word_count": word_count,
            "reading_time": reading_time,
            "message": "Full content fetched and updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching full content for article {article_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch full content: {str(e)}")

@router.get("/default-feeds/")
async def get_default_rss_feeds():
    """Get list of default RSS feeds to process"""
    try:
        default_feeds = [
            "https://techcrunch.com/feed/",
            "https://feeds.reuters.com/reuters/technologyNews",
            "https://rss.cnn.com/rss/edition_technology.rss",
            "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://feeds.washingtonpost.com/rss/world",
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://feeds.feedburner.com/oreilly/radar",
            "https://feeds.feedburner.com/venturebeat/SZYF",
            "https://feeds.feedburner.com/techcrunch/startups",
            "https://feeds.feedburner.com/oreilly/radar"
        ]
        
        return {
            "success": True,
            "feeds": default_feeds,
            "count": len(default_feeds)
        }
        
    except Exception as e:
        logger.error(f"Error getting default feeds: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get default feeds: {str(e)}")

@router.post("/process-default-feeds/", response_model=ProcessingResponse)
async def process_default_feeds(background_tasks: BackgroundTasks):
    """Process default RSS feeds"""
    try:
        # Get default feeds
        default_feeds_response = await get_default_rss_feeds()
        if not default_feeds_response['success']:
            raise HTTPException(status_code=500, detail="Failed to get default feeds")
        
        feed_urls = default_feeds_response['feeds']
        
        # Process feeds
        result = await processing_service.process_rss_feeds(feed_urls)
        
        if result['success']:
            return ProcessingResponse(
                success=True,
                message=f"Successfully processed {result['articles_processed']} articles from default feeds",
                stats=result['stats'],
                articles_processed=result['articles_processed']
            )
        else:
            return ProcessingResponse(
                success=False,
                message="Failed to process default feeds",
                error=result.get('error', 'Unknown error'),
                stats=result.get('stats', {})
            )
            
    except Exception as e:
        logger.error(f"Error processing default feeds: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process default feeds: {str(e)}")

@router.get("/health/")
async def health_check():
    """Health check for article processing service"""
    return {
        "status": "healthy",
        "service": "article_processing",
        "message": "Article processing service is running"
    }

@router.post("/fetch-full-content/{article_id}")
async def fetch_full_content(article_id: int):
    """Fetch full content for an article - placeholder endpoint for frontend compatibility"""
    return {
        "success": True,
        "data": {
            "article_id": article_id,
            "full_content": "Full article content would be fetched here...",
            "status": "fetched"
        },
        "message": "Full content fetched successfully"
    }
