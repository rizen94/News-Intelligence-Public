"""
News Intelligence System v3.1.0 - Article Processing Service
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
import json
import hashlib
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time

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
            conn = psycopg2.connect(**self.db_config)
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
        """Save cleaned articles to database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            saved_count = 0
            for article in articles:
                try:
                    # Generate unique ID as integer
                    article_id = int(time.time() * 1000) + hash(article['url']) % 10000
                    
                    # Insert article
                    cursor.execute("""
                        INSERT INTO articles (
                            id, title, content, url, published_at, source, tags, 
                            entities, sentiment_score, readability_score, quality_score,
                            summary, ml_data, language, word_count, reading_time, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            content = EXCLUDED.content,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        article_id,
                        article.get('title', ''),
                        article.get('cleaned_content', ''),
                        article.get('url', ''),
                        article.get('published_at'),
                        article.get('source', ''),
                        json.dumps(article.get('tags', [])),
                        json.dumps(article.get('entities', {})),
                        article.get('sentiment_score'),
                        article.get('readability_score'),
                        article.get('quality_score'),
                        article.get('summary', ''),
                        json.dumps(article.get('ml_data', {})),
                        article.get('language', 'en'),
                        article.get('word_count', 0),
                        article.get('reading_time', 0),
                        article.get('created_at')
                    ))
                    
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving article {article.get('title', 'Unknown')}: {e}")
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Saved {saved_count} articles to database")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving articles to database: {e}")
            return 0
    
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
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get article details
            cursor.execute("""
                SELECT id, title, content, url, source, published_at, created_at
                FROM articles 
                WHERE id = %s AND processing_status = 'raw'
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

# Global instance
_article_processor = None

def get_article_processor() -> ArticleProcessingService:
    """Get global article processor instance"""
    global _article_processor
    if _article_processor is None:
        from database.connection import get_db_config
        db_config = get_db_config()
        _article_processor = ArticleProcessingService(db_config)
    return _article_processor
