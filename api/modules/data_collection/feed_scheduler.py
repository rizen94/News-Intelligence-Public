"""
RSS Feed Scheduler
Background service for regular RSS feed collection
"""

import logging
import threading
import time
from typing import Dict, Any
from datetime import datetime, timedelta
import schedule
import atexit

from modules.rss_feed_service import RSSFeedService

logger = logging.getLogger(__name__)

class FeedScheduler:
    """Background scheduler for RSS feed collection"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize Feed Scheduler
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.rss_service = RSSFeedService(db_config)
        self.scheduler_thread = None
        self.running = False
        self.collection_interval = 30  # minutes
        self.max_articles_per_feed = 50
        
        # Statistics
        self.stats = {
            'total_collections': 0,
            'successful_collections': 0,
            'failed_collections': 0,
            'last_collection': None,
            'next_collection': None,
            'total_articles_collected': 0,
            'start_time': None
        }
        
        # Register cleanup function
        atexit.register(self.stop)
    
    def start(self, collection_interval_minutes: int = 30):
        """
        Start the background scheduler
        
        Args:
            collection_interval_minutes: How often to collect feeds (in minutes)
        """
        if self.running:
            logger.warning("Feed scheduler is already running")
            return
        
        self.collection_interval = collection_interval_minutes
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        # Schedule regular collection
        schedule.every(collection_interval_minutes).minutes.do(self._collect_feeds_job)
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Schedule first collection
        self.stats['next_collection'] = datetime.now() + timedelta(minutes=collection_interval_minutes)
        
        logger.info(f"Feed scheduler started - collecting every {collection_interval_minutes} minutes")
    
    def stop(self):
        """Stop the background scheduler"""
        if not self.running:
            return
        
        self.running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Feed scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)
    
    def _collect_feeds_job(self):
        """Background job to collect RSS feeds"""
        try:
            logger.info("Starting scheduled RSS feed collection")
            
            # Update next collection time
            self.stats['next_collection'] = datetime.now() + timedelta(minutes=self.collection_interval)
            
            # Collect feeds
            results = self.rss_service.collect_all_feeds(self.max_articles_per_feed)
            
            # Update statistics
            self.stats['total_collections'] += 1
            self.stats['last_collection'] = datetime.now()
            
            if results['feeds_successful'] > 0:
                self.stats['successful_collections'] += 1
                self.stats['total_articles_collected'] += results['new_articles']
                logger.info(f"Scheduled collection completed: {results['new_articles']} new articles from {results['feeds_successful']} feeds")
            else:
                self.stats['failed_collections'] += 1
                logger.warning("Scheduled collection failed - no feeds successful")
            
        except Exception as e:
            logger.error(f"Error in scheduled feed collection: {e}")
            self.stats['failed_collections'] += 1
    
    def collect_now(self) -> Dict[str, Any]:
        """
        Trigger immediate RSS feed collection
        
        Returns:
            Dictionary with collection results
        """
        try:
            logger.info("Starting immediate RSS feed collection")
            results = self.rss_service.collect_all_feeds(self.max_articles_per_feed)
            
            # Update statistics
            self.stats['total_collections'] += 1
            self.stats['last_collection'] = datetime.now()
            
            if results['feeds_successful'] > 0:
                self.stats['successful_collections'] += 1
                self.stats['total_articles_collected'] += results['new_articles']
            else:
                self.stats['failed_collections'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error in immediate feed collection: {e}")
            self.stats['failed_collections'] += 1
            return {'error': str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status and statistics"""
        try:
            feed_status = self.rss_service.get_feed_status()
            
            return {
                'scheduler': {
                    'running': self.running,
                    'collection_interval_minutes': self.collection_interval,
                    'max_articles_per_feed': self.max_articles_per_feed,
                    'statistics': self.stats
                },
                'feeds': feed_status,
                'uptime': str(datetime.now() - self.stats['start_time']) if self.stats['start_time'] else None
            }
            
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {'error': str(e)}
    
    def update_collection_interval(self, minutes: int):
        """Update the collection interval"""
        if minutes < 5:
            logger.warning("Collection interval too short, minimum is 5 minutes")
            return False
        
        self.collection_interval = minutes
        
        if self.running:
            # Restart scheduler with new interval
            self.stop()
            self.start(minutes)
        
        logger.info(f"Updated collection interval to {minutes} minutes")
        return True
    
    def get_collection_history(self, hours: int = 24) -> Dict[str, Any]:
        """Get collection history from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get articles collected in the last N hours
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT 
                    source,
                    COUNT(*) as article_count,
                    MIN(created_at) as first_article,
                    MAX(created_at) as last_article
                FROM articles 
                WHERE created_at >= %s
                GROUP BY source
                ORDER BY article_count DESC
            """, (cutoff_time,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'source': row[0],
                    'article_count': row[1],
                    'first_article': row[2].isoformat() if row[2] else None,
                    'last_article': row[3].isoformat() if row[3] else None
                })
            
            # Get total articles by hour
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(*) as article_count
                FROM articles 
                WHERE created_at >= %s
                GROUP BY hour
                ORDER BY hour DESC
            """, (cutoff_time,))
            
            hourly_stats = []
            for row in cursor.fetchall():
                hourly_stats.append({
                    'hour': row[0].isoformat(),
                    'article_count': row[1]
                })
            
            conn.close()
            
            return {
                'period_hours': hours,
                'sources': history,
                'hourly_stats': hourly_stats,
                'total_articles': sum(h['article_count'] for h in history)
            }
            
        except Exception as e:
            logger.error(f"Error getting collection history: {e}")
            return {'error': str(e)}
