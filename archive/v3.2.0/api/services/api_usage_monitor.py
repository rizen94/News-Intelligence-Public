"""
API Usage Monitor for News Intelligence System
Tracks API usage to stay within free tier limits
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os

logger = logging.getLogger(__name__)

class APIUsageMonitor:
    """Monitor API usage to prevent exceeding free tier limits"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        
        # Free tier limits (requests per day)
        self.daily_limits = {
            'wikipedia': 10000,  # Very generous limit
            'gdelt': 10000,      # Very generous limit
            'newsapi': 1000,     # Actual NewsAPI free tier
            'rag_context': 1000  # Custom limit for RAG operations
        }
        
        # Rate limiting (requests per minute)
        self.rate_limits = {
            'wikipedia': 60,     # 1 per second
            'gdelt': 30,         # 1 per 2 seconds
            'newsapi': 30,       # 1 per 2 seconds
            'rag_context': 10    # 1 per 6 seconds
        }
        
        # Current usage tracking
        self.current_usage = {}
        self.last_reset = {}
        
    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    async def check_rate_limit(self, service: str) -> bool:
        """Check if service is within rate limits"""
        try:
            current_time = time.time()
            minute_key = f"{service}_{int(current_time // 60)}"
            
            if minute_key not in self.current_usage:
                self.current_usage[minute_key] = 0
            
            rate_limit = self.rate_limits.get(service, 60)
            
            if self.current_usage[minute_key] >= rate_limit:
                logger.warning(f"Rate limit exceeded for {service}: {self.current_usage[minute_key]}/{rate_limit}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow on error
    
    async def check_daily_limit(self, service: str) -> bool:
        """Check if service is within daily limits"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get today's usage
            cursor.execute("""
                SELECT COUNT(*) as request_count
                FROM api_usage_tracking 
                WHERE service = %s 
                AND created_at >= CURRENT_DATE
            """, (service,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            current_usage = result['request_count'] if result else 0
            daily_limit = self.daily_limits.get(service, 1000)
            
            if current_usage >= daily_limit:
                logger.warning(f"Daily limit exceeded for {service}: {current_usage}/{daily_limit}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking daily limit: {e}")
            return True  # Allow on error
    
    async def record_api_call(self, service: str, endpoint: str, 
                            response_size: int = 0, processing_time_ms: int = 0, 
                            success: bool = True, error_message: str = None) -> None:
        """Record API call for monitoring"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO api_usage_tracking 
                (service, endpoint, response_size, processing_time_ms, success, error_message)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (service, endpoint, response_size, processing_time_ms, success, error_message))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Update in-memory tracking
            current_time = time.time()
            minute_key = f"{service}_{int(current_time // 60)}"
            if minute_key not in self.current_usage:
                self.current_usage[minute_key] = 0
            self.current_usage[minute_key] += 1
            
        except Exception as e:
            logger.error(f"Error recording API call: {e}")
    
    async def get_usage_stats(self, service: str = None, days: int = 7) -> Dict[str, Any]:
        """Get usage statistics"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if service:
                # Get stats for specific service
                cursor.execute("""
                    SELECT 
                        service,
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN success = true THEN 1 END) as successful_requests,
                        COUNT(CASE WHEN success = false THEN 1 END) as failed_requests,
                        AVG(response_size) as avg_response_size,
                        AVG(processing_time_ms) as avg_processing_time,
                        MAX(created_at) as last_request
                    FROM api_usage_tracking 
                    WHERE service = %s 
                    AND created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY service
                """, (service, days))
            else:
                # Get stats for all services
                cursor.execute("""
                    SELECT 
                        service,
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN success = true THEN 1 END) as successful_requests,
                        COUNT(CASE WHEN success = false THEN 1 END) as failed_requests,
                        AVG(response_size) as avg_response_size,
                        AVG(processing_time_ms) as avg_processing_time,
                        MAX(created_at) as last_request
                    FROM api_usage_tracking 
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY service
                    ORDER BY total_requests DESC
                """, (days,))
            
            stats = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Add limit information
            result = {
                'usage_stats': [dict(row) for row in stats],
                'daily_limits': self.daily_limits,
                'rate_limits': self.rate_limits,
                'period_days': days
            }
            
            # Add usage percentages
            for stat in result['usage_stats']:
                service_name = stat['service']
                daily_limit = self.daily_limits.get(service_name, 1000)
                stat['usage_percentage'] = (stat['total_requests'] / daily_limit) * 100
                stat['remaining_requests'] = max(0, daily_limit - stat['total_requests'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return {'error': str(e)}
    
    async def get_service_status(self, service: str) -> Dict[str, Any]:
        """Get current status of a service"""
        try:
            # Check rate limit
            rate_ok = await self.check_rate_limit(service)
            
            # Check daily limit
            daily_ok = await self.check_daily_limit(service)
            
            # Get current usage
            stats = await self.get_usage_stats(service, 1)  # Today only
            today_usage = stats['usage_stats'][0] if stats['usage_stats'] else {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0
            }
            
            return {
                'service': service,
                'rate_limit_ok': rate_ok,
                'daily_limit_ok': daily_ok,
                'status': 'healthy' if (rate_ok and daily_ok) else 'limited',
                'today_usage': today_usage,
                'daily_limit': self.daily_limits.get(service, 1000),
                'rate_limit': self.rate_limits.get(service, 60)
            }
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {'error': str(e)}

# Global instance
_usage_monitor = None

def get_usage_monitor() -> APIUsageMonitor:
    """Get global usage monitor instance"""
    global _usage_monitor
    if _usage_monitor is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        _usage_monitor = APIUsageMonitor(db_config)
    return _usage_monitor


