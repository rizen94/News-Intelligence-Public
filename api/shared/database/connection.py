"""
Shared Database Connection Module for News Intelligence System v4.0
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def get_db_config() -> Dict[str, Any]:
    """Get database configuration from environment variables"""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "news_intelligence"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "password")
    }

def get_db_connection() -> Optional[psycopg2.extensions.connection]:
    """Get database connection"""
    try:
        config = get_db_config()
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"]
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def check_database_health() -> Dict[str, Any]:
    """Check database health"""
    try:
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "error": "Cannot connect to database"
            }
        
        try:
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
        finally:
            conn.close()
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
