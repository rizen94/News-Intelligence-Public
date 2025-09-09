"""
News Intelligence System v3.1.0 - Monitoring Dashboard
Real-time system monitoring and alerting
"""

import logging
from fastapi import APIRouter, HTTPException
from services.automation_manager import get_automation_manager
from schemas.response_schemas import APIResponse
from datetime import datetime, timezone
import psutil
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/dashboard", response_model=APIResponse)
async def get_monitoring_dashboard():
    """Get comprehensive monitoring dashboard"""
    try:
        automation_manager = get_automation_manager()
        automation_status = automation_manager.get_status()
        automation_metrics = automation_manager.get_metrics()
        
        # System metrics
        system_metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        }
        
        # Database metrics
        db_metrics = await get_database_metrics()
        
        # Application metrics
        app_metrics = {
            'uptime': automation_metrics['performance']['system_uptime'],
            'last_health_check': automation_metrics['performance']['last_health_check'],
            'active_workers': automation_status['active_workers'],
            'queue_size': automation_status['queue_size']
        }
        
        # Task metrics
        task_metrics = {
            'completed': automation_metrics['performance']['tasks_completed'],
            'failed': automation_metrics['performance']['tasks_failed'],
            'avg_processing_time': automation_metrics['performance']['avg_processing_time'],
            'distribution': automation_metrics['task_distribution']
        }
        
        # Health status
        health_status = determine_health_status(system_metrics, app_metrics, task_metrics)
        
        dashboard_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'health_status': health_status,
            'system_metrics': system_metrics,
            'database_metrics': db_metrics,
            'application_metrics': app_metrics,
            'task_metrics': task_metrics,
            'automation_status': automation_status,
            'alerts': generate_alerts(system_metrics, app_metrics, task_metrics)
        }
        
        return APIResponse(
            success=True,
            data=dashboard_data,
            message="Monitoring dashboard retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting monitoring dashboard: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get monitoring dashboard: {str(e)}"
        )

@router.get("/alerts", response_model=APIResponse)
async def get_system_alerts():
    """Get current system alerts"""
    try:
        automation_manager = get_automation_manager()
        automation_status = automation_manager.get_status()
        
        alerts = []
        
        # Check automation status
        if not automation_status['is_running']:
            alerts.append({
                'level': 'critical',
                'message': 'Automation system is not running',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        # Check worker count
        if automation_status['active_workers'] < 3:
            alerts.append({
                'level': 'warning',
                'message': f'Low worker count: {automation_status["active_workers"]}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        # Check queue size
        if automation_status['queue_size'] > 50:
            alerts.append({
                'level': 'warning',
                'message': f'High queue size: {automation_status["queue_size"]}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High CPU usage: {cpu_percent}%',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        if memory_percent > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High memory usage: {memory_percent}%',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        return APIResponse(
            success=True,
            data={'alerts': alerts, 'count': len(alerts)},
            message=f"Retrieved {len(alerts)} alerts"
        )
        
    except Exception as e:
        logger.error(f"Error getting system alerts: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get system alerts: {str(e)}"
        )

async def get_database_metrics():
    """Get database performance metrics"""
    try:
        import psycopg2
        from services.automation_manager import get_automation_manager
        
        automation_manager = get_automation_manager()
        conn = await automation_manager._get_db_connection()
        cursor = conn.cursor()
        
        # Get article count
        cursor.execute("SELECT COUNT(*) FROM articles")
        article_count = cursor.fetchone()[0]
        
        # Get recent articles
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE published_at > NOW() - INTERVAL '1 hour'
        """)
        recent_articles = cursor.fetchone()[0]
        
        # Get database size
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)
        db_size = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            'total_articles': article_count,
            'recent_articles': recent_articles,
            'database_size': db_size,
            'connection_status': 'healthy'
        }
        
    except Exception as e:
        logger.error(f"Error getting database metrics: {e}")
        return {
            'total_articles': 0,
            'recent_articles': 0,
            'database_size': 'unknown',
            'connection_status': 'error',
            'error': str(e)
        }

def determine_health_status(system_metrics, app_metrics, task_metrics):
    """Determine overall system health status"""
    if not app_metrics['active_workers']:
        return 'critical'
    
    if (system_metrics['cpu_percent'] > 90 or 
        system_metrics['memory_percent'] > 90 or
        app_metrics['queue_size'] > 100):
        return 'critical'
    
    if (system_metrics['cpu_percent'] > 70 or 
        system_metrics['memory_percent'] > 70 or
        app_metrics['queue_size'] > 50):
        return 'warning'
    
    return 'healthy'

def generate_alerts(system_metrics, app_metrics, task_metrics):
    """Generate system alerts based on metrics"""
    alerts = []
    
    if system_metrics['cpu_percent'] > 80:
        alerts.append(f"High CPU usage: {system_metrics['cpu_percent']:.1f}%")
    
    if system_metrics['memory_percent'] > 80:
        alerts.append(f"High memory usage: {system_metrics['memory_percent']:.1f}%")
    
    if app_metrics['queue_size'] > 50:
        alerts.append(f"High task queue size: {app_metrics['queue_size']}")
    
    if task_metrics['failed'] > 10:
        alerts.append(f"High task failure rate: {task_metrics['failed']} failures")
    
    return alerts
