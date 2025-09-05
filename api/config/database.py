#!/usr/bin/env python3
"""
Database Configuration Module for News Intelligence System v3.0
FastAPI-compatible database connection management with robust connection pooling
"""

import os
import logging
import asyncio
import psycopg2
from contextlib import asynccontextmanager
from .simple_robust_database import db_manager, get_db_cursor, check_database_health

logger = logging.getLogger(__name__)

def get_db_config():
    """Get database configuration"""
    return db_manager.config

async def get_db_connection():
    """Get database connection for async operations"""
    return db_manager.get_connection()

async def init_database():
    """Initialize database connection"""
    try:
        # Initialize the robust database manager
        if not db_manager._ensure_pool():
            logger.error("Failed to initialize database connection pool")
            return False
        
        # Test the connection
        if db_manager.test_connection():
            logger.info("Database connection established with robust pooling")
            return True
        else:
            logger.error("Database connection test failed")
            return False
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    return db_manager.test_connection()

# New robust functions
def get_robust_connection():
    """Get a robust database connection with retry logic"""
    return db_manager.get_connection()

def execute_query(query: str, params: tuple = None):
    """Execute a SELECT query with robust connection handling"""
    return db_manager.execute_query(query, params)

def execute_update(query: str, params: tuple = None):
    """Execute an UPDATE/INSERT/DELETE query with robust connection handling"""
    return db_manager.execute_update(query, params)

def get_database_health():
    """Get comprehensive database health status"""
    return check_database_health()
