import logging
import psycopg2
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class StorylineAlertService:
    """
    Service for managing storyline alerts and notifications.
    Detects significant updates to storylines and creates alerts.
    """
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.logger = logger
        
        # Alert thresholds
        self.significance_thresholds = {
            'new_articles': 3,  # Minimum new articles to trigger alert
            'significance_score': 0.6,  # Minimum significance score
            'time_window_hours': 24,  # Time window for considering updates
            'article_quality_threshold': 0.7  # Minimum quality score for articles
        }
    
    def check_for_significant_updates(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if there have been significant updates to a storyline that warrant an alert.
        
        Args:
            thread_id: Story thread ID to check
            
        Returns:
            Alert data if significant update found, None otherwise
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get thread info
            cursor.execute("""
                SELECT id, title, description, category, created_at, updated_at
                FROM story_threads 
                WHERE id = %s
            """, (thread_id,))
            
            thread_row = cursor.fetchone()
            if not thread_row:
                return None
            
            thread_info = {
                'id': thread_row[0],
                'title': thread_row[1],
                'description': thread_row[2],
                'category': thread_row[3],
                'created_at': thread_row[4],
                'updated_at': thread_row[5]
            }
            
            # Check for recent articles assigned to this thread
            time_window = datetime.now() - timedelta(hours=self.significance_thresholds['time_window_hours'])
            
            cursor.execute("""
                SELECT a.id, a.title, a.source, a.published_at, a.quality_score, a.category,
                       cpa.assigned_at, cpa.confidence_score
                FROM articles a
                JOIN content_priority_assignments cpa ON a.id = cpa.article_id
                WHERE cpa.thread_id = %s 
                AND cpa.assigned_at >= %s
                AND a.quality_score >= %s
                ORDER BY cpa.assigned_at DESC
            """, (
                thread_id, 
                time_window,
                self.significance_thresholds['article_quality_threshold']
            ))
            
            recent_articles = cursor.fetchall()
            
            if len(recent_articles) < self.significance_thresholds['new_articles']:
                conn.close()
                return None
            
            # Calculate significance score
            significance_score = self._calculate_significance_score(recent_articles, thread_info)
            
            if significance_score < self.significance_thresholds['significance_score']:
                conn.close()
                return None
            
            # Check if we already have a recent alert for this thread
            cursor.execute("""
                SELECT id FROM storyline_alerts 
                WHERE thread_id = %s 
                AND created_at >= %s
                AND alert_type = 'significant_update'
            """, (thread_id, time_window))
            
            if cursor.fetchone():
                conn.close()
                return None  # Already alerted recently
            
            # Create alert data
            alert_data = self._create_alert_data(thread_info, recent_articles, significance_score)
            
            conn.close()
            return alert_data
            
        except Exception as e:
            self.logger.error(f"Error checking for significant updates: {e}")
            return None
    
    def create_alert(self, alert_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new storyline alert in the database.
        
        Args:
            alert_data: Alert information
            
        Returns:
            Alert ID if created successfully, None otherwise
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO storyline_alerts 
                (thread_id, alert_type, title, message, significance_score, article_count, 
                 new_articles, context_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                alert_data['thread_id'],
                alert_data['alert_type'],
                alert_data['title'],
                alert_data['message'],
                alert_data['significance_score'],
                alert_data['article_count'],
                json.dumps(alert_data['new_articles']),
                alert_data['context_summary']
            ))
            
            alert_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            
            self.logger.info(f"Created storyline alert {alert_id} for thread {alert_data['thread_id']}")
            return alert_id
            
        except Exception as e:
            self.logger.error(f"Error creating alert: {e}")
            return None
    
    def get_unread_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get unread storyline alerts.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of unread alerts
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT sa.id, sa.thread_id, sa.alert_type, sa.title, sa.message, 
                       sa.significance_score, sa.article_count, sa.new_articles, 
                       sa.context_summary, sa.created_at,
                       st.title as thread_title, st.category
                FROM storyline_alerts sa
                JOIN story_threads st ON sa.thread_id = st.id
                WHERE sa.is_read = false
                ORDER BY sa.created_at DESC
                LIMIT %s
            """, (limit,))
            
            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    'id': row[0],
                    'thread_id': row[1],
                    'alert_type': row[2],
                    'title': row[3],
                    'message': row[4],
                    'significance_score': float(row[5]),
                    'article_count': row[6],
                    'new_articles': json.loads(row[7]) if row[7] else [],
                    'context_summary': row[8],
                    'created_at': row[9].isoformat(),
                    'thread_title': row[10],
                    'category': row[11]
                })
            
            conn.close()
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting unread alerts: {e}")
            return []
    
    def mark_alert_as_read(self, alert_id: int) -> bool:
        """
        Mark an alert as read.
        
        Args:
            alert_id: Alert ID to mark as read
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE storyline_alerts 
                SET is_read = true, read_at = NOW()
                WHERE id = %s
            """, (alert_id,))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking alert as read: {e}")
            return False
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """
        Get alert statistics.
        
        Returns:
            Dictionary with alert statistics
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_alerts,
                    COUNT(CASE WHEN is_read = false THEN 1 END) as unread_alerts,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as recent_alerts,
                    AVG(significance_score) as avg_significance
                FROM storyline_alerts
            """)
            
            row = cursor.fetchone()
            stats = {
                'total_alerts': row[0],
                'unread_alerts': row[1],
                'recent_alerts': row[2],
                'avg_significance': float(row[3]) if row[3] else 0.0
            }
            
            conn.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting alert statistics: {e}")
            return {}
    
    def _calculate_significance_score(self, articles: List, thread_info: Dict[str, Any]) -> float:
        """
        Calculate significance score for a set of articles.
        
        Args:
            articles: List of recent articles
            thread_info: Thread information
            
        Returns:
            Significance score between 0 and 1
        """
        if not articles:
            return 0.0
        
        # Base score from article count
        article_count_score = min(len(articles) / 10.0, 1.0)  # Max at 10 articles
        
        # Quality score from average article quality
        avg_quality = sum(article[4] for article in articles if article[4]) / len(articles)
        quality_score = avg_quality if avg_quality else 0.5
        
        # Source diversity score
        sources = set(article[2] for article in articles)
        diversity_score = min(len(sources) / 5.0, 1.0)  # Max at 5 different sources
        
        # Category relevance score
        category_matches = sum(1 for article in articles if article[5] == thread_info['category'])
        relevance_score = category_matches / len(articles) if articles else 0.0
        
        # Weighted combination
        significance = (
            article_count_score * 0.3 +
            quality_score * 0.3 +
            diversity_score * 0.2 +
            relevance_score * 0.2
        )
        
        return min(significance, 1.0)
    
    def _create_alert_data(self, thread_info: Dict[str, Any], articles: List, significance_score: float) -> Dict[str, Any]:
        """
        Create alert data structure.
        
        Args:
            thread_info: Thread information
            articles: List of recent articles
            significance_score: Calculated significance score
            
        Returns:
            Alert data dictionary
        """
        # Create article summaries
        article_summaries = []
        for article in articles:
            article_summaries.append({
                'id': article[0],
                'title': article[1],
                'source': article[2],
                'published_at': article[3].isoformat() if article[3] else None,
                'quality_score': float(article[4]) if article[4] else 0.0,
                'category': article[5],
                'assigned_at': article[6].isoformat() if article[6] else None
            })
        
        # Generate alert message
        sources = set(article[2] for article in articles)
        message = f"Found {len(articles)} new high-quality articles from {len(sources)} sources. "
        message += f"Average quality score: {sum(article[4] for article in articles if article[4]) / len(articles):.2f}. "
        message += f"Significance score: {significance_score:.2f}"
        
        # Generate context summary
        context_summary = f"Recent developments in {thread_info['category']} category. "
        context_summary += f"Key sources: {', '.join(list(sources)[:3])}. "
        context_summary += f"Articles span from {min(article[3] for article in articles if article[3]).strftime('%Y-%m-%d') if articles else 'recent'} to present."
        
        return {
            'thread_id': thread_info['id'],
            'alert_type': 'significant_update',
            'title': f"Significant Update: {thread_info['title']}",
            'message': message,
            'significance_score': significance_score,
            'article_count': len(articles),
            'new_articles': article_summaries,
            'context_summary': context_summary
        }
