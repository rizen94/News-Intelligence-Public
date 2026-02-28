"""
News Intelligence System — comprehensive logging configuration.
Centralized logging with multiple handlers; wired to settings for LOG_LEVEL and LOG_DIR.
Finance domain uses component 'finance'.
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json
import traceback
from contextlib import contextmanager

class NewsIntelligenceLogger:
    """
    Comprehensive logging system for News Intelligence System
    Provides structured logging with multiple outputs and storage
    """
    
    def __init__(self, 
                 log_level: str = "INFO",
                 log_dir: str = "/app/logs",
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 enable_console: bool = True,
                 enable_file: bool = True,
                 enable_json: bool = True,
                 enable_ml_logging: bool = True):
        """
        Initialize comprehensive logging system
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files
            max_file_size: Maximum size per log file in bytes
            backup_count: Number of backup files to keep
            enable_console: Enable console output
            enable_file: Enable file logging
            enable_json: Enable JSON structured logging
            enable_ml_logging: Enable ML-specific logging
        """
        self.log_level = getattr(logging, log_level.upper())
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.enable_json = enable_json
        self.enable_ml_logging = enable_ml_logging
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize loggers
        self._setup_loggers()
        
        # Create specialized loggers
        self._create_specialized_loggers()
    
    def _setup_loggers(self):
        """Setup main application loggers"""
        # Main application logger
        self.app_logger = self._create_logger(
            name="news_intelligence",
            log_file="app.log",
            json_file="app_structured.json"
        )
        
        # API logger
        self.api_logger = self._create_logger(
            name="news_intelligence.api",
            log_file="api.log",
            json_file="api_structured.json"
        )
        
        # Database logger
        self.db_logger = self._create_logger(
            name="news_intelligence.database",
            log_file="database.log",
            json_file="database_structured.json"
        )
        
        # Error logger
        self.error_logger = self._create_logger(
            name="news_intelligence.errors",
            log_file="errors.log",
            json_file="errors_structured.json"
        )
        
        # Performance logger
        self.perf_logger = self._create_logger(
            name="news_intelligence.performance",
            log_file="performance.log",
            json_file="performance_structured.json"
        )
    
    def _create_specialized_loggers(self):
        """Create specialized loggers for different components"""
        if self.enable_ml_logging:
            # ML Processing logger
            self.ml_logger = self._create_logger(
                name="news_intelligence.ml",
                log_file="ml_processing.log",
                json_file="ml_structured.json"
            )
            
            # Deduplication logger
            self.dedup_logger = self._create_logger(
                name="news_intelligence.deduplication",
                log_file="deduplication.log",
                json_file="deduplication_structured.json"
            )
        
        # RSS Processing logger
        self.rss_logger = self._create_logger(
            name="news_intelligence.rss",
            log_file="rss_processing.log",
            json_file="rss_structured.json"
        )
        
        # Finance domain logger (market data, FRED, evidence)
        self.finance_logger = self._create_logger(
            name="news_intelligence.finance",
            log_file="finance.log",
            json_file="finance_structured.json"
        )
        
        # Security logger
        self.security_logger = self._create_logger(
            name="news_intelligence.security",
            log_file="security.log",
            json_file="security_structured.json"
        )
    
    def _create_logger(self, name: str, log_file: str, json_file: str) -> logging.Logger:
        """Create a logger with multiple handlers"""
        logger = logging.getLogger(name)
        logger.setLevel(self.log_level)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Console handler
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # File handler with rotation
        if self.enable_file:
            file_path = self.log_dir / log_file
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            file_handler.setLevel(self.log_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        # JSON structured logging
        if self.enable_json:
            json_path = self.log_dir / json_file
            json_handler = logging.handlers.RotatingFileHandler(
                json_path,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            json_handler.setLevel(self.log_level)
            json_handler.setFormatter(JSONFormatter())
            logger.addHandler(json_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        return logger
    
    def get_logger(self, component: str) -> logging.Logger:
        """Get logger for specific component"""
        logger_map = {
            'app': self.app_logger,
            'api': self.api_logger,
            'database': self.db_logger,
            'error': self.error_logger,
            'performance': self.perf_logger,
            'ml': getattr(self, 'ml_logger', None),
            'deduplication': getattr(self, 'dedup_logger', None),
            'rss': self.rss_logger,
            'finance': self.finance_logger,
            'security': self.security_logger
        }
        
        return logger_map.get(component, self.app_logger)
    
    @contextmanager
    def log_execution_time(self, operation: str, logger: Optional[logging.Logger] = None):
        """Context manager for logging execution time"""
        if logger is None:
            logger = self.perf_logger
        
        start_time = datetime.now()
        logger.info(f"Starting {operation}")
        
        try:
            yield
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Completed {operation} in {execution_time:.3f} seconds")
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed {operation} after {execution_time:.3f} seconds: {str(e)}")
            raise
    
    def log_error_with_context(self, 
                             error: Exception, 
                             context: Dict[str, Any],
                             logger: Optional[logging.Logger] = None):
        """Log error with additional context information"""
        if logger is None:
            logger = self.error_logger
        
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.error(f"Error occurred: {json.dumps(error_info, indent=2)}")
    
    def log_ml_processing(self, 
                         operation: str,
                         article_id: Optional[int] = None,
                         processing_time: Optional[float] = None,
                         success: bool = True,
                         details: Optional[Dict[str, Any]] = None):
        """Log ML processing operations with structured data"""
        if not self.enable_ml_logging:
            return
        
        ml_data = {
            'operation': operation,
            'article_id': article_id,
            'processing_time': processing_time,
            'success': success,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        
        if success:
            self.ml_logger.info(f"ML Processing: {json.dumps(ml_data)}")
        else:
            self.ml_logger.error(f"ML Processing Failed: {json.dumps(ml_data)}")
    
    def log_database_operation(self,
                             operation: str,
                             table: str,
                             duration: Optional[float] = None,
                             success: bool = True,
                             details: Optional[Dict[str, Any]] = None):
        """Log database operations with performance metrics"""
        db_data = {
            'operation': operation,
            'table': table,
            'duration': duration,
            'success': success,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        
        if success:
            self.db_logger.info(f"Database Operation: {json.dumps(db_data)}")
        else:
            self.db_logger.error(f"Database Operation Failed: {json.dumps(db_data)}")
    
    def log_api_request(self,
                       method: str,
                       endpoint: str,
                       status_code: int,
                       duration: Optional[float] = None,
                       user_id: Optional[str] = None,
                       details: Optional[Dict[str, Any]] = None):
        """Log API requests with performance and security metrics"""
        api_data = {
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'duration': duration,
            'user_id': user_id,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        
        if 200 <= status_code < 400:
            self.api_logger.info(f"API Request: {json.dumps(api_data)}")
        else:
            self.api_logger.warning(f"API Request Error: {json.dumps(api_data)}")


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


# Global logger instance
_logger_instance = None


def _get_defaults():
    """Use settings when available; avoid circular import."""
    try:
        from config.settings import LOG_LEVEL, LOG_DIR
        return str(LOG_LEVEL), str(LOG_DIR)
    except Exception:
        return "INFO", str(Path(__file__).resolve().parent.parent.parent / "logs")


def get_logger_instance() -> NewsIntelligenceLogger:
    """Get global logger instance. Initializes from settings if not yet setup."""
    global _logger_instance
    if _logger_instance is None:
        log_level, log_dir = _get_defaults()
        _logger_instance = NewsIntelligenceLogger(
            log_level=log_level,
            log_dir=log_dir,
        )
    return _logger_instance


def get_component_logger(component: str) -> logging.Logger:
    """Get logger for specific component (app, api, database, error, finance, etc.)."""
    return get_logger_instance().get_logger(component)


def setup_logging(
    log_level: str | None = None,
    log_dir: str | None = None,
    **kwargs,
) -> NewsIntelligenceLogger:
    """Setup logging system. Uses settings defaults if args not provided."""
    global _logger_instance
    default_level, default_dir = _get_defaults()
    _logger_instance = NewsIntelligenceLogger(
        log_level=log_level or default_level,
        log_dir=log_dir or default_dir,
        **kwargs
    )
    return _logger_instance
