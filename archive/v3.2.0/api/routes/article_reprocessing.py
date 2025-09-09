"""
News Intelligence System v3.1.0 - Article Reprocessing API
Reprocess existing articles with improved formatting
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, Any, Optional, List
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from services.article_processing_service import ArticleProcessingService
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/reprocess-all")
async def reprocess_all_articles(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Force reprocessing even if content exists")
):
    """Reprocess all articles with improved formatting"""
    try:
        logger.info("Starting reprocessing of all articles with improved formatting")
        
        # Get database connection
        db_config = {
            'host': 'news-system-postgres',
            'database': 'newsintelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025',
            'port': '5432'
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all articles
        cursor.execute("""
            SELECT id, title, url, content
            FROM articles 
            WHERE url IS NOT NULL
            ORDER BY created_at DESC
        """)
        
        articles = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not articles:
            return {
                "success": True,
                "message": "No articles found to reprocess",
                "data": {"processed": 0, "skipped": 0, "errors": 0}
            }
        
        # Process articles
        processing_service = ArticleProcessingService(db_config)
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for article in articles:
            try:
                # Check if we should skip this article
                if not force and article['content'] and len(article['content']) > 500:
                    skipped_count += 1
                    continue
                
                # Reprocess with improved formatting
                # For existing articles, we'll need to fetch fresh content from the URL
                if article['url']:
                    try:
                        # Fetch fresh content from URL
                        fresh_content = await processing_service._fetch_article_content(article['url'])
                        if fresh_content:
                            cleaned_content = processing_service._clean_html_content(fresh_content)
                        else:
                            # Fallback to existing content
                            cleaned_content = processing_service._clean_html_content(article['content'] or '')
                    except Exception as e:
                        logger.warning(f"Could not fetch fresh content for {article['url']}: {e}")
                        # Fallback to existing content
                        cleaned_content = processing_service._clean_html_content(article['content'] or '')
                else:
                    # No URL available, use existing content
                    cleaned_content = processing_service._clean_html_content(article['content'] or '')
                
                if cleaned_content and len(cleaned_content) > 100:
                    # Update database
                    conn = psycopg2.connect(**db_config)
                    cursor = conn.cursor()
                    
                    word_count = len(cleaned_content.split())
                    reading_time = max(1, word_count // 200)
                    
                    cursor.execute("""
                        UPDATE articles 
                        SET content = %s, word_count = %s, reading_time = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (cleaned_content, word_count, reading_time, article['id']))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    processed_count += 1
                    logger.info(f"Reprocessed article: {article['title'][:50]}...")
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error reprocessing article {article['id']}: {e}")
                error_count += 1
                continue
        
        return {
            "success": True,
            "message": f"Reprocessing complete. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}",
            "data": {
                "processed": processed_count,
                "skipped": skipped_count,
                "errors": error_count,
                "total": len(articles)
            }
        }
        
    except Exception as e:
        logger.error(f"Error in reprocess_all_articles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reprocess articles: {str(e)}")

@router.post("/reprocess/{article_id}")
async def reprocess_single_article(
    article_id: str,
    force: bool = Query(False, description="Force reprocessing even if content exists")
):
    """Reprocess a single article with improved formatting"""
    try:
        logger.info(f"Reprocessing article {article_id} with improved formatting")
        
        # Get database connection
        db_config = {
            'host': 'news-system-postgres',
            'database': 'newsintelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025',
            'port': '5432'
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get article
        cursor.execute("""
            SELECT id, title, url, content
            FROM articles 
            WHERE id = %s
        """, (article_id,))
        
        article = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Check if we should skip this article
        if not force and article['content'] and len(article['content']) > 500:
            return {
                "success": True,
                "message": "Article already has content, use force=true to reprocess",
                "data": {"article_id": article_id, "skipped": True}
            }
        
        # Reprocess with improved formatting
        processing_service = ArticleProcessingService(db_config)
        
        # For existing articles, we'll need to fetch fresh content from the URL
        if article['url']:
            try:
                # Fetch fresh content from URL
                fresh_content = await processing_service._fetch_article_content(article['url'])
                if fresh_content:
                    cleaned_content = processing_service._clean_html_content(fresh_content)
                else:
                    # Fallback to existing content
                    cleaned_content = processing_service._clean_html_content(article['content'] or '')
            except Exception as e:
                logger.warning(f"Could not fetch fresh content for {article['url']}: {e}")
                # Fallback to existing content
                cleaned_content = processing_service._clean_html_content(article['content'] or '')
        else:
            # No URL available, use existing content
            cleaned_content = processing_service._clean_html_content(article['content'] or '')
        
        if cleaned_content and len(cleaned_content) > 100:
            # Update database
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            
            word_count = len(cleaned_content.split())
            reading_time = max(1, word_count // 200)
            
            cursor.execute("""
                UPDATE articles 
                SET content = %s, word_count = %s, reading_time = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (cleaned_content, word_count, reading_time, article['id']))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "message": "Article reprocessed successfully",
                "data": {
                    "article_id": article_id,
                    "title": article['title'],
                    "word_count": word_count,
                    "reading_time": reading_time,
                    "content_length": len(cleaned_content)
                }
            }
        else:
            return {
                "success": False,
                "message": "Could not extract meaningful content",
                "data": {"article_id": article_id, "skipped": True}
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing article {article_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reprocess article: {str(e)}")

@router.get("/reprocess-status")
async def get_reprocess_status():
    """Get status of article reprocessing"""
    try:
        # Get database connection
        db_config = {
            'host': 'news-system-postgres',
            'database': 'newsintelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025',
            'port': '5432'
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get article statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_articles,
                COUNT(CASE WHEN content IS NOT NULL AND LENGTH(content) > 500 THEN 1 END) as articles_with_content,
                AVG(LENGTH(content)) as avg_content_length
            FROM articles
        """)
        
        stats = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "data": {
                "total_articles": stats['total_articles'],
                "articles_with_content": stats['articles_with_content'],
                "avg_content_length": float(stats['avg_content_length'] or 0),
                "reprocessing_available": True
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting reprocess status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get reprocess status: {str(e)}")
