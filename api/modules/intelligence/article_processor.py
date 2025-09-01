#!/usr/bin/env python3
"""
News Intelligence System v2.5.0 - Article Processor
Transforms raw articles into ML-ready processed data
"""

import os
import re
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticleProcessor:
    """Core article processing for ML preparation"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.connection = None
        
    def connect_db(self) -> bool:
        """Establish database connection with timeout protection"""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config.get('host', 'postgres'),
                database=self.db_config.get('database', 'news_system'),
                user=self.db_config.get('user', 'newsapp'),
                password=self.db_config.get('password', ''),
                connect_timeout=10,
                options='-c statement_timeout=30000'
            )
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def extract_article_metadata(self, article: Dict) -> Dict:
        """Extract and normalize article metadata"""
        try:
            # Clean and normalize title
            title = self._clean_text(article.get('title', ''))
            
            # Extract publication date
            pub_date = self._parse_date(article.get('published_date'))
            
            # Generate content hash for deduplication
            content = article.get('content', '')
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # Extract source domain
            url = article.get('url', '')
            domain = self._extract_domain(url)
            
            # Calculate content metrics
            word_count = len(content.split())
            char_count = len(content)
            
            # Estimate reading time (average 200 words per minute)
            reading_time = max(1, round(word_count / 200))
            
            return {
                'title': title,
                'url': url,
                'domain': domain,
                'published_date': pub_date,
                'content_hash': content_hash,
                'word_count': word_count,
                'char_count': char_count,
                'reading_time': reading_time,
                'processing_status': 'metadata_extracted'
            }
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}
    
    def clean_article_content(self, content: str) -> str:
        """Clean and normalize article content for ML processing"""
        try:
            if not content:
                return ""
            
            # Remove HTML tags
            content = re.sub(r'<[^>]+>', '', content)
            
            # Remove extra whitespace
            content = re.sub(r'\s+', ' ', content)
            
            # Remove special characters but keep punctuation
            content = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}]', '', content)
            
            # Normalize quotes and dashes
            content = content.replace('"', '"').replace('"', '"')
            content = content.replace('–', '-').replace('—', '-')
            
            # Remove multiple periods
            content = re.sub(r'\.{2,}', '.', content)
            
            # Strip leading/trailing whitespace
            content = content.strip()
            
            return content
        except Exception as e:
            logger.error(f"Error cleaning content: {e}")
            return content
    
    def segment_content(self, content: str) -> List[str]:
        """Segment content into logical chunks for ML processing"""
        try:
            if not content:
                return []
            
            # Split by sentences (basic approach)
            sentences = re.split(r'[.!?]+', content)
            
            # Clean and filter sentences
            segments = []
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 10:  # Minimum meaningful length
                    segments.append(sentence)
            
            # If no good segments, split by paragraphs
            if not segments:
                paragraphs = content.split('\n\n')
                segments = [p.strip() for p in paragraphs if len(p.strip()) > 20]
            
            return segments
        except Exception as e:
            logger.error(f"Error segmenting content: {e}")
            return [content]
    
    def extract_key_phrases(self, content: str) -> List[str]:
        """Extract key phrases for topic identification"""
        try:
            if not content:
                return []
            
            # Simple key phrase extraction (can be enhanced with NLP)
            words = content.lower().split()
            
            # Filter out common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            filtered_words = [word for word in words if word not in stop_words and len(word) > 3]
            
            # Count word frequency
            word_freq = {}
            for word in filtered_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top phrases (simple approach)
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            key_phrases = [word for word, freq in sorted_words[:20] if freq > 1]
            
            return key_phrases
        except Exception as e:
            logger.error(f"Error extracting key phrases: {e}")
            return []
    
    def calculate_content_quality_score(self, article: Dict) -> float:
        """Calculate content quality score for ML prioritization"""
        try:
            score = 0.0
            
            # Content length score (0-30 points)
            content = article.get('content', '')
            word_count = len(content.split())
            if word_count > 500:
                score += 30
            elif word_count > 200:
                score += 20
            elif word_count > 100:
                score += 10
            
            # Title quality score (0-20 points)
            title = article.get('title', '')
            if len(title) > 20 and len(title) < 100:
                score += 20
            elif len(title) > 10:
                score += 10
            
            # URL quality score (0-15 points)
            url = article.get('url', '')
            if url and 'http' in url:
                score += 15
            
            # Date recency score (0-20 points)
            pub_date = article.get('published_date')
            if pub_date:
                try:
                    if isinstance(pub_date, str):
                        pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    
                    days_old = (datetime.now() - pub_date).days
                    if days_old <= 1:
                        score += 20
                    elif days_old <= 7:
                        score += 15
                    elif days_old <= 30:
                        score += 10
                except:
                    pass
            
            # Content structure score (0-15 points)
            if '\n\n' in content:  # Has paragraphs
                score += 15
            elif '\n' in content:  # Has line breaks
                score += 10
            
            return min(100.0, score)
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 0.0
    
    def process_article_for_ml(self, article_id: int) -> Dict:
        """Process a single article for ML consumption"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return {}
            
            # Fetch article
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM articles WHERE id = %s
                """, (article_id,))
                article = cursor.fetchone()
                
                if not article:
                    logger.warning(f"Article {article_id} not found")
                    return {}
            
            # Extract metadata
            metadata = self.extract_article_metadata(article)
            
            # Clean content
            cleaned_content = self.clean_article_content(article.get('content', ''))
            
            # Segment content
            segments = self.segment_content(cleaned_content)
            
            # Extract key phrases
            key_phrases = self.extract_key_phrases(cleaned_content)
            
            # Calculate quality score
            quality_score = self.calculate_content_quality_score(article)
            
            # Prepare ML-ready data
            ml_data = {
                'article_id': article_id,
                'metadata': metadata,
                'cleaned_content': cleaned_content,
                'segments': segments,
                'key_phrases': key_phrases,
                'quality_score': quality_score,
                'processing_timestamp': datetime.now().isoformat(),
                'ml_ready': True
            }
            
            # Update article processing status
            self._update_processing_status(article_id, 'ml_processed', ml_data)
            
            return ml_data
            
        except Exception as e:
            logger.error(f"Error processing article {article_id} for ML: {e}")
            self._update_processing_status(article_id, 'processing_error', {'error': str(e)})
            return {}
    
    def batch_process_articles(self, limit: int = 100) -> List[Dict]:
        """Process multiple articles in batch"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return []
            
            # Get unprocessed articles
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id FROM articles 
                    WHERE processing_status IS NULL 
                    OR processing_status NOT IN ('ml_processed', 'processing_error')
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (limit,))
                
                article_ids = [row['id'] for row in cursor.fetchall()]
            
            # Process each article
            processed_articles = []
            for article_id in article_ids:
                try:
                    ml_data = self.process_article_for_ml(article_id)
                    if ml_data:
                        processed_articles.append(ml_data)
                        logger.info(f"Processed article {article_id} for ML")
                except Exception as e:
                    logger.error(f"Failed to process article {article_id}: {e}")
                    continue
            
            logger.info(f"Batch processing completed: {len(processed_articles)} articles processed")
            return processed_articles
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            return []
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove HTML entities
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        return text.strip()
    
    def _parse_date(self, date_input) -> Optional[datetime]:
        """Parse various date formats"""
        try:
            if isinstance(date_input, datetime):
                return date_input
            
            if isinstance(date_input, str):
                # Try common date formats
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%dT%H:%M:%SZ',
                    '%Y-%m-%d',
                    '%m/%d/%Y',
                    '%d/%m/%Y'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(date_input, fmt)
                    except ValueError:
                        continue
            
            return None
        except Exception:
            return None
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            if not url:
                return ""
            
            # Simple domain extraction
            if '://' in url:
                domain = url.split('://')[1]
            else:
                domain = url
            
            if '/' in domain:
                domain = domain.split('/')[0]
            
            return domain.lower()
        except Exception:
            return ""
    
    def _update_processing_status(self, article_id: int, status: str, data: Dict = None):
        """Update article processing status"""
        try:
            with self.connection.cursor() as cursor:
                if data:
                    cursor.execute("""
                        UPDATE articles 
                        SET processing_status = %s, 
                            ml_data = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (status, json.dumps(data), article_id))
                else:
                    cursor.execute("""
                        UPDATE articles 
                        SET processing_status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (status, article_id))
                
                self.connection.commit()
        except Exception as e:
            logger.error(f"Error updating processing status: {e}")
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
