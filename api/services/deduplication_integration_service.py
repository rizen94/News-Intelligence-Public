"""
Deduplication Integration Service
Integrates advanced deduplication with the article processing pipeline
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection

from modules.deduplication.advanced_deduplication_service import (
    AdvancedDeduplicationService,
    ArticleMetadata,
    DuplicateResult,
    ClusterResult
)

logger = logging.getLogger(__name__)

class DeduplicationIntegrationService:
    """
    Service that integrates deduplication with the article processing pipeline
    """
    
    def __init__(self, db_config: Dict):
        """Initialize the integration service"""
        self.db_config = db_config
        self.deduplication_service = AdvancedDeduplicationService(db_config)
        
        # Configuration
        self.config = {
            'enable_same_source_dedup': True,
            'enable_cross_source_dedup': True,
            'enable_clustering': True,
            'enable_storyline_suggestions': True,
            'batch_size': 50,
            'max_processing_time_minutes': 30,
        }
    
    async def process_new_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a new article through the deduplication pipeline
        
        Args:
            article_data: Article data from RSS processing
            
        Returns:
            Dictionary with processing results and recommendations
        """
        start_time = datetime.now()
        
        try:
            # Create ArticleMetadata object
            article_meta = ArticleMetadata(
                id=0,  # Will be set after insertion
                title=article_data.get('title', ''),
                content=article_data.get('cleaned_content', ''),
                url=article_data.get('url', ''),
                source=article_data.get('source', ''),
                published_at=article_data.get('published_at'),
                author=article_data.get('author'),
                word_count=article_data.get('word_count', 0)
            )
            
            # Generate content hash
            article_meta.content_hash = self.deduplication_service.generate_content_hash(
                article_meta.content, article_meta.title
            )
            
            # Step 1: Check same-source duplicates
            same_source_result = None
            if self.config['enable_same_source_dedup']:
                same_source_result = self.deduplication_service.check_same_source_duplicates(article_meta)
                
                if same_source_result.is_duplicate:
                    logger.info(f"Same-source duplicate found: {article_meta.title}")
                    return {
                        'status': 'duplicate',
                        'duplicate_type': 'same_source',
                        'similarity_score': same_source_result.similarity_score,
                        'matched_article_id': same_source_result.matched_article_id,
                        'confidence': same_source_result.confidence,
                        'reasons': same_source_result.reasons,
                        'recommendation': 'Skip processing - exact duplicate from same source'
                    }
            
            # Step 2: Check cross-source duplicates
            cross_source_result = None
            if self.config['enable_cross_source_dedup']:
                cross_source_result = self.deduplication_service.check_cross_source_duplicates(article_meta)
                
                if cross_source_result.is_duplicate:
                    logger.info(f"Cross-source duplicate found: {article_meta.title}")
                    return {
                        'status': 'duplicate',
                        'duplicate_type': 'cross_source',
                        'similarity_score': cross_source_result.similarity_score,
                        'matched_article_id': cross_source_result.matched_article_id,
                        'confidence': cross_source_result.confidence,
                        'reasons': cross_source_result.reasons,
                        'recommendation': 'Consider merging with existing article or skip processing'
                    }
            
            # Step 3: Find storyline candidates
            storyline_candidates = []
            if self.config['enable_storyline_suggestions']:
                storyline_candidates = self.deduplication_service.find_storyline_candidates(article_meta)
            
            # Step 4: Prepare for database insertion
            article_data['content_hash'] = article_meta.content_hash
            article_data['deduplication_status'] = 'processed'
            
            if same_source_result:
                article_data['similarity_score'] = same_source_result.similarity_score
            elif cross_source_result:
                article_data['similarity_score'] = cross_source_result.similarity_score
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log the deduplication operation
            await self._log_deduplication_operation(
                operation_type='new_article_processing',
                article_id=None,  # Will be set after insertion
                articles_processed=1,
                duplicates_found=1 if (same_source_result and same_source_result.is_duplicate) or 
                                   (cross_source_result and cross_source_result.is_duplicate) else 0,
                clusters_created=len(storyline_candidates),
                processing_time_ms=int(processing_time),
                status='completed'
            )
            
            return {
                'status': 'unique',
                'article_data': article_data,
                'same_source_result': same_source_result,
                'cross_source_result': cross_source_result,
                'storyline_candidates': [
                    {
                        'cluster_id': cluster.cluster_id,
                        'centroid_title': cluster.centroid_title,
                        'cluster_size': cluster.cluster_size,
                        'storyline_suggestion': cluster.storyline_suggestion,
                        'similarity_threshold': cluster.similarity_threshold
                    }
                    for cluster in storyline_candidates
                ],
                'recommendation': 'Process article - appears to be unique content',
                'processing_time_ms': processing_time
            }
            
        except Exception as e:
            logger.error(f"Error processing article for deduplication: {e}")
            
            # Log the error
            await self._log_deduplication_operation(
                operation_type='new_article_processing',
                article_id=None,
                articles_processed=1,
                duplicates_found=0,
                clusters_created=0,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                status='failed',
                error_message=str(e)
            )
            
            return {
                'status': 'error',
                'error': str(e),
                'recommendation': 'Manual review required - deduplication failed'
            }
    
    async def batch_process_articles(self, article_ids: List[int]) -> Dict[str, Any]:
        """
        Process multiple articles for clustering and storyline suggestions
        
        Args:
            article_ids: List of article IDs to process
            
        Returns:
            Dictionary with clustering results
        """
        start_time = datetime.now()
        
        try:
            # Get articles from database
            articles = await self._get_articles_by_ids(article_ids)
            
            if len(articles) < 2:
                return {
                    'status': 'insufficient_articles',
                    'message': 'Need at least 2 articles for clustering',
                    'articles_processed': len(articles)
                }
            
            # Perform clustering
            clusters = self.deduplication_service.cluster_similar_articles(articles)
            
            # Store clustering results in database
            stored_clusters = await self._store_clustering_results(clusters)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log the operation
            await self._log_deduplication_operation(
                operation_type='batch_clustering',
                article_id=None,
                articles_processed=len(articles),
                duplicates_found=0,
                clusters_created=len(stored_clusters),
                processing_time_ms=int(processing_time),
                status='completed'
            )
            
            return {
                'status': 'completed',
                'articles_processed': len(articles),
                'clusters_created': len(stored_clusters),
                'clusters': [
                    {
                        'cluster_id': cluster.cluster_id,
                        'centroid_title': cluster.centroid_title,
                        'cluster_size': cluster.cluster_size,
                        'storyline_suggestion': cluster.storyline_suggestion,
                        'articles': [
                            {
                                'id': article.id,
                                'title': article.title,
                                'source': article.source
                            }
                            for article in cluster.articles
                        ]
                    }
                    for cluster in stored_clusters
                ],
                'processing_time_ms': processing_time
            }
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            
            await self._log_deduplication_operation(
                operation_type='batch_clustering',
                article_id=None,
                articles_processed=len(article_ids),
                duplicates_found=0,
                clusters_created=0,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                status='failed',
                error_message=str(e)
            )
            
            return {
                'status': 'error',
                'error': str(e),
                'articles_processed': len(article_ids)
            }
    
    async def find_duplicates_for_article(self, article_id: int) -> Dict[str, Any]:
        """
        Find all duplicates for a specific article
        
        Args:
            article_id: ID of the article to check
            
        Returns:
            Dictionary with duplicate information
        """
        try:
            # Get article from database
            article = await self._get_article_by_id(article_id)
            if not article:
                return {'status': 'error', 'message': 'Article not found'}
            
            # Check for duplicates
            same_source_result = self.deduplication_service.check_same_source_duplicates(article)
            cross_source_result = self.deduplication_service.check_cross_source_duplicates(article)
            
            # Get existing duplicate pairs from database
            existing_duplicates = await self._get_existing_duplicates(article_id)
            
            return {
                'status': 'completed',
                'article_id': article_id,
                'article_title': article.title,
                'same_source_duplicates': {
                    'is_duplicate': same_source_result.is_duplicate,
                    'similarity_score': same_source_result.similarity_score,
                    'matched_article_id': same_source_result.matched_article_id,
                    'reasons': same_source_result.reasons
                },
                'cross_source_duplicates': {
                    'is_duplicate': cross_source_result.is_duplicate,
                    'similarity_score': cross_source_result.similarity_score,
                    'matched_article_id': cross_source_result.matched_article_id,
                    'reasons': cross_source_result.reasons
                },
                'existing_duplicates': existing_duplicates
            }
            
        except Exception as e:
            logger.error(f"Error finding duplicates for article {article_id}: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_storyline_suggestions(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get storyline suggestions from recent clusters
        
        Args:
            limit: Maximum number of suggestions to return
            
        Returns:
            Dictionary with storyline suggestions
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get recent clusters with storyline suggestions
            cursor.execute("""
                SELECT 
                    cm.cluster_id,
                    cm.centroid_title,
                    cm.storyline_suggestion,
                    cm.cluster_size,
                    cm.similarity_threshold,
                    cm.created_at,
                    COUNT(ac.article_id) as actual_articles,
                    ARRAY_AGG(DISTINCT a.source_domain) as sources,
                    ARRAY_AGG(DISTINCT a.title ORDER BY a.created_at DESC) as article_titles
                FROM cluster_metadata cm
                LEFT JOIN article_clusters ac ON cm.cluster_id = ac.cluster_id
                LEFT JOIN articles a ON ac.article_id = a.id
                WHERE cm.storyline_suggestion IS NOT NULL
                AND cm.created_at > %s
                GROUP BY cm.cluster_id, cm.centroid_title, cm.storyline_suggestion, 
                         cm.cluster_size, cm.similarity_threshold, cm.created_at
                ORDER BY cm.cluster_size DESC, cm.created_at DESC
                LIMIT %s
            """, (datetime.now() - timedelta(days=7), limit))
            
            clusters = cursor.fetchall()
            conn.close()
            
            suggestions = []
            for cluster in clusters:
                suggestions.append({
                    'cluster_id': cluster['cluster_id'],
                    'storyline_suggestion': cluster['storyline_suggestion'],
                    'centroid_title': cluster['centroid_title'],
                    'cluster_size': cluster['cluster_size'],
                    'actual_articles': cluster['actual_articles'],
                    'sources': cluster['sources'],
                    'article_titles': cluster['article_titles'][:5],  # Limit to 5 titles
                    'similarity_threshold': cluster['similarity_threshold'],
                    'created_at': cluster['created_at'].isoformat()
                })
            
            return {
                'status': 'completed',
                'suggestions': suggestions,
                'total_suggestions': len(suggestions)
            }
            
        except Exception as e:
            logger.error(f"Error getting storyline suggestions: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def _get_articles_by_ids(self, article_ids: List[int]) -> List[ArticleMetadata]:
        """Get articles by IDs from database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            placeholders = ','.join(['%s'] * len(article_ids))
            cursor.execute(f"""
                SELECT id, title, content, url, source, published_at, author, content_hash, word_count
                FROM articles 
                WHERE id IN ({placeholders})
                AND LENGTH(content) > 100
            """, article_ids)
            
            rows = cursor.fetchall()
            conn.close()
            
            articles = []
            for row in rows:
                article = ArticleMetadata(
                    id=row['id'],
                    title=row['title'],
                    content=row['content'],
                    url=row['url'],
                    source=row['source'],
                    published_at=row['published_at'],
                    author=row['author'],
                    content_hash=row['content_hash'],
                    word_count=row['word_count']
                )
                articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"Error getting articles by IDs: {e}")
            return []
    
    async def _get_article_by_id(self, article_id: int) -> Optional[ArticleMetadata]:
        """Get single article by ID"""
        articles = await self._get_articles_by_ids([article_id])
        return articles[0] if articles else None
    
    async def _store_clustering_results(self, clusters: List[ClusterResult]) -> List[ClusterResult]:
        """Store clustering results in database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            stored_clusters = []
            
            for cluster in clusters:
                # Store cluster metadata
                cursor.execute("""
                    INSERT INTO cluster_metadata (
                        cluster_id, centroid_title, centroid_content, cluster_size,
                        similarity_threshold, storyline_suggestion
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cluster_id) DO UPDATE SET
                        centroid_title = EXCLUDED.centroid_title,
                        centroid_content = EXCLUDED.centroid_content,
                        cluster_size = EXCLUDED.cluster_size,
                        similarity_threshold = EXCLUDED.similarity_threshold,
                        storyline_suggestion = EXCLUDED.storyline_suggestion,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    cluster.cluster_id,
                    cluster.centroid_title,
                    cluster.centroid_content,
                    cluster.cluster_size,
                    cluster.similarity_threshold,
                    cluster.storyline_suggestion
                ))
                
                # Store article-cluster relationships
                for i, article in enumerate(cluster.articles):
                    cursor.execute("""
                        INSERT INTO article_clusters (
                            cluster_id, article_id, similarity_score, cluster_rank
                        ) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (cluster_id, article_id) DO UPDATE SET
                            similarity_score = EXCLUDED.similarity_score,
                            cluster_rank = EXCLUDED.cluster_rank
                    """, (
                        cluster.cluster_id,
                        article.id,
                        cluster.similarity_threshold,  # Use threshold as similarity score
                        i  # Rank within cluster
                    ))
                    
                    # Update article with cluster_id
                    cursor.execute("""
                        UPDATE articles 
                        SET cluster_id = %s
                        WHERE id = %s
                    """, (cluster.cluster_id, article.id))
                
                stored_clusters.append(cluster)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored {len(stored_clusters)} clusters in database")
            return stored_clusters
            
        except Exception as e:
            logger.error(f"Error storing clustering results: {e}")
            return []
    
    async def _get_existing_duplicates(self, article_id: int) -> List[Dict]:
        """Get existing duplicate pairs for an article"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    dp.id,
                    dp.article1_id,
                    dp.article2_id,
                    dp.similarity_score,
                    dp.duplicate_type,
                    dp.confidence_score,
                    dp.detection_method,
                    dp.detected_at,
                    a1.title as article1_title,
                    a1.source as article1_source,
                    a2.title as article2_title,
                    a2.source as article2_source
                FROM duplicate_pairs dp
                JOIN articles a1 ON dp.article1_id = a1.id
                JOIN articles a2 ON dp.article2_id = a2.id
                WHERE (dp.article1_id = %s OR dp.article2_id = %s)
                AND dp.status = 'active'
                ORDER BY dp.similarity_score DESC
            """, (article_id, article_id))
            
            duplicates = cursor.fetchall()
            conn.close()
            
            return [dict(dup) for dup in duplicates]
            
        except Exception as e:
            logger.error(f"Error getting existing duplicates: {e}")
            return []
    
    async def _log_deduplication_operation(self, operation_type: str, article_id: Optional[int],
                                        articles_processed: int, duplicates_found: int,
                                        clusters_created: int, processing_time_ms: int,
                                        status: str, error_message: str = None):
        """Log deduplication operation"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO deduplication_log (
                    operation_type, article_id, articles_processed, duplicates_found,
                    clusters_created, processing_time_ms, status, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                operation_type, article_id, articles_processed, duplicates_found,
                clusters_created, processing_time_ms, status, error_message
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging deduplication operation: {e}")
