"""
Domain-Aware Article Service for v4.0
Handles article operations within a specific domain schema
"""

from typing import List, Optional, Dict, Any
from psycopg2.extras import RealDictCursor
import logging
from shared.services.domain_aware_service import DomainAwareService

logger = logging.getLogger(__name__)


class ArticleService(DomainAwareService):
    """
    Article service that works for any domain.
    All queries are automatically scoped to the domain schema.
    """
    
    def __init__(self, domain: str = 'politics'):
        """
        Initialize article service with domain context.
        
        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        super().__init__(domain)
    
    def get_articles(
        self, 
        limit: int = 50, 
        offset: int = 0, 
        filters: Optional[Dict[str, Any]] = None,
        include_content: bool = False
    ) -> Dict[str, Any]:
        """
        Get articles from current domain.
        
        Args:
            limit: Maximum number of articles to return
            offset: Number of articles to skip
            filters: Optional filters (source_domain, category, processing_status, etc.)
            include_content: If False (default), excludes full content for faster loading
        
        Returns:
            Dictionary with articles and metadata
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # OPTIMIZED: Only select lightweight fields for listings
                # Full content is loaded only when viewing article details
                if include_content:
                    select_fields = """
                        id, title, content, url,
                        published_at, source_domain, category,
                        language_code, feed_id, content_hash,
                        processing_status, created_at, updated_at,
                        summary, quality_score, sentiment_label, sentiment_score
                    """
                else:
                    # Lightweight query - excludes large content field
                    select_fields = """
                        id, title, 
                        LEFT(summary, 200) as summary,
                        url, published_at, source_domain, category,
                        processing_status, created_at,
                        quality_score, sentiment_label
                    """
                
                query = f"""
                    SELECT {select_fields}
                    FROM {self.schema}.articles
                    WHERE 1=1
                """
                params = []
                
                # Add filters
                if filters:
                    if filters.get('source_domain'):
                        query += " AND source_domain = %s"
                        params.append(filters['source_domain'])
                    
                    if filters.get('category'):
                        query += " AND category = %s"
                        params.append(filters['category'])
                    
                    if filters.get('processing_status'):
                        query += " AND processing_status = %s"
                        params.append(filters['processing_status'])
                    
                    if filters.get('published_after'):
                        query += " AND published_at >= %s"
                        params.append(filters['published_after'])
                    
                    if filters.get('published_before'):
                        query += " AND published_at <= %s"
                        params.append(filters['published_before'])
                
                # Get total count (before adding LIMIT/OFFSET)
                count_query = f"""
                    SELECT COUNT(*) 
                    FROM {self.schema}.articles
                    WHERE 1=1
                """
                count_params = []
                
                # Add same filters to count query
                if filters:
                    if filters.get('source_domain'):
                        count_query += " AND source_domain = %s"
                        count_params.append(filters['source_domain'])
                    
                    if filters.get('category'):
                        count_query += " AND category = %s"
                        count_params.append(filters['category'])
                    
                    if filters.get('processing_status'):
                        count_query += " AND processing_status = %s"
                        count_params.append(filters['processing_status'])
                    
                    if filters.get('published_after'):
                        count_query += " AND published_at >= %s"
                        count_params.append(filters['published_after'])
                    
                    if filters.get('published_before'):
                        count_query += " AND published_at <= %s"
                        count_params.append(filters['published_before'])
                
                cur.execute(count_query, count_params)
                total_result = cur.fetchone()
                total = total_result['count'] if isinstance(total_result, dict) else total_result[0]
                
                # Add ordering and pagination
                query += " ORDER BY published_at DESC NULLS LAST, created_at DESC"
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                articles = cur.fetchall()
                
                return {
                    'success': True,
                    'data': {
                        'articles': [dict(article) for article in articles],
                        'domain': self.domain,
                        'count': len(articles),
                        'total': total,
                        'limit': limit,
                        'offset': offset
                    }
                }
        except Exception as e:
            logger.error(f"Error getting articles for domain {self.domain}: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single article by ID from current domain.
        
        Args:
            article_id: Article ID
        
        Returns:
            Article dictionary or None if not found
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT 
                        id, title, content, url,
                        published_at, source_domain, category,
                        language_code, feed_id, content_hash,
                        processing_status, created_at, updated_at,
                        summary, quality_score, sentiment_label, sentiment_score
                    FROM {self.schema}.articles
                    WHERE id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                if article:
                    return dict(article)
                return None
        except Exception as e:
            logger.error(f"Error getting article {article_id} from domain {self.domain}: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def create_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create article in current domain.
        
        Args:
            article_data: Dictionary with article fields
        
        Returns:
            Created article dictionary
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build INSERT query
                columns = list(article_data.keys())
                placeholders = ', '.join(['%s'] * len(columns))
                column_names = ', '.join(columns)
                values = [article_data[col] for col in columns]
                
                cur.execute(f"""
                    INSERT INTO {self.schema}.articles ({column_names})
                    VALUES ({placeholders})
                    RETURNING id, title, created_at
                """, values)
                
                result = cur.fetchone()
                conn.commit()
                
                return {
                    'success': True,
                    'data': dict(result),
                    'domain': self.domain
                }
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating article in domain {self.domain}: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def get_recent_articles(self, hours: Optional[int] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Get recent articles from current domain.
        
        Args:
            hours: Number of hours to look back (None = all articles)
            limit: Maximum number of articles to return
        
        Returns:
            Dictionary with recent articles
        """
        filters = {}
        if hours:
            from datetime import datetime, timedelta
            filters['published_after'] = datetime.now() - timedelta(hours=hours)
        
        return self.get_articles(limit=limit, offset=0, filters=filters)
    
    def get_article_count(self) -> int:
        """
        Get total article count for current domain.
        
        Returns:
            Total number of articles
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.schema}.articles")
                return cur.fetchone()[0]
        finally:
            conn.close()

