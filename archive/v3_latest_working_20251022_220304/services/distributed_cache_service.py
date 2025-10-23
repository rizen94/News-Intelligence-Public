"""
Distributed Cache Service for News Intelligence System v3.0
Distributed caching with cache warming and consistency management
"""

import asyncio
import logging
import json
import hashlib
import time
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

@dataclass
class CacheNode:
    """Cache node information"""
    node_id: str
    host: str
    port: int
    status: str  # 'active', 'inactive', 'maintenance'
    last_heartbeat: datetime
    cache_size: int
    hit_rate: float

@dataclass
class CacheConsistencyInfo:
    """Cache consistency information"""
    key: str
    version: int
    last_updated: datetime
    nodes: List[str]
    is_consistent: bool

class DistributedCacheService:
    """Distributed cache service with consistency management and cache warming"""
    
    def __init__(self, db_config: Dict[str, str], node_id: str = None):
        self.db_config = db_config
        self.node_id = node_id or self._generate_node_id()
        self.local_cache = {}
        self.cache_nodes = {}
        self.consistency_map = {}
        self.warming_queue = asyncio.Queue()
        self.heartbeat_interval = 30  # seconds
        self.consistency_check_interval = 60  # seconds
        self.warming_batch_size = 10
        
        # Cache warming patterns
        self.warming_patterns = {
            'common_topics': ['artificial intelligence', 'climate change', 'economy', 'politics', 'technology'],
            'trending_entities': ['United States', 'China', 'Europe', 'COVID-19', 'inflation'],
            'recent_queries': []
        }
        
        # Start background tasks
        asyncio.create_task(self._heartbeat_task())
        asyncio.create_task(self._consistency_check_task())
        asyncio.create_task(self._cache_warming_task())
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID"""
        return f"node_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    async def get(self, key: str, service: str = 'default') -> Optional[Any]:
        """Get value from distributed cache"""
        try:
            # Check local cache first
            local_key = f"{service}:{key}"
            if local_key in self.local_cache:
                entry = self.local_cache[local_key]
                if entry['expires_at'] > datetime.now(timezone.utc):
                    # Update access statistics
                    entry['access_count'] += 1
                    entry['last_accessed'] = datetime.now(timezone.utc)
                    return entry['data']
                else:
                    # Expired entry
                    del self.local_cache[local_key]
            
            # Check other nodes
            for node_id, node in self.cache_nodes.items():
                if node.status != 'active':
                    continue
                
                try:
                    value = await self._get_from_node(node, key, service)
                    if value is not None:
                        # Store in local cache
                        await self._store_local(key, service, value)
                        return value
                except Exception as e:
                    logger.warning(f"Error getting from node {node_id}: {e}")
                    continue
            
            # Not found in any cache
            return None
            
        except Exception as e:
            logger.error(f"Error getting from distributed cache: {e}")
            return None
    
    async def set(self, key: str, value: Any, service: str = 'default', ttl_seconds: int = 3600) -> bool:
        """Set value in distributed cache"""
        try:
            # Store locally
            await self._store_local(key, service, value, ttl_seconds)
            
            # Replicate to other active nodes
            replication_tasks = []
            for node_id, node in self.cache_nodes.items():
                if node.status == 'active' and node_id != self.node_id:
                    task = self._replicate_to_node(node, key, service, value, ttl_seconds)
                    replication_tasks.append(task)
            
            # Wait for replication (don't fail if some nodes are down)
            if replication_tasks:
                await asyncio.gather(*replication_tasks, return_exceptions=True)
            
            # Update consistency map
            await self._update_consistency_map(key, service)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting in distributed cache: {e}")
            return False
    
    async def _store_local(self, key: str, service: str, value: Any, ttl_seconds: int = 3600):
        """Store value in local cache"""
        local_key = f"{service}:{key}"
        now = datetime.now(timezone.utc)
        
        self.local_cache[local_key] = {
            'data': value,
            'created_at': now,
            'expires_at': now + timedelta(seconds=ttl_seconds),
            'access_count': 1,
            'last_accessed': now,
            'size_bytes': len(json.dumps(value).encode('utf-8'))
        }
    
    async def _get_from_node(self, node: CacheNode, key: str, service: str) -> Optional[Any]:
        """Get value from specific node (simplified - in production, use actual network calls)"""
        # This is a simplified implementation
        # In production, you would make actual HTTP/gRPC calls to the node
        try:
            # Simulate network call
            await asyncio.sleep(0.01)  # Simulate network latency
            
            # For now, return None (simulating cache miss)
            # In production, this would query the actual node
            return None
            
        except Exception as e:
            logger.warning(f"Error getting from node {node.node_id}: {e}")
            return None
    
    async def _replicate_to_node(self, node: CacheNode, key: str, service: str, value: Any, ttl_seconds: int):
        """Replicate value to specific node (simplified - in production, use actual network calls)"""
        try:
            # Simulate network call
            await asyncio.sleep(0.01)  # Simulate network latency
            
            # In production, this would send the data to the actual node
            logger.debug(f"Replicated {key} to node {node.node_id}")
            
        except Exception as e:
            logger.warning(f"Error replicating to node {node.node_id}: {e}")
    
    async def _update_consistency_map(self, key: str, service: str):
        """Update consistency map for cache key"""
        cache_key = f"{service}:{key}"
        now = datetime.now(timezone.utc)
        
        if cache_key not in self.consistency_map:
            self.consistency_map[cache_key] = CacheConsistencyInfo(
                key=cache_key,
                version=1,
                last_updated=now,
                nodes=[self.node_id],
                is_consistent=True
            )
        else:
            self.consistency_map[cache_key].version += 1
            self.consistency_map[cache_key].last_updated = now
            if self.node_id not in self.consistency_map[cache_key].nodes:
                self.consistency_map[cache_key].nodes.append(self.node_id)
    
    async def _heartbeat_task(self):
        """Background task to send heartbeats and update node status"""
        while True:
            try:
                # Update own status
                self.cache_nodes[self.node_id] = CacheNode(
                    node_id=self.node_id,
                    host='localhost',  # In production, get actual host
                    port=8000,  # In production, get actual port
                    status='active',
                    last_heartbeat=datetime.now(timezone.utc),
                    cache_size=len(self.local_cache),
                    hit_rate=self._calculate_hit_rate()
                )
                
                # Check other nodes (simplified - in production, use actual discovery)
                await self._discover_nodes()
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _discover_nodes(self):
        """Discover other cache nodes (simplified implementation)"""
        try:
            # In production, this would use service discovery (Consul, etcd, etc.)
            # For now, we'll simulate with database-based discovery
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT node_id, host, port, status, last_heartbeat, cache_size, hit_rate
                FROM cache_nodes 
                WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'
                AND node_id != %s
            """, (self.node_id,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            for row in results:
                self.cache_nodes[row['node_id']] = CacheNode(
                    node_id=row['node_id'],
                    host=row['host'],
                    port=row['port'],
                    status=row['status'],
                    last_heartbeat=row['last_heartbeat'],
                    cache_size=row['cache_size'],
                    hit_rate=row['hit_rate']
                )
            
        except Exception as e:
            logger.warning(f"Error discovering nodes: {e}")
    
    async def _consistency_check_task(self):
        """Background task to check cache consistency"""
        while True:
            try:
                await self._check_consistency()
                await asyncio.sleep(self.consistency_check_interval)
                
            except Exception as e:
                logger.error(f"Error in consistency check task: {e}")
                await asyncio.sleep(self.consistency_check_interval)
    
    async def _check_consistency(self):
        """Check cache consistency across nodes"""
        try:
            for cache_key, consistency_info in self.consistency_map.items():
                # Check if all nodes have the latest version
                expected_nodes = set(consistency_info.nodes)
                active_nodes = {node_id for node_id, node in self.cache_nodes.items() 
                              if node.status == 'active'}
                
                # Nodes that should have this key but might not
                missing_nodes = expected_nodes - active_nodes
                
                if missing_nodes:
                    consistency_info.is_consistent = False
                    logger.warning(f"Cache key {cache_key} missing from nodes: {missing_nodes}")
                else:
                    consistency_info.is_consistent = True
                
        except Exception as e:
            logger.error(f"Error checking consistency: {e}")
    
    async def _cache_warming_task(self):
        """Background task for cache warming"""
        while True:
            try:
                # Process warming queue
                warming_items = []
                for _ in range(self.warming_batch_size):
                    try:
                        item = self.warming_queue.get_nowait()
                        warming_items.append(item)
                    except asyncio.QueueEmpty:
                        break
                
                if warming_items:
                    await self._warm_cache_batch(warming_items)
                
                # Add common patterns to warming queue
                await self._add_warming_patterns()
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in cache warming task: {e}")
                await asyncio.sleep(60)
    
    async def _warm_cache_batch(self, items: List[Dict[str, Any]]):
        """Warm cache with a batch of items"""
        try:
            for item in items:
                key = item['key']
                service = item['service']
                
                # Check if already cached
                if await self.get(key, service) is not None:
                    continue
                
                # Fetch and cache the data
                data = await self._fetch_data_for_warming(key, service)
                if data is not None:
                    await self.set(key, data, service, item.get('ttl', 3600))
                    logger.debug(f"Warmed cache for {service}:{key}")
                
        except Exception as e:
            logger.error(f"Error warming cache batch: {e}")
    
    async def _fetch_data_for_warming(self, key: str, service: str) -> Optional[Any]:
        """Fetch data for cache warming"""
        try:
            # This would integrate with actual services to fetch data
            # For now, we'll simulate based on the service type
            
            if service == 'wikipedia':
                # Simulate Wikipedia API call
                await asyncio.sleep(0.1)
                return {
                    'title': f'Wikipedia article for {key}',
                    'extract': f'This is a simulated Wikipedia extract for {key}',
                    'url': f'https://en.wikipedia.org/wiki/{key}'
                }
            elif service == 'gdelt':
                # Simulate GDELT API call
                await asyncio.sleep(0.1)
                return {
                    'events': [{'title': f'GDELT event for {key}', 'date': datetime.now().isoformat()}],
                    'mentions': []
                }
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Error fetching data for warming {service}:{key}: {e}")
            return None
    
    async def _add_warming_patterns(self):
        """Add common patterns to warming queue"""
        try:
            # Add common topics
            for topic in self.warming_patterns['common_topics']:
                await self.warming_queue.put({
                    'key': topic,
                    'service': 'wikipedia',
                    'ttl': 86400  # 24 hours
                })
            
            # Add trending entities
            for entity in self.warming_patterns['trending_entities']:
                await self.warming_queue.put({
                    'key': entity,
                    'service': 'gdelt',
                    'ttl': 3600  # 1 hour
                })
            
            # Add recent queries (if any)
            for query in self.warming_patterns['recent_queries'][-10:]:  # Last 10 queries
                await self.warming_queue.put({
                    'key': query,
                    'service': 'wikipedia',
                    'ttl': 7200  # 2 hours
                })
                
        except Exception as e:
            logger.error(f"Error adding warming patterns: {e}")
    
    def _calculate_hit_rate(self) -> float:
        """Calculate local cache hit rate"""
        if not self.local_cache:
            return 0.0
        
        total_accesses = sum(entry['access_count'] for entry in self.local_cache.values())
        if total_accesses == 0:
            return 0.0
        
        # Simplified hit rate calculation
        return min(1.0, total_accesses / len(self.local_cache))
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get distributed cache statistics"""
        try:
            total_nodes = len(self.cache_nodes)
            active_nodes = sum(1 for node in self.cache_nodes.values() if node.status == 'active')
            
            local_stats = {
                'entries': len(self.local_cache),
                'hit_rate': self._calculate_hit_rate(),
                'total_size_bytes': sum(entry['size_bytes'] for entry in self.local_cache.values())
            }
            
            consistency_stats = {
                'total_keys': len(self.consistency_map),
                'consistent_keys': sum(1 for info in self.consistency_map.values() if info.is_consistent),
                'inconsistent_keys': sum(1 for info in self.consistency_map.values() if not info.is_consistent)
            }
            
            return {
                'node_id': self.node_id,
                'total_nodes': total_nodes,
                'active_nodes': active_nodes,
                'local_cache': local_stats,
                'consistency': consistency_stats,
                'warming_queue_size': self.warming_queue.qsize()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    async def invalidate_key(self, key: str, service: str = 'default') -> bool:
        """Invalidate cache key across all nodes"""
        try:
            # Remove from local cache
            local_key = f"{service}:{key}"
            if local_key in self.local_cache:
                del self.local_cache[local_key]
            
            # Invalidate on other nodes
            for node_id, node in self.cache_nodes.items():
                if node.status == 'active' and node_id != self.node_id:
                    try:
                        await self._invalidate_on_node(node, key, service)
                    except Exception as e:
                        logger.warning(f"Error invalidating on node {node_id}: {e}")
            
            # Update consistency map
            if local_key in self.consistency_map:
                del self.consistency_map[local_key]
            
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating key: {e}")
            return False
    
    async def _invalidate_on_node(self, node: CacheNode, key: str, service: str):
        """Invalidate key on specific node (simplified - in production, use actual network calls)"""
        try:
            # Simulate network call
            await asyncio.sleep(0.01)
            logger.debug(f"Invalidated {key} on node {node.node_id}")
            
        except Exception as e:
            logger.warning(f"Error invalidating on node {node.node_id}: {e}")
    
    async def add_warming_query(self, query: str, service: str = 'wikipedia'):
        """Add query to warming patterns"""
        try:
            if query not in self.warming_patterns['recent_queries']:
                self.warming_patterns['recent_queries'].append(query)
                
                # Keep only last 50 queries
                if len(self.warming_patterns['recent_queries']) > 50:
                    self.warming_patterns['recent_queries'] = self.warming_patterns['recent_queries'][-50:]
                
                # Add to warming queue
                await self.warming_queue.put({
                    'key': query,
                    'service': service,
                    'ttl': 7200  # 2 hours
                })
                
        except Exception as e:
            logger.error(f"Error adding warming query: {e}")

# Global instance
_distributed_cache_service = None

def get_distributed_cache_service() -> DistributedCacheService:
    """Get global distributed cache service instance"""
    global _distributed_cache_service
    if _distributed_cache_service is None:
        from config.database import get_db_config
        _distributed_cache_service = DistributedCacheService(get_db_config())
    return _distributed_cache_service




