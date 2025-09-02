#!/usr/bin/env python3
"""
Database Configuration Module for News Intelligence System v3.0
FastAPI-compatible database connection management
"""

import os
import logging
import asyncio
import psycopg2
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

def get_db_config():
    """Get database configuration"""
    return {
        'host': os.getenv('DB_HOST', 'postgres'),
        'database': os.getenv('DB_NAME', 'news_system'),
        'user': os.getenv('DB_USER', 'NewsInt_DB'),
        'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
        'port': os.getenv('DB_PORT', '5432')
    }

async def get_db_connection():
    """Get database connection for async operations"""
    config = get_db_config()
    return psycopg2.connect(**config)

async def init_database():
    """Initialize database connection"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        logger.info("Database connection established")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    try:
        config = get_db_config()
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
