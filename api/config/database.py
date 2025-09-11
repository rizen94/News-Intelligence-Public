#!/usr/bin/env python3
"""
News Intelligence System v3.0 - Unified Database Configuration
Single source of truth for all database connections and configurations
"""

import os
import logging
import time
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import psycopg2.extensions
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Unified database connection manager with comprehensive error handling"""
    
    def __init__(self):
        self.config = self._get_database_config()
        self.connection_pool = None
        self.sqlalchemy_engine = None
        self.sqlalchemy_session = None
        
        # Connection settings
        self.max_retries = 5
        self.retry_delay = 1
        self.connection_timeout = 30
        self.pool_size = 10
        self.max_overflow = 5
        self._lock = threading.Lock()
        self._last_health_check = 0
        self._health_check_interval = 30
        
        # Initialize connections
        self._initialize_connections()
    
    def _get_database_config(self) -> Dict[str, Any]:
        """Get unified database configuration with proper fallbacks"""
        # Standardized configuration - single source of truth
        config = {
            'host': os.getenv('DB_HOST', 'news-intelligence-postgres'),
            'database': os.getenv('DB_NAME', 'news_intelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'connect_timeout': 10,
            'application_name': 'news_intelligence_app'
        }
        
        # Validate configuration
        required_fields = ['host', 'database', 'user', 'password', 'port']
        for field in required_fields:
            if not config.get(field):
                raise ValueError(f"Database configuration missing required field: {field}")
        
        logger.info(f"Database configuration loaded: {config['host']}:{config['port']}/{config['database']}")
        return config
    
    def _initialize_connections(self):
        """Initialize both psycopg2 and SQLAlchemy connections"""
        try:
            # Initialize psycopg2 connection pool
            self._create_connection_pool()
            
            # Initialize SQLAlchemy engine
            self._create_sqlalchemy_engine()
            
            logger.info("Database connections initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connections: {e}")
            raise
    
    def _create_connection_pool(self):
        """Create psycopg2 connection pool"""
        try:
            logger.info("Creating psycopg2 connection pool...")
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.pool_size + self.max_overflow,
                **self.config
            )
            logger.info(f"psycopg2 connection pool created with {self.pool_size} connections")
        except Exception as e:
            logger.error(f"Failed to create psycopg2 connection pool: {e}")
            raise
    
    def _create_sqlalchemy_engine(self):
        """Create SQLAlchemy engine"""
        try:
            # Build SQLAlchemy URL
            sqlalchemy_url = f"postgresql://{self.config['user']}:{self.config['password']}@{self.config['host']}:{self.config['port']}/{self.config['database']}"
            
            logger.info("Creating SQLAlchemy engine...")
            self.sqlalchemy_engine = create_engine(
                sqlalchemy_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=10,
                max_overflow=20,
                echo=False  # Set to True for SQL debugging
            )
            
            # Create session factory
            self.sqlalchemy_session = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.sqlalchemy_engine
            )
            
            logger.info("SQLAlchemy engine created successfully")
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise
    
    def _ensure_pool(self):
        """Ensure connection pool exists and is healthy"""
        with self._lock:
            current_time = time.time()
            
            # Check if pool needs health check
            if (current_time - self._last_health_check) > self._health_check_interval:
                self._last_health_check = current_time
                
                if self.connection_pool is None:
                    return self._create_connection_pool()
                
                # Test pool health
                try:
                    conn = self.connection_pool.getconn()
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    self.connection_pool.putconn(conn)
                    return True
                except Exception as e:
                    logger.warning(f"Connection pool health check failed: {e}")
                    # Close existing pool and create new one
                    try:
                        self.connection_pool.closeall()
                    except:
                        pass
                    self.connection_pool = None
                    return self._create_connection_pool()
            
            return self.connection_pool is not None
    
    def get_psycopg2_connection(self, retries: int = None) -> Optional[psycopg2.extensions.connection]:
        """Get a psycopg2 connection from the pool with retry logic"""
        if retries is None:
            retries = self.max_retries
            
        for attempt in range(retries + 1):
            try:
                if not self._ensure_pool():
                    raise Exception("Failed to ensure connection pool")
                
                conn = self.connection_pool.getconn()
                
                # Test the connection
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                
                logger.debug(f"Successfully obtained psycopg2 connection (attempt {attempt + 1})")
                return conn
                
            except Exception as e:
                logger.warning(f"psycopg2 connection attempt {attempt + 1} failed: {e}")
                
                if attempt < retries:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"All psycopg2 connection attempts failed after {retries + 1} tries")
                    return None
        
        return None
    
    def return_psycopg2_connection(self, conn: psycopg2.extensions.connection):
        """Return a psycopg2 connection to the pool"""
        if conn and self.connection_pool:
            try:
                self.connection_pool.putconn(conn)
                logger.debug("psycopg2 connection returned to pool")
            except Exception as e:
                logger.error(f"Error returning psycopg2 connection to pool: {e}")
                try:
                    conn.close()
                except:
                    pass
    
    def get_sqlalchemy_session(self) -> Generator[Session, None, None]:
        """Get SQLAlchemy session"""
        if not self.sqlalchemy_session:
            raise Exception("SQLAlchemy session not initialized")
        
        session = self.sqlalchemy_session()
        try:
            yield session
        finally:
            session.close()
    
    @contextmanager
    def get_psycopg2_cursor(self, retries: int = None):
        """Context manager for psycopg2 database operations"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_psycopg2_connection(retries)
            if not conn:
                raise Exception("Failed to obtain psycopg2 connection")
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            yield cursor
            
        except Exception as e:
            logger.error(f"psycopg2 database operation failed: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_psycopg2_connection(conn)
    
    def execute_query(self, query: str, params: tuple = None, retries: int = None) -> list:
        """Execute a SELECT query and return results"""
        with self.get_psycopg2_cursor(retries) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None, retries: int = None) -> int:
        """Execute an UPDATE/INSERT/DELETE query and return affected rows"""
        with self.get_psycopg2_cursor(retries) as cursor:
            cursor.execute(query, params)
            cursor.connection.commit()
            return cursor.rowcount
    
    def test_connection(self) -> bool:
        """Test database connection health"""
        try:
            with self.get_psycopg2_cursor() as cursor:
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                return result['test'] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status"""
        status = {
            "timestamp": time.time(),
            "psycopg2_pool": "not_initialized",
            "sqlalchemy_engine": "not_initialized",
            "connection_test": False
        }
        
        try:
            # Test psycopg2 pool
            if self.connection_pool:
                status["psycopg2_pool"] = "active"
            
            # Test SQLAlchemy engine
            if self.sqlalchemy_engine:
                status["sqlalchemy_engine"] = "active"
            
            # Test actual connection
            status["connection_test"] = self.test_connection()
            
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def close_all_connections(self):
        """Close all database connections"""
        try:
            if self.connection_pool:
                self.connection_pool.closeall()
                logger.info("psycopg2 connection pool closed")
            
            if self.sqlalchemy_engine:
                self.sqlalchemy_engine.dispose()
                logger.info("SQLAlchemy engine disposed")
                
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
        finally:
            self.connection_pool = None
            self.sqlalchemy_engine = None
            self.sqlalchemy_session = None

# Global database manager instance - SINGLE SOURCE OF TRUTH
db_manager = DatabaseManager()

# Standardized API functions - Use these throughout the application
def get_db_connection():
    """Get a psycopg2 database connection"""
    return db_manager.get_psycopg2_connection()

def get_db():
    """Get SQLAlchemy database session (for FastAPI dependency injection)"""
    return db_manager.get_sqlalchemy_session()

def get_db_config():
    """Get database configuration"""
    return db_manager.config

def test_database_connection():
    """Test database connection"""
    return db_manager.test_connection()

@contextmanager
def get_db_cursor():
    """Context manager for psycopg2 database operations"""
    with db_manager.get_psycopg2_cursor() as cursor:
        yield cursor

def check_database_health() -> Dict[str, Any]:
    """Check database health and return comprehensive status"""
    try:
        status = db_manager.get_connection_status()
        
        return {
            "status": "healthy" if status["connection_test"] else "unhealthy",
            "details": status,
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

# Backward compatibility functions
def get_database_url():
    """Get database URL for SQLAlchemy"""
    config = db_manager.config
    return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"

def get_database_config():
    """Get database configuration (legacy compatibility)"""
    return db_manager.config