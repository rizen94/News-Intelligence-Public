#!/usr/bin/env python3
"""
Advanced Deduplication Engine
Implements multi-layered deduplication strategy for news articles
"""

import logging
import psycopg2
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import hashlib
import re

from .content_normalizer import ContentNormalizer

logger = logging.getLogger(__name__)

class DeduplicationEngine:
    """Multi-layered deduplication engine for news articles"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize deduplication engine
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.normalizer = ContentNormalizer()
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = {
            'semantic_threshold': 0.85,
            'entity_threshold': 0.7,
            'batch_size': 50,
            'max_similar_articles': 10,
            'enable_semantic_check': True,
            'enable_entity_check': True,
            'log_duplicates': True
        }
        
        # Load configuration from database
        self._load_config()
    
    def _load_config(self):
        """Load deduplication configuration from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT key, value FROM system_config 
                WHERE key LIKE 'deduplication_%'
            """)
            
            for key, value in cursor.fetchall():
                config_key = key.replace('deduplication_', '')
                if config_key in self.config:
                    try:
                        if value.lower() in ('true', 'false'):
                            self.config[config_key] = value.lower() == 'true'
                        elif '.' in value:
                            self.config[config_key] = float(value)
                        else:
                            self.config[config_key] = int(value)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid config value for {key}: {value}")
            
            conn.close()
            
        except Exception as e:
            self.logger.warning(f"Could not load config from database: {e}")
    
    def check_duplicates(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for duplicates using multi-layered approach
        
        Args:
            article_data: Article data including content, title, url, source
            
        Returns:
            Dictionary with duplicate status and details
        """
        try:
            self.logger.info(f"Checking duplicates for article: {article_data.get('title', 'Unknown')}")
            
            # Step 1: Immediate deduplication checks (fast)
            immediate_result = self._check_immediate_duplicates(article_data)
            
            if immediate_result['is_duplicate']:
                return immediate_result
            
            # Step 2: Content normalization
            cleaned_content, normalized_content, content_hash = self.normalizer.normalize_content(
                article_data.get('content', ''),
                article_data.get('title', '')
            )
            
            # Step 3: Content hash deduplication
            hash_result = self._check_content_hash_duplicate(content_hash)
            if hash_result['is_duplicate']:
                return hash_result
            
            # Step 4: Intelligent deduplication (slower but more accurate)
            if self.config['enable_semantic_check']:
                intelligent_result = self._check_intelligent_duplicates(
                    normalized_content, 
                    article_data.get('title', ''),
                    article_data.get('source', '')
                )
                
                if intelligent_result['is_duplicate']:
                    return intelligent_result
            
            # No duplicates found
            result = {
                'is_duplicate': False,
                'duplicate_type': None,
                'duplicate_of_id': None,
                'similarity_score': 0.0,
                'detection_method': None,
                'content_hash': content_hash,
                'cleaned_content': cleaned_content,
                'normalized_content': normalized_content,
                'reason': 'Article is unique'
            }
            
            self.logger.info(f"Article is unique: {article_data.get('title', 'Unknown')}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking duplicates: {e}")
            return {
                'is_duplicate': False,
                'duplicate_type': 'error',
                'duplicate_of_id': None,
                'similarity_score': 0.0,
                'detection_method': 'error',
                'content_hash': '',
                'cleaned_content': article_data.get('content', ''),
                'normalized_content': '',
                'reason': f'Error during deduplication: {str(e)}'
            }
    
    def _check_immediate_duplicates(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for immediate duplicates (URL, exact title)"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Check URL duplicate
            if article_data.get('url'):
                cursor.execute("""
                    SELECT id, title, source, published_date 
                    FROM articles 
                    WHERE url = %s
                """, (article_data['url'],))
                
                url_duplicate = cursor.fetchone()
                if url_duplicate:
                    conn.close()
                    return {
                        'is_duplicate': True,
                        'duplicate_type': 'exact_url',
                        'duplicate_of_id': url_duplicate[0],
                        'similarity_score': 1.0,
                        'detection_method': 'url',
                        'content_hash': '',
                        'cleaned_content': '',
                        'normalized_content': '',
                        'reason': f'URL already exists: {url_duplicate[1]} from {url_duplicate[2]}'
                    }
            
            # Check exact title duplicate (case-insensitive)
            if article_data.get('title'):
                cursor.execute("""
                    SELECT id, title, source, published_date 
                    FROM articles 
                    WHERE LOWER(title) = LOWER(%s)
                    AND source != %s
                """, (article_data['title'], article_data.get('source', '')))
                
                title_duplicate = cursor.fetchone()
                if title_duplicate:
                    conn.close()
                    return {
                        'is_duplicate': True,
                        'duplicate_type': 'exact_title',
                        'duplicate_of_id': title_duplicate[0],
                        'similarity_score': 0.95,
                        'detection_method': 'title',
                        'content_hash': '',
                        'cleaned_content': '',
                        'normalized_content': '',
                        'reason': f'Title already exists: {title_duplicate[1]} from {title_duplicate[2]}'
                    }
            
            conn.close()
            return {'is_duplicate': False}
            
        except Exception as e:
            self.logger.error(f"Error in immediate duplicate check: {e}")
            return {'is_duplicate': False}
    
    def _check_content_hash_duplicate(self, content_hash: str) -> Dict[str, Any]:
        """Check for content hash duplicates"""
        if not content_hash:
            return {'is_duplicate': False}
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, source, published_date 
                FROM articles 
                WHERE content_hash = %s
            """, (content_hash,))
            
            hash_duplicate = cursor.fetchone()
            conn.close()
            
            if hash_duplicate:
                return {
                    'is_duplicate': True,
                    'duplicate_type': 'exact_content',
                    'duplicate_of_id': hash_duplicate[0],
                    'similarity_score': 1.0,
                    'detection_method': 'content_hash',
                    'content_hash': content_hash,
                    'cleaned_content': '',
                    'normalized_content': '',
                    'reason': f'Content already exists: {hash_duplicate[1]} from {hash_duplicate[2]}'
                }
            
            return {'is_duplicate': False}
            
        except Exception as e:
            self.logger.error(f"Error in content hash duplicate check: {e}")
            return {'is_duplicate': False}
    
    def _check_intelligent_duplicates(self, normalized_content: str, title: str, source: str) -> Dict[str, Any]:
        """Check for intelligent duplicates using semantic similarity and entity overlap"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get recent articles for comparison (last 30 days)
            cursor.execute("""
                SELECT id, title, normalized_content, source, published_date
                FROM articles 
                WHERE published_date >= NOW() - INTERVAL '30 days'
                AND normalized_content IS NOT NULL
                AND normalized_content != ''
                AND source != %s
                ORDER BY published_date DESC
                LIMIT %s
            """, (source, self.config['max_similar_articles']))
            
            recent_articles = cursor.fetchall()
            conn.close()
            
            if not recent_articles:
                return {'is_duplicate': False}
            
            # Check semantic similarity
            best_match = None
            best_score = 0.0
            
            for article_id, article_title, article_content, article_source, article_date in recent_articles:
                if not article_content:
                    continue
                
                # Calculate similarity score
                similarity_score = self._calculate_similarity(
                    normalized_content, 
                    article_content,
                    title,
                    article_title
                )
                
                if similarity_score > best_score and similarity_score >= self.config['semantic_threshold']:
                    best_score = similarity_score
                    best_match = {
                        'id': article_id,
                        'title': article_title,
                        'source': article_source,
                        'date': article_date,
                        'similarity': similarity_score
                    }
            
            if best_match:
                return {
                    'is_duplicate': True,
                    'duplicate_type': 'semantic_similarity',
                    'duplicate_of_id': best_match['id'],
                    'similarity_score': best_match['similarity'],
                    'detection_method': 'semantic',
                    'content_hash': '',
                    'cleaned_content': '',
                    'normalized_content': '',
                    'reason': f'Semantic similarity {best_match["similarity"]:.2f} with: {best_match["title"]} from {best_match["source"]}'
                }
            
            return {'is_duplicate': False}
            
        except Exception as e:
            self.logger.error(f"Error in intelligent duplicate check: {e}")
            return {'is_duplicate': False}
    
    def _calculate_similarity(self, content1: str, content2: str, title1: str, title2: str) -> float:
        """Calculate similarity between two pieces of content"""
        try:
            # Simple text similarity (can be enhanced with ML models later)
            if not content1 or not content2:
                return 0.0
            
            # Title similarity (weighted higher)
            title_similarity = self._calculate_text_similarity(title1, title2)
            
            # Content similarity
            content_similarity = self._calculate_text_similarity(content1, content2)
            
            # Weighted combination (title is more important)
            final_similarity = (title_similarity * 0.4) + (content_similarity * 0.6)
            
            return min(final_similarity, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate basic text similarity using word overlap"""
        try:
            if not text1 or not text2:
                return 0.0
            
            # Convert to sets of words
            words1 = set(re.findall(r'\w+', text1.lower()))
            words2 = set(re.findall(r'\w+', text2.lower()))
            
            if not words1 or not words2:
                return 0.0
            
            # Calculate Jaccard similarity
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            if union == 0:
                return 0.0
            
            similarity = intersection / union
            
            return similarity
            
        except Exception as e:
            self.logger.error(f"Error calculating text similarity: {e}")
            return 0.0
    
    def log_duplicate_detection(self, article_id: int, duplicate_of_id: int, 
                               detection_method: str, similarity_score: float, reason: str):
        """Log duplicate detection for audit trail"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO duplicate_detection_log 
                (article_id, duplicate_of_id, detection_method, similarity_score, reason)
                VALUES (%s, %s, %s, %s, %s)
            """, (article_id, duplicate_of_id, detection_method, similarity_score, reason))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error logging duplicate detection: {e}")
    
    def update_article_deduplication_status(self, article_id: int, duplicate_status: Dict[str, Any]):
        """Update article with deduplication results"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            if duplicate_status['is_duplicate']:
                cursor.execute("""
                    UPDATE articles 
                    SET duplicate_of = %s, is_duplicate = TRUE, 
                        deduplication_status = 'duplicate_detected',
                        content_similarity_score = %s
                    WHERE id = %s
                """, (duplicate_status['duplicate_of_id'], 
                      duplicate_status['similarity_score'], 
                      article_id))
            else:
                cursor.execute("""
                    UPDATE articles 
                    SET deduplication_status = 'unique',
                        content_hash = %s,
                        normalized_content = %s
                    WHERE id = %s
                """, (duplicate_status['content_hash'],
                      duplicate_status['normalized_content'],
                      article_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error updating article deduplication status: {e}")
    
    def process_batch_deduplication(self, article_ids: List[int]) -> Dict[str, Any]:
        """Process deduplication for a batch of articles"""
        results = {
            'total_processed': 0,
            'duplicates_found': 0,
            'unique_articles': 0,
            'errors': 0,
            'details': []
        }
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            for article_id in article_ids:
                try:
                    # Get article data
                    cursor.execute("""
                        SELECT title, content, url, source, published_date
                        FROM articles 
                        WHERE id = %s
                    """, (article_id,))
                    
                    article_data = cursor.fetchone()
                    if not article_data:
                        results['errors'] += 1
                        continue
                    
                    # Check for duplicates
                    duplicate_status = self.check_duplicates({
                        'title': article_data[0],
                        'content': article_data[1],
                        'url': article_data[2],
                        'source': article_data[3],
                        'published_date': article_data[4]
                    })
                    
                    # Update article status
                    self.update_article_deduplication_status(article_id, duplicate_status)
                    
                    # Log duplicate if found
                    if duplicate_status['is_duplicate']:
                        self.log_duplicate_detection(
                            article_id,
                            duplicate_status['duplicate_of_id'],
                            duplicate_status['detection_method'],
                            duplicate_status['similarity_score'],
                            duplicate_status['reason']
                        )
                        results['duplicates_found'] += 1
                    else:
                        results['unique_articles'] += 1
                    
                    results['total_processed'] += 1
                    results['details'].append({
                        'article_id': article_id,
                        'title': article_data[0],
                        'duplicate_status': duplicate_status
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error processing article {article_id}: {e}")
                    results['errors'] += 1
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error in batch deduplication: {e}")
            results['errors'] += 1
        
        return results
