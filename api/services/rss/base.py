"""
RSS Service Base - Feed Management
Core RSS feed CRUD operations, statistics, and configuration management
Consolidated from enhanced_rss_service.py
"""

import asyncio
import logging
import json
import feedparser
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from config.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class FeedTier(Enum):
    """RSS feed tier classification"""
    WIRE_SERVICES = 1  # Reuters, AP, AFP
    INSTITUTIONS = 2   # BBC, CNN, NYT
    SPECIALIZED = 3    # TechCrunch, Ars Technica


class FeedStatus(Enum):
    """RSS feed status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    WARNING = "warning"
    MAINTENANCE = "maintenance"


@dataclass
class FeedConfig:
    """Configuration for RSS feed management"""
    name: str
    url: str
    tier: int
    priority: int
    category: str
    language: str = "en"
    country: str = None
    description: str = None
    update_frequency: int = 30  # minutes
    max_articles: int = 50
    tags: List[str] = None
    custom_headers: Dict[str, str] = None
    filters: Dict[str, Any] = None


class BaseRSSService:
    """
    Base RSS Service - Core feed management operations
    
    Provides:
    - Feed CRUD operations
    - Feed statistics
    - Filtering configuration management
    - URL validation
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.filtering_config = None
        self._load_filtering_config()
    
    def _load_filtering_config(self):
        """Load global filtering configuration from database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT config_name, config_data 
                    FROM global_filtering_config 
                    WHERE is_active = true
                """)).fetchall()
                
                self.filtering_config = {}
                for row in result:
                    self.filtering_config[row[0]] = row[1]
                    
                self.logger.info(f"Loaded {len(self.filtering_config)} filtering configurations")
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error loading filtering config: {e}")
            self.filtering_config = {}
    
    async def create_feed(self, feed_config: FeedConfig) -> Dict[str, Any]:
        """Create a new RSS feed in the registry with URL validation"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Validate feed URL
                if not await self._validate_feed_url(feed_config.url):
                    return {"error": "Invalid or unreachable RSS feed URL"}
                
                # Insert feed
                result = db.execute(text("""
                    INSERT INTO rss_feeds (
                        name, url, description, tier, priority, language, country,
                        category, update_frequency, max_articles_per_update,
                        tags, custom_headers, filters
                    ) VALUES (
                        :name, :url, :description, :tier, :priority, :language, :country,
                        :category, :update_frequency, :max_articles,
                        :tags, :custom_headers, :filters
                    ) RETURNING id
                """), {
                    "name": feed_config.name,
                    "url": feed_config.url,
                    "description": feed_config.description,
                    "tier": feed_config.tier,
                    "priority": feed_config.priority,
                    "language": feed_config.language,
                    "country": feed_config.country,
                    "category": feed_config.category,
                    "update_frequency": feed_config.update_frequency,
                    "max_articles": feed_config.max_articles,
                    "tags": json.dumps(feed_config.tags or []),
                    "custom_headers": json.dumps(feed_config.custom_headers or {}),
                    "filters": json.dumps(feed_config.filters or {})
                })
                
                feed_id = result.fetchone()[0]
                db.commit()
                
                self.logger.info(f"Created RSS feed: {feed_config.name} (ID: {feed_id})")
                return {
                    "id": feed_id,
                    "status": "created",
                    "message": f"RSS feed '{feed_config.name}' created successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error creating RSS feed: {e}")
            return {"error": str(e)}
    
    async def get_feeds(self, 
                       active_only: bool = False,
                       tier: int = None,
                       category: str = None,
                       limit: int = 100,
                       offset: int = 0) -> Dict[str, Any]:
        """Get RSS feeds with filtering options"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Build query with filters
                where_conditions = []
                params = {}
                
                if active_only:
                    where_conditions.append("is_active = true")
                
                if tier is not None:
                    where_conditions.append("tier = :tier")
                    params["tier"] = tier
                
                if category:
                    where_conditions.append("category = :category")
                    params["category"] = category
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                query = f"""
                    SELECT id, feed_name, feed_url, description, tier, priority, language, country,
                           category, subcategory, is_active, status, update_frequency,
                           max_articles_per_update, success_rate, avg_response_time,
                           reliability_score, last_fetched_at, last_success, last_error_message,
                           warning_message, tags, custom_headers, filters,
                           created_at, updated_at
                    FROM rss_feeds 
                    WHERE {where_clause}
                    ORDER BY priority ASC, tier ASC, created_at DESC
                    LIMIT :limit OFFSET :offset
                """
                
                params.update({"limit": limit, "offset": offset})
                result = db.execute(text(query), params).fetchall()
                
                feeds = []
                for row in result:
                    feeds.append({
                        "id": row[0],
                        "name": row[1],
                        "url": row[2],
                        "description": row[3],
                        "tier": row[4],
                        "priority": row[5],
                        "language": row[6],
                        "country": row[7],
                        "category": row[8],
                        "subcategory": row[9],
                        "is_active": row[10],
                        "status": row[11],
                        "update_frequency": row[12],
                        "max_articles_per_update": row[13],
                        "success_rate": float(row[14]) if row[14] else 0.0,
                        "avg_response_time": row[15],
                        "reliability_score": float(row[16]) if row[16] else 0.0,
                        "last_fetched": row[17].isoformat() if row[17] else None,
                        "last_success": row[18].isoformat() if row[18] else None,
                        "last_error": row[19],
                        "warning_message": row[20],
                        "tags": json.loads(row[21]) if row[21] else [],
                        "custom_headers": json.loads(row[22]) if row[22] else {},
                        "filters": json.loads(row[23]) if row[23] else {},
                        "created_at": row[24].isoformat() if row[24] else None,
                        "updated_at": row[25].isoformat() if row[25] else None
                    })
                
                return {"feeds": feeds, "count": len(feeds)}
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting RSS feeds: {e}")
            return {"feeds": [], "error": str(e)}
    
    async def update_feed(self, feed_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update RSS feed configuration with dynamic field updates"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Build dynamic update query
                update_fields = []
                params = {"feed_id": feed_id}
                
                allowed_fields = [
                    "name", "url", "description", "tier", "priority", "language", "country",
                    "category", "subcategory", "is_active", "status", "update_frequency",
                    "max_articles_per_update", "tags", "custom_headers", "filters"
                ]
                
                for field, value in updates.items():
                    if field in allowed_fields:
                        if field in ["tags", "custom_headers", "filters"]:
                            update_fields.append(f"{field} = :{field}")
                            params[field] = json.dumps(value)
                        else:
                            update_fields.append(f"{field} = :{field}")
                            params[field] = value
                
                if not update_fields:
                    return {"error": "No valid fields to update"}
                
                query = f"""
                    UPDATE rss_feeds 
                    SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :feed_id
                """
                
                result = db.execute(text(query), params)
                db.commit()
                
                if result.rowcount == 0:
                    return {"error": "Feed not found"}
                
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
    
    async def delete_feed(self, feed_id: int) -> Dict[str, Any]:
        """Delete RSS feed and associated data"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get feed name for logging
                feed_result = db.execute(text("SELECT name FROM rss_feeds WHERE id = :feed_id"), 
                                       {"feed_id": feed_id}).fetchone()
                
                if not feed_result:
                    return {"error": "Feed not found"}
                
                feed_name = feed_result[0]
                
                # Delete feed and cascade to related tables
                db.execute(text("DELETE FROM rss_feeds WHERE id = :feed_id"), {"feed_id": feed_id})
                db.commit()
                
                self.logger.info(f"Deleted RSS feed: {feed_name} (ID: {feed_id})")
                return {
                    "id": feed_id,
                    "status": "deleted",
                    "message": f"RSS feed '{feed_name}' deleted successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error deleting RSS feed {feed_id}: {e}")
            return {"error": str(e)}
    
    async def _validate_feed_url(self, url: str) -> bool:
        """Validate that the RSS feed URL is accessible and contains valid RSS content"""
        try:
            headers = {
                'User-Agent': 'News Intelligence RSS Validator/1.0'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Try to parse as RSS
            feed = feedparser.parse(response.content)
            
            # Check if it's a valid RSS feed
            if hasattr(feed, 'version') and feed.version:
                return True
            
            return False
        except Exception as e:
            self.logger.warning(f"Invalid RSS feed URL {url}: {e}")
            return False
    
    async def get_feed_stats(self, feed_id: int = None) -> Dict[str, Any]:
        """Get comprehensive statistics for RSS feeds"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                if feed_id:
                    # Single feed stats
                    result = db.execute(text("""
                        SELECT 
                            f.name, f.tier, f.category, f.status, f.success_rate,
                            f.avg_response_time, f.reliability_score,
                            COUNT(a.id) as total_articles,
                            COUNT(CASE WHEN a.created_at >= CURRENT_DATE THEN a.id END) as articles_today,
                            COUNT(CASE WHEN a.created_at >= CURRENT_DATE - INTERVAL '7 days' THEN a.id END) as articles_this_week,
                            MAX(a.created_at) as last_article_date
                        FROM rss_feeds f
                        LEFT JOIN articles a ON f.feed_name = a.source_domain
                        WHERE f.id = :feed_id
                        GROUP BY f.id, f.name, f.tier, f.category, f.status, f.success_rate, f.avg_response_time, f.reliability_score
                    """), {"feed_id": feed_id}).fetchone()
                    
                    if not result:
                        return {"error": "Feed not found"}
                    
                    return {
                        "feed_id": feed_id,
                        "name": result[0],
                        "tier": result[1],
                        "category": result[2],
                        "status": result[3],
                        "success_rate": float(result[4]) if result[4] else 0.0,
                        "avg_response_time": result[5],
                        "reliability_score": float(result[6]) if result[6] else 0.0,
                        "total_articles": result[7],
                        "articles_today": result[8],
                        "articles_this_week": result[9],
                        "last_article_date": result[10].isoformat() if result[10] else None
                    }
                else:
                    # Overall stats
                    total_feeds = db.execute(text("SELECT COUNT(*) FROM rss_feeds")).fetchone()[0]
                    active_feeds = db.execute(text("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")).fetchone()[0]
                    
                    tier_stats = db.execute(text("""
                        SELECT tier, COUNT(*) as count, AVG(success_rate) as avg_success_rate
                        FROM rss_feeds 
                        WHERE is_active = true
                        GROUP BY tier
                        ORDER BY tier
                    """)).fetchall()
                    
                    category_stats = db.execute(text("""
                        SELECT category, COUNT(*) as count, AVG(success_rate) as avg_success_rate
                        FROM rss_feeds 
                        WHERE is_active = true
                        GROUP BY category
                        ORDER BY count DESC
                    """)).fetchall()
                    
                    return {
                        "total_feeds": total_feeds,
                        "active_feeds": active_feeds,
                        "tier_breakdown": [{"tier": row[0], "count": row[1], "avg_success_rate": float(row[2]) if row[2] else 0.0} for row in tier_stats],
                        "category_breakdown": [{"category": row[0], "count": row[1], "avg_success_rate": float(row[2]) if row[2] else 0.0} for row in category_stats]
                    }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting feed stats: {e}")
            return {"error": str(e)}
    
    async def get_stats_overview(self) -> Dict[str, Any]:
        """Get RSS feed statistics overview (backward compatibility)"""
        stats = await self.get_feed_stats()
        if "error" in stats:
            return {
                "total_feeds": 0,
                "active_feeds": 0,
                "status_breakdown": [],
                "status": "error",
                "error": stats["error"]
            }
        
        # Transform to old format for backward compatibility
        return {
            "total_feeds": stats.get("total_feeds", 0),
            "active_feeds": stats.get("active_feeds", 0),
            "status_breakdown": stats.get("category_breakdown", []),
            "status": "success"
        }
    
    async def get_filtering_config(self) -> Dict[str, Any]:
        """Get current filtering configuration"""
        return self.filtering_config or {}
    
    async def update_filtering_config(self, config_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update global filtering configuration"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    INSERT INTO global_filtering_config (config_name, config_data)
                    VALUES (:config_name, :config_data)
                    ON CONFLICT (config_name) 
                    DO UPDATE SET config_data = :config_data, updated_at = CURRENT_TIMESTAMP
                """), {
                    "config_name": config_name,
                    "config_data": json.dumps(config_data)
                })
                db.commit()
                
                # Reload config
                self._load_filtering_config()
                
                return {
                    "status": "updated",
                    "message": f"Filtering configuration '{config_name}' updated successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error updating filtering config: {e}")
            return {"error": str(e)}

