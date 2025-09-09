"""
Database Configuration for News Intelligence System v3.1.0
Production-ready database connection management
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

def get_database_config():
    """Get database configuration from environment variables"""
    return {
        "host": os.getenv("DB_HOST", "news-system-postgres"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "newsintelligence"),
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", "Database@NEWSINT2025")
    }

@asynccontextmanager
async def get_db_connection():
    """Get database connection context manager"""
    config = get_database_config()
    conn = None
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            cursor_factory=RealDictCursor
        )
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_db():
    """Get database connection generator for FastAPI dependency injection"""
    config = get_database_config()
    conn = None
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            cursor_factory=RealDictCursor
        )
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()
