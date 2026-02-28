"""
RSS Processing Module - Pipeline Integration
Automated RSS feed processing with pipeline integration and deduplication
Extracted from rss_processing_service.py
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import feedparser
from sqlalchemy import text
from config.database import get_db
from services.pipeline_logger import get_pipeline_logger
from services.pipeline_deduplication_service import PipelineDeduplicationService

from .base import BaseRSSService

logger = logging.getLogger(__name__)


class RSSProcessingModule:
    """
    RSS Processing Module - Pipeline-integrated feed processing
    
    Provides:
    - Automated feed processing with pipeline logging
    - Batch article processing
    - Deduplication integration
    - Feed status management
    """
    
    def __init__(self, base_service: BaseRSSService):
        """
        Initialize processing module
        
        Args:
            base_service: Base RSS service for feed management
        """
        self.base_service = base_service
        self.session = None
        self.pipeline_logger = get_pipeline_logger()
        self.deduplication_service = PipelineDeduplicationService()
        self.logger = logging.getLogger(__name__)
        
    async def process_all_feeds(self) -> Dict[str, Any]:
        """Process all active RSS feeds with pipeline integration"""
        
        try:
            logger.info("Starting RSS feed processing")
            self.session = next(get_db())
            
            # Start pipeline trace
            trace_id = self.pipeline_logger.start_trace(
                rss_feed_id="all_feeds"
            )
            
            # Get all active feeds using base service
            feeds_result = await self.base_service.get_feeds(active_only=True)
            feeds = feeds_result.get("feeds", [])
            
            if not feeds:
                logger.info("No active feeds found")
                self.pipeline_logger.end_trace(trace_id, success=True)
                return {"success": True, "processed": 0, "errors": 0}
            
            processed_count = 0
            error_count = 0
            
            for feed in feeds:
                try:
                    await self._process_feed(feed)
                    processed_count += 1
                    logger.info(f"Processed feed: {feed['name']}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing feed {feed['name']}: {e}")
                    self.pipeline_logger.add_checkpoint(
                        trace_id=trace_id,
                        stage="feed_processing",
                        status="error",
                        error_message=str(e),
                        metadata={"feed_name": feed['name']}
                    )
            
            logger.info(f"RSS processing completed: {processed_count} feeds processed, {error_count} errors")
            
            # Run deduplication pipeline after article import
            if processed_count > 0:
                logger.info("Starting automatic deduplication pipeline")
                deduplication_results = await self.deduplication_service.run_deduplication_pipeline(trace_id)
                
                if deduplication_results["success"]:
                    logger.info(f"Deduplication completed: {deduplication_results['duplicates_found']} duplicates found, {deduplication_results['duplicates_merged']} merged")
                else:
                    logger.error(f"Deduplication failed: {deduplication_results.get('error', 'Unknown error')}")
            
            # End pipeline trace
            self.pipeline_logger.end_trace(
                trace_id=trace_id, 
                success=error_count == 0
            )
            
            return {
                "success": True,
                "processed": processed_count,
                "errors": error_count,
                "total_feeds": len(feeds),
                "trace_id": trace_id
            }
            
        except Exception as e:
            logger.error(f"RSS processing failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if self.session:
                self.session.close()
    
    async def _process_feed(self, feed: Dict[str, Any]) -> None:
        """Process a single RSS feed"""
        try:
            # Parse RSS feed
            feed_data = feedparser.parse(feed['url'])
            
            if feed_data.bozo:
                logger.warning(f"Feed parsing warning for {feed['name']}: {feed_data.bozo_exception}")
            
            # Extract articles
            articles = []
            for entry in feed_data.entries[:feed.get('max_articles_per_update', 50)]:
                article = {
                    "title": entry.get('title', ''),
                    "content": entry.get('description', ''),
                    "url": entry.get('link', ''),
                    "published_at": self._parse_date(entry.get('published', '')),
                    "source_domain": feed['name'],
                    "category": feed.get('category'),
                    "language_code": feed.get('language', 'en'),
                    "feed_id": feed['id'],
                    "processing_status": "pending"
                }
                articles.append(article)
            
            # Save articles to database
            if articles:
                await self._save_articles(articles)
                
                # Run deduplication for this feed's articles
                logger.info(f"Running deduplication for {feed['name']} ({len(articles)} articles)")
                deduplication_results = await self.deduplication_service.run_deduplication_pipeline(
                    trace_id="feed_deduplication", 
                    feed_id=str(feed['id'])
                )
                
                if deduplication_results["success"] and deduplication_results["duplicates_found"] > 0:
                    logger.info(f"Feed deduplication: {deduplication_results['duplicates_found']} duplicates found, {deduplication_results['duplicates_merged']} merged")
            
            # Update feed last_checked timestamp
            await self._update_feed_timestamp(feed['id'])
            
        except Exception as e:
            logger.error(f"Error processing feed {feed['name']}: {e}")
            # Update feed status to error
            await self._update_feed_status(feed['id'], 'error')
            raise
    
    async def _save_articles(self, articles: List[Dict[str, Any]]) -> None:
        """Save articles to database with deduplication"""
        try:
            from scripts.article_deduplication import ArticleDeduplicationSystem
            
            deduplicator = ArticleDeduplicationSystem()
            
            for article in articles:
                # Generate content hash for deduplication
                content_hash = deduplicator.generate_content_hash(article.get('content', ''))
                
                # Check if article exists by url first (since we may not have unique constraint)
                check_query = text("""
                    SELECT id FROM articles WHERE url = :url LIMIT 1
                """)
                existing = self.session.execute(check_query, {'url': article.get('url')}).fetchone()
                
                if existing:
                    # Update existing article
                    query = text("""
                        UPDATE articles SET
                            title = :title,
                            content = :content,
                            content_hash = :content_hash,
                            updated_at = NOW()
                        WHERE url = :url
                    """)
                else:
                    # Insert new article
                    query = text("""
                        INSERT INTO articles (
                            title, content, url, published_at, source_domain, category, 
                            language_code, feed_id, processing_status, content_hash, created_at
                        ) VALUES (
                            :title, :content, :url, :published_at, :source_domain, :category,
                            :language_code, :feed_id, :processing_status, :content_hash, NOW()
                        )
                    """)
                
                article_data = {
                    **article,
                    'content_hash': content_hash
                }
                
                self.session.execute(query, article_data)
            
            self.session.commit()
            logger.info(f"Saved {len(articles)} articles to database with deduplication")
            
        except Exception as e:
            logger.error(f"Error saving articles: {e}")
            self.session.rollback()
            raise
    
    async def _update_feed_timestamp(self, feed_id: int) -> None:
        """Update feed last_checked timestamp"""
        try:
            query = text("""
                UPDATE rss_feeds 
                SET last_fetched_at = NOW(), is_active = true
                WHERE id = :feed_id
            """)
            
            self.session.execute(query, {"feed_id": feed_id})
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating feed timestamp: {e}")
            self.session.rollback()
    
    async def _update_feed_status(self, feed_id: int, status: str) -> None:
        """Update feed status"""
        try:
            query = text("""
                UPDATE rss_feeds 
                SET is_active = :is_active, last_fetched_at = NOW()
                WHERE id = :feed_id
            """)
            
            is_active = status == 'active'
            self.session.execute(query, {"feed_id": feed_id, "is_active": is_active})
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating feed status: {e}")
            self.session.rollback()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None
        
        try:
            # Try to parse common date formats
            from dateutil import parser
            return parser.parse(date_str)
        except Exception:
            logger.warning(f"Could not parse date: {date_str}")
            return None

