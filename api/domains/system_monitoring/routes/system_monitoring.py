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
    prefix="/api/v4/system_monitoring",
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

        # Get GPU info if available
        gpu_vram_percent = None
        gpu_utilization_percent = None
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                gpu_vram_percent = gpu.memoryUtil * 100
                gpu_utilization_percent = gpu.load * 100
        except ImportError:
            pass
        except Exception:
            pass
        
        # Check database connection
        db_status = "healthy"
        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.close()
            else:
                db_status = "unhealthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)[:50]}"
            logger.warning(f"Database health check failed: {e}")
        
        # Check Redis connection
        redis_status = "healthy"
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True, socket_timeout=1)
            r.ping()
        except ImportError:
            redis_status = "not_configured"
        except Exception as e:
            redis_status = f"unhealthy: {str(e)[:50]}"
            logger.warning(f"Redis health check failed: {e}")
        
        # Determine overall status
        overall_status = "healthy"
        if db_status != "healthy" or redis_status not in ["healthy", "not_configured"]:
            overall_status = "degraded"
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
            overall_status = "warning"
        
        return {
            "success": True,
            "domain": "system_monitoring",
            "status": overall_status,
            "services": {
                "database": db_status,
                "redis": redis_status,
                "system": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning"
            },
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "gpu_vram_percent": gpu_vram_percent,
                "gpu_utilization_percent": gpu_utilization_percent,
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
            "services": {
                "database": "unknown",
                "redis": "unknown",
                "system": "unknown"
            },
            "error": str(e)
        }


@router.get("/fast_stats")
async def get_fast_stats():
    """
    Fast dashboard stats using indexed queries.
    Optimized for quick page loads by using a SINGLE query with UNION ALL.
    """
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Use a SINGLE query to get all stats at once (minimizes SSH round-trips)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 'politics' as domain, 'articles' as type, COUNT(*) as cnt FROM politics.articles
                    UNION ALL SELECT 'politics', 'storylines', COUNT(*) FROM politics.storylines WHERE status = 'active'
                    UNION ALL SELECT 'politics', 'feeds', COUNT(*) FROM politics.rss_feeds WHERE is_active = true
                    UNION ALL SELECT 'finance', 'articles', COUNT(*) FROM finance.articles
                    UNION ALL SELECT 'finance', 'storylines', COUNT(*) FROM finance.storylines WHERE status = 'active'
                    UNION ALL SELECT 'finance', 'feeds', COUNT(*) FROM finance.rss_feeds WHERE is_active = true
                    UNION ALL SELECT 'science-tech', 'articles', COUNT(*) FROM science_tech.articles
                    UNION ALL SELECT 'science-tech', 'storylines', COUNT(*) FROM science_tech.storylines WHERE status = 'active'
                    UNION ALL SELECT 'science-tech', 'feeds', COUNT(*) FROM science_tech.rss_feeds WHERE is_active = true
                """)
                
                stats = {
                    "domains": {
                        "politics": {"articles": 0, "storylines": 0, "feeds": 0},
                        "finance": {"articles": 0, "storylines": 0, "feeds": 0},
                        "science-tech": {"articles": 0, "storylines": 0, "feeds": 0}
                    },
                    "totals": {"articles": 0, "storylines": 0, "feeds": 0},
                    "timestamp": datetime.now().isoformat()
                }
                
                for row in cur.fetchall():
                    domain, stat_type, count = row
                    stats["domains"][domain][stat_type] = count
                    stats["totals"][stat_type] += count
            
            return {
                "success": True,
                "data": stats
            }
            
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Fast stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                where_conditions.append("metric_type = %s")
                params.append(metric_name)
            
            where_conditions.append("timestamp >= %s")
            params.append(datetime.now() - timedelta(hours=hours))
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            with conn.cursor() as cur:
                # FIXED: Use correct column names from schema
                # metric_type (not metric_name), labels (not tags)
                # system_metrics stores individual metrics, not metric_value/unit
                cur.execute(f"""
                    SELECT id, timestamp, metric_type, cpu_percent, memory_percent, 
                           disk_percent, load_avg_1m, labels
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
                        "metric_type": row[2],
                        "cpu_percent": float(row[3]) if row[3] else None,
                        "memory_percent": float(row[4]) if row[4] else None,
                        "disk_percent": float(row[5]) if row[5] else None,
                        "load_avg_1m": float(row[6]) if row[6] else None,
                        "labels": row[7] if row[7] else {}
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
                # FIXED: Use correct column names from schema
                # category (not alert_type), message (not description), resolved (not resolved_at)
                cur.execute(f"""
                    SELECT id, category, severity, title, message, 
                           alert_data, created_at, resolved_at, is_active
                    FROM system_alerts 
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, params + [limit])
                
                alerts = []
                for row in cur.fetchall():
                    alerts.append({
                        "id": row[0],
                        "category": row[1],  # Using category instead of alert_type
                        "severity": row[2],
                        "title": row[3],
                        "message": row[4],  # Using message instead of description
                        "data": row[5],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "resolved_at": row[7].isoformat() if row[7] else None,
                        "is_active": row[8] if row[8] is not None else True
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

                # Get GPU info if available
                logger.info("🔍 Starting GPU monitoring in /status endpoint")
                gpu_vram_percent = None
                gpu_utilization_percent = None
                try:
                    logger.info("🔍 Attempting to import GPUtil")
                    import GPUtil
                    logger.info("🔍 GPUtil imported successfully")
                    gpus = GPUtil.getGPUs()
                    logger.info(f"🔍 Found {len(gpus)} GPUs")
                    if gpus:
                        gpu = gpus[0]
                        gpu_vram_percent = gpu.memoryUtil * 100
                        gpu_utilization_percent = gpu.load * 100
                        logger.info(f"✅ GPU monitoring successful: VRAM={gpu_vram_percent}%, Utilization={gpu_utilization_percent}%")
                    else:
                        logger.warning("❌ No GPUs found")
                except ImportError as e:
                    logger.warning(f"❌ GPUtil not available: {e}")
                except Exception as e:
                    logger.error(f"❌ GPU monitoring failed: {e}")
                    import traceback
                    logger.error(f"❌ GPU monitoring traceback: {traceback.format_exc()}")
                
                logger.info(f"🔍 Final GPU values: VRAM={gpu_vram_percent}, Utilization={gpu_utilization_percent}")
                
                # Get database metrics from all domain schemas
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM politics.articles) +
                        (SELECT COUNT(*) FROM finance.articles) +
                        (SELECT COUNT(*) FROM science_tech.articles) as total_articles,
                        (SELECT COUNT(*) FROM politics.storylines) +
                        (SELECT COUNT(*) FROM finance.storylines) +
                        (SELECT COUNT(*) FROM science_tech.storylines) as total_storylines,
                        (SELECT COUNT(*) FROM politics.rss_feeds WHERE is_active = true) +
                        (SELECT COUNT(*) FROM finance.rss_feeds WHERE is_active = true) +
                        (SELECT COUNT(*) FROM science_tech.rss_feeds WHERE is_active = true) as active_feeds
                """)
                stats = cur.fetchone()
                total_articles = stats[0] if stats and stats[0] else 0
                total_storylines = stats[1] if stats and stats[1] else 0
                active_feeds = stats[2] if stats and stats[2] else 0
                
                # Get articles per week from all domains
                week_ago = datetime.now() - timedelta(days=7)
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM politics.articles WHERE created_at >= %s) +
                        (SELECT COUNT(*) FROM finance.articles WHERE created_at >= %s) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE created_at >= %s) as articles_this_week
                """, (week_ago, week_ago, week_ago))
                week_result = cur.fetchone()
                articles_this_week = week_result[0] if week_result and week_result[0] else 0
                
                # Get articles today from all domains
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM politics.articles WHERE DATE(created_at) = CURRENT_DATE) +
                        (SELECT COUNT(*) FROM finance.articles WHERE DATE(created_at) = CURRENT_DATE) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE DATE(created_at) = CURRENT_DATE) as articles_today
                """)
                today_result = cur.fetchone()
                articles_today = today_result[0] if today_result and today_result[0] else 0
                
                # Get active alerts
                cur.execute("SELECT COUNT(*) FROM system_alerts WHERE is_active = true")
                active_alerts = cur.fetchone()[0]
                
                # Get recent errors
                cur.execute("""
                    SELECT COUNT(*) FROM system_alerts 
                    WHERE severity = 'error' AND created_at >= %s
                """, (datetime.now() - timedelta(hours=24),))
                recent_errors = cur.fetchone()[0]
                
                # Get deduplication metrics from all domains
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM politics.articles WHERE content_hash IS NOT NULL) +
                        (SELECT COUNT(*) FROM finance.articles WHERE content_hash IS NOT NULL) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE content_hash IS NOT NULL) as articles_with_hash
                """)
                hash_result = cur.fetchone()
                articles_with_hash = hash_result[0] if hash_result and hash_result[0] else 0
                
                # URL duplicates across all domains
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT url FROM politics.articles
                        UNION ALL SELECT url FROM finance.articles
                        UNION ALL SELECT url FROM science_tech.articles
                    ) all_articles
                    GROUP BY url 
                    HAVING COUNT(*) > 1
                """)
                url_result = cur.fetchone()
                url_duplicates = url_result[0] if url_result and url_result[0] else 0
                
                # Content duplicates across all domains
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT content_hash FROM politics.articles WHERE content_hash IS NOT NULL
                        UNION ALL SELECT content_hash FROM finance.articles WHERE content_hash IS NOT NULL
                        UNION ALL SELECT content_hash FROM science_tech.articles WHERE content_hash IS NOT NULL
                    ) all_hashes
                    GROUP BY content_hash 
                    HAVING COUNT(*) > 1
                """)
                content_result = cur.fetchone()
                content_duplicates = content_result[0] if content_result and content_result[0] else 0
                
                cur.execute("""
                    SELECT COUNT(*) FROM pipeline_traces 
                    WHERE error_stage LIKE '%deduplication%' 
                    AND (end_time >= NOW() - INTERVAL '24 hours' OR start_time >= NOW() - INTERVAL '24 hours')
                """)
                recent_deduplication_runs = cur.fetchone()[0]
                
                # Check Redis status
                redis_status = "healthy"
                try:
                    import redis
                    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                    r.ping()
                except Exception as e:
                    redis_status = "unhealthy"
                    logger.warning(f"Redis connection failed: {e}")
                
                return {
                    "success": True,
                    "data": {
                        "system": {
                            "cpu_percent": cpu_percent,
                            "memory_percent": memory.percent,
                            "disk_percent": disk.percent,
                            "gpu_vram_percent": gpu_vram_percent,
                            "gpu_utilization_percent": gpu_utilization_percent,
                            "status": "healthy" if cpu_percent < 80 and memory.percent < 80 and disk.percent < 90 else "warning"
                        },
                        "database": {
                            "total_articles": total_articles,
                            "total_storylines": total_storylines,
                            "active_feeds": active_feeds,
                            "articles_this_week": articles_this_week,
                            "articles_today": articles_today,
                            "status": "healthy"
                        },
                        "redis": {
                            "status": redis_status,
                            "host": "localhost",
                            "port": 6379
                        },
                        "alerts": {
                            "active_alerts": active_alerts,
                            "recent_errors": recent_errors,
                            "status": "healthy" if active_alerts == 0 and recent_errors == 0 else "warning"
                        },
                        "deduplication": {
                            "articles_with_hash": articles_with_hash,
                            "hash_coverage_percentage": (articles_with_hash / total_articles * 100) if total_articles > 0 else 0,
                            "url_duplicates": url_duplicates,
                            "content_duplicates": content_duplicates,
                            "recent_deduplication_runs": recent_deduplication_runs,
                            "status": "healthy" if url_duplicates == 0 and content_duplicates == 0 else "warning"
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

@router.get("/dashboard")
async def get_dashboard_metrics():
    """Get dashboard-specific database metrics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get aggregated metrics from all domain schemas
                week_ago = datetime.now() - timedelta(days=7)
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM politics.articles) +
                        (SELECT COUNT(*) FROM finance.articles) +
                        (SELECT COUNT(*) FROM science_tech.articles) as total_articles,
                        (SELECT COUNT(*) FROM politics.storylines) +
                        (SELECT COUNT(*) FROM finance.storylines) +
                        (SELECT COUNT(*) FROM science_tech.storylines) as total_storylines,
                        (SELECT COUNT(*) FROM politics.rss_feeds) +
                        (SELECT COUNT(*) FROM finance.rss_feeds) +
                        (SELECT COUNT(*) FROM science_tech.rss_feeds) as total_feeds,
                        (SELECT COUNT(*) FROM politics.rss_feeds WHERE is_active = true) +
                        (SELECT COUNT(*) FROM finance.rss_feeds WHERE is_active = true) +
                        (SELECT COUNT(*) FROM science_tech.rss_feeds WHERE is_active = true) as active_feeds,
                        (SELECT COUNT(*) FROM politics.articles WHERE DATE(created_at) = CURRENT_DATE) +
                        (SELECT COUNT(*) FROM finance.articles WHERE DATE(created_at) = CURRENT_DATE) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE DATE(created_at) = CURRENT_DATE) as articles_today,
                        (SELECT COUNT(*) FROM politics.articles WHERE created_at >= %s) +
                        (SELECT COUNT(*) FROM finance.articles WHERE created_at >= %s) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE created_at >= %s) as articles_this_week
                """, (week_ago, week_ago, week_ago))
                
                stats = cur.fetchone()
                
                return {
                    "success": True,
                    "data": {
                        "total_articles": stats[0] if stats and stats[0] else 0,
                        "total_storylines": stats[1] if stats and stats[1] else 0,
                        "total_feeds": stats[2] if stats and stats[2] else 0,
                        "active_feeds": stats[3] if stats and stats[3] else 0,
                        "articles_today": stats[4] if stats and stats[4] else 0,
                        "articles_this_week": stats[5] if stats and stats[5] else 0,
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
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

                # Get GPU info if available
                gpu_vram_percent = None
                gpu_utilization_percent = None
                try:
                    import GPUtil
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_vram_percent = gpu.memoryUtil * 100
                        gpu_utilization_percent = gpu.load * 100
                except ImportError:
                    pass
                except Exception:
                    pass
                
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

@router.get("/pipeline_status")
async def get_pipeline_status():
    """Get pipeline monitoring status with stage progress tracking"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get pipeline trace statistics (using correct column names)
                # Table has: success (boolean), error_stage (varchar), not status/stage
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_traces,
                        COUNT(CASE WHEN success = true THEN 1 END) as successful_traces,
                        COUNT(CASE WHEN success = false THEN 1 END) as error_traces,
                        COUNT(CASE WHEN COALESCE(end_time, start_time) >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_traces,
                        COUNT(CASE WHEN success IS NULL AND end_time IS NULL THEN 1 END) as active_traces
                    FROM pipeline_traces
                """)
                
                trace_stats = cur.fetchone()
                total_traces = trace_stats[0] if trace_stats[0] else 0
                successful_traces = trace_stats[1] if trace_stats[1] else 0
                error_traces = trace_stats[2] if trace_stats[2] else 0
                recent_traces = trace_stats[3] if trace_stats[3] else 0
                truly_active_traces = trace_stats[4] if trace_stats[4] else 0
                
                # Calculate success rate
                success_rate = (successful_traces / total_traces * 100) if total_traces > 0 else 0.0
                
                # Get the most recent orchestration run
                cur.execute("""
                    SELECT DISTINCT trace_id
                    FROM pipeline_traces
                    WHERE trace_id LIKE 'pipeline_%'
                    ORDER BY trace_id DESC
                    LIMIT 1
                """)
                latest_trace = cur.fetchone()
                latest_trace_id = latest_trace[0] if latest_trace else None
                
                # Get stage progress for latest orchestration
                # Note: pipeline_traces table doesn't have stage/status columns
                # It has error_stage and success (boolean)
                stage_progress = {}
                current_stage = None
                
                # Get recent pipeline traces (using actual column names)
                cur.execute("""
                    SELECT id, trace_id, error_stage, success, 
                           COALESCE(end_time, start_time) as ts,
                           performance_metrics
                    FROM pipeline_traces
                    ORDER BY COALESCE(end_time, start_time) DESC
                    LIMIT 10
                """)
                
                recent_traces_data = []
                for row in cur.fetchall():
                    trace_id = row[1]
                    error_stage = row[2]
                    success = row[3]
                    ts = row[4]
                    metrics = row[5]
                    
                    # Determine status from success boolean
                    if success is None:
                        status = "running"
                    elif success:
                        status = "completed"
                    else:
                        status = "error"
                    
                    recent_traces_data.append({
                        "id": str(row[0]),
                        "trace_id": trace_id,
                        "stage": error_stage or "unknown",
                        "status": status,
                        "created_at": ts.isoformat() if ts else None,
                        "error_message": None,  # No error_message column
                        "success": success
                    })
                
                # Get processing statistics (sum across all domain schemas)
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM politics.articles) +
                        (SELECT COUNT(*) FROM finance.articles) +
                        (SELECT COUNT(*) FROM science_tech.articles) as total_articles,
                        (SELECT COUNT(*) FROM politics.articles WHERE sentiment_score IS NOT NULL) +
                        (SELECT COUNT(*) FROM finance.articles WHERE sentiment_score IS NOT NULL) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE sentiment_score IS NOT NULL) as articles_analyzed,
                        (SELECT COUNT(*) FROM politics.articles WHERE created_at >= NOW() - INTERVAL '1 hour') +
                        (SELECT COUNT(*) FROM finance.articles WHERE created_at >= NOW() - INTERVAL '1 hour') +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE created_at >= NOW() - INTERVAL '1 hour') as recent_articles
                """)
                
                processing_stats = cur.fetchone()
                articles_processed = processing_stats[0] if processing_stats[0] else 0
                articles_analyzed = processing_stats[1] if processing_stats[1] else 0
                recent_articles = processing_stats[2] if processing_stats[2] else 0
                
                # Calculate overall pipeline progress
                overall_progress = 0
                if stage_progress:
                    stage_count = len(stage_progress)
                    total_progress = sum(s.get("progress", 0) for s in stage_progress.values())
                    overall_progress = int(total_progress / stage_count) if stage_count > 0 else 0
                
                # Determine pipeline status
                if total_traces == 0:
                    pipeline_status = "idle"  # No traces yet
                elif truly_active_traces > 0:
                    pipeline_status = "running"
                elif error_traces > 0 and error_traces > successful_traces:
                    pipeline_status = "error"
                else:
                    pipeline_status = "healthy"
                
                return {
                    "success": True,
                    "data": {
                        "pipeline_status": pipeline_status,
                        "overall_progress": overall_progress,
                        "current_stage": current_stage,
                        "stage_progress": stage_progress,
                        "active_traces": truly_active_traces,
                        "recent_traces_count": recent_traces,
                        "total_traces": total_traces,
                        "success_rate": round(success_rate, 1),
                        "articles_processed": articles_processed,
                        "articles_analyzed": articles_analyzed,
                        "recent_articles": recent_articles,
                        "errors": error_traces,
                        "recent_traces": recent_traces_data,
                        "latest_trace_id": latest_trace_id
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pipeline/run_all")
async def run_all_pipeline_processes(background_tasks: BackgroundTasks):
    """
    Orchestrate and run all pipeline processes in sequence:
    1. RSS Feed Collection
    2. Topic Clustering
    3. AI Analysis (Sentiment & Entity Extraction)
    """
    try:
        # Start orchestration in background
        background_tasks.add_task(run_pipeline_orchestration_sync)
        
        return {
            "success": True,
            "message": "Pipeline orchestration started",
            "stages": [
                {"stage": "rss_collection", "status": "queued", "estimated_duration_minutes": 5},
                {"stage": "topic_clustering", "status": "queued", "estimated_duration_minutes": 30},
                {"stage": "ai_analysis", "status": "queued", "estimated_duration_minutes": 30}
            ],
            "total_estimated_time_minutes": 65,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting pipeline orchestration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def run_pipeline_orchestration_sync():
    """Sync wrapper for pipeline orchestration"""
    execute_pipeline_orchestration()

def execute_pipeline_orchestration():
    """Execute pipeline stages sequentially"""
    trace_id = f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # Stage 1: RSS Collection
        logger.info(f"[{trace_id}] Starting RSS Feed Collection")
        _log_pipeline_trace(trace_id, "rss_collection", "started")
        
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            from collectors.rss_collector import collect_rss_feeds
            
            articles_added = collect_rss_feeds()
            _log_pipeline_trace(trace_id, "rss_collection", "completed", {"articles_added": articles_added})
            logger.info(f"[{trace_id}] RSS Collection completed: {articles_added} articles added")
        except Exception as e:
            _log_pipeline_trace(trace_id, "rss_collection", "error", {"error": str(e)})
            logger.error(f"[{trace_id}] RSS Collection failed: {e}")
            raise
        
        # Stage 2: Topic Clustering
        logger.info(f"[{trace_id}] Starting Topic Clustering")
        _log_pipeline_trace(trace_id, "topic_clustering", "started")
        
        try:
            from domains.content_analysis.services.advanced_topic_extractor import AdvancedTopicExtractor
            from shared.database.connection import get_db_connection
            
            extractor = AdvancedTopicExtractor(get_db_connection)
            topics = extractor.extract_topics_from_articles(time_period_hours=24)
            
            if topics:
                success = extractor.save_topics_to_database(topics)
                if success:
                    _log_pipeline_trace(trace_id, "topic_clustering", "completed", {"topics_extracted": len(topics)})
                    logger.info(f"[{trace_id}] Topic Clustering completed: {len(topics)} topics extracted")
                else:
                    raise Exception("Failed to save topics to database")
            else:
                _log_pipeline_trace(trace_id, "topic_clustering", "completed", {"topics_extracted": 0})
                logger.info(f"[{trace_id}] Topic Clustering completed: No topics found")
        except Exception as e:
            _log_pipeline_trace(trace_id, "topic_clustering", "error", {"error": str(e)})
            logger.error(f"[{trace_id}] Topic Clustering failed: {e}")
            raise
        
        # Stage 3: AI Analysis (Sentiment & Entity Extraction on recent articles)
        logger.info(f"[{trace_id}] Starting AI Analysis")
        _log_pipeline_trace(trace_id, "ai_analysis", "started")
        
        try:
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        # Get recent articles without analysis
                        cur.execute("""
                            SELECT id, title, content 
                            FROM articles 
                            WHERE created_at >= NOW() - INTERVAL '24 hours'
                            AND (sentiment_score IS NULL OR LENGTH(COALESCE(content, '')) > 0)
                            ORDER BY created_at DESC
                            LIMIT 100
                        """)
                        articles = cur.fetchall()
                        
                        analyzed_count = 0
                        
                        # Use a simple sync sentiment approach for batch processing
                        # Full LLM analysis can be done per-article later
                        for article_id, title, content in articles[:50]:  # Limit to 50 for performance
                            if content and len(content) > 50:
                                try:
                                    # Simple sentiment scoring based on keywords (fast batch processing)
                                    # Full LLM analysis can be triggered per-article
                                    positive_words = ['good', 'great', 'excellent', 'positive', 'success', 'win', 'improve', 'better']
                                    negative_words = ['bad', 'worse', 'fail', 'negative', 'crisis', 'problem', 'concern', 'risk']
                                    
                                    content_lower = content[:500].lower()
                                    positive_count = sum(1 for word in positive_words if word in content_lower)
                                    negative_count = sum(1 for word in negative_words if word in content_lower)
                                    
                                    if positive_count > negative_count:
                                        sentiment_score = 0.6 + min(positive_count * 0.05, 0.3)
                                    elif negative_count > positive_count:
                                        sentiment_score = 0.4 - min(negative_count * 0.05, 0.3)
                                    else:
                                        sentiment_score = 0.5
                                    
                                    sentiment_score = max(0.0, min(1.0, sentiment_score))
                                    
                                    
                                    cur.execute("""
                                        UPDATE articles 
                                        SET sentiment_score = %s, 
                                            analysis_updated_at = NOW()
                                        WHERE id = %s
                                    """, (sentiment_score, article_id))
                                    
                                    analyzed_count += 1
                                except Exception as e:
                                    logger.warning(f"[{trace_id}] Error analyzing article {article_id}: {e}")
                                    continue
                        
                        conn.commit()
                        _log_pipeline_trace(trace_id, "ai_analysis", "completed", {"articles_analyzed": analyzed_count})
                        logger.info(f"[{trace_id}] AI Analysis completed: {analyzed_count} articles analyzed")
                finally:
                    conn.close()
            else:
                raise Exception("Database connection failed")
        except Exception as e:
            _log_pipeline_trace(trace_id, "ai_analysis", "error", {"error": str(e)})
            logger.error(f"[{trace_id}] AI Analysis failed: {e}")
            raise
        
        logger.info(f"[{trace_id}] Pipeline orchestration completed successfully")
        
    except Exception as e:
        logger.error(f"[{trace_id}] Pipeline orchestration failed: {e}")
        _log_pipeline_trace(trace_id, "orchestration", "error", {"error": str(e)})

def _log_pipeline_trace(trace_id: str, stage: str, status: str, metadata: Dict[str, Any] = None):
    """Log pipeline trace to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_traces (trace_id, stage, status, start_time, end_time, error_message)
                    VALUES (%s, %s, %s, NOW(), 
                        CASE WHEN %s IN ('completed', 'error') THEN NOW() ELSE NULL END,
                        CASE WHEN %s = 'error' THEN %s ELSE NULL END)
                """, (
                    trace_id,
                    stage,
                    status,
                    status,
                    status,
                    str(metadata.get('error', '')) if metadata else None
                ))
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error logging pipeline trace: {e}")


@router.get("/logs/stats")
async def get_log_statistics(days: int = 7):
    """
    Get log statistics aggregated by level
    Returns counts of errors, warnings, info, and total entries
    """
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Calculate date threshold
                date_threshold = datetime.now() - timedelta(days=days)
                
                # Get statistics from system_alerts (which acts as our log system)
                # Count by severity level
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(CASE WHEN severity = 'error' OR severity = 'critical' THEN 1 ELSE 0 END) as error_count,
                        SUM(CASE WHEN severity = 'warning' THEN 1 ELSE 0 END) as warning_count,
                        SUM(CASE WHEN severity = 'info' THEN 1 ELSE 0 END) as info_count
                    FROM system_alerts
                    WHERE created_at >= %s
                """, (date_threshold,))
                
                stats_row = cur.fetchone()
                
                # Also check processing logs for additional context
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM article_processing_log
                    WHERE created_at >= %s
                """, (date_threshold,))
                processing_logs_count = cur.fetchone()[0] or 0
                
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM storyline_processing_log
                    WHERE created_at >= %s
                """, (date_threshold,))
                storyline_logs_count = cur.fetchone()[0] or 0
                
                # Aggregate totals
                total_entries = (stats_row[0] or 0) + processing_logs_count + storyline_logs_count
                error_count = stats_row[1] or 0
                warning_count = stats_row[2] or 0
                info_count = stats_row[3] or 0
                
                return {
                    "success": True,
                    "data": {
                        "total_entries": total_entries,
                        "error_count": error_count,
                        "warning_count": warning_count,
                        "info_count": info_count,
                        "debug_count": 0,  # Not tracked separately
                        "period_days": days,
                        "timestamp": datetime.now().isoformat()
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting log statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/realtime")
async def get_realtime_logs(limit: int = 50):
    """
    Get real-time logs from system alerts and processing logs
    Returns recent log entries in chronological order
    """
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get recent alerts (these are our primary log entries)
                cur.execute("""
                    SELECT 
                        id,
                        category,
                        severity,
                        title,
                        message,
                        created_at,
                        is_active
                    FROM system_alerts
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                
                logs = []
                for row in cur.fetchall():
                    logs.append({
                        "id": row[0],
                        "timestamp": row[5].isoformat() if row[5] else datetime.now().isoformat(),
                        "level": (row[2] or 'INFO').upper(),  # severity -> level
                        "logger": row[1] or 'system',  # category -> logger
                        "message": row[4] or row[3] or 'System event',  # message or title
                        "module": row[1] or 'system',  # category -> module
                        "is_active": row[6] if row[6] is not None else True
                    })
                
                # Also get recent processing log entries
                cur.execute("""
                    SELECT 
                        id,
                        'article_processing' as category,
                        CASE 
                            WHEN status = 'error' THEN 'ERROR'
                            WHEN status = 'warning' THEN 'WARNING'
                            ELSE 'INFO'
                        END as severity,
                        article_id::text as title,
                        COALESCE(error_message, 'Article processed') as message,
                        created_at
                    FROM article_processing_log
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit // 2,))
                
                for row in cur.fetchall():
                    logs.append({
                        "id": f"proc_{row[0]}",
                        "timestamp": row[5].isoformat() if row[5] else datetime.now().isoformat(),
                        "level": (row[2] or 'INFO').upper(),
                        "logger": row[1] or 'processing',
                        "message": row[4] or 'Processing event',
                        "module": row[1] or 'processing',
                        "is_active": True
                    })
                
                # Sort all logs by timestamp (most recent first)
                logs.sort(key=lambda x: x['timestamp'], reverse=True)
                logs = logs[:limit]  # Limit final results
                
                return {
                    "success": True,
                    "data": {
                        "entries": logs,
                        "count": len(logs),
                        "timestamp": datetime.now().isoformat()
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting realtime logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
