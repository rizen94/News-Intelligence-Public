"""
RSS Service for News Intelligence System v3.1.0
Production-ready RSS feed management
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from database.connection import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class RSSService:
    def __init__(self, db_connection=None):
        """Initialize RSS service with optional database connection"""
        self.db_connection = db_connection
        self.logger = logging.getLogger(__name__)
    
    async def get_feeds(self, active_only: bool = False) -> Dict[str, Any]:
        """Get all RSS feeds"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                if active_only:
                    result = db.execute(text("""
                        SELECT id, name, url, last_fetched, created_at
                        FROM rss_feeds 
                        WHERE is_active = true
                        ORDER BY created_at DESC
                    """)).fetchall()
                else:
                    result = db.execute(text("""
                        SELECT id, name, url, last_fetched, created_at
                        FROM rss_feeds 
                        ORDER BY created_at DESC
                    """)).fetchall()
                
                feeds = []
                for row in result:
                    feeds.append({
                        "id": row[0],
                        "name": row[1],
                        "url": row[2],
                        "last_fetched": row[3].isoformat() if row[3] else None,
                        "created_at": row[4].isoformat() if row[4] else None
                    })
                
                return {"feeds": feeds}
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting RSS feeds: {e}")
            return {"feeds": [], "error": str(e)}
    
    async def get_stats_overview(self) -> Dict[str, Any]:
        """Get RSS feed statistics overview"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get total feeds count
                total_result = db.execute(text("SELECT COUNT(*) FROM rss_feeds")).fetchone()
                total_feeds = total_result[0] if total_result else 0
                
                # Get active feeds count
                active_result = db.execute(text("SELECT COUNT(*) FROM rss_feeds WHERE status = 'active'")).fetchone()
                active_feeds = active_result[0] if active_result else 0
                
                # Get feeds by status
                status_result = db.execute(text("""
                    SELECT status, COUNT(*) as count 
                    FROM rss_feeds 
                    GROUP BY status 
                    ORDER BY count DESC
                """)).fetchall()
                
                status_breakdown = [{"status": row[0], "count": row[1]} for row in status_result]
                
                return {
                    "total_feeds": total_feeds,
                    "active_feeds": active_feeds,
                    "status_breakdown": status_breakdown,
                    "status": "success"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting RSS stats: {e}")
            return {
                "total_feeds": 0,
                "active_feeds": 0,
                "status_breakdown": [],
                "error": str(e)
            }
    
    async def create_feed(self, feed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new RSS feed"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Handle both dict and Pydantic model
                if hasattr(feed_data, 'dict'):
                    data = feed_data.dict()
                else:
                    data = feed_data
                
                result = db.execute(text("""
                    INSERT INTO rss_feeds (name, url, description, tier, priority, language, country, 
                                         category, subcategory, is_active, status, update_frequency, 
                                         max_articles_per_update, created_at, updated_at)
                    VALUES (:name, :url, :description, :tier, :priority, :language, :country, 
                            :category, :subcategory, :is_active, :status, :update_frequency, 
                            :max_articles_per_update, :created_at, :updated_at)
                    RETURNING id
                """), {
                    "name": data.get("name"),
                    "url": data.get("url"),
                    "description": data.get("description"),
                    "tier": data.get("tier", 2),
                    "priority": data.get("priority", 5),
                    "language": data.get("language", "en"),
                    "country": data.get("country"),
                    "category": data.get("category"),
                    "subcategory": data.get("subcategory"),
                    "is_active": data.get("is_active", True),
                    "status": data.get("status", "active"),
                    "update_frequency": data.get("update_frequency", 30),
                    "max_articles_per_update": data.get("max_articles_per_update", 50),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                })
                
                feed_id = result.fetchone()[0]
                db.commit()
                
                return {
                    "id": feed_id,
                    "status": "created",
                    "message": "RSS feed created successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error creating RSS feed: {e}")
            return {"error": str(e)}
    
    async def update_feed(self, feed_id: str, feed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update RSS feed"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Handle both dict and Pydantic model
                if hasattr(feed_data, 'dict'):
                    data = feed_data.dict()
                else:
                    data = feed_data
                
                db.execute(text("""
                    UPDATE rss_feeds 
                    SET name = %s, url = %s, status = %s
                    WHERE id = %s
                """), (
                    data.get("name"),
                    data.get("url"),
                    data.get("status"),
                    feed_id
                ))
                db.commit()
                
                return {
                    "id": feed_id,
                    "status": "updated",
                    "message": "RSS feed updated successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error updating RSS feed {feed_id}: {e}")
            return {"error": str(e)}
    
    async def delete_feed(self, feed_id: str) -> Dict[str, Any]:
        """Delete RSS feed"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("DELETE FROM rss_feeds WHERE id = %s"), (feed_id,))
                db.commit()
                
                return {
                    "id": feed_id,
                    "status": "deleted",
                    "message": "RSS feed deleted successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error deleting RSS feed {feed_id}: {e}")
            return {"error": str(e)}
