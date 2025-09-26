"""
News Intelligence System v3.0 - Monitoring Dashboard
Real-time system monitoring and alerting
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
import psutil
import asyncio
import subprocess

from config.database import get_db, get_db_connection
from psycopg2.extras import RealDictCursor
from schemas.robust_schemas import APIResponse

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

async def get_database_metrics():
    """Get real-time database metrics by querying the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get total articles count
        cursor.execute("SELECT COUNT(*) as total_articles FROM articles")
        total_articles = cursor.fetchone()['total_articles']
        
        # Get recent articles (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) as recent_articles 
            FROM articles 
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        recent_articles = cursor.fetchone()['recent_articles']
        
        # Get total RSS feeds count
        cursor.execute("SELECT COUNT(*) as total_rss_feeds FROM rss_feeds")
        total_rss_feeds = cursor.fetchone()['total_rss_feeds']
        
        # Get total storylines count
        cursor.execute("SELECT COUNT(*) as total_storylines FROM storylines")
        total_storylines = cursor.fetchone()['total_storylines']
        
        # Get database size (approximate)
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size(current_database())) as database_size
        """)
        database_size = cursor.fetchone()['database_size']
        
        cursor.close()
        conn.close()
        
        return {
            'total_articles': total_articles,
            'recent_articles': recent_articles,
            'total_rss_feeds': total_rss_feeds,
            'total_storylines': total_storylines,
            'database_size': database_size,
            'connection_status': 'healthy'
        }
        
    except Exception as e:
        logger.error(f"Error getting database metrics: {e}")
        return {
            'total_articles': 0,
            'recent_articles': 0,
            'total_rss_feeds': 0,
            'total_storylines': 0,
            'database_size': 'unknown',
            'connection_status': 'error'
        }

def get_gpu_metrics():
    """Get GPU metrics using nvidia-smi"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'], 
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            gpu_info = result.stdout.strip().split(',')
            if len(gpu_info) >= 4:
                memory_used_mb = int(gpu_info[0])
                memory_total_mb = int(gpu_info[1])
                utilization_percent = int(gpu_info[2])
                temperature_c = int(gpu_info[3])
                
                return {
                    'gpu_memory_used_mb': memory_used_mb,
                    'gpu_memory_total_mb': memory_total_mb,
                    'gpu_vram_percent': round((memory_used_mb / memory_total_mb) * 100, 1),
                    'gpu_utilization_percent': utilization_percent,
                    'gpu_temperature_c': temperature_c
                }
    except Exception as e:
        logger.debug(f"GPU metrics collection failed: {e}")
    
    return {
        'gpu_memory_used_mb': 0,
        'gpu_memory_total_mb': 0,
        'gpu_vram_percent': 0,
        'gpu_utilization_percent': 0,
        'gpu_temperature_c': 0
    }

@router.get("/dashboard", response_model=APIResponse)
async def get_monitoring_dashboard():
    """Get comprehensive monitoring dashboard"""
    try:
        # System metrics
        system_metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        }
        
        # Add GPU metrics
        gpu_metrics = get_gpu_metrics()
        system_metrics.update(gpu_metrics)
        
        # Database metrics - query real data
        db_metrics = await get_database_metrics()
        
        # Application metrics
        app_metrics = {
            'uptime': get_system_uptime(),
            'last_health_check': datetime.now(timezone.utc).isoformat(),
            'active_workers': 1,  # Placeholder - can be enhanced with actual worker tracking
            'queue_size': 0  # Placeholder - can be enhanced with actual queue tracking
        }
        
        # Task metrics - hardcoded for now
        task_metrics = {
            'completed': 15,
            'failed': 0,
            'avg_processing_time': 0.0,
            'distribution': {}
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
async def get_system_alerts(db: Session = Depends(get_db)):
    """Get current system alerts"""
    try:
        alerts = []
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        # Check system resources
        if cpu_percent > 90:
            alerts.append({
                'level': 'critical',
                'message': f'Critical CPU usage: {cpu_percent:.1f}%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'system'
            })
        elif cpu_percent > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High CPU usage: {cpu_percent:.1f}%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'system'
            })
        
        if memory_percent > 90:
            alerts.append({
                'level': 'critical',
                'message': f'Critical memory usage: {memory_percent:.1f}%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'system'
            })
        elif memory_percent > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High memory usage: {memory_percent:.1f}%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'system'
            })
        
        if disk_percent > 90:
            alerts.append({
                'level': 'critical',
                'message': f'Critical disk usage: {disk_percent:.1f}%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'system'
            })
        elif disk_percent > 80:
            alerts.append({
                'level': 'warning',
                'message': f'High disk usage: {disk_percent:.1f}%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'system'
            })
        
        # Check database health
        try:
            db_metrics = await get_database_metrics(db)
            if db_metrics.get('connection_status') != 'healthy':
                alerts.append({
                    'level': 'critical',
                    'message': f'Database connection issue: {db_metrics.get("error", "Unknown error")}',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'category': 'database'
                })
        except Exception as e:
            alerts.append({
                'level': 'critical',
                'message': f'Database health check failed: {str(e)}',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'database'
            })
        
        # Check article processing
        try:
            recent_articles = db.execute(text("""
                SELECT COUNT(*) FROM articles 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)).fetchone()[0] or 0
            
            if recent_articles == 0:
                alerts.append({
                    'level': 'warning',
                    'message': 'No articles processed in the last hour',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'category': 'processing'
                })
        except Exception as e:
            alerts.append({
                'level': 'warning',
                'message': f'Article processing check failed: {str(e)}',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'category': 'processing'
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

@router.get("/metrics/system", response_model=APIResponse)
async def get_system_metrics():
    """Get detailed system metrics"""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        # Network metrics
        network = psutil.net_io_counters()
        
        metrics = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cpu': {
                'percent_total': psutil.cpu_percent(interval=1),
                'percent_per_core': cpu_percent,
                'count': cpu_count,
                'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent,
                'swap_total': swap.total,
                'swap_used': swap.used,
                'swap_percent': swap.percent
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent,
                'read_bytes': disk_io.read_bytes if disk_io else 0,
                'write_bytes': disk_io.write_bytes if disk_io else 0
            },
            'network': {
                'bytes_sent': network.bytes_sent if network else 0,
                'bytes_recv': network.bytes_recv if network else 0,
                'packets_sent': network.packets_sent if network else 0,
                'packets_recv': network.packets_recv if network else 0
            }
        }
        
        return APIResponse(
            success=True,
            data=metrics,
            message="System metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/database", response_model=APIResponse)
async def get_database_metrics_endpoint(db: Session = Depends(get_db)):
    """Get detailed database metrics"""
    try:
        metrics = await get_database_metrics(db)
        
        return APIResponse(
            success=True,
            data=metrics,
            message="Database metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting database metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/application", response_model=APIResponse)
async def get_application_metrics(db: Session = Depends(get_db)):
    """Get application-specific metrics"""
    try:
        # Get article statistics
        article_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_articles,
                COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_articles,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_articles,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_articles,
                COUNT(CASE WHEN created_at > NOW() - INTERVAL '1 hour' THEN 1 END) as recent_articles,
                AVG(quality_score) as avg_quality_score
            FROM articles
        """)).first()
        
        # Get RSS feed statistics
        rss_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_feeds,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_feeds,
                COUNT(CASE WHEN last_fetch_at > NOW() - INTERVAL '1 hour' THEN 1 END) as recently_updated_feeds
            FROM rss_feeds
        """)).first()
        
        # Get storyline statistics
        storyline_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_storylines,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_storylines
            FROM storylines
        """)).first()
        
        metrics = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'articles': {
                'total': article_stats[0] or 0,
                'processed': article_stats[1] or 0,
                'pending': article_stats[2] or 0,
                'failed': article_stats[3] or 0,
                'recent': article_stats[4] or 0,
                'avg_quality_score': float(article_stats[5]) if article_stats[5] else 0.0
            },
            'rss_feeds': {
                'total': rss_stats[0] or 0,
                'active': rss_stats[1] or 0,
                'recently_updated': rss_stats[2] or 0
            },
            'storylines': {
                'total': storyline_stats[0] or 0,
                'active': storyline_stats[1] or 0
            },
            'system': {
                'uptime': get_system_uptime(),
                'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}"
            }
        }
        
        return APIResponse(
            success=True,
            data=metrics,
            message="Application metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting application metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=APIResponse)
async def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check"""
    try:
        health_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'healthy',
            'checks': {}
        }
        
        # Database health check
        try:
            db.execute(text("SELECT 1")).fetchone()
            health_data['checks']['database'] = {'status': 'healthy', 'message': 'Database connection successful'}
        except Exception as e:
            health_data['checks']['database'] = {'status': 'unhealthy', 'message': f'Database error: {str(e)}'}
            health_data['status'] = 'unhealthy'
        
        # System resource check
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 90 or memory_percent > 90:
            health_data['checks']['system'] = {'status': 'unhealthy', 'message': f'High resource usage: CPU {cpu_percent}%, Memory {memory_percent}%'}
            health_data['status'] = 'unhealthy'
        else:
            health_data['checks']['system'] = {'status': 'healthy', 'message': f'Resource usage normal: CPU {cpu_percent}%, Memory {memory_percent}%'}
        
        # Application health check
        try:
            article_count = db.execute(text("SELECT COUNT(*) FROM articles")).fetchone()[0] or 0
            health_data['checks']['application'] = {'status': 'healthy', 'message': f'Application running, {article_count} articles in database'}
        except Exception as e:
            health_data['checks']['application'] = {'status': 'unhealthy', 'message': f'Application error: {str(e)}'}
            health_data['status'] = 'unhealthy'
        
        return APIResponse(
            success=health_data['status'] == 'healthy',
            data=health_data,
            message=f"Health check completed - Status: {health_data['status']}"
        )
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return APIResponse(
            success=False,
            data={'status': 'unhealthy', 'error': str(e)},
            message=f"Health check failed: {str(e)}"
        )

# Helper functions
async def get_database_metrics(db: Session):
    """Get database performance metrics"""
    try:
        # Get article count
        article_count = db.execute(text("SELECT COUNT(*) FROM articles")).scalar() or 0
        
        # Get recent articles
        recent_articles = db.execute(text("""
            SELECT COUNT(*) FROM articles 
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """)).scalar() or 0
        
        # Get database size (PostgreSQL specific)
        try:
            db_size = db.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """)).scalar()
        except Exception:
            db_size = 'unknown'
        
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

def get_system_uptime():
    """Get system uptime in seconds"""
    try:
        return psutil.boot_time()
    except Exception:
        return 0

def get_completed_tasks_count(db: Session):
    """Get count of completed tasks"""
    try:
        result = db.execute(text("""
            SELECT COUNT(*) FROM articles WHERE status = 'processed'
        """)).scalar()
        return result or 0
    except Exception:
        return 0

def get_failed_tasks_count(db: Session):
    """Get count of failed tasks"""
    try:
        result = db.execute(text("""
            SELECT COUNT(*) FROM articles WHERE status = 'failed'
        """)).scalar()
        return result or 0
    except Exception:
        return 0

def determine_health_status(system_metrics, app_metrics, task_metrics):
    """Determine overall system health status"""
    if (system_metrics['cpu_percent'] > 90 or 
        system_metrics['memory_percent'] > 90):
        return 'critical'
    
    if (system_metrics['cpu_percent'] > 70 or 
        system_metrics['memory_percent'] > 70):
        return 'warning'
    
    return 'healthy'

def generate_alerts(system_metrics, app_metrics, task_metrics):
    """Generate system alerts based on metrics"""
    alerts = []
    
    if system_metrics['cpu_percent'] > 80:
        alerts.append(f"High CPU usage: {system_metrics['cpu_percent']:.1f}%")
    
    if system_metrics['memory_percent'] > 80:
        alerts.append(f"High memory usage: {system_metrics['memory_percent']:.1f}%")
    
    if task_metrics['failed'] > 10:
        alerts.append(f"High task failure rate: {task_metrics['failed']} failures")
    
    return alerts

