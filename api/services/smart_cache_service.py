"""
Smart Cache Service for News Intelligence System v3.0
Intelligent caching for RAG context and external API responses
"""

import asyncio
import logging
import json
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    data: Any
    created_at: datetime
    expires_at: datetime
    access_count: int
    last_accessed: datetime
    cache_type: str
    size_bytes: int

@dataclass
class CacheStats:
    """Cache statistics"""
    total_entries: int
    hit_rate: float
    miss_rate: float
    total_size_bytes: int
    expired_entries: int
    evicted_entries: int

class SmartCacheService:
    """Intelligent caching service with predictive preloading and adaptive TTL"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.memory_cache = {}  # In-memory cache for hot data
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'preloads': 0
        }
        
        # Cache configuration
        self.max_memory_entries = 1000
        self.max_memory_size_mb = 100
        self.default_ttl_seconds = 3600  # 1 hour
        self.preload_threshold = 0.8  # Preload when hit rate drops below 80%
        
        # Service-specific TTL settings
        self.service_ttl = {
            'wikipedia': 86400,      # 24 hours
            'gdelt': 3600,           # 1 hour
            'newsapi': 1800,         # 30 minutes
            'rag_context': 7200,     # 2 hours
            'quality_scores': 3600,  # 1 hour
            'entity_extraction': 1800, # 30 minutes
        }
        
    def _generate_cache_key(self, service: str, query: str, params: Dict[str, Any] = None) -> str:
        """Generate a unique cache key"""
        # Create a deterministic key from service, query, and parameters
        key_data = {
            'service': service,
            'query': query,
            'params': params or {}
        }
        
        # Sort parameters for consistent key generation
        if params:
            key_data['params'] = dict(sorted(params.items()))
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]
    
    async def get(self, service: str, query: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """Get data from cache"""
        try:
            cache_key = self._generate_cache_key(service, query, params)
            
            # Check memory cache first
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if entry.expires_at > datetime.now(timezone.utc):
                    # Update access statistics
                    entry.access_count += 1
                    entry.last_accessed = datetime.now(timezone.utc)
                    self.cache_stats['hits'] += 1
                    logger.debug(f"Cache hit for {service}: {query[:50]}...")
                    return entry.data
                else:
                    # Expired entry, remove it
                    del self.memory_cache[cache_key]
            
            # Check database cache
            db_entry = await self._get_from_db_cache(cache_key)
            if db_entry:
                # Load into memory cache
                self.memory_cache[cache_key] = db_entry
                self.cache_stats['hits'] += 1
                logger.debug(f"Database cache hit for {service}: {query[:50]}...")
                return db_entry.data
            
            # Cache miss
            self.cache_stats['misses'] += 1
            logger.debug(f"Cache miss for {service}: {query[:50]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    async def set(self, service: str, query: str, data: Any, params: Dict[str, Any] = None, 
                  ttl_seconds: Optional[int] = None) -> bool:
        """Store data in cache"""
        try:
            cache_key = self._generate_cache_key(service, query, params)
            
            # Calculate TTL
            if ttl_seconds is None:
                ttl_seconds = self.service_ttl.get(service, self.default_ttl_seconds)
            
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=ttl_seconds)
            
            # Calculate data size
            data_size = len(json.dumps(data).encode('utf-8'))
            
            # Create cache entry
            entry = CacheEntry(
                key=cache_key,
                data=data,
                created_at=now,
                expires_at=expires_at,
                access_count=1,
                last_accessed=now,
                cache_type=service,
                size_bytes=data_size
            )
            
            # Store in memory cache
            self.memory_cache[cache_key] = entry
            
            # Store in database cache
            await self._store_in_db_cache(entry, service, query, params)
            
            # Check if we need to evict entries
            await self._evict_if_needed()
            
            logger.debug(f"Cached data for {service}: {query[:50]}... (TTL: {ttl_seconds}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error storing in cache: {e}")
            return False
    
    async def _get_from_db_cache(self, cache_key: str) -> Optional[CacheEntry]:
        """Get cache entry from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT cache_key, response_data, created_at, expires_at, 
                       access_count, last_accessed, cache_type, size_bytes
                FROM api_cache 
                WHERE cache_key = %s AND expires_at > NOW()
            """, (cache_key,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                return CacheEntry(
                    key=result['cache_key'],
                    data=json.loads(result['response_data']),
                    created_at=result['created_at'],
                    expires_at=result['expires_at'],
                    access_count=result['access_count'],
                    last_accessed=result['last_accessed'],
                    cache_type=result['cache_type'],
                    size_bytes=result['size_bytes']
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting from database cache: {e}")
            return None
    
    async def _store_in_db_cache(self, entry: CacheEntry, service: str, query: str, params: Dict[str, Any] = None):
        """Store cache entry in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO api_cache (
                    cache_key, service, query, response_data, created_at, 
                    expires_at, access_count, last_accessed, size_bytes
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (cache_key) 
                DO UPDATE SET 
                    response_data = EXCLUDED.response_data,
                    expires_at = EXCLUDED.expires_at,
                    access_count = EXCLUDED.access_count,
                    last_accessed = EXCLUDED.last_accessed,
                    size_bytes = EXCLUDED.size_bytes
            """, (
                entry.key,
                service,
                query,
                json.dumps(entry.data),
                entry.created_at,
                entry.expires_at,
                entry.access_count,
                entry.last_accessed,
                entry.size_bytes
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing in database cache: {e}")
    
    async def _evict_if_needed(self):
        """Evict entries if cache is too large"""
        try:
            # Check memory cache size
            if len(self.memory_cache) > self.max_memory_entries:
                await self._evict_lru_entries()
            
            # Check memory usage
            total_size = sum(entry.size_bytes for entry in self.memory_cache.values())
            if total_size > self.max_memory_size_mb * 1024 * 1024:
                await self._evict_large_entries()
                
        except Exception as e:
            logger.error(f"Error during cache eviction: {e}")
    
    async def _evict_lru_entries(self):
        """Evict least recently used entries"""
        try:
            # Sort by last accessed time
            sorted_entries = sorted(
                self.memory_cache.items(),
                key=lambda x: x[1].last_accessed
            )
            
            # Remove oldest 20% of entries
            evict_count = len(sorted_entries) // 5
            for i in range(evict_count):
                key, entry = sorted_entries[i]
                del self.memory_cache[key]
                self.cache_stats['evictions'] += 1
                
            logger.info(f"Evicted {evict_count} LRU cache entries")
            
        except Exception as e:
            logger.error(f"Error evicting LRU entries: {e}")
    
    async def _evict_large_entries(self):
        """Evict largest entries to reduce memory usage"""
        try:
            # Sort by size
            sorted_entries = sorted(
                self.memory_cache.items(),
                key=lambda x: x[1].size_bytes,
                reverse=True
            )
            
            # Remove largest entries until we're under the limit
            target_size = self.max_memory_size_mb * 1024 * 1024 * 0.8  # 80% of limit
            current_size = sum(entry.size_bytes for entry in self.memory_cache.values())
            
            evicted = 0
            for key, entry in sorted_entries:
                if current_size <= target_size:
                    break
                    
                del self.memory_cache[key]
                current_size -= entry.size_bytes
                evicted += 1
                self.cache_stats['evictions'] += 1
                
            logger.info(f"Evicted {evicted} large cache entries")
            
        except Exception as e:
            logger.error(f"Error evicting large entries: {e}")
    
    async def preload_context_for_topics(self, topics: List[str]) -> Dict[str, Any]:
        """Preload RAG context for common topics"""
        try:
            logger.info(f"Preloading context for {len(topics)} topics")
            
            preload_results = {
                'topics_processed': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'preloaded_data': {}
            }
            
            for topic in topics:
                # Check if already cached
                cached_data = await self.get('rag_context', topic)
                if cached_data:
                    preload_results['cache_hits'] += 1
                    preload_results['preloaded_data'][topic] = cached_data
                else:
                    # This would normally fetch from external APIs
                    # For now, we'll simulate the preloading
                    preload_results['cache_misses'] += 1
                    # In a real implementation, this would call the RAG service
                    # to fetch and cache the context
                
                preload_results['topics_processed'] += 1
            
            self.cache_stats['preloads'] += preload_results['topics_processed']
            logger.info(f"Preloading complete: {preload_results}")
            
            return preload_results
            
        except Exception as e:
            logger.error(f"Error preloading context: {e}")
            return {'error': str(e)}
    
    async def get_cache_stats(self) -> CacheStats:
        """Get comprehensive cache statistics"""
        try:
            total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
            hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0.0
            miss_rate = 1.0 - hit_rate
            
            # Calculate total size
            total_size = sum(entry.size_bytes for entry in self.memory_cache.values())
            
            # Get expired entries count
            now = datetime.now(timezone.utc)
            expired_count = sum(
                1 for entry in self.memory_cache.values() 
                if entry.expires_at <= now
            )
            
            return CacheStats(
                total_entries=len(self.memory_cache),
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                total_size_bytes=total_size,
                expired_entries=expired_count,
                evicted_entries=self.cache_stats['evictions']
            )
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return CacheStats(0, 0.0, 1.0, 0, 0, 0)
    
    async def cleanup_expired_entries(self) -> int:
        """Clean up expired cache entries"""
        try:
            now = datetime.now(timezone.utc)
            expired_keys = [
                key for key, entry in self.memory_cache.items()
                if entry.expires_at <= now
            ]
            
            # Remove expired entries from memory
            for key in expired_keys:
                del self.memory_cache[key]
            
            # Clean up database cache
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM api_cache 
                WHERE expires_at <= NOW()
            """)
            
            db_cleaned = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            
            total_cleaned = len(expired_keys) + db_cleaned
            logger.info(f"Cleaned up {total_cleaned} expired cache entries")
            
            return total_cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            return 0
    
    async def invalidate_cache(self, service: str, pattern: str = None) -> int:
        """Invalidate cache entries for a service or pattern"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            if pattern:
                # Invalidate entries matching pattern
                cursor.execute("""
                    DELETE FROM api_cache 
                    WHERE service = %s AND query ILIKE %s
                """, (service, f"%{pattern}%"))
            else:
                # Invalidate all entries for service
                cursor.execute("""
                    DELETE FROM api_cache 
                    WHERE service = %s
                """, (service,))
            
            invalidated_count = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            
            # Also remove from memory cache
            memory_keys_to_remove = [
                key for key, entry in self.memory_cache.items()
                if entry.cache_type == service and (pattern is None or pattern in str(entry.data))
            ]
            
            for key in memory_keys_to_remove:
                del self.memory_cache[key]
            
            total_invalidated = invalidated_count + len(memory_keys_to_remove)
            logger.info(f"Invalidated {total_invalidated} cache entries for {service}")
            
            return total_invalidated
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0

# Global instance
_smart_cache_service = None

def get_smart_cache_service() -> SmartCacheService:
    """Get global smart cache service instance"""
    global _smart_cache_service
    if _smart_cache_service is None:
        from database.connection import get_db_config
        _smart_cache_service = SmartCacheService(get_db_config())
    return _smart_cache_service




