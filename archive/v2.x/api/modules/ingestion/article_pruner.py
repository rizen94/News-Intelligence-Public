#!/usr/bin/env python3
"""
Article Pruner for News Intelligence System v2.0.0
Automatically removes old, low-quality, and duplicate articles.
"""

import os
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ArticlePruner:
    """Manages automatic pruning of old and unused articles"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.pruning_config = {
            'max_article_age_days': 90,           # Remove articles older than 90 days
            'min_quality_score': 0.3,             # Remove articles with very low quality scores
            'max_duplicate_articles': 5,          # Keep max 5 articles per cluster
            'min_engagement_threshold': 0.1,      # Remove articles with very low engagement
            'batch_size': 100,                    # Process in batches to avoid locks
            'dry_run': False                      # Set to True to preview changes without deleting
        }
    
    def get_db_connection(self):
        """Get database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return None
    
    def analyze_article_usage(self) -> Dict:
        """Analyze current article statistics"""
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            cur = conn.cursor()
            
            # Get article statistics
            cur.execute("""
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END) as last_7_days,
                    COUNT(CASE WHEN quality_score > 0.7 THEN 1 END) as high_quality,
                    COUNT(CASE WHEN sentiment_score IS NOT NULL THEN 1 END) as has_sentiment,
                    COUNT(CASE WHEN sentiment_score IS NULL THEN 1 END) as no_sentiment
                FROM articles
            """)
            
            result = cur.fetchone()
            stats = {
                'total_articles': result[0],
                'last_7_days': result[1],
                'high_quality': result[2],
                'has_sentiment': result[3],
                'no_sentiment': result[4]
            }
            
            logger.info(f"Current article statistics: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error analyzing article usage: {e}")
            return {}
        finally:
            if conn:
                conn.close()
    
    def identify_articles_for_pruning(self) -> List[int]:
        """Identify articles that should be pruned"""
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            articles_to_prune = []
            
            # 1. Old articles
            cur.execute("""
                SELECT id FROM articles 
                WHERE created_at < NOW() - INTERVAL '%s days'
                ORDER BY created_at ASC
            """, (self.pruning_config['max_article_age_days'],))
            
            old_articles = [row[0] for row in cur.fetchall()]
            articles_to_prune.extend(old_articles)
            
            # 2. Low quality articles (if quality scoring exists)
            try:
                cur.execute("""
                    SELECT id FROM articles 
                    WHERE quality_score < %s AND quality_score IS NOT NULL
                    ORDER BY quality_score ASC
                """, (self.pruning_config['min_quality_score'],))
                
                low_quality = [row[0] for row in cur.fetchall()]
                articles_to_prune.extend(low_quality)
            except:
                # Quality scoring not implemented yet
                pass
            
            # 3. Duplicate articles (keep only the most recent)
            cur.execute("""
                SELECT url, COUNT(*) as count
                FROM articles 
                WHERE url IS NOT NULL
                GROUP BY url 
                HAVING COUNT(*) > %s
            """, (self.pruning_config['max_duplicate_articles'],))
            
            for url, count in cur.fetchall():
                cur.execute("""
                    SELECT id FROM articles 
                    WHERE url = %s 
                    ORDER BY created_at DESC
                    OFFSET %s
                """, (url, self.pruning_config['max_duplicate_articles']))
                
                duplicates = [row[0] for row in cur.fetchall()]
                articles_to_prune.extend(duplicates)
            
            # Remove duplicates and limit batch size
            articles_to_prune = list(set(articles_to_prune))[:self.pruning_config['batch_size']]
            
            logger.info(f"Identified {len(articles_to_prune)} articles for pruning")
            return articles_to_prune
            
        except Exception as e:
            logger.error(f"Error identifying articles for pruning: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def prune_duplicate_articles(self) -> int:
        """Remove duplicate articles based on URL"""
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            cur = conn.cursor()
            
            # Find URLs with multiple articles
            cur.execute("""
                SELECT url, COUNT(*) as count
                FROM articles 
                WHERE url IS NOT NULL
                GROUP BY url 
                HAVING COUNT(*) > 1
            """)
            
            duplicates_removed = 0
            
            for url, count in cur.fetchall():
                # Keep the most recent article, remove others
                cur.execute("""
                    DELETE FROM articles 
                    WHERE url = %s 
                    AND id NOT IN (
                        SELECT id FROM articles 
                        WHERE url = %s 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    )
                """, (url, url))
                
                duplicates_removed += cur.rowcount
            
            if not self.pruning_config['dry_run']:
                conn.commit()
                logger.info(f"Pruned {duplicates_removed} duplicate articles")
            else:
                logger.info(f"DRY RUN: Would prune {duplicates_removed} duplicate articles")
            
            return duplicates_removed
            
        except Exception as e:
            logger.error(f"Error pruning duplicate articles: {e}")
            if not self.pruning_config['dry_run']:
                conn.rollback()
            return 0
        finally:
            if conn:
                conn.close()
    
    def prune_old_articles(self) -> int:
        """Remove articles older than configured threshold"""
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            cur = conn.cursor()
            
            cur.execute("""
                DELETE FROM articles 
                WHERE created_at < NOW() - INTERVAL '%s days'
            """, (self.pruning_config['max_article_age_days'],))
            
            old_articles_removed = cur.rowcount
            
            if not self.pruning_config['dry_run']:
                conn.commit()
                logger.info(f"Pruned {old_articles_removed} old articles")
            else:
                logger.info(f"DRY RUN: Would prune {old_articles_removed} old articles")
            
            return old_articles_removed
            
        except Exception as e:
            logger.error(f"Error pruning old articles: {e}")
            if not self.pruning_config['dry_run']:
                conn.rollback()
            return 0
        finally:
            if conn:
                conn.close()
    
    def prune_low_quality_articles(self) -> int:
        """Remove articles with very low quality scores"""
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            cur = conn.cursor()
            
            # Check if quality scoring exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'articles' AND column_name = 'quality_score'
            """)
            
            if not cur.fetchone():
                logger.info("Quality scoring not implemented yet, skipping low quality pruning")
                return 0
            
            cur.execute("""
                DELETE FROM articles 
                WHERE quality_score < %s AND quality_score IS NOT NULL
            """, (self.pruning_config['min_quality_score'],))
            
            low_quality_removed = cur.rowcount
            
            if not self.pruning_config['dry_run']:
                conn.commit()
                logger.info(f"Pruned {low_quality_removed} low quality articles")
            else:
                logger.info(f"DRY RUN: Would prune {low_quality_removed} low quality articles")
            
            return low_quality_removed
            
        except Exception as e:
            logger.error(f"Error pruning low quality articles: {e}")
            if not self.pruning_config['dry_run']:
                conn.rollback()
            return 0
        finally:
            if conn:
                conn.close()
    
    def cleanup_orphaned_data(self) -> Dict:
        """Clean up orphaned data in related tables"""
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            cur = conn.cursor()
            cleanup_results = {}
            
            # Clean up orphaned entities (if table exists)
            try:
                cur.execute("""
                    DELETE FROM entities 
                    WHERE article_id NOT IN (SELECT id FROM articles)
                """)
                cleanup_results['entities'] = cur.rowcount
            except:
                cleanup_results['entities'] = 0
            
            # Clean up orphaned clusters (if table exists)
            try:
                cur.execute("""
                    DELETE FROM clusters 
                    WHERE id NOT IN (
                        SELECT DISTINCT cluster_id FROM articles WHERE cluster_id IS NOT NULL
                    )
                """)
                cleanup_results['clusters'] = cur.rowcount
            except:
                cleanup_results['clusters'] = 0
            
            # Clean up orphaned story data (if tables exist)
            try:
                cur.execute("""
                    DELETE FROM story_thread_articles 
                    WHERE article_id NOT IN (SELECT id FROM articles)
                """)
                cleanup_results['story_thread_articles'] = cur.rowcount
            except:
                cleanup_results['story_thread_articles'] = 0
            
            if not self.pruning_config['dry_run']:
                conn.commit()
                logger.info(f"Cleaned up orphaned data: {cleanup_results}")
            else:
                logger.info(f"DRY RUN: Would clean up orphaned data: {cleanup_results}")
            
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error cleaning up orphaned data: {e}")
            if not self.pruning_config['dry_run']:
                conn.rollback()
            return {}
        finally:
            if conn:
                conn.close()
    
    def run_pruning_pipeline(self, dry_run: bool = False) -> Dict:
        """Run the complete pruning pipeline"""
        logger.info("Starting article pruning pipeline...")
        
        # Update dry run setting
        self.pruning_config['dry_run'] = dry_run
        
        # Analyze current state
        usage_stats = self.analyze_article_usage()
        
        # Identify articles for pruning
        articles_identified = self.identify_articles_for_pruning()
        
        # Run pruning operations
        duplicates_removed = self.prune_duplicate_articles()
        old_articles_removed = self.prune_old_articles()
        low_quality_removed = self.prune_low_quality_articles()
        
        # Clean up orphaned data
        orphaned_data_cleaned = self.cleanup_orphaned_data()
        
        # Calculate total articles removed
        total_articles_removed = duplicates_removed + old_articles_removed + low_quality_removed
        
        # Get final statistics
        final_stats = self.analyze_article_usage()
        
        # Prepare results
        results = {
            'usage_stats': usage_stats,
            'articles_identified': len(articles_identified),
            'duplicates_removed': duplicates_removed,
            'old_articles_removed': old_articles_removed,
            'low_quality_removed': low_quality_removed,
            'orphaned_data_cleaned': orphaned_data_cleaned,
            'total_articles_removed': total_articles_removed,
            'final_stats': final_stats
        }
        
        if dry_run:
            logger.info("DRY RUN MODE - No articles will be deleted")
        
        logger.info(f"Pruning pipeline completed: {results}")
        return results
    
    def set_pruning_config(self, config: Dict):
        """Update pruning configuration"""
        self.pruning_config.update(config)
        logger.info(f"Updated pruning configuration: {self.pruning_config}")
    
    def get_pruning_config(self) -> Dict:
        """Get current pruning configuration"""
        return self.pruning_config.copy()
    
    def reset_pruning_config(self):
        """Reset pruning configuration to defaults"""
        self.pruning_config = {
            'max_article_age_days': 90,
            'min_quality_score': 0.3,
            'max_duplicate_articles': 5,
            'min_engagement_threshold': 0.1,
            'batch_size': 100,
            'dry_run': False
        }
        logger.info("Reset pruning configuration to defaults")

if __name__ == "__main__":
    # Test the article pruner
    db_config = {
        'host': 'postgres',
        'database': 'news_system',
        'user': 'newsapp',
        'password': ''
    }
    
    pruner = ArticlePruner(db_config)
    
    # Run dry run first
    print("Running dry run...")
    results = pruner.run_pruning_pipeline(dry_run=True)
    print(f"Dry run results: {results}")
    
    # Ask user if they want to proceed
    response = input("Proceed with actual pruning? (yes/no): ")
    if response.lower() == 'yes':
        print("Running actual pruning...")
        results = pruner.run_pruning_pipeline(dry_run=False)
        print(f"Pruning results: {results}")
    else:
        print("Pruning cancelled")
