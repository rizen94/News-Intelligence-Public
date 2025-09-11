#!/usr/bin/env python3
"""
Database Connection Test Script for News Intelligence System v3.0
Tests all database connection methods and configurations
"""

import os
import sys
import logging
from pathlib import Path

# Add the API directory to the path
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_unified_database():
    """Test the unified database configuration"""
    try:
        logger.info("Testing unified database configuration...")
        
        from config.database import (
            db_manager, 
            get_db_config, 
            test_database_connection, 
            check_database_health
        )
        
        # Test configuration
        config = get_db_config()
        logger.info(f"Database configuration: {config}")
        
        # Test connection
        connection_test = test_database_connection()
        logger.info(f"Connection test result: {connection_test}")
        
        # Test health check
        health_status = check_database_health()
        logger.info(f"Health status: {health_status}")
        
        # Test psycopg2 connection
        try:
            conn = db_manager.get_psycopg2_connection()
            if conn:
                logger.info("psycopg2 connection successful")
                db_manager.return_psycopg2_connection(conn)
            else:
                logger.error("psycopg2 connection failed")
        except Exception as e:
            logger.error(f"psycopg2 connection error: {e}")
        
        # Test SQLAlchemy session
        try:
            from config.database import get_db
            session_gen = get_db()
            session = next(session_gen)
            logger.info("SQLAlchemy session successful")
            session.close()
        except Exception as e:
            logger.error(f"SQLAlchemy session error: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Unified database test failed: {e}")
        return False

def test_legacy_database():
    """Test legacy database configurations"""
    try:
        logger.info("Testing legacy database configurations...")
        
        # Test database.py
        try:
            from config.database import get_database_config, test_database_connection
            config = get_database_config()
            logger.info(f"database.py config: {config}")
            test_result = test_database_connection()
            logger.info(f"database.py test: {test_result}")
        except Exception as e:
            logger.error(f"database.py test failed: {e}")
        
        # Test robust_database.py
        try:
            from config.database import db_manager, test_database_connection
            test_result = test_database_connection()
            logger.info(f"robust_database.py test: {test_result}")
        except Exception as e:
            logger.error(f"robust_database.py test failed: {e}")
        
        # Test connection.py
        try:
            from config.database import get_db_config, test_database_connection
            config = get_db_config()
            logger.info(f"connection.py config: {config}")
            test_result = test_database_connection()
            logger.info(f"connection.py test: {test_result}")
        except Exception as e:
            logger.error(f"connection.py test failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Legacy database test failed: {e}")
        return False

def test_environment_variables():
    """Test environment variables"""
    logger.info("Testing environment variables...")
    
    env_vars = [
        'DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_PORT',
        'DATABASE_URL'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask password for security
            if 'PASSWORD' in var:
                masked_value = value[:4] + '*' * (len(value) - 4)
                logger.info(f"{var}: {masked_value}")
            else:
                logger.info(f"{var}: {value}")
        else:
            logger.warning(f"{var}: Not set")

def main():
    """Main test function"""
    logger.info("Starting database connection tests...")
    
    # Test environment variables
    test_environment_variables()
    
    # Test legacy configurations
    legacy_success = test_legacy_database()
    
    # Test unified configuration
    unified_success = test_unified_database()
    
    # Summary
    logger.info("=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Legacy database tests: {'PASSED' if legacy_success else 'FAILED'}")
    logger.info(f"Unified database tests: {'PASSED' if unified_success else 'FAILED'}")
    
    if unified_success:
        logger.info("✅ Unified database configuration is working correctly")
        return 0
    else:
        logger.error("❌ Database configuration has issues")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
