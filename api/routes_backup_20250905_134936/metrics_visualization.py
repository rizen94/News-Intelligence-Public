"""
News Intelligence System v3.1.0 - Metrics Visualization API
Provides chart data for monitoring dashboard
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from schemas.response_schemas import APIResponse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/charts/system-resources", response_model=APIResponse)
async def get_system_resources_chart(
    hours: int = Query(168, description="Hours of data to retrieve (default: 168 = 1 week)")
):
    """Get system resources chart data for the last week"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get system metrics for the specified time period
        cursor.execute("""
            SELECT 
                timestamp,
                cpu_percent,
                memory_percent,
                memory_used_mb,
                memory_total_mb,
                disk_percent,
                load_avg_1m
            FROM system_metrics 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY timestamp ASC
        """, (hours,))
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format data for chart
        chart_data = {
            'timestamps': [row['timestamp'].isoformat() for row in data],
            'cpu_percent': [float(row['cpu_percent']) for row in data],
            'memory_percent': [float(row['memory_percent']) for row in data],
            'memory_used_mb': [int(row['memory_used_mb']) for row in data],
            'memory_total_mb': [int(row['memory_total_mb']) for row in data],
            'disk_percent': [float(row['disk_percent']) for row in data],
            'load_avg_1m': [float(row['load_avg_1m']) if row['load_avg_1m'] else 0 for row in data]
        }
        
        return APIResponse(
            success=True,
            data=chart_data,
            message=f"System resources chart data retrieved for last {hours} hours"
        )
        
    except Exception as e:
        logger.error(f"Error getting system resources chart data: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get system resources chart data: {str(e)}"
        )

@router.get("/charts/article-processing", response_model=APIResponse)
async def get_article_processing_chart(
    hours: int = Query(168, description="Hours of data to retrieve (default: 168 = 1 week)")
):
    """Get article processing chart data for the last week"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get application metrics for the specified time period
        cursor.execute("""
            SELECT 
                timestamp,
                articles_processed,
                articles_failed,
                processing_time_ms,
                queue_size,
                active_workers,
                tasks_completed,
                tasks_failed,
                avg_processing_time_ms
            FROM application_metrics 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY timestamp ASC
        """, (hours,))
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format data for chart
        chart_data = {
            'timestamps': [row['timestamp'].isoformat() for row in data],
            'articles_processed': [int(row['articles_processed']) for row in data],
            'articles_failed': [int(row['articles_failed']) for row in data],
            'processing_time_ms': [int(row['processing_time_ms']) for row in data],
            'queue_size': [int(row['queue_size']) for row in data],
            'active_workers': [int(row['active_workers']) for row in data],
            'tasks_completed': [int(row['tasks_completed']) for row in data],
            'tasks_failed': [int(row['tasks_failed']) for row in data],
            'avg_processing_time_ms': [float(row['avg_processing_time_ms']) for row in data]
        }
        
        return APIResponse(
            success=True,
            data=chart_data,
            message=f"Article processing chart data retrieved for last {hours} hours"
        )
        
    except Exception as e:
        logger.error(f"Error getting article processing chart data: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get article processing chart data: {str(e)}"
        )

@router.get("/charts/article-volume", response_model=APIResponse)
async def get_article_volume_chart(
    hours: int = Query(168, description="Hours of data to retrieve (default: 168 = 1 week)")
):
    """Get article volume chart data for the last week"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get article volume metrics for the specified time period
        cursor.execute("""
            SELECT 
                timestamp,
                total_articles,
                new_articles_last_hour,
                new_articles_last_day,
                articles_by_source,
                articles_by_category,
                processing_success_rate
            FROM article_volume_metrics 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY timestamp ASC
        """, (hours,))
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format data for chart
        chart_data = {
            'timestamps': [row['timestamp'].isoformat() for row in data],
            'total_articles': [int(row['total_articles']) for row in data],
            'new_articles_last_hour': [int(row['new_articles_last_hour']) for row in data],
            'new_articles_last_day': [int(row['new_articles_last_day']) for row in data],
            'articles_by_source': [row['articles_by_source'] for row in data],
            'articles_by_category': [row['articles_by_category'] for row in data],
            'processing_success_rate': [float(row['processing_success_rate']) for row in data]
        }
        
        return APIResponse(
            success=True,
            data=chart_data,
            message=f"Article volume chart data retrieved for last {hours} hours"
        )
        
    except Exception as e:
        logger.error(f"Error getting article volume chart data: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get article volume chart data: {str(e)}"
        )

@router.get("/charts/database-performance", response_model=APIResponse)
async def get_database_performance_chart(
    hours: int = Query(168, description="Hours of data to retrieve (default: 168 = 1 week)")
):
    """Get database performance chart data for the last week"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get database metrics for the specified time period
        cursor.execute("""
            SELECT 
                timestamp,
                connection_count,
                active_queries,
                slow_queries,
                avg_query_time_ms,
                database_size_mb
            FROM database_metrics 
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY timestamp ASC
        """, (hours,))
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format data for chart
        chart_data = {
            'timestamps': [row['timestamp'].isoformat() for row in data],
            'connection_count': [int(row['connection_count']) for row in data],
            'active_queries': [int(row['active_queries']) for row in data],
            'slow_queries': [int(row['slow_queries']) for row in data],
            'avg_query_time_ms': [float(row['avg_query_time_ms']) for row in data],
            'database_size_mb': [float(row['database_size_mb']) for row in data]
        }
        
        return APIResponse(
            success=True,
            data=chart_data,
            message=f"Database performance chart data retrieved for last {hours} hours"
        )
        
    except Exception as e:
        logger.error(f"Error getting database performance chart data: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get database performance chart data: {str(e)}"
        )

@router.get("/charts/summary", response_model=APIResponse)
async def get_charts_summary():
    """Get summary of all chart data for the last week"""
    try:
        # Get all chart data
        system_data = await get_system_resources_chart(168)
        processing_data = await get_article_processing_chart(168)
        volume_data = await get_article_volume_chart(168)
        db_data = await get_database_performance_chart(168)
        
        summary = {
            'system_resources': system_data.data if system_data.success else None,
            'article_processing': processing_data.data if processing_data.success else None,
            'article_volume': volume_data.data if volume_data.success else None,
            'database_performance': db_data.data if db_data.success else None,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        return APIResponse(
            success=True,
            data=summary,
            message="All chart data retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting charts summary: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get charts summary: {str(e)}"
        )

async def get_db_connection():
    """Get database connection"""
    db_config = {
        'host': 'news-system-postgres',
        'database': 'newsintelligence',
        'user': 'newsapp',
        'password': 'Database@NEWSINT2025',
        'port': '5432'
    }
    return psycopg2.connect(**db_config)
