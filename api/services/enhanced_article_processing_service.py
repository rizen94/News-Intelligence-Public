"""
News Intelligence System v3.0 - Enhanced Article Processing Service
Includes topic clustering using Ollama LLM
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
from bs4 import BeautifulSoup
import time

# Import our topic clustering service
from services.topic_clustering_service import topic_clustering_service

# Import deduplication service
from services.deduplication_integration_service import DeduplicationIntegrationService

# Configure logging
logger = logging.getLogger(__name__)

class EnhancedArticleProcessingService:
    """Enhanced article processing service with topic clustering"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.processed_urls = set()
        self.deduplication_service = DeduplicationIntegrationService(db_config)
        
    async def process_articles_with_topics(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process articles and add topic clustering"""
        try:
            logger.info(f"Processing {len(articles)} articles with topic clustering...")
            
            processed_articles = []
            topic_stats = {
                'articles_processed': 0,
                'topics_extracted': 0,
                'clusters_created': 0,
                'errors': 0
            }
            
            # Process articles in batches for topic clustering
            batch_size = 5
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i + batch_size]
                
                # Process each article in the batch
                for article in batch:
                    try:
                        # Extract topics for individual article
                        topic_result = await topic_clustering_service.extract_topics_from_article(
                            article.get('title', ''),
                            article.get('content', '')
                        )
                        
                        if topic_result['success']:
                            topic_data = topic_result['data']
                            
                            # Add topic data to article
                            article['primary_topic'] = topic_data['primary_topic']
                            article['secondary_topics'] = topic_data['secondary_topics']
                            article['keywords'] = topic_data['keywords']
                            article['entities'] = topic_data['entities']
                            article['category'] = topic_data['category']
                            article['subcategory'] = topic_data['subcategory']
                            article['sentiment'] = topic_data['sentiment']
                            article['urgency'] = topic_data['urgency']
                            article['geographic_scope'] = topic_data['geographic_scope']
                            article['topic_confidence'] = topic_data['confidence']
                            
                            topic_stats['topics_extracted'] += 1
                            
                        processed_articles.append(article)
                        topic_stats['articles_processed'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing article topics: {e}")
                        topic_stats['errors'] += 1
                        # Add article without topic data
                        processed_articles.append(article)
                
                # Cluster articles in this batch
                if len(batch) > 1:
                    try:
                        cluster_result = await topic_clustering_service.cluster_articles_by_topic(batch)
                        if cluster_result['success']:
                            # Save clustering results to database
                            await topic_clustering_service.save_topics_to_database(
                                cluster_result['data'], 
                                batch
                            )
                            topic_stats['clusters_created'] += len(cluster_result['data'].get('topics', []))
                    except Exception as e:
                        logger.error(f"Error clustering articles: {e}")
                        topic_stats['errors'] += 1
            
            logger.info(f"Topic processing complete: {topic_stats}")
            
            return {
                'success': True,
                'processed_articles': processed_articles,
                'topic_stats': topic_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced article processing: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def process_rss_feeds_with_topics(self, feed_urls: List[str]) -> Dict[str, Any]:
        """Process RSS feeds with topic clustering"""
        try:
            logger.info(f"Processing {len(feed_urls)} RSS feeds with topic clustering...")
            
            all_articles = []
            processing_stats = {
                'feeds_processed': 0,
                'articles_found': 0,
                'articles_with_topics': 0,
                'clusters_created': 0,
                'errors': 0
            }
            
            # Process each feed
            for feed_url in feed_urls:
                try:
                    articles = await self._process_single_feed(feed_url)
                    all_articles.extend(articles)
                    processing_stats['feeds_processed'] += 1
                    processing_stats['articles_found'] += len(articles)
                    
                except Exception as e:
                    logger.error(f"Error processing feed {feed_url}: {e}")
                    processing_stats['errors'] += 1
                    continue
            
            # Process articles with topic clustering
            if all_articles:
                topic_result = await self.process_articles_with_topics(all_articles)
                
                if topic_result['success']:
                    processing_stats['articles_with_topics'] = topic_result['topic_stats']['articles_processed']
                    processing_stats['clusters_created'] = topic_result['topic_stats']['clusters_created']
                    
                    # Save articles to database
                    saved_count = await self._save_articles_to_database(topic_result['processed_articles'])
                    processing_stats['articles_saved'] = saved_count
            
            return {
                'success': True,
                'stats': processing_stats,
                'articles_processed': len(all_articles),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing RSS feeds with topics: {e}")
            return {
                'success': False,
                'error': str(e),
                'stats': processing_stats,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _process_single_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """Process a single RSS feed"""
        try:
            # Parse RSS feed
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"Feed parsing issues for {feed_url}: {feed.bozo_exception}")
            
            articles = []
            for entry in feed.entries:
                try:
                    article = {
                        'title': entry.get('title', ''),
                        'url': entry.get('link', ''),
                        'published_at': self._parse_date(entry.get('published', '')),
                        'summary': entry.get('summary', ''),
                        'content': '',  # Will be fetched and cleaned
                        'source': self._extract_source_from_url(entry.get('link', '')),
                        'raw_content': '',  # Original HTML content
                        'cleaned_content': '',  # Cleaned text content
                        'word_count': 0,
                        'reading_time': 0,
                        'tags': self._extract_tags(entry),
                        'entities': {},
                        'sentiment_score': None,
                        'readability_score': None,
                        'quality_score': None,
                        'language': 'en',
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        # Topic fields (will be populated later)
                        'primary_topic': None,
                        'secondary_topics': [],
                        'keywords': [],
                        'category': None,
                        'subcategory': None,
                        'sentiment': 'neutral',
                        'urgency': 'normal',
                        'geographic_scope': 'national',
                        'topic_confidence': 0.0
                    }
                    
                    # Fetch full article content
                    if article['url']:
                        full_content = await self._fetch_article_content(article['url'])
                        article['raw_content'] = full_content
                        article['content'] = full_content  # Will be cleaned later
                    
                    articles.append(article)
                    
                except Exception as e:
                    logger.error(f"Error processing article from {feed_url}: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")
            return []
    
    async def _fetch_article_content(self, url: str) -> str:
        """Fetch full article content from URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
            return ""
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to ISO format"""
        try:
            if not date_str:
                return None
            
            # Try different date formats
            date_formats = [
                '%a, %d %b %Y %H:%M:%S %z',
                '%a, %d %b %Y %H:%M:%S %Z',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'
            ]
            
            for fmt in date_formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return None
    
    def _extract_source_from_url(self, url: str) -> str:
        """Extract source name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Remove common TLDs
            domain = domain.split('.')[0]
            
            return domain.title()
            
        except Exception as e:
            logger.error(f"Error extracting source from {url}: {e}")
            return "Unknown"
    
    def _extract_tags(self, entry) -> List[str]:
        """Extract tags from RSS entry"""
        try:
            tags = []
            
            # Check for tags in different fields
            if hasattr(entry, 'tags'):
                tags.extend([tag.term for tag in entry.tags])
            
            if hasattr(entry, 'category'):
                tags.append(entry.category)
            
            return tags
            
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return []
    
    async def _save_articles_to_database(self, articles: List[Dict[str, Any]]) -> int:
        """Save articles to database with topic data"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            saved_count = 0
            
            for article in articles:
                try:
                    cursor.execute("""
                        INSERT INTO articles (
                            title, content, url, published_at, source, category, subcategory,
                            status, tags, entities, sentiment_score, quality_score, summary,
                            language, word_count, reading_time, created_at, updated_at,
                            primary_topic, secondary_topics, keywords, sentiment, urgency,
                            geographic_scope, topic_confidence
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        article.get('title'),
                        article.get('content'),
                        article.get('url'),
                        article.get('published_at'),
                        article.get('source'),
                        article.get('category'),
                        article.get('subcategory'),
                        'processed',
                        json.dumps(article.get('tags', [])),
                        json.dumps(article.get('entities', {})),
                        article.get('sentiment_score'),
                        article.get('quality_score'),
                        article.get('summary'),
                        article.get('language'),
                        article.get('word_count'),
                        article.get('reading_time'),
                        article.get('created_at'),
                        datetime.now().isoformat(),
                        article.get('primary_topic'),
                        json.dumps(article.get('secondary_topics', [])),
                        json.dumps(article.get('keywords', [])),
                        article.get('sentiment'),
                        article.get('urgency'),
                        article.get('geographic_scope'),
                        article.get('topic_confidence')
                    ))
                    
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving article to database: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Saved {saved_count} articles to database")
            
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving articles to database: {e}")
            conn.rollback()
            return 0
        finally:
            if 'conn' in locals():
                conn.close()

# Global instance
_enhanced_article_processor = None

def get_enhanced_article_processor() -> EnhancedArticleProcessingService:
    """Get global enhanced article processor instance"""
    global _enhanced_article_processor
    if _enhanced_article_processor is None:
        from config.database import get_db_config
        _enhanced_article_processor = EnhancedArticleProcessingService(get_db_config())
    return _enhanced_article_processor
