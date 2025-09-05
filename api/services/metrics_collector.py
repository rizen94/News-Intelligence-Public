"""
News Intelligence System v3.1.0 - Metrics Collection Service
Collects and stores system, application, and business metrics
"""

import asyncio
import logging
import psutil
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: int
    memory_total_mb: int
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    load_avg_1m: Optional[float] = None
    load_avg_5m: Optional[float] = None
    load_avg_15m: Optional[float] = None

@dataclass
class ApplicationMetrics:
    """Application processing metrics"""
    articles_processed: int
    articles_failed: int
    processing_time_ms: int
    queue_size: int
    active_workers: int
    tasks_completed: int
    tasks_failed: int
    avg_processing_time_ms: float

@dataclass
class ArticleVolumeMetrics:
    """Article volume and processing metrics"""
    total_articles: int
    new_articles_last_hour: int
    new_articles_last_day: int
    articles_by_source: Dict[str, int]
    articles_by_category: Dict[str, int]
    avg_article_length: int
    processing_success_rate: float

@dataclass
class DatabaseMetrics:
    """Database performance metrics"""
    connection_count: int
    active_queries: int
    slow_queries: int
    avg_query_time_ms: float
    database_size_mb: float
    table_sizes: Dict[str, float]

class MetricsCollector:
    """Collects and stores system metrics"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.is_running = False
        self.collection_interval = 60  # Collect every minute
        self.retention_days = 365  # Keep data for 1 year
        
    async def start(self):
        """Start metrics collection"""
        logger.info("Starting metrics collection service...")
        self.is_running = True
        
        # Start collection loop
        while self.is_running:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)
        
        logger.info("Metrics collection service stopped")
    
    async def stop(self):
        """Stop metrics collection"""
        self.is_running = False
    
    async def _collect_all_metrics(self):
        """Collect all types of metrics"""
        try:
            # Collect system metrics
            system_metrics = await self._collect_system_metrics()
            await self._store_system_metrics(system_metrics)
            
            # Collect application metrics
            app_metrics = await self._collect_application_metrics()
            await self._store_application_metrics(app_metrics)
            
            # Collect article volume metrics
            volume_metrics = await self._collect_article_volume_metrics()
            await self._store_article_volume_metrics(volume_metrics)
            
            # Collect database metrics
            db_metrics = await self._collect_database_metrics()
            await self._store_database_metrics(db_metrics)
            
            logger.debug("All metrics collected and stored successfully")
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used // (1024 * 1024)
            memory_total_mb = memory.total // (1024 * 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_total_gb = disk.total / (1024 * 1024 * 1024)
            
            # Load average (if available)
            try:
                load_avg = psutil.getloadavg()
                load_avg_1m, load_avg_5m, load_avg_15m = load_avg
            except AttributeError:
                load_avg_1m = load_avg_5m = load_avg_15m = None
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_total_mb=memory_total_mb,
                disk_percent=disk_percent,
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
                load_avg_1m=load_avg_1m,
                load_avg_5m=load_avg_5m,
                load_avg_15m=load_avg_15m
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            # Return default values
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0,
                memory_total_mb=0,
                disk_percent=0.0,
                disk_used_gb=0.0,
                disk_total_gb=0.0
            )
    
    async def _collect_application_metrics(self) -> ApplicationMetrics:
        """Collect application processing metrics"""
        try:
            # Get automation manager status
            from services.automation_manager import get_automation_manager
            automation_manager = get_automation_manager()
            status = automation_manager.get_status()
            metrics = automation_manager.get_metrics()
            
            # Calculate articles processed in last hour
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            articles_processed = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 hour' 
                AND processing_status = 'failed'
            """)
            articles_failed = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return ApplicationMetrics(
                articles_processed=articles_processed,
                articles_failed=articles_failed,
                processing_time_ms=int(metrics['performance']['avg_processing_time'] * 1000),
                queue_size=status['queue_size'],
                active_workers=status['active_workers'],
                tasks_completed=metrics['performance']['tasks_completed'],
                tasks_failed=metrics['performance']['tasks_failed'],
                avg_processing_time_ms=metrics['performance']['avg_processing_time'] * 1000
            )
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            return ApplicationMetrics(
                articles_processed=0,
                articles_failed=0,
                processing_time_ms=0,
                queue_size=0,
                active_workers=0,
                tasks_completed=0,
                tasks_failed=0,
                avg_processing_time_ms=0.0
            )
    
    async def _collect_article_volume_metrics(self) -> ArticleVolumeMetrics:
        """Collect article volume and processing metrics"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            # Total articles
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            # New articles in last hour
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            new_articles_last_hour = cursor.fetchone()[0]
            
            # New articles in last day
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 day'
            """)
            new_articles_last_day = cursor.fetchone()[0]
            
            # Articles by source
            cursor.execute("""
                SELECT source, COUNT(*) as count 
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY source
            """)
            articles_by_source = dict(cursor.fetchall())
            
            # Articles by category
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '7 days'
                AND category IS NOT NULL
                GROUP BY category
            """)
            articles_by_category = dict(cursor.fetchall())
            
            # Average article length
            cursor.execute("""
                SELECT AVG(COALESCE(word_count, 0)) as avg_length 
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            result = cursor.fetchone()
            avg_article_length = int(result[0]) if result[0] else 0
            
            # Processing success rate
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as successful
                FROM articles 
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            total, successful = cursor.fetchone()
            processing_success_rate = (successful / total * 100) if total > 0 else 0
            
            cursor.close()
            conn.close()
            
            return ArticleVolumeMetrics(
                total_articles=total_articles,
                new_articles_last_hour=new_articles_last_hour,
                new_articles_last_day=new_articles_last_day,
                articles_by_source=articles_by_source,
                articles_by_category=articles_by_category,
                avg_article_length=avg_article_length,
                processing_success_rate=processing_success_rate
            )
            
        except Exception as e:
            logger.error(f"Error collecting article volume metrics: {e}")
            return ArticleVolumeMetrics(
                total_articles=0,
                new_articles_last_hour=0,
                new_articles_last_day=0,
                articles_by_source={},
                articles_by_category={},
                avg_article_length=0,
                processing_success_rate=0.0
            )
    
    async def _collect_database_metrics(self) -> DatabaseMetrics:
        """Collect database performance metrics"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            # Connection count
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE datname = current_database()
            """)
            connection_count = cursor.fetchone()[0]
            
            # Active queries
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE state = 'active' AND datname = current_database()
            """)
            active_queries = cursor.fetchone()[0]
            
            # Slow queries (queries taking more than 1 second)
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE state = 'active' 
                AND query_start < NOW() - INTERVAL '1 second'
                AND datname = current_database()
            """)
            slow_queries = cursor.fetchone()[0]
            
            # Database size
            cursor.execute("""
                SELECT pg_database_size(current_database()) / (1024 * 1024) as size_mb
            """)
            database_size_mb = cursor.fetchone()[0]
            
            # Table sizes
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10
            """)
            table_sizes = {f"{row[0]}.{row[1]}": row[2] for row in cursor.fetchall()}
            
            cursor.close()
            conn.close()
            
            return DatabaseMetrics(
                connection_count=connection_count,
                active_queries=active_queries,
                slow_queries=slow_queries,
                avg_query_time_ms=0.0,  # Would need more complex monitoring
                database_size_mb=database_size_mb,
                table_sizes=table_sizes
            )
            
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            return DatabaseMetrics(
                connection_count=0,
                active_queries=0,
                slow_queries=0,
                avg_query_time_ms=0.0,
                database_size_mb=0.0,
                table_sizes={}
            )
    
    async def _store_system_metrics(self, metrics: SystemMetrics):
        """Store system metrics in database"""
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO system_metrics (
                cpu_percent, memory_percent, memory_used_mb, memory_total_mb,
                disk_percent, disk_used_gb, disk_total_gb,
                load_avg_1m, load_avg_5m, load_avg_15m
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            metrics.cpu_percent, metrics.memory_percent, 
            metrics.memory_used_mb, metrics.memory_total_mb,
            metrics.disk_percent, metrics.disk_used_gb, metrics.disk_total_gb,
            metrics.load_avg_1m, metrics.load_avg_5m, metrics.load_avg_15m
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    async def _store_application_metrics(self, metrics: ApplicationMetrics):
        """Store application metrics in database"""
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO application_metrics (
                articles_processed, articles_failed, processing_time_ms,
                queue_size, active_workers, tasks_completed, tasks_failed,
                avg_processing_time_ms
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            metrics.articles_processed, metrics.articles_failed, metrics.processing_time_ms,
            metrics.queue_size, metrics.active_workers, metrics.tasks_completed, 
            metrics.tasks_failed, metrics.avg_processing_time_ms
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    async def _store_article_volume_metrics(self, metrics: ArticleVolumeMetrics):
        """Store article volume metrics in database"""
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO article_volume_metrics (
                total_articles, new_articles_last_hour, new_articles_last_day,
                articles_by_source, articles_by_category, avg_article_length,
                processing_success_rate
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            metrics.total_articles, metrics.new_articles_last_hour, metrics.new_articles_last_day,
            json.dumps(metrics.articles_by_source), json.dumps(metrics.articles_by_category),
            metrics.avg_article_length, metrics.processing_success_rate
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    async def _store_database_metrics(self, metrics: DatabaseMetrics):
        """Store database metrics in database"""
        conn = await self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO database_metrics (
                connection_count, active_queries, slow_queries,
                avg_query_time_ms, database_size_mb, table_sizes
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            metrics.connection_count, metrics.active_queries, metrics.slow_queries,
            metrics.avg_query_time_ms, metrics.database_size_mb, json.dumps(metrics.table_sizes)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    async def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    async def cleanup_old_data(self):
        """Clean up old metrics data (keep retention_days)"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            
            # Clean up each metrics table
            tables = ['system_metrics', 'application_metrics', 'article_volume_metrics', 'database_metrics']
            
            for table in tables:
                cursor.execute(f"DELETE FROM {table} WHERE timestamp < %s", (cutoff_date,))
                deleted_count = cursor.rowcount
                logger.info(f"Cleaned up {deleted_count} old records from {table}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error cleaning up old metrics data: {e}")

# Global instance
metrics_collector = None

def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global metrics_collector
    if metrics_collector is None:
        db_config = {
            'host': 'news-system-postgres',
            'database': 'newsintelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025',
            'port': '5432'
        }
        metrics_collector = MetricsCollector(db_config)
    return metrics_collector
