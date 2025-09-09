"""
API Cache Service for News Intelligence System
Implements caching for external API calls to reduce costs and improve performance
"""

import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os

logger = logging.getLogger(__name__)

class APICacheService:
    """Service for caching external API responses"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.cache_durations = {
            'wikipedia': 24 * 60 * 60,  # 24 hours
            'gdelt': 60 * 60,           # 1 hour
            'newsapi': 30 * 60,         # 30 minutes
            'rag_context': 6 * 60 * 60  # 6 hours
        }
        
    def _get_cache_key(self, service: str, query: str) -> str:
        """Generate cache key for API call"""
        return hashlib.md5(f"{service}:{query}".encode()).hexdigest()
    
    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    async def get_cached_response(self, service: str, query: str) -> Optional[Dict[str, Any]]:
        """Get cached API response if available and not expired"""
        try:
            cache_key = self._get_cache_key(service, query)
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT response_data, created_at 
                FROM api_cache 
                WHERE cache_key = %s AND service = %s
                ORDER BY created_at DESC 
                LIMIT 1
            """, (cache_key, service))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                # Check if cache is still valid
                cache_age = time.time() - result['created_at'].timestamp()
                max_age = self.cache_durations.get(service, 3600)
                
                if cache_age < max_age:
                    logger.info(f"Cache hit for {service}: {query[:50]}...")
                    return json.loads(result['response_data'])
                else:
                    logger.info(f"Cache expired for {service}: {query[:50]}...")
                    return None
            else:
                logger.info(f"Cache miss for {service}: {query[:50]}...")
                return None
                
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None
    
    async def cache_response(self, service: str, query: str, response_data: Dict[str, Any]) -> None:
        """Cache API response"""
        try:
            cache_key = self._get_cache_key(service, query)
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO api_cache (cache_key, service, query, response_data, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (cache_key, service) 
                DO UPDATE SET 
                    response_data = EXCLUDED.response_data,
                    created_at = EXCLUDED.created_at
            """, (cache_key, service, query, json.dumps(response_data), datetime.now()))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Cached response for {service}: {query[:50]}...")
            
        except Exception as e:
            logger.error(f"Error caching response: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get cache stats by service
            cursor.execute("""
                SELECT 
                    service,
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '1 hour' THEN 1 END) as recent_entries,
                    AVG(LENGTH(response_data::text)) as avg_response_size,
                    MAX(created_at) as last_cached
                FROM api_cache 
                GROUP BY service
                ORDER BY total_entries DESC
            """)
            
            stats = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return {
                'cache_stats': [dict(row) for row in stats],
                'cache_durations': self.cache_durations,
                'total_services': len(stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    async def clear_expired_cache(self) -> int:
        """Clear expired cache entries"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Clear expired entries for each service
            total_cleared = 0
            for service, max_age in self.cache_durations.items():
                cursor.execute("""
                    DELETE FROM api_cache 
                    WHERE service = %s AND created_at < NOW() - INTERVAL '%s seconds'
                """, (service, max_age))
                
                cleared = cursor.rowcount
                total_cleared += cleared
                logger.info(f"Cleared {cleared} expired entries for {service}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return total_cleared
            
        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")
            return 0

# Global instance
_cache_service = None

def get_cache_service() -> APICacheService:
    """Get global cache service instance"""
    global _cache_service
    if _cache_service is None:
        from database.connection import get_db_config
        db_config = get_db_config()
        _cache_service = APICacheService(db_config)
    return _cache_service
