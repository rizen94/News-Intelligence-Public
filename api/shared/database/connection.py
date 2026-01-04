"""
Shared Database Connection Module for News Intelligence System v4.0
With connection pooling for improved performance over SSH tunnel.
"""

import os
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Global connection pool (thread-safe)
_connection_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()
_pool_initialized = False


class PooledConnection:
    """
    Wrapper around psycopg2 connection that properly returns to pool on close.
    Transparent wrapper that delegates all operations to underlying connection.
    """
    def __init__(self, conn, pool_ref):
        self._conn = conn
        self._pool = pool_ref
        self._closed = False
    
    def cursor(self, *args, **kwargs):
        """Create cursor - delegate to underlying connection"""
        return self._conn.cursor(*args, **kwargs)
    
    def commit(self):
        """Commit transaction"""
        return self._conn.commit()
    
    def rollback(self):
        """Rollback transaction"""
        return self._conn.rollback()
    
    def close(self):
        """Return connection to pool instead of closing it"""
        if not self._closed:
            if self._pool is not None:
                try:
                    # Return to pool (doesn't actually close the connection)
                    self._pool.putconn(self._conn)
                except Exception as e:
                    logger.warning(f"Error returning connection to pool: {e}")
                    # If pool error, actually close the connection
                    try:
                        self._conn.close()
                    except:
                        pass
            else:
                # No pool, actually close the connection
                try:
                    self._conn.close()
                except:
                    pass
            self._closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only return to pool if no exception, or if exception is handled
        self.close()
        return False  # Don't suppress exceptions
    
    @property
    def closed(self):
        """Check if connection is closed"""
        if self._closed:
            return True
        return getattr(self._conn, 'closed', False)
    
    # Delegate ALL other attributes/methods to underlying connection
    def __getattr__(self, name):
        """Delegate any other attribute access to underlying connection"""
        return getattr(self._conn, name)


def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables
    CRITICAL: System MUST use SSH tunnel to NAS database (localhost:5433)
    Direct connections to 192.168.93.100:5432 are BLOCKED by firewall requirement.
    """
    db_host = os.getenv("DB_HOST")
    db_port_str = os.getenv('DB_PORT', '5433')  # Default to SSH tunnel port
    db_port = int(db_port_str)
    
    # HARD REQUIREMENT: Must use SSH tunnel (localhost:5433)
    if db_host not in ['localhost', '127.0.0.1', '::1']:
        raise ValueError(
            f"❌ DIRECT CONNECTION BLOCKED: DB_HOST='{db_host}' is not allowed.\n"
            "   HARD REQUIREMENT: System MUST use SSH tunnel to NAS database.\n"
            "   Set DB_HOST=localhost DB_PORT=5433\n"
            "   Direct connections to 192.168.93.100:5432 are blocked by firewall."
        )
    
    # HARD REQUIREMENT: Must use SSH tunnel port (5433)
    if db_port != 5433:
        raise ValueError(
            f"❌ INVALID PORT: DB_PORT={db_port} is not allowed.\n"
            "   HARD REQUIREMENT: System MUST use SSH tunnel port 5433.\n"
            "   Set DB_PORT=5433\n"
            "   This connects via SSH tunnel: localhost:5433 -> 192.168.93.100:5432"
        )
    
    # Verify SSH tunnel is running
    import subprocess
    tunnel_check = subprocess.run(
        ["pgrep", "-f", "ssh -L 5433:localhost:5432.*192.168.93.100"],
        capture_output=True
    )
    
    if tunnel_check.returncode != 0:
        raise ValueError(
            "❌ SSH TUNNEL NOT RUNNING: Required SSH tunnel is not active.\n"
            "   Run: ./scripts/setup_nas_ssh_tunnel.sh\n"
            "   The tunnel must be running before starting the API server.\n"
            "   Tunnel: localhost:5433 -> 192.168.93.100:5432"
        )
    
    logger.info("✅ Using SSH tunnel to NAS database (localhost:5433 -> 192.168.93.100:5432)")
    
    return {
        "host": db_host,
        "port": str(db_port),
        "database": os.getenv("DB_NAME", "news_intelligence"),
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", "newsapp_password"),
        "connect_timeout": 2  # 2 second timeout to prevent hanging
    }


def _init_pool() -> pool.ThreadedConnectionPool:
    """Initialize the connection pool (called once)"""
    global _connection_pool, _pool_initialized
    
    with _pool_lock:
        if _connection_pool is not None:
            return _connection_pool
        
        config = get_db_config()
        
        # Log connection info once
        if config["host"] in ['localhost', '127.0.0.1'] and config["port"] == '5433':
            logger.info("✅ Using SSH tunnel to NAS database (localhost:5433 -> 192.168.93.100:5432)")
        
        logger.info(f"🔗 Initializing connection pool: {config['host']}:{config['port']}")
        
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=2,      # Minimum connections to keep open
            maxconn=15,     # Maximum connections (increased for parallel requests)
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=config.get("connect_timeout", 2)  # 2 second timeout
        )
        
        _pool_initialized = True
        logger.info("✅ Connection pool initialized with 2-15 connections")
        
        return _connection_pool


def get_db_connection() -> Optional[psycopg2.extensions.connection]:
    """
    Get database connection from pool (persistent connection).
    IMPORTANT: Always call conn.close() when done - it returns to pool.
    
    Uses connection pooling for better performance and persistence.
    """
    try:
        # Initialize pool if not already done
        pool = _init_pool()
        
        # Get connection from pool
        conn = pool.getconn()
        
        # Return a PooledConnection wrapper that returns to pool on close
        return PooledConnection(conn, pool)
        
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # Fallback to direct connection if pool fails
        try:
            config = get_db_config()
            logger.warning("Falling back to direct connection (pool unavailable)")
            return psycopg2.connect(
                host=config["host"],
                port=config["port"],
                database=config["database"],
                user=config["user"],
                password=config["password"]
            )
        except Exception as e2:
            logger.error(f"Direct connection fallback also failed: {e2}")
            return None


def return_connection(conn: psycopg2.extensions.connection) -> None:
    """Explicitly return a connection to the pool"""
    global _connection_pool
    if _connection_pool is not None and conn is not None:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            logger.warning(f"Error returning connection to pool: {e}")
            try:
                conn.close()
            except:
                pass


def close_pool() -> None:
    """Close all connections in the pool (call on shutdown)"""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Connection pool closed")

def check_database_health() -> Dict[str, Any]:
    """Check database health"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "error": "Cannot connect to database"
            }
        
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            
            if result:
                return {
                    "success": True,
                    "status": "healthy",
                    "message": "Database connection successful"
                }
            else:
                return {
                    "success": False,
                    "error": "Database query failed"
                }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if conn is not None:
            conn.close()
