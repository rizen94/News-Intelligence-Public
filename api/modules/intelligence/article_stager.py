#!/usr/bin/env python3
"""
Article Stager for News Intelligence System v2.5.0
Manages raw article staging and quality verification workflow
"""
import os
import sys
import logging
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StagedArticle:
    """Represents an article in the staging area."""
    id: Optional[int]
    title: str
    content: str
    url: str
    source: str
    published_date: Optional[datetime]
    collected_date: datetime
    content_hash: str
    url_hash: str
    stage: str  # 'raw', 'cleaning', 'validation', 'ready', 'failed'
    stage_timestamp: datetime
    processing_attempts: int
    last_error: Optional[str]
    metadata: Dict
    quality_score: Optional[float]
    language_detected: Optional[str]
    validation_status: Optional[str]

@dataclass
class StagingResult:
    """Result of staging operation."""
    article_id: int
    stage: str
    success: bool
    message: str
    timestamp: datetime
    next_stage: Optional[str]

class ArticleStager:
    """
    Comprehensive article staging system that:
    - Manages raw articles before processing
    - Tracks article progression through stages
    - Provides quality gates and validation
    - Manages failed articles and retries
    """
    
    def __init__(self, db_config: Dict = None):
        """Initialize the article stager."""
        self.db_config = db_config or {
            'host': 'postgres',
            'database': 'news_system',
            'user': 'newsapp',
            'password': 'newsapp123'
        }
        
        # Staging workflow configuration
        self.staging_workflow = {
            'raw': {
                'next_stage': 'cleaning',
                'max_retries': 3,
                'timeout_minutes': 30,
                'description': 'Raw article received'
            },
            'cleaning': {
                'next_stage': 'validation',
                'max_retries': 3,
                'timeout_minutes': 15,
                'description': 'Content cleaning in progress'
            },
            'validation': {
                'next_stage': 'ready',
                'max_retries': 2,
                'timeout_minutes': 10,
                'description': 'Quality validation in progress'
            },
            'ready': {
                'next_stage': None,
                'max_retries': 0,
                'timeout_minutes': 0,
                'description': 'Article ready for processing'
            },
            'failed': {
                'next_stage': 'raw',
                'max_retries': 5,
                'description': 'Article processing failed'
            }
        }
        
        # Initialize database connection
        self._init_database()
    
    def _init_database(self):
        """Initialize database connection and create staging table if needed."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self._create_staging_table()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.conn = None
    
    def _create_staging_table(self):
        """Create the staging table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS article_staging (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            url VARCHAR(500) UNIQUE NOT NULL,
            source VARCHAR(100) NOT NULL,
            published_date TIMESTAMP,
            collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_hash VARCHAR(64) NOT NULL,
            url_hash VARCHAR(64) NOT NULL,
            stage VARCHAR(20) DEFAULT 'raw',
            stage_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_attempts INTEGER DEFAULT 0,
            last_error TEXT,
            metadata JSONB DEFAULT '{}',
            quality_score DECIMAL(5,3),
            language_detected VARCHAR(10),
            validation_status VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_staging_stage ON article_staging(stage);
        CREATE INDEX IF NOT EXISTS idx_staging_content_hash ON article_staging(content_hash);
        CREATE INDEX IF NOT EXISTS idx_staging_url_hash ON article_staging(url_hash);
        CREATE INDEX IF NOT EXISTS idx_staging_collected_date ON article_staging(collected_date);
        CREATE INDEX IF NOT EXISTS idx_staging_quality_score ON article_staging(quality_score);
        """
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(create_table_sql)
            self.conn.commit()
            logger.info("Staging table created/verified")
        except Exception as e:
            logger.error(f"Failed to create staging table: {e}")
            self.conn.rollback()
    
    def stage_article(self, article_data: Dict) -> StagingResult:
        """
        Stage a new article in the raw stage.
        
        Args:
            article_data: Dictionary containing article information
            
        Returns:
            StagingResult with staging details
        """
        if not self.conn:
            return StagingResult(
                article_id=0,
                stage='failed',
                success=False,
                message='Database connection not available',
                timestamp=datetime.now(),
                next_stage=None
            )
        
        try:
            # Generate hashes
            content_hash = self._generate_content_hash(article_data.get('content', ''))
            url_hash = self._generate_url_hash(article_data.get('url', ''))
            
            # Check for duplicates
            if self._is_duplicate(content_hash, url_hash):
                return StagingResult(
                    article_id=0,
                    stage='failed',
                    success=False,
                    message='Duplicate article detected',
                    timestamp=datetime.now(),
                    next_stage=None
                )
            
            # Insert article into staging
            insert_sql = """
            INSERT INTO article_staging (
                title, content, url, source, published_date, content_hash, url_hash,
                stage, stage_timestamp, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            with self.conn.cursor() as cursor:
                cursor.execute(insert_sql, (
                    article_data.get('title', ''),
                    article_data.get('content', ''),
                    article_data.get('url', ''),
                    article_data.get('source', 'unknown'),
                    article_data.get('published_date'),
                    content_hash,
                    url_hash,
                    'raw',
                    datetime.now(),
                    json.dumps(article_data.get('metadata', {}))
                ))
                
                article_id = cursor.fetchone()[0]
            
            self.conn.commit()
            
            logger.info(f"Article staged successfully: ID {article_id}")
            
            return StagingResult(
                article_id=article_id,
                stage='raw',
                success=True,
                message='Article staged successfully',
                timestamp=datetime.now(),
                next_stage='cleaning'
            )
            
        except Exception as e:
            logger.error(f"Failed to stage article: {e}")
            self.conn.rollback()
            
            return StagingResult(
                article_id=0,
                stage='failed',
                success=False,
                message=f'Staging failed: {str(e)}',
                timestamp=datetime.now(),
                next_stage=None
            )
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _generate_url_hash(self, url: str) -> str:
        """Generate SHA-256 hash of URL."""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    def _is_duplicate(self, content_hash: str, url_hash: str) -> bool:
        """Check if article is duplicate based on hashes."""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM article_staging 
                    WHERE content_hash = %s OR url_hash = %s
                """, (content_hash, url_hash))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return False
    
    def get_articles_by_stage(self, stage: str, limit: int = 100) -> List[StagedArticle]:
        """Get articles by stage."""
        if not self.conn:
            return []
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM article_staging 
                    WHERE stage = %s 
                    ORDER BY stage_timestamp ASC 
                    LIMIT %s
                """, (stage, limit))
                
                rows = cursor.fetchall()
                articles = []
                
                for row in rows:
                    article = StagedArticle(
                        id=row['id'],
                        title=row['title'],
                        content=row['content'],
                        url=row['url'],
                        source=row['source'],
                        published_date=row['published_date'],
                        collected_date=row['collected_date'],
                        content_hash=row['content_hash'],
                        url_hash=row['url_hash'],
                        stage=row['stage'],
                        stage_timestamp=row['stage_timestamp'],
                        processing_attempts=row['processing_attempts'],
                        last_error=row['last_error'],
                        metadata=row['metadata'] or {},
                        quality_score=row['quality_score'],
                        language_detected=row['language_detected'],
                        validation_status=row['validation_status']
                    )
                    articles.append(article)
                
                return articles
                
        except Exception as e:
            logger.error(f"Failed to get articles by stage: {e}")
            return []
    
    def update_article_stage(self, article_id: int, new_stage: str, 
                           metadata: Dict = None, error: str = None) -> bool:
        """Update article stage and metadata."""
        if not self.conn:
            return False
        
        try:
            update_sql = """
            UPDATE article_staging 
            SET stage = %s, stage_timestamp = %s, updated_at = %s
            """
            params = [new_stage, datetime.now(), datetime.now()]
            
            if metadata:
                update_sql += ", metadata = metadata || %s"
                params.append(json.dumps(metadata))
            
            if error:
                update_sql += ", last_error = %s"
                params.append(error)
            
            update_sql += " WHERE id = %s"
            params.append(article_id)
            
            with self.conn.cursor() as cursor:
                cursor.execute(update_sql, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"No article found with ID {article_id}")
                    return False
            
            self.conn.commit()
            logger.info(f"Article {article_id} stage updated to {new_stage}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update article stage: {e}")
            self.conn.rollback()
            return False
    
    def mark_article_failed(self, article_id: int, error: str, 
                          increment_attempts: bool = True) -> bool:
        """Mark article as failed and increment attempt counter."""
        if not self.conn:
            return False
        
        try:
            update_sql = """
            UPDATE article_staging 
            SET stage = 'failed', stage_timestamp = %s, last_error = %s, updated_at = %s
            """
            params = [datetime.now(), error, datetime.now()]
            
            if increment_attempts:
                update_sql += ", processing_attempts = processing_attempts + 1"
            
            update_sql += " WHERE id = %s"
            params.append(article_id)
            
            with self.conn.cursor() as cursor:
                cursor.execute(update_sql, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"No article found with ID {article_id}")
                    return False
            
            self.conn.commit()
            logger.info(f"Article {article_id} marked as failed: {error}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark article as failed: {e}")
            self.conn.rollback()
            return False
    
    def retry_failed_articles(self, max_attempts: int = 3) -> List[int]:
        """Retry failed articles that haven't exceeded max attempts."""
        if not self.conn:
            return []
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM article_staging 
                    WHERE stage = 'failed' AND processing_attempts < %s
                    ORDER BY stage_timestamp ASC
                """, (max_attempts,))
                
                article_ids = [row[0] for row in cursor.fetchall()]
                
                if article_ids:
                    # Reset to raw stage for retry
                    placeholders = ','.join(['%s'] * len(article_ids))
                    cursor.execute(f"""
                        UPDATE article_staging 
                        SET stage = 'raw', stage_timestamp = %s, updated_at = %s
                        WHERE id IN ({placeholders})
                    """, [datetime.now(), datetime.now()] + article_ids)
                    
                    self.conn.commit()
                    logger.info(f"Retrying {len(article_ids)} failed articles")
                
                return article_ids
                
        except Exception as e:
            logger.error(f"Failed to retry articles: {e}")
            self.conn.rollback()
            return []
    
    def cleanup_old_staged_articles(self, days_old: int = 7) -> int:
        """Clean up old staged articles that are no longer needed."""
        if not self.conn:
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM article_staging 
                    WHERE stage IN ('ready', 'failed') 
                    AND updated_at < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
            
            self.conn.commit()
            logger.info(f"Cleaned up {deleted_count} old staged articles")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old articles: {e}")
            self.conn.rollback()
            return 0
    
    def get_staging_statistics(self) -> Dict:
        """Get comprehensive staging statistics."""
        if not self.conn:
            return {}
        
        try:
            with self.conn.cursor() as cursor:
                # Stage distribution
                cursor.execute("""
                    SELECT stage, COUNT(*) as count 
                    FROM article_staging 
                    GROUP BY stage
                """)
                stage_distribution = dict(cursor.fetchall())
                
                # Total articles
                cursor.execute("SELECT COUNT(*) FROM article_staging")
                total_articles = cursor.fetchone()[0]
                
                # Failed articles
                cursor.execute("""
                    SELECT COUNT(*) FROM article_staging 
                    WHERE stage = 'failed'
                """)
                failed_articles = cursor.fetchone()[0]
                
                # Articles ready for processing
                cursor.execute("""
                    SELECT COUNT(*) FROM article_staging 
                    WHERE stage = 'ready'
                """)
                ready_articles = cursor.fetchone()[0]
                
                # Average processing time
                cursor.execute("""
                    SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/60) 
                    FROM article_staging 
                    WHERE stage IN ('ready', 'failed')
                """)
                avg_processing_time = cursor.fetchone()[0] or 0
                
                # Recent activity
                cursor.execute("""
                    SELECT COUNT(*) FROM article_staging 
                    WHERE created_at > %s
                """, (datetime.now() - timedelta(hours=24),))
                articles_last_24h = cursor.fetchone()[0]
                
                return {
                    'total_articles': total_articles,
                    'stage_distribution': stage_distribution,
                    'failed_articles': failed_articles,
                    'ready_articles': ready_articles,
                    'avg_processing_time_minutes': round(avg_processing_time, 2),
                    'articles_last_24h': articles_last_24h,
                    'staging_health': {
                        'success_rate': ((total_articles - failed_articles) / total_articles * 100) if total_articles > 0 else 0,
                        'ready_rate': (ready_articles / total_articles * 100) if total_articles > 0 else 0
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get staging statistics: {e}")
            return {}
    
    def promote_article_to_main_system(self, article_id: int) -> bool:
        """Promote a ready article to the main articles table."""
        if not self.conn:
            return False
        
        try:
            # Get article data
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM article_staging WHERE id = %s AND stage = 'ready'
                """, (article_id,))
                
                article = cursor.fetchone()
                if not article:
                    logger.warning(f"Article {article_id} not found or not ready")
                    return False
                
                # Insert into main articles table
                insert_sql = """
                INSERT INTO articles (
                    title, content, url, source, published_date, collected_date,
                    content_hash, url_hash, detected_language, quality_score,
                    validation_status, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(insert_sql, (
                    article['title'],
                    article['content'],
                    article['url'],
                    article['source'],
                    article['published_date'],
                    article['collected_date'],
                    article['content_hash'],
                    article['url_hash'],
                    article['language_detected'],
                    article['quality_score'],
                    article['validation_status'],
                    json.dumps(article['metadata'])
                ))
                
                # Remove from staging
                cursor.execute("DELETE FROM article_staging WHERE id = %s", (article_id,))
            
            self.conn.commit()
            logger.info(f"Article {article_id} promoted to main system")
            return True
            
        except Exception as e:
            logger.error(f"Failed to promote article: {e}")
            self.conn.rollback()
            return False
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

def main():
    """Test the article stager."""
    stager = ArticleStager()
    
    # Test staging an article
    test_article = {
        'title': 'Test Article Title',
        'content': 'This is a test article content for testing the staging system.',
        'url': 'https://example.com/test-article',
        'source': 'test_source',
        'published_date': datetime.now(),
        'metadata': {'test': True, 'category': 'test'}
    }
    
    print("Testing Article Stager:")
    print("=" * 50)
    
    # Stage article
    result = stager.stage_article(test_article)
    print(f"Staging result: {result.message}")
    print(f"Article ID: {result.article_id}")
    print(f"Stage: {result.stage}")
    print(f"Next stage: {result.next_stage}")
    
    # Get staging statistics
    stats = stager.get_staging_statistics()
    print(f"\nStaging Statistics:")
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")
    
    # Clean up
    stager.close()

if __name__ == "__main__":
    main()
