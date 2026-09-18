"""
Content Validation Service
Ensures data integrity throughout the pipeline by validating article content availability
before proceeding with downstream processing.
"""

import logging
from shared.domain_registry import resolve_domain_schema
from typing import Dict, List, Optional, Tuple
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

class ContentValidationService:
    """Service to validate content availability and pipeline integrity."""
    
    @staticmethod
    async def validate_article_content_availability(domain: str, article_ids: List[int]) -> Dict[str, any]:
        """
        Validate that articles have full content available.
        
        Args:
            domain: The domain/schema to check
            article_ids: List of article IDs to validate
            
        Returns:
            Dict with validation results and counts
        """
        schema = resolve_domain_schema(domain)
        valid_articles = []
        missing_content_articles = []
        
        if not article_ids:
            return {
                "valid": True,
                "total_count": 0,
                "valid_count": 0,
                "missing_content_count": 0,
                "missing_articles": []
            }
        
        conn = get_db_connection()
        if not conn:
            logger.error("No database connection for content validation")
            return {
                "valid": False,
                "total_count": len(article_ids),
                "valid_count": 0,
                "missing_content_count": len(article_ids),
                "missing_articles": article_ids
            }
        
        try:
            with conn.cursor() as cursor:
                # Check which articles have content available
                placeholders = ",".join(["%s"] * len(article_ids))
                cursor.execute(
                    f"""
                    SELECT id, content, LENGTH(content) as content_length
                    FROM {schema}.articles
                    WHERE id IN ({placeholders})
                    """,
                    article_ids
                )
                articles = cursor.fetchall()
                
                for row in articles:
                    article_id, content, content_length = row
                    if content and content_length and content_length > 100:  # 100 chars minimum
                        valid_articles.append(article_id)
                    else:
                        missing_content_articles.append(article_id)
            
            conn.commit()
            
            return {
                "valid": len(missing_content_articles) == 0,
                "total_count": len(article_ids),
                "valid_count": len(valid_articles),
                "missing_content_count": len(missing_content_articles),
                "missing_articles": missing_content_articles
            }
            
        except Exception as e:
            logger.error(f"Content validation error for domain {domain}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            return {
                "valid": False,
                "total_count": len(article_ids),
                "valid_count": 0,
                "missing_content_count": len(article_ids),
                "missing_articles": article_ids
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
    @staticmethod
    async def validate_storyline_content_requirements(domain: str, storyline_id: int) -> Dict[str, any]:
        """
        Validate that a storyline has sufficient content for processing.
        
        Args:
            domain: The domain/schema to check
            storyline_id: The storyline ID to validate
            
        Returns:
            Dict with validation results
        """
        schema = resolve_domain_schema(domain)
        conn = get_db_connection()
        if not conn:
            return {"valid": False, "error": "No database connection"}
        
        try:
            with conn.cursor() as cursor:
                # Check storyline articles and their content
                cursor.execute(
                    f"""
                    SELECT 
                        COUNT(*) as total_articles,
                        COUNT(CASE WHEN LENGTH(a.content) > 100 THEN 1 END) as articles_with_content,
                        COUNT(CASE WHEN a.content IS NULL OR LENGTH(a.content) <= 100 THEN 1 END) as articles_without_content
                    FROM {schema}.storylines s
                    JOIN {schema}.storyline_articles sa ON s.id = sa.storyline_id
                    JOIN {schema}.articles a ON sa.article_id = a.id
                    WHERE s.id = %s
                    """,
                    (storyline_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    total_articles, articles_with_content, articles_without_content = result
                    has_sufficient_content = articles_with_content > 0
                    
                    return {
                        "valid": has_sufficient_content,
                        "total_articles": total_articles,
                        "articles_with_content": articles_with_content,
                        "articles_without_content": articles_without_content,
                        "content_ratio": articles_with_content / total_articles if total_articles > 0 else 0
                    }
                else:
                    return {"valid": False, "error": "Storyline not found"}
                    
        except Exception as e:
            logger.error(f"Storyline content validation error for {domain}/{storyline_id}: {e}")
            return {"valid": False, "error": str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
    @staticmethod
    async def get_pipeline_content_health(domain: str) -> Dict[str, any]:
        """
        Get overall content health for a pipeline domain.
        
        Args:
            domain: The domain/schema to check
            
        Returns:
            Dict with content health metrics
        """
        schema = resolve_domain_schema(domain)
        conn = get_db_connection()
        if not conn:
            return {"error": "No database connection"}
        
        try:
            with conn.cursor() as cursor:
                # Get content health metrics
                cursor.execute(
                    f"""
                    SELECT 
                        COUNT(*) as total_articles,
                        COUNT(CASE WHEN LENGTH(content) > 100 THEN 1 END) as articles_with_content,
                        COUNT(CASE WHEN content IS NULL OR LENGTH(content) <= 100 THEN 1 END) as articles_without_content,
                        AVG(LENGTH(content)) as avg_content_length,
                        MIN(LENGTH(content)) as min_content_length,
                        MAX(LENGTH(content)) as max_content_length
                    FROM {schema}.articles
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    """,
                    ()
                )
                result = cursor.fetchone()
                
                if result:
                    total_articles, articles_with_content, articles_without_content, avg_length, min_length, max_length = result
                    
                    return {
                        "total_articles": total_articles,
                        "articles_with_content": articles_with_content,
                        "articles_without_content": articles_without_content,
                        "content_coverage_ratio": articles_with_content / total_articles if total_articles > 0 else 0,
                        "average_content_length": avg_length,
                        "minimum_content_length": min_length,
                        "maximum_content_length": max_length,
                        "health_status": "healthy" if (articles_with_content / total_articles) > 0.7 else "warning" if (articles_with_content / total_articles) > 0.3 else "critical"
                    }
                else:
                    return {"error": "No data found"}
                    
        except Exception as e:
            logger.error(f"Pipeline content health error for {domain}: {e}")
            return {"error": str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass

# Global instance for easy access
content_validation_service = ContentValidationService()