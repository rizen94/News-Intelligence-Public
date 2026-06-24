"""
Health check utility functions for domains
Provides a centralized way to perform domain-specific health checks
"""
import logging
from typing import Dict, Any
from shared.database.connection import get_ui_db_connection

logger = logging.getLogger(__name__)

def get_domain_health_check(domain: str) -> Dict[str, Any]:
    """
    Get health check for a specific domain
    
    Args:
        domain: Domain name to check
        
    Returns:
        Health status dictionary for the domain
    """
    # Import domain-specific health check functions
    if domain == "news_aggregation":
        return check_news_aggregation_health()
    elif domain == "content_analysis":
        return check_content_analysis_health()
    elif domain == "storyline_management":
        return check_storyline_management_health()
    elif domain == "intelligence_hub":
        return check_intelligence_hub_health()
    elif domain == "system_monitoring":
        return check_system_monitoring_health()
    elif domain == "user_management":
        return check_user_management_health()
    elif domain == "public_auth":
        return check_public_auth_health()
    elif domain == "finance":
        return check_finance_health()
    elif domain == "politics":
        return check_politics_health()
    else:
        logger.warning(f"Unknown domain requested for health check: {domain}")
        return {
            "domain": domain,
            "status": "unhealthy",
            "error": f"Unknown domain: {domain}"
        }

def check_news_aggregation_health() -> Dict[str, Any]:
    """Health check for news aggregation domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            conn.close()
            
        if result:
            return {"status": "healthy"}
        else:
            return {"status": "unhealthy", "error": "Database query failed"}
    except Exception as e:
        logger.error(f"News aggregation health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_content_analysis_health() -> Dict[str, Any]:
    """Health check for content analysis domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Check if topic clustering tables exist and are accessible
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'intelligence' AND table_name = 'topic_clusters'")
            result = cur.fetchone()
            conn.close()
            
        if result and result[0] > 0:
            return {"status": "healthy"}
        else:
            return {"status": "healthy"}  # Still healthy if table doesn't exist yet
    except Exception as e:
        logger.error(f"Content analysis health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_storyline_management_health() -> Dict[str, Any]:
    """Health check for storyline management domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Check if storyline tables exist
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'intelligence' AND table_name = 'storylines'")
            result = cur.fetchone()
            conn.close()
            
        if result and result[0] > 0:
            return {"status": "healthy"}
        else:
            return {"status": "healthy"}  # Still healthy if table doesn't exist yet
    except Exception as e:
        logger.error(f"Storyline management health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_intelligence_hub_health() -> Dict[str, Any]:
    """Health check for intelligence hub domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        # Basic connectivity check
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            conn.close()
            
        if result:
            return {"status": "healthy"}
        else:
            return {"status": "unhealthy", "error": "Database query failed"}
    except Exception as e:
        logger.error(f"Intelligence hub health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_system_monitoring_health() -> Dict[str, Any]:
    """Health check for system monitoring domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Check automation run history table
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'intelligence' AND table_name = 'automation_run_history'")
            result = cur.fetchone()
            conn.close()
            
        if result and result[0] > 0:
            return {"status": "healthy"}
        else:
            return {"status": "healthy"}  # Still healthy if table doesn't exist yet
    except Exception as e:
        logger.error(f"System monitoring health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_user_management_health() -> Dict[str, Any]:
    """Health check for user management domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Check user tables
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users'")
            result = cur.fetchone()
            conn.close()
            
        if result and result[0] > 0:
            return {"status": "healthy"}
        else:
            return {"status": "healthy"}  # Still healthy if table doesn't exist yet
    except Exception as e:
        logger.error(f"User management health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_public_auth_health() -> Dict[str, Any]:
    """Health check for public auth domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Basic connectivity check
            cur.execute("SELECT 1")
            result = cur.fetchone()
            conn.close()
            
        if result:
            return {"status": "healthy"}
        else:
            return {"status": "unhealthy", "error": "Database query failed"}
    except Exception as e:
        logger.error(f"Public auth health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_finance_health() -> Dict[str, Any]:
    """Health check for finance domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Check finance tables
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'finance'")
            result = cur.fetchone()
            conn.close()
            
        if result and result[0] > 0:
            return {"status": "healthy"}
        else:
            return {"status": "healthy"}  # Still healthy if tables don't exist yet
    except Exception as e:
        logger.error(f"Finance health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

def check_politics_health() -> Dict[str, Any]:
    """Health check for politics domain"""
    try:
        conn = get_ui_db_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        with conn.cursor() as cur:
            # Check politics tables
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'politics'")
            result = cur.fetchone()
            conn.close()
            
        if result and result[0] > 0:
            return {"status": "healthy"}
        else:
            return {"status": "healthy"}  # Still healthy if tables don't exist yet
    except Exception as e:
        logger.error(f"Politics health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}