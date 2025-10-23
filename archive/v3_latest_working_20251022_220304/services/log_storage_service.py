"""
News Intelligence System v3.3.0 - Log Storage and Management Service
Handles log storage, rotation, retention, and analysis
"""

import os
import json
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import sqlite3
import logging
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: str
    logger: str
    message: str
    module: str
    function: str
    line: int
    exception: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None

@dataclass
class LogStats:
    """Log statistics"""
    total_entries: int
    error_count: int
    warning_count: int
    info_count: int
    debug_count: int
    time_range: Tuple[datetime, datetime]
    top_loggers: List[Tuple[str, int]]
    top_errors: List[Tuple[str, int]]

class LogStorageService:
    """
    Comprehensive log storage and management service
    Provides log storage, analysis, and cleanup capabilities
    """
    
    def __init__(self, 
                 log_dir: str = "/app/logs",
                 db_path: str = "/app/logs/log_analysis.db",
                 retention_days: int = 30,
                 compression_enabled: bool = True):
        """
        Initialize log storage service
        
        Args:
            log_dir: Directory containing log files
            db_path: Path to SQLite database for log analysis
            retention_days: Number of days to retain logs
            compression_enabled: Enable log compression for old files
        """
        self.log_dir = Path(log_dir)
        self.db_path = db_path
        self.retention_days = retention_days
        self.compression_enabled = compression_enabled
        
        # Create directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup database
        self._setup_database()
        
        # Setup logger
        self.logger = logging.getLogger("news_intelligence.log_storage")
    
    def _setup_database(self):
        """Setup SQLite database for log analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create log entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                logger TEXT NOT NULL,
                message TEXT NOT NULL,
                module TEXT,
                function TEXT,
                line INTEGER,
                exception_type TEXT,
                exception_message TEXT,
                traceback TEXT,
                extra_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create log statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                total_entries INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                warning_count INTEGER DEFAULT 0,
                info_count INTEGER DEFAULT 0,
                debug_count INTEGER DEFAULT 0,
                top_loggers TEXT,
                top_errors TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log_entries(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_level ON log_entries(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_logger ON log_entries(logger)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_date ON log_statistics(date)")
        
        conn.commit()
        conn.close()
    
    def store_log_entry(self, log_entry: LogEntry):
        """Store a log entry in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO log_entries 
                (timestamp, level, logger, message, module, function, line, 
                 exception_type, exception_message, traceback, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_entry.timestamp.isoformat(),
                log_entry.level,
                log_entry.logger,
                log_entry.message,
                log_entry.module,
                log_entry.function,
                log_entry.line,
                log_entry.exception.get('type') if log_entry.exception else None,
                log_entry.exception.get('message') if log_entry.exception else None,
                log_entry.exception.get('traceback') if log_entry.exception else None,
                json.dumps(log_entry.extra_data) if log_entry.extra_data else None
            ))
            
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to store log entry: {e}")
        finally:
            conn.close()
    
    def get_log_entries(self, 
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       level: Optional[str] = None,
                       logger: Optional[str] = None,
                       limit: int = 1000) -> List[LogEntry]:
        """Retrieve log entries with filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM log_entries WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        if level:
            query += " AND level = ?"
            params.append(level)
        
        if logger:
            query += " AND logger = ?"
            params.append(logger)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to LogEntry objects
        entries = []
        for row in rows:
            entry = LogEntry(
                timestamp=datetime.fromisoformat(row[1]),
                level=row[2],
                logger=row[3],
                message=row[4],
                module=row[5],
                function=row[6],
                line=row[7],
                exception={
                    'type': row[8],
                    'message': row[9],
                    'traceback': row[10]
                } if row[8] else None,
                extra_data=json.loads(row[11]) if row[11] else None
            )
            entries.append(entry)
        
        return entries
    
    def get_log_statistics(self, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> LogStats:
        """Get log statistics for a date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM log_entries WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return LogStats(0, 0, 0, 0, 0, (datetime.now(), datetime.now()), [], [])
        
        # Calculate statistics
        total_entries = len(rows)
        error_count = sum(1 for row in rows if row[2] == 'ERROR')
        warning_count = sum(1 for row in rows if row[2] == 'WARNING')
        info_count = sum(1 for row in rows if row[2] == 'INFO')
        debug_count = sum(1 for row in rows if row[2] == 'DEBUG')
        
        # Time range
        timestamps = [datetime.fromisoformat(row[1]) for row in rows]
        time_range = (min(timestamps), max(timestamps))
        
        # Top loggers
        logger_counts = defaultdict(int)
        for row in rows:
            logger_counts[row[3]] += 1
        top_loggers = sorted(logger_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Top errors
        error_counts = defaultdict(int)
        for row in rows:
            if row[2] == 'ERROR':
                error_counts[row[4]] += 1
        top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return LogStats(
            total_entries=total_entries,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            debug_count=debug_count,
            time_range=time_range,
            top_loggers=top_loggers,
            top_errors=top_errors
        )
    
    def compress_old_logs(self):
        """Compress old log files to save space"""
        if not self.compression_enabled:
            return
        
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                compressed_file = log_file.with_suffix('.log.gz')
                
                if not compressed_file.exists():
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(compressed_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Remove original file
                    log_file.unlink()
                    self.logger.info(f"Compressed log file: {log_file.name}")
    
    def cleanup_old_logs(self):
        """Clean up old log files and database entries"""
        # Clean up compressed files older than retention period
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        for compressed_file in self.log_dir.glob("*.log.gz"):
            if compressed_file.stat().st_mtime < cutoff_date.timestamp():
                compressed_file.unlink()
                self.logger.info(f"Removed old compressed log: {compressed_file.name}")
        
        # Clean up database entries older than retention period
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM log_entries 
            WHERE timestamp < ?
        """, (cutoff_date.isoformat(),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old log entries from database")
    
    def analyze_error_patterns(self, 
                               days: int = 7) -> Dict[str, Any]:
        """Analyze error patterns in recent logs"""
        start_date = datetime.now() - timedelta(days=days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get error patterns
        cursor.execute("""
            SELECT exception_type, COUNT(*) as count
            FROM log_entries 
            WHERE level = 'ERROR' AND timestamp >= ?
            GROUP BY exception_type
            ORDER BY count DESC
        """, (start_date.isoformat(),))
        
        error_patterns = cursor.fetchall()
        
        # Get error frequency by hour
        cursor.execute("""
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM log_entries 
            WHERE level = 'ERROR' AND timestamp >= ?
            GROUP BY hour
            ORDER BY hour
        """, (start_date.isoformat(),))
        
        hourly_errors = cursor.fetchall()
        
        conn.close()
        
        return {
            'error_patterns': error_patterns,
            'hourly_errors': hourly_errors,
            'analysis_period_days': days,
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def export_logs(self, 
                   output_path: str,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   format: str = 'json') -> bool:
        """Export logs to file"""
        try:
            entries = self.get_log_entries(start_time, end_time, limit=10000)
            
            if format == 'json':
                with open(output_path, 'w') as f:
                    json.dump([{
                        'timestamp': entry.timestamp.isoformat(),
                        'level': entry.level,
                        'logger': entry.logger,
                        'message': entry.message,
                        'module': entry.module,
                        'function': entry.function,
                        'line': entry.line,
                        'exception': entry.exception,
                        'extra_data': entry.extra_data
                    } for entry in entries], f, indent=2)
            
            elif format == 'csv':
                import csv
                with open(output_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'level', 'logger', 'message', 'module', 'function', 'line'])
                    for entry in entries:
                        writer.writerow([
                            entry.timestamp.isoformat(),
                            entry.level,
                            entry.logger,
                            entry.message,
                            entry.module,
                            entry.function,
                            entry.line
                        ])
            
            self.logger.info(f"Exported {len(entries)} log entries to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export logs: {e}")
            return False
    
    def get_system_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics based on logs"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)
        
        # Get recent error rate
        recent_errors = self.get_log_entries(start_time=last_hour, level='ERROR')
        recent_total = self.get_log_entries(start_time=last_hour)
        
        error_rate = len(recent_errors) / len(recent_total) if recent_total else 0
        
        # Get error trends
        hourly_errors = []
        for i in range(24):
            hour_start = now - timedelta(hours=i+1)
            hour_end = now - timedelta(hours=i)
            hour_errors = self.get_log_entries(start_time=hour_start, end_time=hour_end, level='ERROR')
            hourly_errors.append(len(hour_errors))
        
        return {
            'error_rate_last_hour': error_rate,
            'total_errors_last_24h': len(self.get_log_entries(start_time=last_24h, level='ERROR')),
            'hourly_error_trend': hourly_errors,
            'system_health_score': max(0, 100 - (error_rate * 1000)),  # Simple health score
            'timestamp': now.isoformat()
        }


# Global log storage instance
_log_storage_instance = None

def get_log_storage() -> LogStorageService:
    """Get global log storage instance"""
    global _log_storage_instance
    if _log_storage_instance is None:
        _log_storage_instance = LogStorageService()
    return _log_storage_instance
