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
        
        return {
            "success": True,
            "domain": "system_monitoring",
            "status": "healthy",
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
                
                # Get database metrics
                cur.execute("SELECT COUNT(*) FROM articles")
                total_articles = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storylines")
                total_storylines = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")
                active_feeds = cur.fetchone()[0]
                
                # Get articles per week
                cur.execute("""
                    SELECT COUNT(*) FROM articles 
                    WHERE created_at >= %s
                """, (datetime.now() - timedelta(days=7),))
                articles_this_week = cur.fetchone()[0]
                
                # Get articles today
                cur.execute("""
                    SELECT COUNT(*) FROM articles 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                articles_today = cur.fetchone()[0]
                
                # Get active alerts
                cur.execute("SELECT COUNT(*) FROM system_alerts WHERE is_active = true")
                active_alerts = cur.fetchone()[0]
                
                # Get recent errors
                cur.execute("""
                    SELECT COUNT(*) FROM system_alerts 
                    WHERE severity = 'error' AND created_at >= %s
                """, (datetime.now() - timedelta(hours=24),))
                recent_errors = cur.fetchone()[0]
                
                # Get deduplication metrics
                cur.execute("SELECT COUNT(*) FROM articles WHERE content_hash IS NOT NULL")
                articles_with_hash = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT url, COUNT(*) as count
                        FROM articles 
                        GROUP BY url 
                        HAVING COUNT(*) > 1
                    ) duplicates
                """)
                url_duplicates = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT content_hash, COUNT(*) as count
                        FROM articles 
                        WHERE content_hash IS NOT NULL
                        GROUP BY content_hash 
                        HAVING COUNT(*) > 1
                    ) duplicates
                """)
                content_duplicates = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(*) FROM pipeline_traces 
                    WHERE stage LIKE '%deduplication%' 
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

@router.get("/pipeline-status")
async def get_pipeline_status():
    """Get pipeline monitoring status with stage progress tracking"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get pipeline trace statistics
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_traces,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_traces,
                        COUNT(CASE WHEN status = 'error' THEN 1 END) as error_traces,
                        COUNT(CASE WHEN COALESCE(end_time, start_time) >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_traces,
                        COUNT(CASE WHEN status NOT IN ('completed', 'error') AND end_time IS NULL THEN 1 END) as active_traces
                    FROM pipeline_traces
                """)
                
                trace_stats = cur.fetchone()
                total_traces = trace_stats[0] if trace_stats[0] else 0
                successful_traces = trace_stats[1] if trace_stats[1] else 0
                error_traces = trace_stats[2] if trace_stats[2] else 0
                recent_traces = trace_stats[3] if trace_stats[3] else 0
                truly_active_traces = trace_stats[4] if trace_stats[4] else 0
                
                # Calculate success rate
                success_rate = (successful_traces / total_traces * 100) if total_traces > 0 else 0
                
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
                stage_progress = {}
                if latest_trace_id:
                    cur.execute("""
                        SELECT stage, status, start_time, end_time,
                               EXTRACT(EPOCH FROM (COALESCE(end_time, NOW()) - start_time)) as duration_seconds
                        FROM pipeline_traces
                        WHERE trace_id = %s
                        ORDER BY start_time
                    """, (latest_trace_id,))
                    
                    stages = {}
                    total_duration = 0
                    for row in cur.fetchall():
                        stage, status, start_time, end_time, duration = row
                        stages[stage] = {
                            "status": status,
                            "start_time": start_time.isoformat() if start_time else None,
                            "end_time": end_time.isoformat() if end_time else None,
                            "duration_seconds": duration if duration else None
                        }
                        if duration:
                            total_duration += duration
                    
                    # Calculate progress percentages and ETA
                    stage_order = ["rss_collection", "topic_clustering", "ai_analysis"]
                    estimated_durations = {"rss_collection": 300, "topic_clustering": 1800, "ai_analysis": 1800}  # seconds
                    
                    current_stage = None
                    completed_stages = []
                    for stage_name in stage_order:
                        if stage_name in stages:
                            stage_info = stages[stage_name]
                            if stage_info["status"] == "completed":
                                completed_stages.append(stage_name)
                                stage_progress[stage_name] = {
                                    "status": "completed",
                                    "progress": 100,
                                    "start_time": stage_info["start_time"],
                                    "end_time": stage_info["end_time"],
                                    "duration_seconds": stage_info["duration_seconds"]
                                }
                            elif stage_info["status"] == "started":
                                if current_stage is None:
                                    current_stage = stage_name
                                    # Estimate progress based on elapsed time
                                    elapsed = stages[stage_name].get("duration_seconds", 0) or 0
                                    estimated = estimated_durations.get(stage_name, 1800)
                                    progress = min(95, int((elapsed / estimated) * 100))
                                    stage_progress[stage_name] = {
                                        "status": "running",
                                        "progress": progress,
                                        "start_time": stage_info["start_time"],
                                        "eta_seconds": max(0, estimated - elapsed)
                                    }
                            elif stage_info["status"] == "error":
                                stage_progress[stage_name] = {
                                    "status": "error",
                                    "progress": 0,
                                    "start_time": stage_info["start_time"],
                                    "error": True
                                }
                        else:
                            stage_progress[stage_name] = {
                                "status": "pending",
                                "progress": 0
                            }
                
                # Get recent pipeline traces
                cur.execute("""
                    SELECT id, trace_id, stage, status, COALESCE(end_time, start_time) as ts, error_message
                    FROM pipeline_traces
                    ORDER BY COALESCE(end_time, start_time) DESC
                    LIMIT 10
                """)
                
                recent_traces_data = []
                for row in cur.fetchall():
                    recent_traces_data.append({
                        "id": row[0],
                        "trace_id": row[1],
                        "stage": row[2],
                        "status": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "error_message": row[5]
                    })
                
                # Get processing statistics
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_articles,
                        COUNT(CASE WHEN sentiment_score IS NOT NULL THEN 1 END) as articles_analyzed,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_articles
                    FROM articles
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
                
                return {
                    "success": True,
                    "data": {
                        "pipeline_status": "running" if current_stage else ("healthy" if error_traces == 0 else "error"),
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

@router.post("/pipeline/run-all")
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
