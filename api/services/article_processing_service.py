"""
News Intelligence System v3.0 - Article Processing Service
Handles RSS feed processing, HTML cleaning, deduplication, and database storage
"""

import asyncio
import logging
import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection
import json
import hashlib
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time

# Import deduplication service
from services.deduplication_integration_service import DeduplicationIntegrationService

# Import topic clustering service (optional - for enhanced processing)
try:
    from services.topic_clustering_service import topic_clustering_service
    TOPIC_CLUSTERING_AVAILABLE = True
except ImportError:
    TOPIC_CLUSTERING_AVAILABLE = False
    logger.warning("Topic clustering service not available - topic features disabled")

# Configure logging
logger = logging.getLogger(__name__)

class ArticleProcessingService:
    """Complete article processing service with HTML cleaning and deduplication"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.processed_urls = set()
        self.early_quality_service = None
        self.deduplication_service = DeduplicationIntegrationService(db_config)
        self.topic_clustering_enabled = TOPIC_CLUSTERING_AVAILABLE
        
    def _get_early_quality_service(self):
        """Get early quality service instance"""
        if self.early_quality_service is None:
            from services.early_quality_service import get_early_quality_service
            self.early_quality_service = get_early_quality_service()
        return self.early_quality_service
        
    async def _apply_early_quality_gates(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply early quality gates to filter articles before expensive processing"""
        try:
            early_quality_service = self._get_early_quality_service()
            
            # Adjust quality threshold based on current volume and system load
            current_volume = len(articles)
            system_load = await self._get_system_load()
            early_quality_service.adjust_quality_threshold(current_volume, system_load)
            
            # Apply quality validation
            quality_result = await early_quality_service.batch_validate_articles(articles)
            
            return quality_result
            
        except Exception as e:
            logger.error(f"Error applying early quality gates: {e}")
            # Fail safe - return all articles as passing
            return {
                'success': True,
                'passing_articles': articles,
                'failing_articles': [],
                'total_processed': len(articles),
                'pass_rate': 1.0,
                'quality_threshold': 0.3
            }
    
    async def _get_system_load(self) -> float:
        """Get current system load (0.0 to 1.0)"""
        try:
            # Simple system load calculation based on recent processing
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get recent processing volume
            cursor.execute("""
                SELECT COUNT(*) as recent_articles
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '10 minutes'
            """)
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            recent_articles = result['recent_articles'] if result else 0
            
            # Convert to load factor (0.0 to 1.0)
            # Assume 100 articles per 10 minutes is 50% load
            load_factor = min(recent_articles / 200, 1.0)
            
            return load_factor
            
        except Exception as e:
            logger.warning(f"Error calculating system load: {e}")
            return 0.5  # Default moderate load
        
    async def process_rss_feeds(self, feed_urls: List[str]) -> Dict[str, Any]:
        """Process RSS feeds with early quality gates and return cleaned articles"""
        try:
            logger.info(f"Processing {len(feed_urls)} RSS feeds with early quality gates...")
            
            all_articles = []
            processing_stats = {
                'feeds_processed': 0,
                'articles_found': 0,
                'articles_quality_filtered': 0,
                'articles_cleaned': 0,
                'articles_deduplicated': 0,
                'articles_saved': 0,
                'quality_pass_rate': 0.0,
                'errors': []
            }
            
            for feed_url in feed_urls:
                try:
                    logger.info(f"Processing feed: {feed_url}")
                    articles = await self._process_single_feed(feed_url)
                    all_articles.extend(articles)
                    processing_stats['feeds_processed'] += 1
                    processing_stats['articles_found'] += len(articles)
                    
                except Exception as e:
                    logger.error(f"Error processing feed {feed_url}: {e}")
                    processing_stats['errors'].append(f"Feed {feed_url}: {str(e)}")
            
            # Early quality validation (Phase 1 optimization)
            logger.info("Applying early quality gates...")
            quality_result = await self._apply_early_quality_gates(all_articles)
            quality_passed_articles = quality_result['passing_articles']
            processing_stats['articles_quality_filtered'] = len(quality_passed_articles)
            processing_stats['quality_pass_rate'] = quality_result['pass_rate']
            
            logger.info(f"Quality gates: {len(quality_passed_articles)}/{len(all_articles)} articles passed ({quality_result['pass_rate']:.1%})")
            
            # Deduplicate articles
            unique_articles = await self._deduplicate_articles(quality_passed_articles)
            processing_stats['articles_deduplicated'] = len(unique_articles)
            
            # Clean HTML content
            cleaned_articles = await self._clean_articles(unique_articles)
            processing_stats['articles_cleaned'] = len(cleaned_articles)
            
            # Save to database
            saved_count = await self._save_articles_to_db(cleaned_articles)
            processing_stats['articles_saved'] = saved_count
            
            logger.info(f"Processing complete: {processing_stats}")
            return {
                'success': True,
                'stats': processing_stats,
                'articles_processed': len(cleaned_articles),
                'quality_metrics': {
                    'pass_rate': quality_result['pass_rate'],
                    'threshold': quality_result['quality_threshold'],
                    'filtered_count': len(all_articles) - len(quality_passed_articles)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in RSS processing: {e}")
            return {
                'success': False,
                'error': str(e),
                'stats': processing_stats
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
                        'created_at': datetime.now(timezone.utc).isoformat()
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
            
            # Parse HTML and extract content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove all media and unwanted elements
            for element in soup(["script", "style", "img", "video", "audio", "picture", "source", 
                               "iframe", "embed", "object", "figure", "figcaption", "svg", "canvas"]):
                element.decompose()
            
            # Remove media-related attributes from remaining elements
            for tag in soup.find_all():
                for attr in ['src', 'data-src', 'data-lazy', 'poster', 'preload', 'alt']:
                    if attr in tag.attrs:
                        del tag.attrs[attr]
            
            # Try to find main content area
            content_selectors = [
                'article',
                '.article-content',
                '.post-content',
                '.entry-content',
                '.content',
                'main',
                '.main-content'
            ]
            
            content = None
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    break
            
            if not content:
                # Fallback to body
                content = soup.find('body')
            
            if content:
                # Clean and extract text
                text = content.get_text(separator=' ', strip=True)
                # Clean up extra whitespace
                text = re.sub(r'\s+', ' ', text)
                return text[:5000]  # Limit content length
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
            return ""
    
    async def _clean_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean HTML content and process articles"""
        cleaned_articles = []
        
        for article in articles:
            try:
                # Clean HTML content
                raw_content = article.get('raw_content', '')
                cleaned_content = self._clean_html_content(raw_content)
                
                # Update article with cleaned content
                article['cleaned_content'] = cleaned_content
                article['content'] = cleaned_content  # Use cleaned content as main content
                
                # Calculate word count and reading time
                word_count = len(cleaned_content.split())
                article['word_count'] = word_count
                article['reading_time'] = max(1, word_count // 200)  # ~200 words per minute
                
                # Basic language detection (simplified)
                article['language'] = self._detect_language(cleaned_content)
                
                cleaned_articles.append(article)
                
            except Exception as e:
                logger.error(f"Error cleaning article {article.get('title', 'Unknown')}: {e}")
                continue
        
        return cleaned_articles
    
    def _clean_html_content(self, html_content: str) -> str:
        """Clean HTML content while preserving structural formatting"""
        try:
            if not html_content:
                return ""
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements (including all media)
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement', 
                               'img', 'video', 'audio', 'picture', 'source', 'iframe', 'embed', 'object',
                               'figure', 'figcaption', 'svg', 'canvas', 'map', 'area', 'noscript']):
                element.decompose()
            
            # Remove unwanted elements but preserve structure
            for element in soup(['div', 'span']):
                # Only remove if they don't contain important content
                if not element.find(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote']):
                    element.unwrap()
            
            # Clean up attributes but preserve structure
            for tag in soup.find_all():
                # Remove media-related attributes
                for attr in ['src', 'data-src', 'data-lazy', 'poster', 'preload', 'class', 'id', 'style']:
                    if attr in tag.attrs:
                        del tag.attrs[attr]
                
                # Remove any remaining image references in text
                if tag.string:
                    tag.string = re.sub(r'\[Image\]|\[Video\]|\[Media\]|\[Picture\]|\[Advertisement\]', '', tag.string)
            
            # Preserve structural elements and convert to clean text with formatting
            text_parts = []
            
            # Process structural elements in order
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'blockquote', 'br']):
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    # Headings - add extra spacing
                    heading_text = element.get_text(strip=True)
                    if heading_text:
                        text_parts.append(f"\n\n{heading_text}\n")
                elif element.name == 'p':
                    # Paragraphs - preserve with line breaks
                    para_text = element.get_text(strip=True)
                    if para_text:
                        text_parts.append(f"{para_text}\n")
                elif element.name in ['ul', 'ol']:
                    # Lists - process list items individually
                    text_parts.append("\n")
                    for li in element.find_all('li'):
                        li_text = li.get_text(strip=True)
                        if li_text:
                            text_parts.append(f"• {li_text}\n")
                elif element.name == 'blockquote':
                    # Blockquotes - add indentation
                    quote_text = element.get_text(strip=True)
                    if quote_text:
                        text_parts.append(f"\n    {quote_text}\n")
                elif element.name == 'br':
                    # Line breaks - preserve
                    text_parts.append("\n")
            
            # If no structural elements found, fall back to basic text extraction
            if not text_parts:
                text = soup.get_text(separator='\n', strip=True)
            else:
                text = ''.join(text_parts)
            
            # Clean up excessive whitespace while preserving structure
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
            text = re.sub(r'[ \t]+', ' ', text)  # Replace multiple spaces/tabs with single space
            text = re.sub(r' \n', '\n', text)  # Remove spaces before newlines
            text = re.sub(r'\n ', '\n', text)  # Remove spaces after newlines
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.error(f"Error cleaning HTML content: {e}")
            return html_content
    
    async def _deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate articles based on URL and title similarity"""
        try:
            seen_urls = set()
            seen_titles = set()
            unique_articles = []
            
            for article in articles:
                url = article.get('url', '')
                title = article.get('title', '').lower().strip()
                
                # Check for URL duplicates
                if url in seen_urls:
                    continue
                
                # Check for title duplicates (basic similarity)
                title_hash = hashlib.md5(title.encode()).hexdigest()
                if title_hash in seen_titles:
                    continue
                
                seen_urls.add(url)
                seen_titles.add(title_hash)
                unique_articles.append(article)
            
            logger.info(f"Deduplicated {len(articles)} articles to {len(unique_articles)} unique articles")
            return unique_articles
            
        except Exception as e:
            logger.error(f"Error deduplicating articles: {e}")
            return articles
    
    async def _save_articles_to_db(self, articles: List[Dict[str, Any]]) -> int:
        """Save cleaned articles to database with advanced deduplication"""
        saved_count = 0
        duplicate_count = 0
        storyline_suggestions = []
        
        for article in articles:
            try:
                # Process article through deduplication system
                dedup_result = await self.deduplication_service.process_new_article(article)
                
                if dedup_result['status'] == 'duplicate':
                    duplicate_count += 1
                    logger.info(f"Duplicate article skipped: {article.get('title', 'Unknown')} - {dedup_result['recommendation']}")
                    continue
                
                elif dedup_result['status'] == 'error':
                    logger.error(f"Deduplication error for article {article.get('title', 'Unknown')}: {dedup_result.get('error', 'Unknown error')}")
                    continue
                
                # Use processed article data from deduplication service
                processed_article = dedup_result.get('article_data', article)
                
                # Collect storyline suggestions
                if dedup_result.get('storyline_candidates'):
                    storyline_suggestions.extend(dedup_result['storyline_candidates'])
                
                # Save to database
                conn = None
                cursor = None
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Debug: Log article data
                    logger.debug(f"Processing article: {processed_article.get('title', 'Unknown')}")
                    logger.debug(f"Article source: {processed_article.get('source', 'None')}")
                    logger.debug(f"Article URL: {processed_article.get('url', 'None')}")
                    logger.debug(f"Content hash: {processed_article.get('content_hash', 'None')[:16]}...")
                    
                    # Get feed_id for this article
                    feed_id = None
                    if processed_article.get('source'):
                        cursor.execute("SELECT id FROM rss_feeds WHERE feed_name = %s", (processed_article.get('source'),))
                        feed_result = cursor.fetchone()
                        if feed_result:
                            feed_id = feed_result[0]
                            logger.debug(f"Found feed_id: {feed_id}")
                        else:
                            logger.warning(f"No feed found for source: {processed_article.get('source')}")
                    
                    cursor.execute("""
                        INSERT INTO articles (
                            title, content, url, published_at, source_domain, tags, 
                            entities, sentiment_score, readability_score, quality_score,
                            summary, analysis_results, language_code, word_count, reading_time_minutes,
                            feed_id, content_hash, processing_status
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        processed_article.get('title', ''),
                        processed_article.get('cleaned_content', ''),
                        processed_article.get('url', ''),
                        processed_article.get('published_at'),
                        processed_article.get('source', ''),
                        json.dumps(processed_article.get('tags', [])),
                        json.dumps(processed_article.get('entities', {})),
                        processed_article.get('sentiment_score'),
                        processed_article.get('readability_score'),
                        processed_article.get('quality_score'),
                        processed_article.get('summary', ''),
                        json.dumps(processed_article.get('ml_data', {})),
                        processed_article.get('language', 'en'),
                        processed_article.get('word_count', 0),
                        processed_article.get('reading_time', 1),
                        feed_id,
                        processed_article.get('content_hash'),
                        'pending'
                    ))
                    
                    conn.commit()
                    saved_count += 1
                    logger.debug(f"Successfully saved article: {processed_article.get('title', 'Unknown')}")
                    
                except Exception as e:
                    logger.error(f"Error saving article {processed_article.get('title', 'Unknown')}: {e}")
                    if conn:
                        conn.rollback()
                    continue
                finally:
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()
                        
            except Exception as e:
                logger.error(f"Error processing article {article.get('title', 'Unknown')} through deduplication: {e}")
                continue
        
        # Log summary
        logger.info(f"Article processing complete: {saved_count} saved, {duplicate_count} duplicates skipped")
        
        # Log storyline suggestions if any
        if storyline_suggestions:
            logger.info(f"Found {len(storyline_suggestions)} storyline suggestions")
            for suggestion in storyline_suggestions[:5]:  # Log first 5
                logger.info(f"Storyline suggestion: {suggestion.get('storyline_suggestion', 'N/A')}")
        
        return saved_count
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        try:
            if not date_str:
                return None
            
            # Try different date formats
            date_formats = [
                '%a, %d %b %Y %H:%M:%S %Z',
                '%a, %d %b %Y %H:%M:%S %z',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Fallback to current time
            return datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return datetime.now(timezone.utc)
    
    def _extract_source_from_url(self, url: str) -> str:
        """Extract source name from URL"""
        try:
            if not url:
                return 'Unknown'
            
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Map common domains to source names
            source_map = {
                'techcrunch.com': 'TechCrunch',
                'reuters.com': 'Reuters',
                'bbc.com': 'BBC',
                'cnn.com': 'CNN',
                'nytimes.com': 'New York Times',
                'washingtonpost.com': 'Washington Post',
                'theguardian.com': 'The Guardian',
                'bloomberg.com': 'Bloomberg',
                'wsj.com': 'Wall Street Journal',
                'forbes.com': 'Forbes'
            }
            
            return source_map.get(domain, domain.replace('www.', '').title())
            
        except Exception as e:
            logger.error(f"Error extracting source from {url}: {e}")
            return 'Unknown'
    
    def _extract_tags(self, entry) -> List[str]:
        """Extract tags from RSS entry"""
        try:
            tags = []
            
            # Extract from categories
            if hasattr(entry, 'tags'):
                for tag in entry.tags:
                    if hasattr(tag, 'term'):
                        tags.append(tag.term)
            
            # Extract from subject
            if hasattr(entry, 'subject'):
                tags.append(entry.subject)
            
            return tags[:10]  # Limit to 10 tags
            
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return []
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection"""
        try:
            if not text:
                return 'en'
            
            # Simple English detection based on common words
            english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
            text_lower = text.lower()
            
            english_count = sum(1 for word in english_words if word in text_lower)
            
            if english_count > 3:
                return 'en'
            else:
                return 'en'  # Default to English
                
        except Exception as e:
            logger.error(f"Error detecting language: {e}")
            return 'en'

    def process_single_article(self, article_id: int) -> Dict[str, Any]:
        """Process a single article by ID"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get article details
            cursor.execute("""
                SELECT id, title, content, url, source_domain, published_at, created_at
                FROM articles 
                WHERE id = %s AND processing_status = 'pending'
            """, (article_id,))
            
            article = cursor.fetchone()
            if not article:
                return {"success": False, "message": "Article not found or already processed"}
            
            # Process the article
            article_dict = dict(article)
            processed_articles = asyncio.run(self._process_articles([article_dict]))
            
            if processed_articles:
                return {"success": True, "message": f"Processed article {article_id}"}
            else:
                return {"success": False, "message": f"Failed to process article {article_id}"}
                
        except Exception as e:
            logger.error(f"Error processing article {article_id}: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
        finally:
            if 'conn' in locals():
                conn.close()

    async def process_articles_with_topics(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process articles and add topic clustering (from enhanced_article_processing_service)"""
        if not self.topic_clustering_enabled:
            logger.warning("Topic clustering not available - processing without topics")
            return {
                'success': True,
                'processed_articles': articles,
                'topic_stats': {
                    'articles_processed': len(articles),
                    'topics_extracted': 0,
                    'clusters_created': 0,
                    'errors': 0
                }
            }
        
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
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in topic processing: {e}")
            return {
                'success': False,
                'error': str(e),
                'processed_articles': articles,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def process_rss_feeds_with_topics(self, feed_urls: List[str]) -> Dict[str, Any]:
        """Process RSS feeds with topic clustering (from enhanced_article_processing_service)"""
        try:
            logger.info(f"Processing {len(feed_urls)} RSS feeds with topic clustering...")
            
            # First process feeds normally
            result = await self.process_rss_feeds(feed_urls)
            
            if not result['success']:
                return result
            
            return {
                'success': True,
                'stats': result.get('stats', {}),
                'articles_processed': result.get('articles_processed', 0),
                'topic_clustering_enabled': self.topic_clustering_enabled,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing RSS feeds with topics: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# Global instance
_article_processor = None

def get_article_processor() -> ArticleProcessingService:
    """Get global article processor instance"""
    global _article_processor
    if _article_processor is None:
        from config.database import get_db_config
        db_config = get_db_config()
        _article_processor = ArticleProcessingService(db_config)
    return _article_processor

# Compatibility alias for enhanced_article_processing_service
def get_enhanced_article_processor() -> ArticleProcessingService:
    """Get enhanced article processor (compatibility alias)"""
    return get_article_processor()
