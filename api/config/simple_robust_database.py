#!/usr/bin/env python3
"""
Simple Robust Database Connection Module for News Intelligence System v3.0
Simplified connection pooling with retry logic
"""

import os
import logging
import time
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class SimpleRobustDatabaseManager:
    """Simple robust database connection manager"""
    
    def __init__(self):
        self.config = self._get_db_config()
        self.connection_pool = None
        self.max_retries = 3
        self.retry_delay = 1
        self.pool_size = 5
        self._lock = threading.Lock()
        
    def _get_db_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return {
            'host': os.getenv('DB_HOST', 'postgres'),
            'database': os.getenv('DB_NAME', 'news_system'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'connect_timeout': 10,
            'application_name': 'news_intelligence_app'
        }
    
    def _create_connection_pool(self):
        """Create a new connection pool"""
        try:
            logger.info("Creating simple database connection pool...")
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.pool_size,
                **self.config
            )
            logger.info(f"Connection pool created with {self.pool_size} connections")
            return True
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            return False
    
    def _ensure_pool(self):
        """Ensure connection pool exists"""
        with self._lock:
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
                try:
                    self.connection_pool.closeall()
                except:
                    pass
                self.connection_pool = None
                return self._create_connection_pool()
    
    def get_connection(self, retries: int = None) -> Optional[psycopg2.extensions.connection]:
        """Get a connection with retry logic"""
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
                
                logger.debug(f"Successfully obtained database connection (attempt {attempt + 1})")
                return conn
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                
                if attempt < retries:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"All connection attempts failed after {retries + 1} tries")
                    return None
        
        return None
    
    def return_connection(self, conn: psycopg2.extensions.connection):
        """Return a connection to the pool"""
        if conn and self.connection_pool:
            try:
                self.connection_pool.putconn(conn)
                logger.debug("Connection returned to pool")
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                try:
                    conn.close()
                except:
                    pass
    
    @contextmanager
    def get_cursor(self, retries: int = None):
        """Context manager for database operations"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection(retries)
            if not conn:
                raise Exception("Failed to obtain database connection")
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            yield cursor
            
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)
    
    def test_connection(self) -> bool:
        """Test database connection health"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                return result['test'] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status"""
        if not self.connection_pool:
            return {"status": "not_initialized", "connections": 0}
        
        try:
            return {
                "status": "active",
                "min_connections": 1,
                "max_connections": self.pool_size
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def execute_query(self, query: str, params: tuple = None) -> list:
        """Execute a SELECT query and return results"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an UPDATE/INSERT/DELETE query and return affected rows"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            cursor.connection.commit()
            return cursor.rowcount
    
    def close_pool(self):
        """Close the connection pool"""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
                logger.info("Connection pool closed")
            except Exception as e:
                logger.error(f"Error closing connection pool: {e}")
            finally:
                self.connection_pool = None

# Global database manager instance
db_manager = SimpleRobustDatabaseManager()

# Convenience functions
def get_db_connection():
    """Get a database connection"""
    return db_manager.get_connection()

def get_db_config():
    """Get database configuration"""
    return db_manager.config

def test_database_connection():
    """Test database connection"""
    return db_manager.test_connection()

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    with db_manager.get_cursor() as cursor:
        yield cursor

def check_database_health() -> Dict[str, Any]:
    """Check database health and return status"""
    try:
        is_healthy = db_manager.test_connection()
        pool_status = db_manager.get_pool_status()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "connection_test": is_healthy,
            "pool_status": pool_status,
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }
