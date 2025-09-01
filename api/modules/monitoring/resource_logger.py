#!/usr/bin/env python3
"""
News Intelligence System - Resource Logger
Captures and stores system and application metrics over time
"""

import os
import json
import time
import logging
import psutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import subprocess

class ResourceLogger:
    """Comprehensive resource logging system"""
    
    def __init__(self, db_path: str = "logs/resource_metrics.db", log_interval: int = 60):
        self.db_path = db_path
        self.log_interval = log_interval
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Metrics storage
        self.current_metrics = {}
        self.metrics_lock = threading.Lock()
        
    def _init_database(self):
        """Initialize SQLite database for metrics storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # System metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_used_gb REAL,
                    memory_total_gb REAL,
                    disk_percent REAL,
                    disk_used_gb REAL,
                    disk_total_gb REAL,
                    network_sent_gb REAL,
                    network_recv_gb REAL,
                    gpu_memory_used_mb INTEGER,
                    gpu_memory_total_mb INTEGER,
                    gpu_utilization_percent INTEGER,
                    gpu_temperature_c INTEGER
                )
            """)
            
            # Application metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    requests_total INTEGER,
                    articles_processed INTEGER,
                    ml_inferences INTEGER,
                    database_queries INTEGER,
                    errors_total INTEGER,
                    uptime_seconds REAL
                )
            """)
            
            # Performance events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT,
                    event_description TEXT,
                    severity TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_metrics_timestamp ON application_metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_events_timestamp ON performance_events(timestamp)")
            
            conn.commit()
            conn.close()
            self.logger.info("Resource logging database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
    
    def collect_system_metrics(self) -> Dict:
        """Collect comprehensive system metrics"""
        metrics = {}
        
        try:
            # CPU metrics
            metrics['cpu_percent'] = psutil.cpu_percent(interval=1)
            metrics['cpu_count'] = psutil.cpu_count()
            metrics['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics['memory_percent'] = memory.percent
            metrics['memory_used_gb'] = round(memory.used / (1024**3), 2)
            metrics['memory_total_gb'] = round(memory.total / (1024**3), 2)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics['disk_percent'] = round((disk.used / disk.total) * 100, 2)
            metrics['disk_used_gb'] = round(disk.used / (1024**3), 2)
            metrics['disk_total_gb'] = round(disk.total / (1024**3), 2)
            
            # Network metrics
            network = psutil.net_io_counters()
            metrics['network_sent_gb'] = round(network.bytes_sent / (1024**3), 2)
            metrics['network_recv_gb'] = round(network.bytes_recv / (1024**3), 2)
            
            # GPU metrics (if available)
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'], 
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    gpu_info = result.stdout.strip().split(',')
                    if len(gpu_info) >= 4:
                        metrics['gpu_memory_used_mb'] = int(gpu_info[0])
                        metrics['gpu_memory_total_mb'] = int(gpu_info[1])
                        metrics['gpu_utilization_percent'] = int(gpu_info[2])
                        metrics['gpu_temperature_c'] = int(gpu_info[3])
            except Exception as e:
                self.logger.debug(f"GPU metrics collection failed: {e}")
                
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            
        return metrics
    
    def collect_application_metrics(self) -> Dict:
        """Collect application-specific metrics"""
        metrics = {}
        
        try:
            # Import app metrics if available
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
            
            # Try to get metrics from the main app
            try:
                from app import app_metrics
                metrics.update({
                    'requests_total': app_metrics.get('requests_total', 0),
                    'articles_processed': app_metrics.get('articles_processed', 0),
                    'ml_inferences': app_metrics.get('ml_inferences', 0),
                    'database_queries': app_metrics.get('database_queries', 0),
                    'errors_total': app_metrics.get('errors_total', 0),
                    'uptime_seconds': time.time() - app_metrics.get('start_time', time.time())
                })
            except ImportError:
                # Fallback metrics
                metrics.update({
                    'requests_total': 0,
                    'articles_processed': 0,
                    'ml_inferences': 0,
                    'database_queries': 0,
                    'errors_total': 0,
                    'uptime_seconds': 0
                })
                
        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {e}")
            
        return metrics
    
    def log_metrics(self, system_metrics: Dict, app_metrics: Dict):
        """Log metrics to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Log system metrics
            cursor.execute("""
                INSERT INTO system_metrics (
                    cpu_percent, memory_percent, memory_used_gb, memory_total_gb,
                    disk_percent, disk_used_gb, disk_total_gb,
                    network_sent_gb, network_recv_gb,
                    gpu_memory_used_mb, gpu_memory_total_mb,
                    gpu_utilization_percent, gpu_temperature_c
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                system_metrics.get('cpu_percent'),
                system_metrics.get('memory_percent'),
                system_metrics.get('memory_used_gb'),
                system_metrics.get('memory_total_gb'),
                system_metrics.get('disk_percent'),
                system_metrics.get('disk_used_gb'),
                system_metrics.get('disk_total_gb'),
                system_metrics.get('network_sent_gb'),
                system_metrics.get('network_recv_gb'),
                system_metrics.get('gpu_memory_used_mb'),
                system_metrics.get('gpu_memory_total_mb'),
                system_metrics.get('gpu_utilization_percent'),
                system_metrics.get('gpu_temperature_c')
            ))
            
            # Log application metrics
            cursor.execute("""
                INSERT INTO application_metrics (
                    requests_total, articles_processed, ml_inferences,
                    database_queries, errors_total, uptime_seconds
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                app_metrics.get('requests_total'),
                app_metrics.get('articles_processed'),
                app_metrics.get('ml_inferences'),
                app_metrics.get('database_queries'),
                app_metrics.get('errors_total'),
                app_metrics.get('uptime_seconds')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error logging metrics: {e}")
    
    def log_performance_event(self, event_type: str, description: str, severity: str = "info", metadata: Dict = None):
        """Log performance events and anomalies"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO performance_events (event_type, event_description, severity, metadata)
                VALUES (?, ?, ?, ?)
            """, (event_type, description, severity, metadata_json))
            
            conn.commit()
            conn.close()
            
            # Also log to standard logging
            if severity == "error":
                self.logger.error(f"Performance Event [{event_type}]: {description}")
            elif severity == "warning":
                self.logger.warning(f"Performance Event [{event_type}]: {description}")
            else:
                self.logger.info(f"Performance Event [{event_type}]: {description}")
                
        except Exception as e:
            self.logger.error(f"Error logging performance event: {e}")
    
    def get_metrics_summary(self, hours: int = 24) -> Dict:
        """Get metrics summary for the last N hours"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get system metrics summary
            cursor.execute("""
                SELECT 
                    AVG(cpu_percent) as avg_cpu,
                    MAX(cpu_percent) as max_cpu,
                    AVG(memory_percent) as avg_memory,
                    MAX(memory_percent) as max_memory,
                    AVG(gpu_utilization_percent) as avg_gpu_util,
                    MAX(gpu_utilization_percent) as max_gpu_util,
                    AVG(gpu_memory_used_mb) as avg_gpu_memory,
                    MAX(gpu_memory_used_mb) as max_gpu_memory
                FROM system_metrics 
                WHERE timestamp >= datetime('now', '-{} hours')
            """.format(hours))
            
            system_summary = cursor.fetchone()
            
            # Get application metrics summary
            cursor.execute("""
                SELECT 
                    SUM(requests_total) as total_requests,
                    SUM(articles_processed) as total_articles,
                    SUM(ml_inferences) as total_ml_inferences,
                    SUM(database_queries) as total_db_queries,
                    SUM(errors_total) as total_errors
                FROM application_metrics 
                WHERE timestamp >= datetime('now', '-{} hours')
            """.format(hours))
            
            app_summary = cursor.fetchone()
            
            conn.close()
            
            return {
                'system': {
                    'avg_cpu_percent': round(system_summary[0] or 0, 2),
                    'max_cpu_percent': round(system_summary[1] or 0, 2),
                    'avg_memory_percent': round(system_summary[2] or 0, 2),
                    'max_memory_percent': round(system_summary[3] or 0, 2),
                    'avg_gpu_utilization': round(system_summary[4] or 0, 2),
                    'max_gpu_utilization': round(system_summary[5] or 0, 2),
                    'avg_gpu_memory_mb': round(system_summary[6] or 0, 2),
                    'max_gpu_memory_mb': round(system_summary[7] or 0, 2)
                },
                'application': {
                    'total_requests': app_summary[0] or 0,
                    'total_articles': app_summary[1] or 0,
                    'total_ml_inferences': app_summary[2] or 0,
                    'total_db_queries': app_summary[3] or 0,
                    'total_errors': app_summary[4] or 0
                },
                'period_hours': hours
            }
            
        except Exception as e:
            self.logger.error(f"Error getting metrics summary: {e}")
            return {}
    
    def cleanup_old_metrics(self, days_to_keep: int = 30):
        """Clean up old metrics to prevent database bloat"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete old system metrics
            cursor.execute("""
                DELETE FROM system_metrics 
                WHERE timestamp < datetime('now', '-{} days')
            """.format(days_to_keep))
            
            system_deleted = cursor.rowcount
            
            # Delete old application metrics
            cursor.execute("""
                DELETE FROM application_metrics 
                WHERE timestamp < datetime('now', '-{} days')
            """.format(days_to_keep))
            
            app_deleted = cursor.rowcount
            
            # Delete old performance events
            cursor.execute("""
                DELETE FROM performance_events 
                WHERE timestamp < datetime('now', '-{} days')
            """.format(days_to_keep))
            
            events_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up old metrics: {system_deleted} system, {app_deleted} app, {events_deleted} events")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old metrics: {e}")
    
    def start_logging(self):
        """Start the resource logging loop"""
        if self.running:
            return
            
        self.running = True
        self.logger.info("Starting resource logging...")
        
        def logging_loop():
            while self.running:
                try:
                    # Collect metrics
                    system_metrics = self.collect_system_metrics()
                    app_metrics = self.collect_application_metrics()
                    
                    # Log metrics
                    self.log_metrics(system_metrics, app_metrics)
                    
                    # Check for performance anomalies
                    self._check_performance_anomalies(system_metrics, app_metrics)
                    
                    # Wait for next interval
                    time.sleep(self.log_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in logging loop: {e}")
                    time.sleep(self.log_interval)
        
        # Start logging in background thread
        self.logging_thread = threading.Thread(target=logging_loop, daemon=True)
        self.logging_thread.start()
    
    def stop_logging(self):
        """Stop the resource logging loop"""
        self.running = False
        if hasattr(self, 'logging_thread'):
            self.logging_thread.join(timeout=5)
        self.logger.info("Resource logging stopped")
    
    def _check_performance_anomalies(self, system_metrics: Dict, app_metrics: Dict):
        """Check for performance anomalies and log events"""
        try:
            # High CPU usage
            if system_metrics.get('cpu_percent', 0) > 80:
                self.log_performance_event(
                    'high_cpu_usage',
                    f"CPU usage is {system_metrics['cpu_percent']:.1f}%",
                    'warning',
                    {'cpu_percent': system_metrics['cpu_percent']}
                )
            
            # High memory usage
            if system_metrics.get('memory_percent', 0) > 85:
                self.log_performance_event(
                    'high_memory_usage',
                    f"Memory usage is {system_metrics['memory_percent']:.1f}%",
                    'warning',
                    {'memory_percent': system_metrics['memory_percent']}
                )
            
            # High GPU memory usage
            if system_metrics.get('gpu_memory_used_mb', 0) > 30000:  # 30GB
                self.log_performance_event(
                    'high_gpu_memory',
                    f"GPU memory usage is {system_metrics['gpu_memory_used_mb']}MB",
                    'warning',
                    {'gpu_memory_mb': system_metrics['gpu_memory_used_mb']}
                )
            
            # High error rate
            if app_metrics.get('errors_total', 0) > 10:
                self.log_performance_event(
                    'high_error_rate',
                    f"Error count is {app_metrics['errors_total']}",
                    'error',
                    {'errors_total': app_metrics['errors_total']}
                )
                
        except Exception as e:
            self.logger.error(f"Error checking performance anomalies: {e}")

# Global instance
resource_logger = ResourceLogger()
