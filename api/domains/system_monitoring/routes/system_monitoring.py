"""
Domain 6: System Monitoring Routes
Handles system metrics, health monitoring, and alerts
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import psutil
import os

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/system-monitoring",
    tags=["System Monitoring"],
    responses={404: {"description": "Not found"}}
)

@router.get("/health")
async def health_check():
    """Health check for System Monitoring domain"""
    try:
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "success": True,
            "domain": "system_monitoring",
            "status": "healthy",
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "timestamp": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "system_monitoring",
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/metrics")
async def get_system_metrics(
    metric_name: Optional[str] = None,
    hours: int = 24,
    limit: int = 100
):
    """Get system metrics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Build query with filters
            where_conditions = []
            params = []
            
            if metric_name:
                where_conditions.append("metric_name = %s")
                params.append(metric_name)
            
            where_conditions.append("timestamp >= %s")
            params.append(datetime.now() - timedelta(hours=hours))
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, timestamp, metric_name, metric_value, unit, tags
                    FROM system_metrics 
                    {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, params + [limit])
                
                metrics = []
                for row in cur.fetchall():
                    metrics.append({
                        "id": row[0],
                        "timestamp": row[1].isoformat(),
                        "metric_name": row[2],
                        "metric_value": row[3],
                        "unit": row[4],
                        "tags": row[5]
                    })
                
                return {
                    "success": True,
                    "data": {"metrics": metrics},
                    "count": len(metrics),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metrics/collect")
async def collect_system_metrics(background_tasks: BackgroundTasks):
    """Collect current system metrics"""
    try:
        # Start background metric collection
        background_tasks.add_task(process_metric_collection)
        
        return {
            "success": True,
            "message": "System metrics collection started",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting metric collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
async def get_system_alerts(
    severity: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50
):
    """Get system alerts"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Build query with filters
            where_conditions = []
            params = []
            
            if severity:
                where_conditions.append("severity = %s")
                params.append(severity)
            
            if active_only:
                where_conditions.append("is_active = true")
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, alert_type, severity, title, description, 
                           alert_data, created_at, updated_at, resolved_at
                    FROM system_alerts 
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, params + [limit])
                
                alerts = []
                for row in cur.fetchall():
                    alerts.append({
                        "id": row[0],
                        "alert_type": row[1],
                        "severity": row[2],
                        "title": row[3],
                        "description": row[4],
                        "data": row[5],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None,
                        "resolved_at": row[8].isoformat() if row[8] else None
                    })
                
                return {
                    "success": True,
                    "data": {"alerts": alerts},
                    "count": len(alerts),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/create")
async def create_system_alert(request: Dict[str, Any]):
    """Create a new system alert"""
    try:
        alert_type = request.get("alert_type")
        severity = request.get("severity", "info")
        title = request.get("title")
        description = request.get("description")
        alert_data = request.get("data", {})
        
        if not alert_type or not title:
            raise HTTPException(status_code=400, detail="Alert type and title are required")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Convert alert_data to JSON string for JSONB column
                import json
                alert_data_json = json.dumps(alert_data) if alert_data else '{}'
                
                cur.execute("""
                    INSERT INTO system_alerts 
                    (alert_type, severity, title, description, alert_data, created_at, updated_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, alert_type, severity, title, created_at
                """, (
                    alert_type, severity, title, description, alert_data_json,
                    datetime.now(), datetime.now(), True
                ))
                
                new_alert = cur.fetchone()
                conn.commit()
                
                return {
                    "success": True,
                    "data": {
                        "id": new_alert[0],
                        "alert_type": new_alert[1],
                        "severity": new_alert[2],
                        "title": new_alert[3],
                        "created_at": new_alert[4].isoformat()
                    },
                    "message": "Alert created successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    """Resolve a system alert"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE system_alerts 
                    SET is_active = false, resolved_at = %s, updated_at = %s
                    WHERE id = %s
                """, (datetime.now(), datetime.now(), alert_id))
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Alert not found")
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Alert resolved successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_system_status():
    """Get comprehensive system status"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Get database metrics
                cur.execute("SELECT COUNT(*) FROM articles")
                total_articles = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storylines")
                total_storylines = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")
                active_feeds = cur.fetchone()[0]
                
                # Get active alerts
                cur.execute("SELECT COUNT(*) FROM system_alerts WHERE is_active = true")
                active_alerts = cur.fetchone()[0]
                
                # Get recent errors
                cur.execute("""
                    SELECT COUNT(*) FROM system_alerts 
                    WHERE severity = 'error' AND created_at >= %s
                """, (datetime.now() - timedelta(hours=24),))
                recent_errors = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "system": {
                            "cpu_percent": cpu_percent,
                            "memory_percent": memory.percent,
                            "disk_percent": disk.percent,
                            "status": "healthy" if cpu_percent < 80 and memory.percent < 80 and disk.percent < 90 else "warning"
                        },
                        "database": {
                            "total_articles": total_articles,
                            "total_storylines": total_storylines,
                            "active_feeds": active_feeds,
                            "status": "healthy"
                        },
                        "alerts": {
                            "active_alerts": active_alerts,
                            "recent_errors": recent_errors,
                            "status": "healthy" if active_alerts == 0 and recent_errors == 0 else "warning"
                        },
                        "overall_status": "healthy"
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_metrics():
    """Get performance metrics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get performance metrics from database
                cur.execute("""
                    SELECT metric_name, AVG(metric_value) as avg_value, MAX(metric_value) as max_value
                    FROM system_metrics 
                    WHERE timestamp >= %s
                    AND metric_name IN ('api_response_time', 'database_query_time', 'llm_processing_time')
                    GROUP BY metric_name
                """, (datetime.now() - timedelta(hours=24),))
                
                performance_metrics = {}
                for row in cur.fetchall():
                    performance_metrics[row[0]] = {
                        "avg_value": round(row[1], 2),
                        "max_value": round(row[2], 2)
                    }
                
                return {
                    "success": True,
                    "data": {
                        "performance_metrics": performance_metrics,
                        "timestamp": datetime.now().isoformat()
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def process_metric_collection():
    """Background task for collecting system metrics"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Store metrics in database
                metrics = [
                    ("cpu_percent", cpu_percent, "percent"),
                    ("memory_percent", memory.percent, "percent"),
                    ("disk_percent", disk.percent, "percent"),
                    ("memory_available", memory.available, "bytes"),
                    ("disk_free", disk.free, "bytes")
                ]
                
                for metric_name, metric_value, unit in metrics:
                    # Convert tags dict to JSON string for JSONB column
                    import json
                    tags_json = json.dumps({})
                    
                    cur.execute("""
                        INSERT INTO system_metrics (timestamp, metric_name, metric_value, unit, tags)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (datetime.now(), metric_name, metric_value, unit, tags_json))
                
                conn.commit()
                logger.info(f"Collected {len(metrics)} system metrics")
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error in metric collection: {e}")
