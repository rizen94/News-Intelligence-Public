"""
RSS Fetcher Service for News Intelligence System v3.0
Async RSS feed fetching with comprehensive filtering and deduplication
"""

import asyncio
import aiohttp
import feedparser
import logging
import json
import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import signal
import time

from database.connection import get_db
from sqlalchemy import text
from .enhanced_rss_service import EnhancedRSSService

logger = logging.getLogger(__name__)

@dataclass
class ArticleData:
    """Structured article data from RSS feed"""
    title: str
    url: str
    content: str
    summary: str
    published_date: datetime
    source: str
    source_tier: int
    source_priority: int
    language: str
    categories: List[str]
    tags: List[str]

class RSSFetcherService:
    """Async RSS feed fetcher with comprehensive filtering and processing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.enhanced_rss_service = EnhancedRSSService()
        self.session = None
        self.filtering_config = None
        self._load_filtering_config()
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'News Intelligence RSS Fetcher/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _load_filtering_config(self):
        """Load filtering configuration"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT config_name, config_data 
                    FROM global_filtering_config 
                    WHERE is_active = true
                """)).fetchall()
                
                self.filtering_config = {}
                for row in result:
                    self.filtering_config[row[0]] = json.loads(row[1])
                    
                self.logger.info(f"Loaded {len(self.filtering_config)} filtering configurations")
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error loading filtering config: {e}")
            self.filtering_config = {}
    
    async def fetch_all_feeds(self, max_concurrent: int = 5) -> Dict[str, Any]:
        """Fetch articles from all active RSS feeds with concurrency control"""
        try:
            # Get all active feeds
            feeds_result = await self.enhanced_rss_service.get_feeds(active_only=True)
            feeds = feeds_result.get("feeds", [])
            
            if not feeds:
                return {"message": "No active feeds found", "articles_processed": 0}
            
            # Sort feeds by priority and tier
            feeds.sort(key=lambda x: (x["priority"], x["tier"]))
            
            # Process feeds in batches
            semaphore = asyncio.Semaphore(max_concurrent)
            tasks = []
            
            for feed in feeds:
                task = asyncio.create_task(
                    self._fetch_feed_with_semaphore(semaphore, feed)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggregate results
            total_articles = 0
            total_filtered = 0
            total_duplicates = 0
            errors = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    errors.append(f"Feed {feeds[i]['name']}: {str(result)}")
                    self.logger.error(f"Error processing feed {feeds[i]['name']}: {result}")
                else:
                    total_articles += result.get("articles_processed", 0)
                    total_filtered += result.get("articles_filtered", 0)
                    total_duplicates += result.get("duplicates_found", 0)
            
            return {
                "feeds_processed": len(feeds),
                "articles_processed": total_articles,
                "articles_filtered": total_filtered,
                "duplicates_found": total_duplicates,
                "errors": errors,
                "status": "completed"
            }
            
        except Exception as e:
            self.logger.error(f"Error in fetch_all_feeds: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def _fetch_feed_with_semaphore(self, semaphore: asyncio.Semaphore, feed: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch single feed with semaphore for concurrency control"""
        async with semaphore:
            return await self.fetch_single_feed(feed)
    
    async def fetch_single_feed(self, feed: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch articles from a single RSS feed"""
        feed_id = feed["id"]
        feed_name = feed["name"]
        feed_url = feed["url"]
        feed_tier = feed["tier"]
        feed_priority = feed["priority"]
        feed_language = feed["language"]
        feed_category = feed["category"]
        max_articles = feed["max_articles_per_update"]
        
        start_time = time.time()
        articles_processed = 0
        articles_filtered = 0
        duplicates_found = 0
        
        try:
            self.logger.info(f"Fetching feed: {feed_name}")
            
            # Fetch RSS content
            async with self.session.get(feed_url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")
                
                content = await response.text()
            
            # Parse RSS feed
            feed_data = feedparser.parse(content)
            
            if not feed_data.entries:
                self.logger.warning(f"No entries found in feed: {feed_name}")
                return {
                    "feed_id": feed_id,
                    "feed_name": feed_name,
                    "articles_processed": 0,
                    "articles_filtered": 0,
                    "duplicates_found": 0,
                    "status": "no_entries"
                }
            
            # Process articles
            for entry in feed_data.entries[:max_articles]:
                try:
                    # Extract article data
                    article_data = self._extract_article_data(entry, feed)
                    
                    # Apply filtering
                    if not await self._apply_filters(article_data):
                        articles_filtered += 1
                        continue
                    
                    # Check for duplicates
                    if await self._is_duplicate(article_data):
                        duplicates_found += 1
                        continue
                    
                    # Save article
                    await self._save_article(article_data)
                    articles_processed += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error processing article from {feed_name}: {e}")
                    continue
            
            # Update feed statistics
            response_time = int((time.time() - start_time) * 1000)
            await self._update_feed_stats(feed_id, articles_processed, response_time, True)
            
            self.logger.info(f"Processed {articles_processed} articles from {feed_name} "
                           f"(filtered: {articles_filtered}, duplicates: {duplicates_found})")
            
            return {
                "feed_id": feed_id,
                "feed_name": feed_name,
                "articles_processed": articles_processed,
                "articles_filtered": articles_filtered,
                "duplicates_found": duplicates_found,
                "response_time": response_time,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching feed {feed_name}: {e}")
            await self._update_feed_stats(feed_id, 0, 0, False, str(e))
            return {
                "feed_id": feed_id,
                "feed_name": feed_name,
                "articles_processed": 0,
                "articles_filtered": 0,
                "duplicates_found": 0,
                "error": str(e),
                "status": "error"
            }
    
    def _extract_article_data(self, entry: Any, feed: Dict[str, Any]) -> ArticleData:
        """Extract structured data from RSS entry"""
        title = entry.get('title', '')[:500]
        url = entry.get('link', '')[:500]
        content = entry.get('summary', '') or entry.get('description', '')
        summary = content[:1000] if content else ""
        
        # Parse published date
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_date = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_date = datetime(*entry.updated_parsed[:6])
        else:
            published_date = datetime.now()
        
        return ArticleData(
            title=title,
            url=url,
            content=content,
            summary=summary,
            published_date=published_date,
            source=feed["name"],
            source_tier=feed["tier"],
            source_priority=feed["priority"],
            language=feed["language"],
            categories=[feed["category"]],
            tags=feed.get("tags", [])
        )
    
    async def _apply_filters(self, article: ArticleData) -> bool:
        """Apply comprehensive filtering to article"""
        try:
            # Category whitelist filter
            if not self._check_category_filter(article):
                return False
            
            # Keyword blacklist filter
            if not self._check_keyword_blacklist(article):
                return False
            
            # URL pattern filter
            if not self._check_url_patterns(article):
                return False
            
            # NLP classifier filter (if available)
            if not await self._check_nlp_classifier(article):
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error applying filters to article: {e}")
            return True  # Allow article if filtering fails
    
    def _check_category_filter(self, article: ArticleData) -> bool:
        """Check if article matches category whitelist"""
        if not self.filtering_config or "category_whitelist" not in self.filtering_config:
            return True
        
        category_config = self.filtering_config["category_whitelist"]
        article_text = f"{article.title} {article.content}".lower()
        
        for category, keywords in category_config.items():
            if any(keyword.lower() in article_text for keyword in keywords):
                return True
        
        return False
    
    def _check_keyword_blacklist(self, article: ArticleData) -> bool:
        """Check if article contains blacklisted keywords"""
        if not self.filtering_config or "keyword_blacklist" not in self.filtering_config:
            return True
        
        blacklist_config = self.filtering_config["keyword_blacklist"]
        article_text = f"{article.title} {article.content}".lower()
        
        for category, keywords in blacklist_config.items():
            if any(keyword.lower() in article_text for keyword in keywords):
                self.logger.debug(f"Article filtered by {category} blacklist: {article.title}")
                return False
        
        return True
    
    def _check_url_patterns(self, article: ArticleData) -> bool:
        """Check if article URL matches include/exclude patterns"""
        if not self.filtering_config or "url_patterns" not in self.filtering_config:
            return True
        
        url_config = self.filtering_config["url_patterns"]
        url = article.url.lower()
        
        # Check exclude patterns first
        exclude_patterns = url_config.get("exclude_patterns", [])
        for pattern in exclude_patterns:
            if pattern.lower() in url:
                self.logger.debug(f"Article filtered by URL exclude pattern: {article.title}")
                return False
        
        # Check include patterns
        include_patterns = url_config.get("include_patterns", [])
        if include_patterns:
            if not any(pattern.lower() in url for pattern in include_patterns):
                self.logger.debug(f"Article filtered by URL include pattern: {article.title}")
                return False
        
        return True
    
    async def _check_nlp_classifier(self, article: ArticleData) -> bool:
        """Check article using NLP classifier (placeholder for future implementation)"""
        # TODO: Implement local NLP classifier using HuggingFace transformers
        # For now, return True to allow all articles
        return True
    
    async def _is_duplicate(self, article: ArticleData) -> bool:
        """Check if article is a duplicate"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Check for exact URL match
                url_result = db.execute(text("""
                    SELECT id FROM articles WHERE url = :url
                """), {"url": article.url}).fetchone()
                
                if url_result:
                    return True
                
                # Check for similar title (basic similarity)
                title_hash = hashlib.md5(article.title.lower().encode()).hexdigest()
                title_result = db.execute(text("""
                    SELECT id FROM articles 
                    WHERE MD5(LOWER(title)) = :title_hash
                    AND created_at >= :recent_date
                """), {
                    "title_hash": title_hash,
                    "recent_date": datetime.now() - timedelta(days=7)
                }).fetchone()
                
                if title_result:
                    return True
                
                return False
            finally:
                db.close()
        except Exception as e:
            self.logger.warning(f"Error checking duplicates: {e}")
            return False
    
    async def _save_article(self, article: ArticleData) -> bool:
        """Save article to database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    INSERT INTO articles (
                        title, url, content, summary, published_date, created_at,
                        source, source_tier, source_priority, language, categories,
                        enrichment_status
                    ) VALUES (
                        :title, :url, :content, :summary, :published_date, :created_at,
                        :source, :source_tier, :source_priority, :language, :categories,
                        'pending'
                    ) ON CONFLICT (url) DO NOTHING
                """), {
                    "title": article.title,
                    "url": article.url,
                    "content": article.content,
                    "summary": article.summary,
                    "published_date": article.published_date,
                    "created_at": datetime.now(),
                    "source": article.source,
                    "source_tier": article.source_tier,
                    "source_priority": article.source_priority,
                    "language": article.language,
                    "categories": json.dumps(article.categories)
                })
                
                db.commit()
                return True
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error saving article: {e}")
            return False
    
    async def _update_feed_stats(self, feed_id: int, articles_processed: int, 
                                response_time: int, success: bool, error_message: str = None):
        """Update feed performance statistics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Update feed table
                if success:
                    db.execute(text("""
                        UPDATE rss_feeds 
                        SET last_fetched = CURRENT_TIMESTAMP,
                            last_success = CURRENT_TIMESTAMP,
                            last_error = NULL,
                            status = 'active'
                        WHERE id = :feed_id
                    """), {"feed_id": feed_id})
                else:
                    db.execute(text("""
                        UPDATE rss_feeds 
                        SET last_fetched = CURRENT_TIMESTAMP,
                            last_error = :error_message,
                            status = 'error'
                        WHERE id = :feed_id
                    """), {"feed_id": feed_id, "error_message": error_message})
                
                # Update daily performance metrics
                today = datetime.now().date()
                db.execute(text("""
                    INSERT INTO feed_performance_metrics (
                        feed_id, date, articles_fetched, success_rate, avg_response_time
                    ) VALUES (
                        :feed_id, :date, :articles_fetched, :success_rate, :avg_response_time
                    ) ON CONFLICT (feed_id, date) 
                    DO UPDATE SET 
                        articles_fetched = feed_performance_metrics.articles_fetched + :articles_fetched,
                        success_rate = CASE 
                            WHEN :success THEN 
                                (feed_performance_metrics.success_rate + 100.0) / 2.0
                            ELSE 
                                (feed_performance_metrics.success_rate + 0.0) / 2.0
                        END,
                        avg_response_time = :avg_response_time
                """), {
                    "feed_id": feed_id,
                    "date": today,
                    "articles_fetched": articles_processed,
                    "success_rate": 100.0 if success else 0.0,
                    "avg_response_time": response_time,
                    "success": success
                })
                
                db.commit()
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error updating feed stats: {e}")

# Convenience function for external use
async def fetch_all_rss_feeds(max_concurrent: int = 5) -> Dict[str, Any]:
    """Fetch all RSS feeds with concurrency control"""
    async with RSSFetcherService() as fetcher:
        return await fetcher.fetch_all_feeds(max_concurrent)

