#!/usr/bin/env python3
"""
Deduplication Manager
High-level interface for managing deduplication operations
"""

import logging
import psycopg2
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time

from .deduplication_engine import DeduplicationEngine
from .content_normalizer import ContentNormalizer

logger = logging.getLogger(__name__)

class DeduplicationManager:
    """Manages deduplication operations and integration with RSS collector"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize deduplication manager
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.engine = DeduplicationEngine(db_config)
        self.normalizer = ContentNormalizer()
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'duplicates_found': 0,
            'unique_articles': 0,
            'processing_time': 0.0,
            'last_run': None
        }
    
    def process_new_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a new article for deduplication before storage
        
        Args:
            article_data: Article data from RSS feed
            
        Returns:
            Dictionary with deduplication results and processed data
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Processing new article for deduplication: {article_data.get('title', 'Unknown')}")
            
            # Step 1: Check for duplicates
            duplicate_status = self.engine.check_duplicates(article_data)
            
            # Step 2: Prepare processed data
            if duplicate_status['is_duplicate']:
                # Article is a duplicate
                processed_data = {
                    'should_store': False,
                    'duplicate_status': duplicate_status,
                    'reason': f"Duplicate detected: {duplicate_status['reason']}",
                    'processing_time': time.time() - start_time
                }
                
                self.stats['duplicates_found'] += 1
                
            else:
                # Article is unique, prepare for storage
                cleaned_content, normalized_content, content_hash = self.normalizer.normalize_content(
                    article_data.get('content', ''),
                    article_data.get('title', '')
                )
                
                # Add deduplication metadata
                article_data.update({
                    'cleaned_content': cleaned_content,
                    'normalized_content': normalized_content,
                    'content_hash': content_hash,
                    'deduplication_status': 'unique'
                })
                
                processed_data = {
                    'should_store': True,
                    'article_data': article_data,
                    'duplicate_status': duplicate_status,
                    'processing_time': time.time() - start_time
                }
                
                self.stats['unique_articles'] += 1
            
            self.stats['total_processed'] += 1
            self.stats['processing_time'] += processed_data['processing_time']
            self.stats['last_run'] = datetime.now()
            
            self.logger.info(f"Article processed: {'Duplicate' if duplicate_status['is_duplicate'] else 'Unique'} "
                           f"({processed_data['processing_time']:.3f}s)")
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Error processing article for deduplication: {e}")
            return {
                'should_store': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def process_existing_articles(self, batch_size: int = 50, 
                                 max_articles: Optional[int] = None) -> Dict[str, Any]:
        """
        Process existing articles for deduplication
        
        Args:
            batch_size: Number of articles to process per batch
            max_articles: Maximum total articles to process (None for all)
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting deduplication of existing articles (batch_size={batch_size})")
            
            # Get articles that need deduplication
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM articles 
                WHERE deduplication_status = 'pending' 
                   OR deduplication_status IS NULL
                ORDER BY created_at ASC
            """)
            
            article_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if max_articles:
                article_ids = article_ids[:max_articles]
            
            total_articles = len(article_ids)
            self.logger.info(f"Found {total_articles} articles to process")
            
            if total_articles == 0:
                return {
                    'total_articles': 0,
                    'batches_processed': 0,
                    'total_processing_time': 0.0,
                    'message': 'No articles need deduplication'
                }
            
            # Process in batches
            results = {
                'total_articles': total_articles,
                'batches_processed': 0,
                'total_processing_time': 0.0,
                'total_duplicates_found': 0,
                'total_unique_articles': 0,
                'total_errors': 0,
                'batch_results': []
            }
            
            for i in range(0, total_articles, batch_size):
                batch_ids = article_ids[i:i + batch_size]
                batch_start = time.time()
                
                self.logger.info(f"Processing batch {i//batch_size + 1}: articles {i+1}-{min(i+batch_size, total_articles)}")
                
                # Process batch
                batch_result = self.engine.process_batch_deduplication(batch_ids)
                batch_result['batch_number'] = i//batch_size + 1
                batch_result['processing_time'] = time.time() - batch_start
                
                results['batch_results'].append(batch_result)
                results['total_duplicates_found'] += batch_result['duplicates_found']
                results['total_unique_articles'] += batch_result['unique_articles']
                results['total_errors'] += batch_result['errors']
                results['batches_processed'] += 1
                
                self.logger.info(f"Batch {i//batch_size + 1} completed: "
                               f"{batch_result['duplicates_found']} duplicates, "
                               f"{batch_result['unique_articles']} unique, "
                               f"{batch_result['processing_time']:.3f}s")
            
            results['total_processing_time'] = time.time() - start_time
            
            self.logger.info(f"Deduplication completed: {results['total_duplicates_found']} duplicates, "
                           f"{results['total_unique_articles']} unique, "
                           f"{results['total_processing_time']:.3f}s total")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing existing articles: {e}")
            return {
                'error': str(e),
                'total_processing_time': time.time() - start_time
            }
    
    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get article counts by deduplication status
            cursor.execute("""
                SELECT deduplication_status, COUNT(*) 
                FROM articles 
                GROUP BY deduplication_status
            """)
            
            status_counts = dict(cursor.fetchall())
            
            # Get duplicate detection log summary
            cursor.execute("""
                SELECT detection_method, COUNT(*) 
                FROM duplicate_detection_log 
                GROUP BY detection_method
            """)
            
            method_counts = dict(cursor.fetchall())
            
            # Get recent duplicate detections
            cursor.execute("""
                SELECT dd.detection_method, dd.similarity_score, dd.reason,
                       a1.title as article_title, a2.title as duplicate_of_title,
                       dd.created_at
                FROM duplicate_detection_log dd
                JOIN articles a1 ON dd.article_id = a1.id
                JOIN articles a2 ON dd.duplicate_of_id = a2.id
                ORDER BY dd.created_at DESC
                LIMIT 10
            """)
            
            recent_duplicates = []
            for row in cursor.fetchall():
                recent_duplicates.append({
                    'detection_method': row[0],
                    'similarity_score': float(row[1]) if row[1] else 0.0,
                    'reason': row[2],
                    'article_title': row[3],
                    'duplicate_of_title': row[4],
                    'detected_at': row[5].isoformat() if row[5] else None
                })
            
            conn.close()
            
            stats = {
                'status_counts': status_counts,
                'method_counts': method_counts,
                'recent_duplicates': recent_duplicates,
                'manager_stats': self.stats,
                'total_articles': sum(status_counts.values()) if status_counts else 0,
                'duplicates_detected': status_counts.get('duplicate_detected', 0),
                'unique_articles': status_counts.get('unique', 0),
                'pending_processing': status_counts.get('pending', 0)
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting deduplication stats: {e}")
            return {'error': str(e)}
    
    def cleanup_duplicate_groups(self) -> Dict[str, Any]:
        """Clean up orphaned duplicate groups"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Call the cleanup function
            cursor.execute("SELECT cleanup_orphaned_duplicate_groups()")
            deleted_count = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted_count} orphaned duplicate groups")
            
            return {
                'orphaned_groups_removed': deleted_count,
                'status': 'success'
            }
            
        except Exception as e:
            self.logger.error(f"Error cleaning up duplicate groups: {e}")
            return {'error': str(e)}
    
    def reset_deduplication_status(self, article_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Reset deduplication status for articles
        
        Args:
            article_ids: List of article IDs to reset (None for all)
            
        Returns:
            Dictionary with reset results
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            if article_ids:
                # Reset specific articles
                placeholders = ','.join(['%s'] * len(article_ids))
                cursor.execute(f"""
                    UPDATE articles 
                    SET deduplication_status = 'pending',
                        duplicate_of = NULL,
                        is_duplicate = FALSE,
                        content_similarity_score = NULL
                    WHERE id IN ({placeholders})
                """, article_ids)
                
                reset_count = cursor.rowcount
                self.logger.info(f"Reset deduplication status for {reset_count} specific articles")
                
            else:
                # Reset all articles
                cursor.execute("""
                    UPDATE articles 
                    SET deduplication_status = 'pending',
                        duplicate_of = NULL,
                        is_duplicate = FALSE,
                        content_similarity_score = NULL
                """)
                
                reset_count = cursor.rowcount
                self.logger.info(f"Reset deduplication status for all {reset_count} articles")
            
            conn.commit()
            conn.close()
            
            return {
                'articles_reset': reset_count,
                'status': 'success'
            }
            
        except Exception as e:
            self.logger.error(f"Error resetting deduplication status: {e}")
            return {'error': str(e)}
    
    def get_duplicate_analysis(self, article_id: int) -> Dict[str, Any]:
        """
        Get detailed duplicate analysis for a specific article
        
        Args:
            article_id: ID of the article to analyze
            
        Returns:
            Dictionary with duplicate analysis
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get article details
            cursor.execute("""
                SELECT title, content, source, published_date, deduplication_status,
                       duplicate_of, content_similarity_score, normalized_content
                FROM articles 
                WHERE id = %s
            """, (article_id,))
            
            article = cursor.fetchone()
            if not article:
                return {'error': 'Article not found'}
            
            # Get duplicate detection logs
            cursor.execute("""
                SELECT detection_method, similarity_score, reason, created_at
                FROM duplicate_detection_log 
                WHERE article_id = %s
                ORDER BY created_at DESC
            """, (article_id,))
            
            detection_logs = []
            for row in cursor.fetchall():
                detection_logs.append({
                    'method': row[0],
                    'similarity_score': float(row[1]) if row[1] else 0.0,
                    'reason': row[2],
                    'detected_at': row[3].isoformat() if row[3] else None
                })
            
            # Get similar articles if this is unique
            similar_articles = []
            if article[4] == 'unique' and article[7]:  # normalized_content exists
                cursor.execute("""
                    SELECT id, title, source, published_date
                    FROM articles 
                    WHERE id != %s 
                    AND normalized_content IS NOT NULL
                    AND normalized_content != ''
                    ORDER BY published_date DESC
                    LIMIT 5
                """, (article_id,))
                
                for row in cursor.fetchall():
                    # Calculate similarity
                    similarity = self.engine._calculate_similarity(
                        article[7],  # normalized_content
                        '',  # We'd need to get this from DB
                        article[0],  # title
                        row[1]  # similar article title
                    )
                    
                    if similarity > 0.5:  # Only show reasonably similar articles
                        similar_articles.append({
                            'id': row[0],
                            'title': row[1],
                            'source': row[2],
                            'published_date': row[3].isoformat() if row[3] else None,
                            'similarity_score': similarity
                        })
            
            conn.close()
            
            analysis = {
                'article_id': article_id,
                'title': article[0],
                'source': article[2],
                'published_date': article[3].isoformat() if article[3] else None,
                'deduplication_status': article[4],
                'duplicate_of_id': article[5],
                'content_similarity_score': float(article[6]) if article[6] else None,
                'detection_logs': detection_logs,
                'similar_articles': similar_articles,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing article {article_id}: {e}")
            return {'error': str(e)}
