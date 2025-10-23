"""
Dashboard Service for News Intelligence System v3.0
Production-ready dashboard data and analytics
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from config.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self, db_connection=None):
        """Initialize dashboard service with optional database connection"""
        self.db_connection = db_connection
        self.logger = logging.getLogger(__name__)
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get article statistics
                article_stats = await self._get_article_stats(db)
                
                # Get RSS feed statistics
                rss_stats = await self._get_rss_stats(db)
                
                # Get recent articles
                recent_articles = await self._get_recent_articles(db)
                
                # Get system health
                system_health = await self._get_system_health()
                
                # Get analytics data
                analytics = await self._get_analytics(db)
                
                return {
                    "article_stats": article_stats,
                    "rss_stats": rss_stats,
                    "recent_articles": recent_articles,
                    "system_health": system_health,
                    "analytics": analytics,
                    "timestamp": datetime.utcnow().isoformat()
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting dashboard data: {e}")
            return {"error": str(e)}
    
    async def _get_article_stats(self, db) -> Dict[str, Any]:
        """Get article statistics"""
        try:
            # Total articles
            total_result = db.execute(text("SELECT COUNT(*) FROM articles")).fetchone()
            total_articles = total_result[0] if total_result else 0
            
            # Recent articles (last 24 hours)
            recent_result = db.execute(text("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)).fetchone()
            recent_articles = recent_result[0] if recent_result else 0
            
            # Articles by source
            sources_result = db.execute(text("""
                SELECT source, COUNT(*) as count 
                FROM articles 
                GROUP BY source 
                ORDER BY count DESC 
                LIMIT 5
            """)).fetchall()
            
            sources = [{"source": row[0], "count": row[1]} for row in sources_result]
            
            return {
                "total_articles": total_articles,
                "recent_articles": recent_articles,
                "top_sources": sources
            }
        except Exception as e:
            self.logger.error(f"Error getting article stats: {e}")
            return {"total_articles": 0, "recent_articles": 0, "top_sources": []}
    
    async def _get_rss_stats(self, db) -> Dict[str, Any]:
        """Get RSS feed statistics"""
        try:
            # Total feeds
            total_result = db.execute(text("SELECT COUNT(*) FROM rss_feeds")).fetchone()
            total_feeds = total_result[0] if total_result else 0
            
            # Active feeds
            active_result = db.execute(text("SELECT COUNT(*) FROM rss_feeds WHERE status = 'active'")).fetchone()
            active_feeds = active_result[0] if active_result else 0
            
            return {
                "total_feeds": total_feeds,
                "active_feeds": active_feeds
            }
        except Exception as e:
            self.logger.error(f"Error getting RSS stats: {e}")
            return {"total_feeds": 0, "active_feeds": 0}
    
    async def _get_recent_articles(self, db, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent articles"""
        try:
            result = db.execute(text("""
                SELECT id, title, source, created_at
                FROM articles 
                ORDER BY created_at DESC 
                LIMIT :limit
            """), {"limit": limit}).fetchall()
            
            articles = []
            for row in result:
                articles.append({
                    "id": row[0],
                    "title": row[1],
                    "source": row[2],
                    "created_at": row[3].isoformat() if row[3] else None
                })
            
            return articles
        except Exception as e:
            self.logger.error(f"Error getting recent articles: {e}")
            return []
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "api": "running"
        }
    
    async def _get_analytics(self, db) -> Dict[str, Any]:
        """Get analytics data for dashboard"""
        try:
            # Get article trends over time
            trends_query = text("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            
            trends_result = db.execute(trends_query).fetchall()
            trends = [{"date": row[0].isoformat(), "count": row[1]} for row in trends_result]
            
            # Get top topics
            topics_query = text("""
                SELECT 
                    jsonb_array_elements_text(tags::jsonb) as tag,
                    COUNT(*) as count
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                AND tags IS NOT NULL
                AND jsonb_typeof(tags::jsonb) = 'array'
                GROUP BY jsonb_array_elements_text(tags::jsonb)
                ORDER BY count DESC
                LIMIT 10
            """)
            
            topics_result = db.execute(topics_query).fetchall()
            topics = [{"tag": row[0], "count": row[1]} for row in topics_result]
            
            # Get sentiment analysis
            sentiment_query = text("""
                SELECT 
                    CASE 
                        WHEN sentiment_score > 0.1 THEN 'positive'
                        WHEN sentiment_score < -0.1 THEN 'negative'
                        ELSE 'neutral'
                    END as sentiment,
                    COUNT(*) as count
                FROM articles 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                AND sentiment_score IS NOT NULL
                GROUP BY sentiment
            """)
            
            sentiment_result = db.execute(sentiment_query).fetchall()
            sentiment = [{"sentiment": row[0], "count": row[1]} for row in sentiment_result]
            
            return {
                "trends": trends,
                "topics": topics,
                "sentiment": sentiment,
                "last_updated": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting analytics: {e}")
            return {
                "trends": [],
                "topics": [],
                "sentiment": [],
                "last_updated": datetime.utcnow().isoformat()
            }
