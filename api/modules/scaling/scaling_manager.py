#!/usr/bin/env python3
"""
Scaling Manager for News Intelligence System
Handles large-scale processing, storage management, and system monitoring
"""

import logging
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import psycopg2
from shared.database.connection import get_db_connection
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class ScalingMetrics:
    """Scaling metrics data structure"""
    total_articles: int
    raw_articles: int
    processing_articles: int
    completed_articles: int
    failed_articles: int
    total_timeline_events: int
    active_storylines: int
    queue_size: int
    running_tasks: int
    database_size_bytes: int
    avg_processing_time_seconds: float
    success_rate: float
    timestamp: datetime

@dataclass
class BatchProcessingConfig:
    """Configuration for batch processing"""
    max_batch_size: int = 100
    max_concurrent_batches: int = 3
    batch_timeout_minutes: int = 30
    retry_failed_articles: bool = True
    priority_threshold: int = 2

class ScalingManager:
    """Manages system scaling and large-scale processing"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.batch_config = BatchProcessingConfig()
        self.is_monitoring = False
        self.monitor_thread = None
        self.cleanup_thread = None
        self.rate_limits = {
            'ml_processing': {'max_requests': 1000, 'window_seconds': 3600},  # 1000/hour
            'timeline_generation': {'max_requests': 100, 'window_seconds': 3600},  # 100/hour
            'api_calls': {'max_requests': 10000, 'window_seconds': 3600},  # 10000/hour
        }
        
    def start_monitoring(self):
        """Start scaling monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
        
        logger.info("Scaling monitoring started")
    
    def stop_monitoring(self):
        """Stop scaling monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        if self.cleanup_thread:
            self.cleanup_thread.join()
        
        logger.info("Scaling monitoring stopped")
    
    def get_scaling_metrics(self) -> ScalingMetrics:
        """Get current scaling metrics"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get article counts
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN processing_status = 'raw' THEN 1 END) as raw,
                    COUNT(CASE WHEN processing_status = 'ml_processing' THEN 1 END) as processing,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed
                FROM articles
            """)
            article_counts = cur.fetchone()
            
            # Get timeline events count
            cur.execute("SELECT COUNT(*) FROM timeline_events")
            timeline_count = cur.fetchone()[0]
            
            # Get active storylines count
            cur.execute("SELECT COUNT(*) FROM story_expectations WHERE is_active = true")
            storylines_count = cur.fetchone()[0]
            
            # Get database size
            cur.execute("SELECT pg_database_size(current_database())")
            db_size = cur.fetchone()[0]
            
            # Get processing performance
            cur.execute("""
                SELECT 
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration,
                    CASE 
                        WHEN COUNT(*) > 0 THEN COUNT(CASE WHEN status = 'completed' THEN 1 END)::float / COUNT(*) * 100 
                        ELSE 0 
                    END as success_rate
                FROM ml_task_queue
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND started_at IS NOT NULL
            """)
            perf_data = cur.fetchone()
            
            cur.close()
            conn.close()
            
            return ScalingMetrics(
                total_articles=article_counts[0],
                raw_articles=article_counts[1],
                processing_articles=article_counts[2],
                completed_articles=article_counts[3],
                failed_articles=article_counts[4],
                total_timeline_events=timeline_count,
                active_storylines=storylines_count,
                queue_size=0,  # Will be updated by ML queue manager
                running_tasks=0,  # Will be updated by ML queue manager
                database_size_bytes=db_size,
                avg_processing_time_seconds=perf_data[0] if perf_data[0] else 0.0,
                success_rate=perf_data[1] if perf_data[1] else 0.0,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error getting scaling metrics: {e}")
            return ScalingMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, datetime.now())
    
    def create_processing_batch(self, article_ids: List[int], batch_type: str = "manual", priority: int = 2) -> str:
        """Create a batch for processing multiple articles"""
        try:
            batch_id = f"batch_{batch_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(article_ids)) % 10000}"
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Create batch record
            cur.execute("""
                INSERT INTO article_processing_batches (
                    batch_id, batch_type, total_articles, status, priority, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                batch_id,
                batch_type,
                len(article_ids),
                'pending',
                priority,
                json.dumps({
                    'created_by': 'scaling_manager',
                    'article_count': len(article_ids),
                    'estimated_duration_minutes': len(article_ids) * 2  # 2 minutes per article
                })
            ))
            
            # Create batch article mappings
            for i, article_id in enumerate(article_ids):
                cur.execute("""
                    INSERT INTO batch_articles (batch_id, article_id, processing_order)
                    VALUES (%s, %s, %s)
                """, (batch_id, article_id, i))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Created processing batch {batch_id} with {len(article_ids)} articles")
            return batch_id
            
        except Exception as e:
            logger.error(f"Error creating processing batch: {e}")
            raise
    
    def process_batch_intelligently(self, batch_id: str) -> Dict[str, Any]:
        """Process a batch of articles with intelligent resource management"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get batch info
            cur.execute("""
                SELECT total_articles, priority, metadata
                FROM article_processing_batches
                WHERE batch_id = %s
            """, (batch_id,))
            
            batch_info = cur.fetchone()
            if not batch_info:
                raise ValueError(f"Batch {batch_id} not found")
            
            total_articles, priority, metadata = batch_info
            
            # Check if batch is too large
            if total_articles > self.batch_config.max_batch_size:
                # Split into smaller batches
                return self._split_large_batch(batch_id, total_articles)
            
            # Update batch status
            cur.execute("""
                UPDATE article_processing_batches
                SET status = 'processing', started_at = CURRENT_TIMESTAMP
                WHERE batch_id = %s
            """, (batch_id,))
            
            # Get articles in batch
            cur.execute("""
                SELECT article_id, processing_order
                FROM batch_articles
                WHERE batch_id = %s
                ORDER BY processing_order
            """, (batch_id,))
            
            articles = cur.fetchall()
            
            # Process articles in chunks to avoid overwhelming the system
            chunk_size = min(10, total_articles)  # Process 10 articles at a time
            processed_count = 0
            failed_count = 0
            
            for i in range(0, len(articles), chunk_size):
                chunk = articles[i:i + chunk_size]
                
                # Process chunk
                chunk_results = self._process_article_chunk([article[0] for article in chunk])
                
                # Update batch article status
                for j, (article_id, order) in enumerate(chunk):
                    success = chunk_results.get(article_id, {}).get('success', False)
                    error_msg = chunk_results.get(article_id, {}).get('error')
                    
                    cur.execute("""
                        UPDATE batch_articles
                        SET status = %s, error_message = %s, processed_at = CURRENT_TIMESTAMP
                        WHERE batch_id = %s AND article_id = %s
                    """, (
                        'completed' if success else 'failed',
                        error_msg,
                        batch_id,
                        article_id
                    ))
                    
                    if success:
                        processed_count += 1
                    else:
                        failed_count += 1
                
                # Update batch progress
                cur.execute("""
                    UPDATE article_processing_batches
                    SET processed_articles = %s, failed_articles = %s
                    WHERE batch_id = %s
                """, (processed_count, failed_count, batch_id))
                
                conn.commit()
                
                # Small delay between chunks to prevent system overload
                time.sleep(1)
            
            # Mark batch as completed
            cur.execute("""
                UPDATE article_processing_batches
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE batch_id = %s
            """, (batch_id,))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Completed batch {batch_id}: {processed_count} processed, {failed_count} failed")
            return {
                "batch_id": batch_id,
                "total_articles": total_articles,
                "processed_articles": processed_count,
                "failed_articles": failed_count,
                "success_rate": processed_count / total_articles * 100 if total_articles > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}")
            # Mark batch as failed
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE article_processing_batches
                    SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP
                    WHERE batch_id = %s
                """, (str(e), batch_id))
                conn.commit()
                cur.close()
                conn.close()
            except:
                pass
            raise
    
    def _split_large_batch(self, batch_id: str, total_articles: int) -> Dict[str, Any]:
        """Split a large batch into smaller manageable batches"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get articles in the large batch
            cur.execute("""
                SELECT article_id FROM batch_articles
                WHERE batch_id = %s
                ORDER BY processing_order
            """, (batch_id,))
            
            article_ids = [row[0] for row in cur.fetchall()]
            
            # Split into smaller batches
            sub_batches = []
            chunk_size = self.batch_config.max_batch_size
            
            for i in range(0, len(article_ids), chunk_size):
                chunk = article_ids[i:i + chunk_size]
                sub_batch_id = f"{batch_id}_sub_{i // chunk_size + 1}"
                
                # Create sub-batch
                cur.execute("""
                    INSERT INTO article_processing_batches (
                        batch_id, batch_type, total_articles, status, priority, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    sub_batch_id,
                    'split_batch',
                    len(chunk),
                    'pending',
                    2,
                    json.dumps({'parent_batch': batch_id, 'split_index': i // chunk_size})
                ))
                
                # Create sub-batch article mappings
                for j, article_id in enumerate(chunk):
                    cur.execute("""
                        INSERT INTO batch_articles (batch_id, article_id, processing_order)
                        VALUES (%s, %s, %s)
                    """, (sub_batch_id, article_id, j))
                
                sub_batches.append(sub_batch_id)
            
            # Mark original batch as split
            cur.execute("""
                UPDATE article_processing_batches
                SET status = 'split', metadata = %s
                WHERE batch_id = %s
            """, (json.dumps({'sub_batches': sub_batches}), batch_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Split batch {batch_id} into {len(sub_batches)} sub-batches")
            return {
                "batch_id": batch_id,
                "action": "split",
                "sub_batches": sub_batches,
                "total_sub_batches": len(sub_batches)
            }
            
        except Exception as e:
            logger.error(f"Error splitting batch {batch_id}: {e}")
            raise
    
    def _process_article_chunk(self, article_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Process a chunk of articles"""
        results = {}
        
        for article_id in article_ids:
            try:
                # Here you would integrate with your ML processing pipeline
                # For now, we'll simulate processing
                success = self._simulate_article_processing(article_id)
                results[article_id] = {
                    "success": success,
                    "error": None if success else "Processing failed"
                }
            except Exception as e:
                results[article_id] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    def _simulate_article_processing(self, article_id: int) -> bool:
        """Simulate article processing (replace with actual ML processing)"""
        # Simulate processing time
        time.sleep(0.1)
        
        # Simulate 95% success rate
        import random
        return random.random() > 0.05
    
    def check_rate_limit(self, resource_type: str, resource_key: str) -> bool:
        """Check if a request is within rate limits"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            if resource_type not in self.rate_limits:
                return True
            
            limit_config = self.rate_limits[resource_type]
            
            cur.execute("""
                SELECT check_rate_limit(%s, %s, %s, %s)
            """, (
                resource_type,
                resource_key,
                limit_config['max_requests'],
                limit_config['window_seconds']
            ))
            
            result = cur.fetchone()[0]
            cur.close()
            conn.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Allow on error
    
    def get_storage_usage(self) -> Dict[str, Any]:
        """Get current storage usage statistics"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Get table sizes
            cur.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 20
            """)
            
            table_sizes = []
            for row in cur.fetchall():
                table_sizes.append({
                    "table": f"{row[0]}.{row[1]}",
                    "size": row[2],
                    "size_bytes": row[3]
                })
            
            # Get database size
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            db_size = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            return {
                "database_size": db_size,
                "table_sizes": table_sizes,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting storage usage: {e}")
            return {"error": str(e)}
    
    def run_cleanup_policies(self) -> Dict[str, int]:
        """Run storage cleanup policies"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT * FROM run_cleanup_policies()")
            results = cur.fetchall()
            
            cur.close()
            conn.close()
            
            cleanup_results = {}
            for policy_name, cleaned_count in results:
                cleanup_results[policy_name] = cleaned_count
            
            logger.info(f"Cleanup completed: {cleanup_results}")
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error running cleanup policies: {e}")
            return {"error": str(e)}
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.is_monitoring:
            try:
                # Update scaling metrics
                metrics = self.get_scaling_metrics()
                self._store_scaling_metrics(metrics)
                
                # Check for alerts
                self._check_scaling_alerts(metrics)
                
                # Sleep for 5 minutes
                time.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.is_monitoring:
            try:
                # Run cleanup policies every hour
                self.run_cleanup_policies()
                
                # Sleep for 1 hour
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(300)
    
    def _store_scaling_metrics(self, metrics: ScalingMetrics):
        """Store scaling metrics in database"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO system_scaling_metrics (
                    total_articles, raw_articles, processing_articles, completed_articles,
                    failed_articles, total_timeline_events, active_storylines, queue_size,
                    running_tasks, database_size_bytes, avg_processing_time_seconds, success_rate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                metrics.total_articles, metrics.raw_articles, metrics.processing_articles,
                metrics.completed_articles, metrics.failed_articles, metrics.total_timeline_events,
                metrics.active_storylines, metrics.queue_size, metrics.running_tasks,
                metrics.database_size_bytes, metrics.avg_processing_time_seconds, metrics.success_rate
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing scaling metrics: {e}")
    
    def _check_scaling_alerts(self, metrics: ScalingMetrics):
        """Check for scaling alerts and warnings"""
        alerts = []
        
        # Check database size
        if metrics.database_size_bytes > 10 * 1024 * 1024 * 1024:  # 10GB
            alerts.append(f"Database size is large: {metrics.database_size_bytes / (1024**3):.2f}GB")
        
        # Check processing backlog
        if metrics.raw_articles > 1000:
            alerts.append(f"Large processing backlog: {metrics.raw_articles} raw articles")
        
        # Check success rate
        if metrics.success_rate < 80 and metrics.success_rate > 0:
            alerts.append(f"Low success rate: {metrics.success_rate:.1f}%")
        
        # Check processing time
        if metrics.avg_processing_time_seconds > 300:  # 5 minutes
            alerts.append(f"Slow processing: {metrics.avg_processing_time_seconds:.1f}s average")
        
        if alerts:
            logger.warning(f"Scaling alerts: {'; '.join(alerts)}")
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a processing batch"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    batch_id, batch_type, total_articles, processed_articles, failed_articles,
                    status, priority, created_at, started_at, completed_at, error_message, metadata
                FROM article_processing_batches
                WHERE batch_id = %s
            """, (batch_id,))
            
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return {
                    "batch_id": row[0],
                    "batch_type": row[1],
                    "total_articles": row[2],
                    "processed_articles": row[3],
                    "failed_articles": row[4],
                    "status": row[5],
                    "priority": row[6],
                    "created_at": row[7].isoformat() if row[7] else None,
                    "started_at": row[8].isoformat() if row[8] else None,
                    "completed_at": row[9].isoformat() if row[9] else None,
                    "error_message": row[10],
                    "metadata": json.loads(row[11]) if row[11] else {},
                    "progress_percentage": (row[3] + row[4]) / row[2] * 100 if row[2] > 0 else 0
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting batch status: {e}")
            return None
