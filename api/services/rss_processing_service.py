"""
News Intelligence System v3.1.0 - RSS Processing Service
Real-time RSS feed processing and article ingestion
"""

import asyncio
import logging
import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import hashlib
import re
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger(__name__)

class RSSProcessingService:
    """Real-time RSS feed processing service"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.is_running = False
        self.processing_interval = 300  # 5 minutes
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'News Intelligence System v3.1.0 RSS Reader'
        })
        
    async def start_processing(self):
        """Start the RSS processing service"""
        self.is_running = True
        logger.info("Starting RSS processing service...")
        
        # Process feeds immediately
        await self.process_all_feeds()
        
        # Start background processing
        asyncio.create_task(self._background_processing())
        
    async def _background_processing(self):
        """Background RSS processing loop"""
        while self.is_running:
            try:
                await asyncio.sleep(self.processing_interval)
                await self.process_all_feeds()
            except Exception as e:
                logger.error(f"Error in background RSS processing: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                
    async def process_all_feeds(self):
        """Process all active RSS feeds"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get active RSS feeds
            cursor.execute("""
                SELECT id, name, url, is_active 
                FROM rss_feeds 
                WHERE is_active = true
            """)
            
            feeds = cursor.fetchall()
            cursor.close()
            conn.close()
            
            logger.info(f"Processing {len(feeds)} RSS feeds...")
            
            for feed in feeds:
                try:
                    await self.process_feed(feed)
                except Exception as e:
                    logger.error(f"Error processing feed {feed['name']}: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing RSS feeds: {e}")
            
    async def process_feed(self, feed: Dict[str, Any]):
        """Process a single RSS feed"""
        try:
            logger.info(f"Processing feed: {feed['name']}")
            
            # Parse RSS feed
            response = self.session.get(feed['url'], timeout=30)
            response.raise_for_status()
            
            parsed_feed = feedparser.parse(response.content)
            
            if parsed_feed.bozo:
                logger.warning(f"Feed {feed['name']} has parsing issues: {parsed_feed.bozo_exception}")
                
            # Process articles
            articles_processed = 0
            for entry in parsed_feed.entries:
                try:
                    article_data = await self._extract_article_data(entry, feed)
                    if article_data:
                        await self._save_article(article_data)
                        articles_processed += 1
                except Exception as e:
                    logger.error(f"Error processing article from {feed['name']}: {e}")
                    
            logger.info(f"Processed {articles_processed} articles from {feed['name']}")
            
        except Exception as e:
            logger.error(f"Error processing feed {feed['name']}: {e}")
            
    async def _extract_article_data(self, entry, feed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract article data from RSS entry"""
        try:
            # Generate unique ID
            article_id = hashlib.md5(entry.link.encode()).hexdigest()
            
            # Extract title and content
            title = entry.get('title', '').strip()
            if not title:
                return None
                
            # Extract content
            content = ''
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].value if isinstance(entry.content, list) else str(entry.content)
            elif hasattr(entry, 'summary'):
                content = entry.summary
            elif hasattr(entry, 'description'):
                content = entry.description
                
            # Clean content
            content = self._clean_html(content)
            
            # Extract published date
            published_at = datetime.now(timezone.utc)
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_at = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                
            # Extract categories/tags
            tags = []
            if hasattr(entry, 'tags'):
                tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
                
            # Basic content analysis
            word_count = len(content.split())
            reading_time = max(1, word_count // 200)  # 200 words per minute
            
            return {
                'id': article_id,
                'title': title,
                'content': content,
                'url': entry.link,
                'source': feed['name'],
                'published_at': published_at,
                'tags': tags,
                'word_count': word_count,
                'reading_time': reading_time,
                'rss_feed_id': feed['id']
            }
            
        except Exception as e:
            logger.error(f"Error extracting article data: {e}")
            return None
            
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content"""
        if not html_content:
            return ''
            
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', html_content)
        # Decode HTML entities
        clean = clean.replace('&amp;', '&')
        clean = clean.replace('&lt;', '<')
        clean = clean.replace('&gt;', '>')
        clean = clean.replace('&quot;', '"')
        clean = clean.replace('&#39;', "'")
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean
        
    async def _save_article(self, article_data: Dict[str, Any]):
        """Save article to database"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            # Check if article already exists
            cursor.execute("SELECT id FROM articles WHERE id = %s", (article_data['id'],))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return
                
            # Insert article (matching actual database schema)
            cursor.execute("""
                INSERT INTO articles (
                    id, title, content, url, source, published_at, 
                    tags, word_count, reading_time, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                article_data['id'],
                article_data['title'],
                article_data['content'],
                article_data['url'],
                article_data['source'],
                article_data['published_at'],
                article_data['tags'],
                article_data['word_count'],
                article_data['reading_time'],
                datetime.now(timezone.utc),
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving article: {e}")
            
    async def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
        
    async def stop_processing(self):
        """Stop the RSS processing service"""
        self.is_running = False
        logger.info("RSS processing service stopped")

# Global instance
rss_processor = None

def get_rss_processor() -> RSSProcessingService:
    """Get the global RSS processor instance"""
    global rss_processor
    if rss_processor is None:
        db_config = {
            'host': 'news-system-postgres',
            'database': 'newsintelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025',
            'port': '5432'
        }
        rss_processor = RSSProcessingService(db_config)
    return rss_processor
