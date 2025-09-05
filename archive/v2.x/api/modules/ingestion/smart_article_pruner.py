"""
Smart Article Pruner for News Intelligence System v2.1.0
Respects cleanup protection rules and RAG system flags
"""

import os
import psycopg2
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartArticlePruner:
    """
    Smart article pruner that respects cleanup protection rules and RAG system flags.
    Only removes articles that are safe to delete based on the protection system.
    """
    
    def __init__(self, db_config: Dict = None):
        """Initialize the smart pruner with database configuration."""
        self.db_config = db_config or {
            'host': os.getenv('DB_HOST', 'postgres'),
            'database': os.getenv('DB_NAME', 'news_system'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', ''),
            'port': os.getenv('DB_PORT', '5432'),
            'connect_timeout': 10,
            'statement_timeout': 30000
        }
        
    def get_db_connection(self):
        """Get database connection with timeout protection."""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def get_cleanup_protection_status(self, article_id: int) -> Dict:
        """Get cleanup protection status for a specific article."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT * FROM get_cleanup_protection_status(%s)
            """
            cursor.execute(query, (article_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'is_protected': result[0],
                    'protection_reason': result[1],
                    'min_retention_days': result[2],
                    'max_retention_days': result[3],
                    'recommended_action': result[4]
                }
            else:
                return {
                    'is_protected': False,
                    'protection_reason': 'Article not found',
                    'min_retention_days': 7,
                    'max_retention_days': 30,
                    'recommended_action': 'Safe to cleanup'
                }
                
        except Exception as e:
            logger.error(f"Error getting cleanup protection status: {e}")
            return {
                'is_protected': True,  # Default to protected on error
                'protection_reason': f'Error occurred: {e}',
                'min_retention_days': 90,
                'max_retention_days': 365,
                'recommended_action': 'Investigate error before cleanup'
            }
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_articles_eligible_for_cleanup(self, max_age_days: int = 30) -> List[Dict]:
        """Get articles that are eligible for cleanup based on protection rules."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                a.id,
                a.title,
                a.published_date,
                a.created_at,
                a.processing_status,
                a.rag_keep_longer,
                a.rag_context_needed,
                a.rag_priority,
                EXTRACT(DAY FROM NOW() - a.published_date)::INTEGER as days_old
            FROM articles a
            WHERE a.published_date < NOW() - INTERVAL '%s days'
            ORDER BY a.published_date ASC
            """
            
            cursor.execute(query, (max_age_days,))
            articles = cursor.fetchall()
            
            eligible_articles = []
            for article in articles:
                article_id = article[0]
                protection_status = self.get_cleanup_protection_status(article_id)
                
                # Only include articles that are not protected
                if not protection_status['is_protected']:
                    eligible_articles.append({
                        'id': article[0],
                        'title': article[1],
                        'published_date': article[2],
                        'created_at': article[3],
                        'processing_status': article[4],
                        'rag_keep_longer': article[5],
                        'rag_context_needed': article[6],
                        'rag_priority': article[7],
                        'days_old': article[8],
                        'protection_status': protection_status
                    })
                else:
                    logger.info(f"Article {article_id} protected from cleanup: {protection_status['protection_reason']}")
            
            return eligible_articles
            
        except Exception as e:
            logger.error(f"Error getting articles eligible for cleanup: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_cleanup_statistics(self) -> Dict:
        """Get comprehensive cleanup statistics."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get overall article statistics
            cursor.execute("SELECT * FROM get_ml_processing_stats()")
            ml_stats = cursor.fetchone()
            
            # Get cleanup protection statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(CASE WHEN rag_keep_longer = TRUE THEN 1 END) as rag_keep_longer_count,
                    COUNT(CASE WHEN rag_context_needed = TRUE THEN 1 END) as rag_context_needed_count,
                    COUNT(CASE WHEN rag_priority > 0 THEN 1 END) as high_priority_count,
                    COUNT(CASE WHEN processing_status = 'raw' THEN 1 END) as raw_articles,
                    COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END) as processed_articles
                FROM articles
            """)
            protection_stats = cursor.fetchone()
            
            # Get age distribution
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN published_date < NOW() - INTERVAL '7 days' THEN 1 END) as older_than_7_days,
                    COUNT(CASE WHEN published_date < NOW() - INTERVAL '30 days' THEN 1 END) as older_than_30_days,
                    COUNT(CASE WHEN published_date < NOW() - INTERVAL '90 days' THEN 1 END) as older_than_90_days,
                    COUNT(CASE WHEN published_date < NOW() - INTERVAL '365 days' THEN 1 END) as older_than_1_year
                FROM articles
            """)
            age_stats = cursor.fetchone()
            
            return {
                'ml_processing': {
                    'total_articles': ml_stats[0] if ml_stats else 0,
                    'raw_articles': ml_stats[1] if ml_stats else 0,
                    'processing_articles': ml_stats[2] if ml_stats else 0,
                    'ml_processed': ml_stats[3] if ml_stats else 0,
                    'processing_errors': ml_stats[4] if ml_stats else 0,
                    'processing_progress': ml_stats[5] if ml_stats else 0,
                    'clusters_count': ml_stats[6] if ml_stats else 0,
                    'datasets_count': ml_stats[7] if ml_stats else 0,
                    'rag_requests_pending': ml_stats[8] if ml_stats else 0,
                    'rag_requests_completed': ml_stats[9] if ml_stats else 0
                },
                'cleanup_protection': {
                    'total_articles': protection_stats[0] if protection_stats else 0,
                    'rag_keep_longer_count': protection_stats[1] if protection_stats else 0,
                    'rag_context_needed_count': protection_stats[2] if protection_stats else 0,
                    'high_priority_count': protection_stats[3] if protection_stats else 0,
                    'raw_articles': protection_stats[4] if protection_stats else 0,
                    'processed_articles': protection_stats[5] if protection_stats else 0
                },
                'age_distribution': {
                    'older_than_7_days': age_stats[0] if age_stats else 0,
                    'older_than_30_days': age_stats[1] if age_stats else 0,
                    'older_than_90_days': age_stats[2] if age_stats else 0,
                    'older_than_1_year': age_stats[3] if age_stats else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cleanup statistics: {e}")
            return {}
        finally:
            if 'conn' in locals():
                conn.close()
    
    def cleanup_old_articles(self, max_age_days: int = 30, dry_run: bool = True) -> Dict:
        """
        Clean up old articles that are not protected by the cleanup protection system.
        
        Args:
            max_age_days: Maximum age in days for articles to be considered for cleanup
            dry_run: If True, only show what would be cleaned up without actually deleting
            
        Returns:
            Dictionary with cleanup results and statistics
        """
        try:
            logger.info(f"Starting smart cleanup process (dry_run={dry_run})")
            
            # Get articles eligible for cleanup
            eligible_articles = self.get_articles_eligible_for_cleanup(max_age_days)
            
            if not eligible_articles:
                logger.info("No articles eligible for cleanup found")
                return {
                    'success': True,
                    'dry_run': dry_run,
                    'articles_removed': 0,
                    'articles_protected': 0,
                    'errors': [],
                    'removed_articles': []
                }
            
            logger.info(f"Found {len(eligible_articles)} articles eligible for cleanup")
            
            if dry_run:
                logger.info("DRY RUN MODE - No articles will be deleted")
                return {
                    'success': True,
                    'dry_run': True,
                    'articles_removed': 0,
                    'articles_protected': 0,
                    'errors': [],
                    'removed_articles': [],
                    'eligible_for_cleanup': eligible_articles
                }
            
            # Perform actual cleanup
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            removed_articles = []
            errors = []
            
            for article in eligible_articles:
                try:
                    article_id = article['id']
                    
                    # Delete from processed_articles first (if exists)
                    cursor.execute("""
                        DELETE FROM processed_articles 
                        WHERE original_article_id = %s
                    """, (article_id,))
                    
                    # Delete from article_clusters (if exists)
                    cursor.execute("""
                        DELETE FROM article_clusters 
                        WHERE main_article_id = %s OR %s = ANY(article_ids)
                    """, (article_id, article_id))
                    
                    # Delete from rag_context_requests (if exists)
                    cursor.execute("""
                        DELETE FROM rag_context_requests 
                        WHERE article_id = %s
                    """, (article_id,))
                    
                    # Finally delete the article
                    cursor.execute("DELETE FROM articles WHERE id = %s", (article_id,))
                    
                    if cursor.rowcount > 0:
                        removed_articles.append({
                            'id': article_id,
                            'title': article['title'],
                            'published_date': article['published_date'],
                            'days_old': article['days_old']
                        })
                        logger.info(f"Removed article {article_id}: {article['title']}")
                    else:
                        logger.warning(f"Article {article_id} was not found for deletion")
                        
                except Exception as e:
                    error_msg = f"Error removing article {article['id']}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Commit changes
            conn.commit()
            logger.info(f"Cleanup completed. Removed {len(removed_articles)} articles")
            
            return {
                'success': True,
                'dry_run': False,
                'articles_removed': len(removed_articles),
                'articles_protected': 0,  # Will be calculated from protection system
                'errors': errors,
                'removed_articles': removed_articles
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup process: {e}")
            if 'conn' in locals():
                conn.rollback()
            return {
                'success': False,
                'dry_run': dry_run,
                'articles_removed': 0,
                'articles_protected': 0,
                'errors': [str(e)],
                'removed_articles': []
            }
        finally:
            if 'conn' in locals():
                conn.close()
    
    def mark_article_for_rag_protection(self, article_id: int, context_needed: bool = True, 
                                      keep_longer: bool = False, priority: int = 1) -> bool:
        """Mark an article for RAG protection to prevent cleanup."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT mark_article_for_rag(%s, %s, %s, %s)
            """
            cursor.execute(query, (article_id, context_needed, keep_longer, priority))
            
            result = cursor.fetchone()
            conn.commit()
            
            if result and result[0]:
                logger.info(f"Article {article_id} marked for RAG protection")
                return True
            else:
                logger.warning(f"Failed to mark article {article_id} for RAG protection")
                return False
                
        except Exception as e:
            logger.error(f"Error marking article for RAG protection: {e}")
            if 'conn' in locals():
                conn.rollback()
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_cleanup_recommendations(self) -> List[Dict]:
        """Get recommendations for cleanup based on current system state."""
        try:
            stats = self.get_cleanup_statistics()
            recommendations = []
            
            # Check for old raw articles
            if stats.get('cleanup_protection', {}).get('raw_articles', 0) > 100:
                recommendations.append({
                    'type': 'warning',
                    'message': f"High number of raw articles ({stats['cleanup_protection']['raw_articles']}) - consider processing or cleanup",
                    'action': 'Process raw articles or increase cleanup frequency'
                })
            
            # Check for articles that might need RAG protection
            if stats.get('cleanup_protection', {}).get('rag_context_needed_count', 0) > 50:
                recommendations.append({
                    'type': 'info',
                    'message': f"Many articles need RAG context ({stats['cleanup_protection']['rag_context_needed_count']})",
                    'action': 'Review RAG research priorities'
                })
            
            # Check for very old articles
            if stats.get('age_distribution', {}).get('older_than_1_year', 0) > 1000:
                recommendations.append({
                    'type': 'warning',
                    'message': f"Large number of articles older than 1 year ({stats['age_distribution']['older_than_1_year']})",
                    'action': 'Review retention policies and cleanup rules'
                })
            
            # Check processing progress
            progress = stats.get('ml_processing', {}).get('processing_progress', 0)
            if progress < 50:
                recommendations.append({
                    'type': 'warning',
                    'message': f"Low ML processing progress ({progress}%)",
                    'action': 'Investigate processing pipeline issues'
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting cleanup recommendations: {e}")
            return []


def main():
    """Main function for testing the smart article pruner."""
    try:
        pruner = SmartArticlePruner()
        
        # Get current statistics
        print("=== Current System Statistics ===")
        stats = pruner.get_cleanup_statistics()
        for category, data in stats.items():
            print(f"\n{category.upper()}:")
            for key, value in data.items():
                print(f"  {key}: {value}")
        
        # Get cleanup recommendations
        print("\n=== Cleanup Recommendations ===")
        recommendations = pruner.get_cleanup_recommendations()
        for rec in recommendations:
            print(f"[{rec['type'].upper()}] {rec['message']}")
            print(f"  Action: {rec['action']}")
        
        # Show what would be cleaned up (dry run)
        print("\n=== Dry Run Cleanup Analysis ===")
        dry_run_result = pruner.cleanup_old_articles(max_age_days=30, dry_run=True)
        
        if dry_run_result.get('eligible_for_cleanup'):
            print(f"Articles eligible for cleanup: {len(dry_run_result['eligible_for_cleanup'])}")
            for article in dry_run_result['eligible_for_cleanup'][:5]:  # Show first 5
                print(f"  - {article['title']} ({article['days_old']} days old)")
            if len(dry_run_result['eligible_for_cleanup']) > 5:
                print(f"  ... and {len(dry_run_result['eligible_for_cleanup']) - 5} more")
        else:
            print("No articles eligible for cleanup")
        
        print("\nSmart article pruner test completed successfully!")
        
    except Exception as e:
        print(f"Error testing smart article pruner: {e}")
        return False
    
    return True


if __name__ == "__main__":
    main()
