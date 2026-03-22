"""
Shared database connection module for the News Intelligence system
With connection pooling for improved performance over SSH tunnel.
Single source of truth for all DB connections (psycopg2 + SQLAlchemy).

Reviewers: all application and script DB access should go through
``get_db_connection`` / ``get_db_connection_context`` here — not raw ``psycopg2.connect``
or duplicate env parsing. Config is **only** ``DB_*`` environment variables
(see ``get_db_config``). Docker samples that use ``DATABASE_URL`` are not authoritative.

Pool architecture (3 independent pools, same PostgreSQL instance):
  - Worker pool (psycopg2): background processing — DB_POOL_WORKER_MIN/MAX (default 4/48)
  - UI pool     (psycopg2): page loads & monitoring — DB_POOL_UI_MIN/MAX     (default 2/16)
  - SA pool   (SQLAlchemy): ORM-based services      — DB_POOL_SA_SIZE/OVERFLOW (default 4/12)

RULES (see also CODING_STYLE_GUIDE.md § Database Connection Rules):
  1. Always use get_db_connection_context() or try/finally conn.close().
  2. Never hold a connection across an LLM call, HTTP request, or sleep.
  3. Worker pool has a default checkout timeout (30 s) to surface leaks early.
  4. UI pool has a 3 s checkout timeout so page loads fail fast.
"""

import os
import logging
import time
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, Generator
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# SQLAlchemy engine (lazy init, independent pool from psycopg2)
_sqlalchemy_engine = None
_sqlalchemy_session_factory = None
_sqlalchemy_lock = threading.Lock()

# Global connection pools (thread-safe)
_connection_pool: Optional[pool.ThreadedConnectionPool] = None           # Worker/data-processing pool
_ui_connection_pool: Optional[pool.ThreadedConnectionPool] = None        # UI/monitoring reserved pool
_pool_lock = threading.Lock()
_pool_initialized = False
_ui_pool_initialized = False


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
        """Return connection to pool instead of closing it. Rollback first so the next user doesn't get 'aborted transaction'."""
        if not self._closed:
            try:
                self._conn.rollback()
            except Exception:
                pass
            if self._pool is not None:
                try:
                    self._pool.putconn(self._conn)
                except Exception as e:
                    logger.warning(f"Error returning connection to pool: {e}")
                    try:
                        self._conn.close()
                    except Exception:
                        pass
            else:
                try:
                    self._conn.close()
                except Exception:
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
    Get database configuration from environment variables.
    Supports two modes:
    - Widow (secondary): DB_HOST=192.168.93.101, DB_PORT=5432, DB_NAME=news_intel
    - NAS via tunnel (rollback): DB_HOST=localhost, DB_PORT=5433, DB_NAME=news_intelligence
    """
    db_host = os.getenv("DB_HOST", "192.168.93.101")
    db_port_str = os.getenv("DB_PORT", "5432")
    db_port = int(db_port_str)
    db_name = os.getenv("DB_NAME", "news_intel")
    
    # NAS tunnel mode: localhost:5433 requires tunnel to be running
    if db_host in ["localhost", "127.0.0.1", "::1"] and db_port == 5433:
        import subprocess
        tunnel_check = subprocess.run(
            ["pgrep", "-f", "ssh -L 5433:localhost:5432"],
            capture_output=True,
        )
        if tunnel_check.returncode != 0:
            raise ValueError(
                "SSH TUNNEL NOT RUNNING: DB_HOST=localhost:5433 requires tunnel. "
                "Run: ./scripts/setup_nas_ssh_tunnel.sh"
            )
        logger.info("Using SSH tunnel to NAS (localhost:5433 -> NAS host:5432)")
    else:
        logger.info("Using direct connection to database: %s:%s", db_host, db_port)
    
    connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
    # Statement timeout: applied to every pool connection. Planned long work (migrations, backfills)
    # must run with a separate connection and SET statement_timeout = 0 at session start.
    # Default 2 min so automation phases and batch jobs don't get killed early; use
    # DB_STATEMENT_TIMEOUT_MS=300000 (5 min) or 0 (disable) in .env if needed.
    statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "120000"))
    return {
        "host": db_host,
        "port": str(db_port),
        "database": db_name,
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": connect_timeout,
        "statement_timeout_ms": statement_timeout_ms,
    }


def get_db_connect_kwargs() -> Dict[str, Any]:
    """
    Return kwargs suitable for psycopg2.connect() (same config + timeouts).
    Use for code that must open a one-off connection instead of the pool.
    """
    config = get_db_config()
    timeout_ms = config.get("statement_timeout_ms", 120000)
    return {
        "host": config["host"],
        "port": config["port"],
        "database": config["database"],
        "user": config["user"],
        "password": config["password"],
        "connect_timeout": config.get("connect_timeout", 5),
        "options": f"-c statement_timeout={timeout_ms}",
    }


def _pool_sizes(pool_kind: str) -> tuple[int, int]:
    """Return (minconn, maxconn) for worker or ui pool."""
    # Backward-compatible fallback for worker pool
    legacy_min = int(os.getenv("DB_POOL_MIN", "2"))
    legacy_max = int(os.getenv("DB_POOL_MAX", "20"))
    if pool_kind == "ui":
        minconn = int(os.getenv("DB_POOL_UI_MIN", "2"))
        maxconn = int(os.getenv("DB_POOL_UI_MAX", "16"))
    else:
        minconn = int(os.getenv("DB_POOL_WORKER_MIN", str(max(legacy_min, 4))))
        maxconn = int(os.getenv("DB_POOL_WORKER_MAX", str(max(legacy_max, 48))))
    maxconn = max(minconn, min(maxconn, 100))
    return minconn, maxconn


def _init_pool(pool_kind: str = "worker") -> pool.ThreadedConnectionPool:
    """Initialize worker/ui connection pools."""
    global _connection_pool, _ui_connection_pool, _pool_initialized, _ui_pool_initialized

    with _pool_lock:
        if pool_kind == "ui":
            if _ui_connection_pool is not None:
                return _ui_connection_pool
        else:
            if _connection_pool is not None:
                return _connection_pool

        config = get_db_config()
        minconn, maxconn = _pool_sizes(pool_kind)
        timeout_ms = config.get("statement_timeout_ms", 120000)
        options = f"-c statement_timeout={timeout_ms}"

        logger.info(
            "Initializing %s DB pool: %s:%s/%s (pool %s-%s, statement_timeout=%sms)",
            pool_kind, config["host"], config["port"], config["database"], minconn, maxconn, timeout_ms,
        )

        created_pool = pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=config.get("connect_timeout", 5),
            options=options,
        )
        if pool_kind == "ui":
            _ui_connection_pool = created_pool
            _ui_pool_initialized = True
        else:
            _connection_pool = created_pool
            _pool_initialized = True

        logger.info("%s DB pool initialized: %s-%s connections", pool_kind, minconn, maxconn)
        return created_pool


def _validate_connection(conn) -> bool:
    """Run a quick check; return True if connection is alive."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def _getconn_from_pool(pool_ref):
    """Get one connection from pool and validate; used with optional timeout."""
    for _ in range(2):
        conn = pool_ref.getconn()
        if _validate_connection(conn):
            return PooledConnection(conn, pool_ref)
        try:
            conn.close()
        except Exception:
            pass
    return None


def get_db_connection(use_reserved: bool = False):
    """
    Get a live database connection from the pool.
    Always use with get_db_connection_context() or try/finally: conn.close() when done (returns to pool).
    If DB_GETCONN_TIMEOUT_SECONDS is set (e.g. 30), getconn will raise after that many seconds
    instead of blocking forever when the pool is exhausted (avoids crashing the process).
    Raises if the database is unreachable (e.g. turned off); no silent None.
    """
    pool_kind = "ui" if use_reserved else "worker"
    timeout_sec = None
    # Pool-specific checkout timeout (seconds). Prevents monitor/page-load hangs when pool is saturated.
    # Priority: DB_UI_GETCONN_TIMEOUT_SECONDS / DB_WORKER_GETCONN_TIMEOUT_SECONDS -> DB_GETCONN_TIMEOUT_SECONDS
    timeout_env = (
        "DB_UI_GETCONN_TIMEOUT_SECONDS"
        if pool_kind == "ui"
        else "DB_WORKER_GETCONN_TIMEOUT_SECONDS"
    )
    default_timeout = "3" if pool_kind == "ui" else "30"
    timeout_raw = os.getenv(timeout_env, os.getenv("DB_GETCONN_TIMEOUT_SECONDS", default_timeout))
    try:
        timeout_sec = int(timeout_raw)
    except ValueError:
        timeout_sec = int(default_timeout)

    if timeout_sec <= 0:
        timeout_sec = int(default_timeout)

    import concurrent.futures
    pool_ref = _init_pool(pool_kind=pool_kind)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_getconn_from_pool, pool_ref)
        try:
            conn = fut.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            raise ConnectionError(
                f"Database {pool_kind} pool timeout after {timeout_sec}s (pool likely exhausted). "
                "Check for connection leaks: use get_db_connection_context() or conn.close() in finally."
            ) from None
    if conn is not None:
        return conn
    logger.warning("%s pool returned stale connections; trying direct connect", pool_kind)

    try:
        kwargs = get_db_connect_kwargs()
        raw = psycopg2.connect(**kwargs)
        if _validate_connection(raw):
            return PooledConnection(raw, None)
        try:
            raw.close()
        except Exception:
            pass
    except Exception as e2:
        logger.error(f"Direct connection failed: {e2}")
    raise ConnectionError(
        "Database connection failed (pool and direct). "
        "Check DB_HOST, DB_PORT, DB_PASSWORD in .env and that the database is running."
    )


def close_pool() -> None:
    """Close all worker/UI pools (call on shutdown)."""
    global _connection_pool, _ui_connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Worker connection pool closed")
    if _ui_connection_pool is not None:
        _ui_connection_pool.closeall()
        _ui_connection_pool = None
        logger.info("UI connection pool closed")

def probe_database_server_reachable(connect_timeout: Optional[int] = None) -> bool:
    """
    True if a **new** connection to PostgreSQL succeeds and SELECT 1 works.

    Does **not** use the worker/UI pools. Use this for automation "is DB up?" checks so that
    **pool exhaustion** (checkout timeout) is not mistaken for an offline database.
    """
    raw = None
    try:
        kwargs = dict(get_db_connect_kwargs())
        if connect_timeout is not None:
            kwargs["connect_timeout"] = int(connect_timeout)
        else:
            try:
                probe_sec = int(os.getenv("DB_AUTOMATION_PROBE_CONNECT_TIMEOUT", "4"))
            except ValueError:
                probe_sec = 4
            kwargs["connect_timeout"] = min(probe_sec, int(kwargs.get("connect_timeout", 5) or 5))
        # Short session timeout — probe only
        kwargs["options"] = "-c statement_timeout=3000"
        raw = psycopg2.connect(**kwargs)
        with raw.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        if raw is not None:
            try:
                raw.close()
            except Exception:
                pass


def check_database_health() -> Dict[str, Any]:
    """Check database health via the **connection pool** (same path as normal app work)."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
        if result:
            return {
                "success": True,
                "status": "healthy",
                "message": "Database connection successful"
            }
        return {"success": False, "error": "Database query failed"}
    except ConnectionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _init_sqlalchemy():
    """Lazy-init SQLAlchemy engine (independent pool from psycopg2). Pool size via DB_POOL_SA_*."""
    global _sqlalchemy_engine, _sqlalchemy_session_factory
    with _sqlalchemy_lock:
        if _sqlalchemy_engine is not None:
            return
        config = get_db_config()
        timeout_ms = config.get("statement_timeout_ms", 120000)
        url = (
            f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
            f"?connect_timeout={config.get('connect_timeout', 5)}"
            f"&options=-c statement_timeout%3D{timeout_ms}"
        )
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sa_pool_size = int(os.getenv("DB_POOL_SA_SIZE", "4"))
        sa_max_overflow = int(os.getenv("DB_POOL_SA_OVERFLOW", "12"))
        sa_pool_size = min(sa_pool_size, 10)
        sa_max_overflow = min(sa_max_overflow, 20)
        _sqlalchemy_engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=sa_pool_size,
            max_overflow=sa_max_overflow,
            pool_timeout=30,
            echo=False,
        )
        _sqlalchemy_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_sqlalchemy_engine)
        logger.info("SQLAlchemy engine initialized (pool %s+%s, statement_timeout=%sms)", sa_pool_size, sa_max_overflow, timeout_ms)


def get_db() -> Generator:
    """SQLAlchemy session generator (use: session = next(get_db()))"""
    _init_sqlalchemy()
    session = _sqlalchemy_session_factory()
    try:
        yield session
    finally:
        session.close()


def get_db_session():
    """Return a SQLAlchemy session directly (caller must close)"""
    _init_sqlalchemy()
    return _sqlalchemy_session_factory()


@contextmanager
def get_db_connection_context():
    """
    Context manager for a pooled DB connection. Always returns the connection to the pool on exit.
    Use this to avoid leaks: 'with get_db_connection_context() as conn: ...'
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_ui_db_connection():
    """Get DB connection from reserved UI/monitoring pool."""
    return get_db_connection(use_reserved=True)


@contextmanager
def get_ui_db_connection_context():
    """Context manager for reserved UI/monitoring pool connections."""
    conn = get_ui_db_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_cursor():
    """Context manager for psycopg2 cursor with RealDictCursor. Raises if DB unreachable."""
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()


def test_database_connection() -> bool:
    """Test DB connection; returns True if healthy"""
    result = check_database_health()
    return result.get("success", False)


def get_database_url() -> str:
    """PostgreSQL URL for SQLAlchemy (legacy compat)"""
    config = get_db_config()
    return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"


# Alias for legacy imports
get_database_config = get_db_config
