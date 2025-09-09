"""
RSS Feed Collection Service
Collects news articles from top English RSS feeds worldwide
"""

import logging
import feedparser
import requests
import time
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import psycopg2
from urllib.parse import urlparse, urljoin
import re
from dataclasses import dataclass
import json
from .progress_tracker import progress_tracker

logger = logging.getLogger(__name__)

@dataclass
class RSSFeed:
    """RSS Feed configuration"""
    name: str
    url: str
    category: str
    country: str
    language: str
    priority: int
    enabled: bool = True
    last_updated: Optional[datetime] = None
    error_count: int = 0
    max_errors: int = 5

@dataclass
class Article:
    """Article data structure"""
    title: str
    content: str
    summary: str
    url: str
    source: str
    published_date: datetime
    category: str
    country: str
    language: str
    content_hash: str
    tags: List[str]
    author: Optional[str] = None
    image_url: Optional[str] = None

class RSSFeedService:
    """Service for collecting news from RSS feeds"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize RSS Feed Service
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsIntelligenceSystem/1.0 (RSS Collector)'
        })
        
        # RSS Feed configurations - Top English news sources worldwide
        self.feeds = [
            # Major International News
            RSSFeed("BBC News", "http://feeds.bbci.co.uk/news/rss.xml", "General", "UK", "en", 1),
            RSSFeed("Reuters World News", "https://feeds.reuters.com/reuters/worldNews", "General", "International", "en", 1),
            RSSFeed("Associated Press", "https://feeds.apnews.com/apnews/topnews", "General", "US", "en", 1),
            RSSFeed("CNN Top Stories", "http://rss.cnn.com/rss/edition.rss", "General", "US", "en", 1),
            RSSFeed("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml", "General", "Qatar", "en", 1),
            
            # US News Sources
            RSSFeed("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "General", "US", "en", 1),
            RSSFeed("Washington Post", "https://feeds.washingtonpost.com/rss/world", "General", "US", "en", 1),
            RSSFeed("Wall Street Journal", "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "Business", "US", "en", 1),
            RSSFeed("NPR News", "https://feeds.npr.org/1001/rss.xml", "General", "US", "en", 1),
            RSSFeed("Politico", "https://www.politico.com/rss/politicopicks.xml", "Politics", "US", "en", 1),
            
            # UK News Sources
            RSSFeed("The Guardian", "https://www.theguardian.com/world/rss", "General", "UK", "en", 1),
            RSSFeed("The Telegraph", "https://www.telegraph.co.uk/rss.xml", "General", "UK", "en", 1),
            RSSFeed("Financial Times", "https://www.ft.com/rss/home", "Business", "UK", "en", 1),
            RSSFeed("The Independent", "https://www.independent.co.uk/rss", "General", "UK", "en", 1),
            
            # Technology News
            RSSFeed("TechCrunch", "https://techcrunch.com/feed/", "Technology", "US", "en", 1),
            RSSFeed("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/", "Technology", "US", "en", 1),
            RSSFeed("The Verge", "https://www.theverge.com/rss/index.xml", "Technology", "US", "en", 1),
            RSSFeed("Wired", "https://www.wired.com/feed/rss", "Technology", "US", "en", 1),
            
            # Business & Finance
            RSSFeed("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss", "Business", "US", "en", 1),
            RSSFeed("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/", "Business", "US", "en", 1),
            RSSFeed("Forbes", "https://www.forbes.com/business/feed/", "Business", "US", "en", 1),
            
            # Science & Health
            RSSFeed("Scientific American", "https://rss.sciam.com/ScientificAmerican-News", "Science", "US", "en", 1),
            RSSFeed("Nature News", "https://www.nature.com/nature.rss", "Science", "International", "en", 1),
            RSSFeed("BBC Science", "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "Science", "UK", "en", 1),
            
            # Regional English Sources
            RSSFeed("Sydney Morning Herald", "https://www.smh.com.au/rss/feed.xml", "General", "Australia", "en", 2),
            RSSFeed("The Globe and Mail", "https://www.theglobeandmail.com/rss.xml", "General", "Canada", "en", 2),
            RSSFeed("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", "General", "India", "en", 2),
            RSSFeed("South China Morning Post", "https://www.scmp.com/rss/91/feed", "General", "Hong Kong", "en", 2),
            
            # Specialized Sources
            RSSFeed("Foreign Policy", "https://foreignpolicy.com/feed/", "International", "US", "en", 2),
            RSSFeed("The Economist", "https://www.economist.com/world/rss.xml", "International", "UK", "en", 1),
            RSSFeed("Time Magazine", "https://feeds.feedburner.com/time/world", "General", "US", "en", 2),
        ]
        
        # Statistics
        self.stats = {
            'total_feeds': len(self.feeds),
            'enabled_feeds': len([f for f in self.feeds if f.enabled]),
            'articles_collected': 0,
            'articles_processed': 0,
            'errors': 0,
            'last_collection': None
        }
    
    def collect_all_feeds(self, max_articles_per_feed: int = 50, collection_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect articles from all enabled RSS feeds with progress tracking
        
        Args:
            max_articles_per_feed: Maximum articles to collect per feed
            collection_id: Optional collection ID for progress tracking
            
        Returns:
            Dictionary with collection results
        """
        # Generate collection ID if not provided
        if not collection_id:
            collection_id = str(uuid.uuid4())
        
        start_time = time.time()
        enabled_feeds = [feed for feed in self.feeds if feed.enabled]
        
        # Start progress tracking
        progress_tracker.start_collection(collection_id, len(enabled_feeds))
        
        collection_results = {
            'collection_id': collection_id,
            'start_time': datetime.now().isoformat(),
            'feeds_processed': 0,
            'feeds_successful': 0,
            'feeds_failed': 0,
            'total_articles': 0,
            'new_articles': 0,
            'duplicate_articles': 0,
            'errors': [],
            'feed_results': []
        }
        
        logger.info(f"Starting RSS feed collection {collection_id} from {len(enabled_feeds)} feeds")
        
        try:
            for feed in enabled_feeds:
                try:
                    collection_results['feeds_processed'] += 1
                    
                    # Update progress for current feed
                    progress_tracker.update_feed_progress(collection_id, feed.name, 0, 0)
                    
                    feed_result = self.collect_feed(feed, max_articles_per_feed)
                    collection_results['feed_results'].append(feed_result)
                    
                    if feed_result['success']:
                        collection_results['feeds_successful'] += 1
                        collection_results['total_articles'] += feed_result['articles_found']
                        collection_results['new_articles'] += feed_result['new_articles']
                        collection_results['duplicate_articles'] += feed_result['duplicate_articles']
                        
                        # Mark feed as completed successfully
                        progress_tracker.complete_feed(
                            collection_id, feed.name,
                            feed_result['articles_found'],
                            feed_result['new_articles'],
                            feed_result['duplicate_articles'],
                            success=True
                        )
                    else:
                        collection_results['feeds_failed'] += 1
                        collection_results['errors'].append(f"{feed.name}: {feed_result['error']}")
                        
                        # Mark feed as failed
                        progress_tracker.complete_feed(
                            collection_id, feed.name,
                            0, 0, 0,
                            success=False
                        )
                        progress_tracker.add_error(collection_id, f"{feed.name}: {feed_result['error']}")
                    
                    # Rate limiting - be respectful to RSS feeds
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing feed {feed.name}: {e}")
                    collection_results['feeds_failed'] += 1
                    collection_results['errors'].append(f"{feed.name}: {str(e)}")
                    
                    # Mark feed as failed
                    progress_tracker.complete_feed(
                        collection_id, feed.name,
                        0, 0, 0,
                        success=False
                    )
                    progress_tracker.add_error(collection_id, f"{feed.name}: {str(e)}")
            
            # Mark collection as completed
            progress_tracker.complete_collection(collection_id, success=True)
            
        except Exception as e:
            logger.error(f"Fatal error in RSS collection {collection_id}: {e}")
            progress_tracker.add_error(collection_id, f"Fatal error: {str(e)}")
            progress_tracker.complete_collection(collection_id, success=False)
            raise
        
        # Update statistics
        collection_results['end_time'] = datetime.now().isoformat()
        collection_results['duration'] = time.time() - start_time
        self.stats['last_collection'] = datetime.now()
        self.stats['articles_collected'] += collection_results['new_articles']
        
        logger.info(f"RSS collection completed: {collection_results['new_articles']} new articles from {collection_results['feeds_successful']} feeds")
        
        return collection_results
    
    def collect_feed(self, feed: RSSFeed, max_articles: int = 50) -> Dict[str, Any]:
        """
        Collect articles from a single RSS feed
        
        Args:
            feed: RSS feed configuration
            max_articles: Maximum articles to collect
            
        Returns:
            Dictionary with feed collection results
        """
        try:
            logger.info(f"Collecting from {feed.name}: {feed.url}")
            
            # Parse RSS feed
            feed_data = feedparser.parse(feed.url)
            
            if feed_data.bozo:
                logger.warning(f"RSS feed {feed.name} has parsing issues: {feed_data.bozo_exception}")
            
            if not feed_data.entries:
                return {
                    'feed_name': feed.name,
                    'success': False,
                    'error': 'No entries found in RSS feed',
                    'articles_found': 0,
                    'new_articles': 0,
                    'duplicate_articles': 0
                }
            
            articles = []
            for entry in feed_data.entries[:max_articles]:
                try:
                    article = self._parse_rss_entry(entry, feed)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error parsing entry from {feed.name}: {e}")
                    continue
            
            # Store articles in database
            new_count, duplicate_count = self._store_articles(articles)
            
            # Update feed status
            feed.last_updated = datetime.now()
            feed.error_count = 0
            
            return {
                'feed_name': feed.name,
                'success': True,
                'articles_found': len(articles),
                'new_articles': new_count,
                'duplicate_articles': duplicate_count,
                'last_updated': feed.last_updated.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error collecting from {feed.name}: {e}")
            feed.error_count += 1
            
            # Disable feed if too many errors
            if feed.error_count >= feed.max_errors:
                feed.enabled = False
                logger.warning(f"Disabled feed {feed.name} due to {feed.error_count} consecutive errors")
            
            return {
                'feed_name': feed.name,
                'success': False,
                'error': str(e),
                'articles_found': 0,
                'new_articles': 0,
                'duplicate_articles': 0
            }
    
    def _parse_rss_entry(self, entry: Any, feed: RSSFeed) -> Optional[Article]:
        """
        Parse a single RSS entry into an Article object
        
        Args:
            entry: RSS entry from feedparser
            feed: RSS feed configuration
            
        Returns:
            Article object or None if parsing fails
        """
        try:
            # Extract basic information
            title = self._clean_text(entry.get('title', ''))
            if not title:
                return None
            
            # Extract content
            content = ''
            if hasattr(entry, 'content') and entry.content:
                content = self._clean_text(entry.content[0].value)
            elif hasattr(entry, 'summary'):
                content = self._clean_text(entry.summary)
            elif hasattr(entry, 'description'):
                content = self._clean_text(entry.description)
            
            # Extract URL
            url = entry.get('link', '')
            if not url:
                return None
            
            # Parse published date
            published_date = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_date = datetime(*entry.updated_parsed[:6])
            
            # Extract author
            author = None
            if hasattr(entry, 'author'):
                author = entry.author
            elif hasattr(entry, 'author_detail') and entry.author_detail:
                author = entry.author_detail.get('name', '')
            
            # Extract image URL
            image_url = None
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        image_url = media.get('url', '')
                        break
            
            # Generate content hash for deduplication
            content_hash = self._generate_content_hash(title, content)
            
            # Extract tags
            tags = []
            if hasattr(entry, 'tags'):
                tags = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
            
            # Create summary (first 200 characters of content)
            summary = content[:200] + '...' if len(content) > 200 else content
            
            return Article(
                title=title,
                content=content,
                summary=summary,
                url=url,
                source=feed.name,
                published_date=published_date,
                category=feed.category,
                country=feed.country,
                language=feed.language,
                content_hash=content_hash,
                tags=tags,
                author=author,
                image_url=image_url
            )
            
        except Exception as e:
            logger.warning(f"Error parsing RSS entry: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ''
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _generate_content_hash(self, title: str, content: str) -> str:
        """Generate hash for content deduplication"""
        combined = f"{title}|{content}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    def _store_articles(self, articles: List[Article]) -> Tuple[int, int]:
        """
        Store articles in database with deduplication
        
        Args:
            articles: List of Article objects
            
        Returns:
            Tuple of (new_articles_count, duplicate_articles_count)
        """
        if not articles:
            return 0, 0
        
        new_count = 0
        duplicate_count = 0
        
        # Process articles one by one to avoid transaction issues
        for article in articles:
            try:
                conn = psycopg2.connect(**self.db_config)
                cursor = conn.cursor()
                
                try:
                    # Check if article already exists
                    cursor.execute("""
                        SELECT id FROM articles 
                        WHERE content_hash = %s OR url = %s
                    """, (article.content_hash, article.url))
                    
                    if cursor.fetchone():
                        duplicate_count += 1
                        conn.close()
                        continue
                    
                    # Insert new article (matching actual database schema)
                    cursor.execute("""
                        INSERT INTO articles (
                            title, content, summary, url, source, published_date,
                            category, language, content_hash, created_at, updated_at,
                            quality_score, processing_status, deduplication_status
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        article.title,
                        article.content,
                        article.summary,
                        article.url,
                        article.source,
                        article.published_date,
                        article.category,
                        article.language,
                        article.content_hash,
                        datetime.now(),
                        datetime.now(),
                        0.5,  # Default quality score for RSS articles
                        'pending',
                        'unique'
                    ))
                    
                    conn.commit()
                    new_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error storing article '{article.title}': {e}")
                    conn.rollback()
                finally:
                    conn.close()
                    
            except Exception as e:
                logger.warning(f"Error connecting to database for article '{article.title}': {e}")
                continue
        
        logger.info(f"Stored {new_count} new articles, {duplicate_count} duplicates")
        return new_count, duplicate_count
    
    def get_feed_status(self) -> Dict[str, Any]:
        """Get status of all RSS feeds"""
        try:
            feed_status = []
            for feed in self.feeds:
                feed_status.append({
                    'name': feed.name,
                    'url': feed.url,
                    'category': feed.category,
                    'country': feed.country,
                    'enabled': feed.enabled,
                    'last_updated': feed.last_updated.isoformat() if feed.last_updated else None,
                    'error_count': feed.error_count,
                    'priority': feed.priority
                })
            
            return {
                'feeds': feed_status,
                'statistics': self.stats,
                'total_feeds': len(self.feeds),
                'enabled_feeds': len([f for f in self.feeds if f.enabled]),
                'disabled_feeds': len([f for f in self.feeds if not f.enabled])
            }
            
        except Exception as e:
            logger.error(f"Error getting feed status: {e}")
            return {'error': str(e)}
    
    def enable_feed(self, feed_name: str) -> bool:
        """Enable a disabled RSS feed"""
        for feed in self.feeds:
            if feed.name == feed_name:
                feed.enabled = True
                feed.error_count = 0
                logger.info(f"Enabled feed: {feed_name}")
                return True
        return False
    
    def disable_feed(self, feed_name: str) -> bool:
        """Disable an RSS feed"""
        for feed in self.feeds:
            if feed.name == feed_name:
                feed.enabled = False
                logger.info(f"Disabled feed: {feed_name}")
                return True
        return False
    
    def add_custom_feed(self, name: str, url: str, category: str, country: str, priority: int = 2) -> bool:
        """Add a custom RSS feed"""
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Check if feed already exists
            for feed in self.feeds:
                if feed.url == url:
                    return False
            
            # Add new feed
            new_feed = RSSFeed(name, url, category, country, "en", priority)
            self.feeds.append(new_feed)
            
            logger.info(f"Added custom feed: {name} ({url})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding custom feed: {e}")
            return False
    
    def test_feed(self, feed_url: str) -> Dict[str, Any]:
        """Test if an RSS feed is valid and accessible"""
        try:
            feed_data = feedparser.parse(feed_url)
            
            if feed_data.bozo:
                return {
                    'valid': False,
                    'error': f'RSS parsing error: {feed_data.bozo_exception}',
                    'entries_count': 0
                }
            
            if not feed_data.entries:
                return {
                    'valid': False,
                    'error': 'No entries found in RSS feed',
                    'entries_count': 0
                }
            
            return {
                'valid': True,
                'title': feed_data.feed.get('title', 'Unknown'),
                'description': feed_data.feed.get('description', ''),
                'entries_count': len(feed_data.entries),
                'sample_entries': [
                    {
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'published': entry.get('published', '')
                    }
                    for entry in feed_data.entries[:3]
                ]
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'entries_count': 0
            }
