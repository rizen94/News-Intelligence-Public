"""
RSS Processing Service for News Intelligence System v3.0
Handles automated RSS feed processing and article collection
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import feedparser
import requests
from sqlalchemy import text
from config.database import get_db

logger = logging.getLogger(__name__)

class RSSProcessor:
    """Main RSS processing service"""
    
    def __init__(self):
        self.session = None
        
    async def process_all_feeds(self) -> Dict[str, Any]:
        """Process all active RSS feeds"""
        try:
            logger.info("Starting RSS feed processing")
            self.session = next(get_db())
            
            # Get all active feeds
            feeds = await self._get_active_feeds()
            
            if not feeds:
                logger.info("No active feeds found")
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
            
            logger.info(f"RSS processing completed: {processed_count} feeds processed, {error_count} errors")
            return {
                "success": True,
                "processed": processed_count,
                "errors": error_count,
                "total_feeds": len(feeds)
            }
            
        except Exception as e:
            logger.error(f"RSS processing failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if self.session:
                self.session.close()
    
    async def _get_active_feeds(self) -> List[Dict[str, Any]]:
        """Get all active RSS feeds from database"""
        try:
            query = text("""
                SELECT id, name, url, category, language, max_articles, 
                       update_frequency, last_checked, status
                FROM rss_feeds 
                WHERE status = 'active' 
                AND (last_checked IS NULL OR last_checked < NOW() - INTERVAL '30 minutes')
                ORDER BY priority DESC, last_checked ASC
            """)
            
            result = self.session.execute(query)
            feeds = []
            
            for row in result:
                feeds.append({
                    "id": row.id,
                    "name": row.name,
                    "url": row.url,
                    "category": row.category,
                    "language": row.language,
                    "max_articles": row.max_articles or 50,
                    "update_frequency": row.update_frequency or 30,
                    "last_checked": row.last_checked,
                    "status": row.status
                })
            
            return feeds
            
        except Exception as e:
            logger.error(f"Error getting active feeds: {e}")
            return []
    
    async def _process_feed(self, feed: Dict[str, Any]) -> None:
        """Process a single RSS feed"""
        try:
            # Parse RSS feed
            feed_data = feedparser.parse(feed['url'])
            
            if feed_data.bozo:
                logger.warning(f"Feed parsing warning for {feed['name']}: {feed_data.bozo_exception}")
            
            # Extract articles
            articles = []
            for entry in feed_data.entries[:feed['max_articles']]:
                article = {
                    "title": entry.get('title', ''),
                    "content": entry.get('description', ''),
                    "url": entry.get('link', ''),
                    "published_at": self._parse_date(entry.get('published', '')),
                    "source": feed['name'],
                    "category": feed['category'],
                    "language": feed['language'],
                    "feed_id": feed['id'],
                    "processing_status": "raw"
                }
                articles.append(article)
            
            # Save articles to database
            if articles:
                await self._save_articles(articles)
            
            # Update feed last_checked timestamp
            await self._update_feed_timestamp(feed['id'])
            
        except Exception as e:
            logger.error(f"Error processing feed {feed['name']}: {e}")
            # Update feed status to error
            await self._update_feed_status(feed['id'], 'error')
            raise
    
    async def _save_articles(self, articles: List[Dict[str, Any]]) -> None:
        """Save articles to database"""
        try:
            for article in articles:
                query = text("""
                    INSERT INTO articles (
                        title, content, url, published_at, source, category, 
                        language, feed_id, processing_status, created_at
                    ) VALUES (
                        :title, :content, :url, :published_at, :source, :category,
                        :language, :feed_id, :processing_status, NOW()
                    )
                    ON CONFLICT (url) DO NOTHING
                """)
                
                self.session.execute(query, article)
            
            self.session.commit()
            logger.info(f"Saved {len(articles)} articles to database")
            
        except Exception as e:
            logger.error(f"Error saving articles: {e}")
            self.session.rollback()
            raise
    
    async def _update_feed_timestamp(self, feed_id: int) -> None:
        """Update feed last_checked timestamp"""
        try:
            query = text("""
                UPDATE rss_feeds 
                SET last_checked = NOW(), status = 'active'
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
                SET status = :status, last_checked = NOW()
                WHERE id = :feed_id
            """)
            
            self.session.execute(query, {"feed_id": feed_id, "status": status})
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

# Global instance
_rss_processor = None

def get_rss_processor() -> RSSProcessor:
    """Get RSS processor instance"""
    global _rss_processor
    if _rss_processor is None:
        _rss_processor = RSSProcessor()
    return _rss_processor
