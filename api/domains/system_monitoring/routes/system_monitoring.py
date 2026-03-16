"""
Domain 6: System Monitoring Routes
Handles system metrics, health monitoring, and alerts
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body, Request
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import psutil
import os
import sys
from collections import defaultdict

from shared.database.connection import get_db_connection
from shared.services.response_cache import cached_response

logger = logging.getLogger(__name__)

# Import filtering functions from RSS collector
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'collectors'))
try:
    from rss_collector import (
        is_excluded_content,
        is_clickbait_title,
        is_advertisement,
        calculate_article_quality_score,
        calculate_article_impact_score
    )
    FILTERING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Filtering functions not available: {e}")
    FILTERING_AVAILABLE = False

router = APIRouter(
    prefix="/api/system_monitoring",
    tags=["System Monitoring"],
    responses={404: {"description": "Not found"}}
)


def _get_gpu_metrics() -> Dict[str, Any]:
    """Get GPU metrics (utilization, VRAM, temperature) from shared helper."""
    try:
        from shared.gpu_metrics import get_gpu_metrics
        return get_gpu_metrics()
    except ImportError:
        return {
            "gpu_utilization_percent": None,
            "gpu_vram_percent": None,
            "gpu_temperature_c": None,
            "gpu_memory_used_mb": None,
            "gpu_memory_total_mb": None,
        }


@router.get("/orchestrator")
async def orchestrator_status(request: Request):
    """Newsroom Orchestrator v6 status: enabled, running, last_event_at, queue_depth."""
    orchestrator = getattr(request.app.state, "newsroom_orchestrator", None)
    if orchestrator is None:
        return {"enabled": False, "running": False, "last_event_at": None, "queue_depth": 0}
    return orchestrator.get_status()


@router.get("/health")
@cached_response(ttl=30)
async def health_check():
    """Health check for System Monitoring domain"""
    try:
        # Check system resources (interval=0.1 for fast response — web load takes priority)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Get GPU info if available (nvidia-smi or GPUtil)
        gpu = _get_gpu_metrics()
        gpu_vram_percent = gpu.get("gpu_vram_percent")
        gpu_utilization_percent = gpu.get("gpu_utilization_percent")

        # Check database connection (with quick timeout to prevent stalling)
        db_status = "healthy"
        try:
            import threading
            import queue
            
            result_queue = queue.Queue()
            exception_queue = queue.Queue()
            
            def db_check():
                try:
                    conn = get_db_connection()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                        conn.close()
                        result_queue.put(True)
                    else:
                        result_queue.put(False)
                except Exception as e:
                    exception_queue.put(e)
            
            # Run database check in thread with timeout
            thread = threading.Thread(target=db_check, daemon=True)
            thread.start()
            thread.join(timeout=2)  # 2 second timeout
            
            if thread.is_alive():
                db_status = "unhealthy: connection timeout"
                logger.warning("Database health check timed out after 2 seconds")
            elif not exception_queue.empty():
                e = exception_queue.get()
                db_status = f"unhealthy: {str(e)[:50]}"
                logger.warning(f"Database health check failed: {e}")
            elif not result_queue.empty():
                if not result_queue.get():
                    db_status = "unhealthy"
            else:
                db_status = "unhealthy: no response"
        except Exception as e:
            db_status = f"unhealthy: {str(e)[:50]}"
            logger.warning(f"Database health check error: {e}")
        
        # Redis removed from architecture; report not_used so frontend can show N/A
        redis_status = "not_used"
        
        # Circuit breaker status
        cb_summary = {}
        try:
            from services.circuit_breaker_service import get_circuit_breaker_service
            cb_service = get_circuit_breaker_service()
            cb_health = cb_service.get_health_status()
            cb_summary = {
                "open_circuits": cb_health.get("open_circuits", 0),
                "breakers": {
                    name: info["state"]
                    for name, info in cb_health.get("circuit_breakers", {}).items()
                },
            }
        except Exception:
            cb_summary = {"open_circuits": 0, "breakers": {}}

        # Determine overall status and why (for troubleshooting)
        overall_status = "healthy"
        degraded_reasons: List[str] = []
        if db_status != "healthy":
            overall_status = "degraded"
            degraded_reasons.append(f"database: {db_status}")
        if redis_status not in ["healthy", "not_configured", "not_used"]:
            overall_status = "degraded"
            degraded_reasons.append(f"redis: {redis_status}")
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
            overall_status = "warning"
        if cb_summary.get("open_circuits", 0) > 0:
            overall_status = "degraded"
            degraded_reasons.append(f"circuit_breakers: {cb_summary.get('open_circuits', 0)} open (e.g. ollama)")
        
        return {
            "success": True,
            "domain": "system_monitoring",
            "status": overall_status,
            "degraded_reasons": degraded_reasons if overall_status == "degraded" else None,
            "services": {
                "database": db_status,
                "redis": redis_status,
                "ollama": "circuit_open" if cb_summary.get("breakers", {}).get("ollama") == "open" else "available",
                "system": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning",
            },
            "circuit_breakers": cb_summary,
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "gpu_vram_percent": gpu_vram_percent,
                "gpu_utilization_percent": gpu_utilization_percent,
                "gpu_temperature_c": gpu.get("gpu_temperature_c"),
                "gpu_memory_used_mb": gpu.get("gpu_memory_used_mb"),
                "gpu_memory_total_mb": gpu.get("gpu_memory_total_mb"),
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


@router.get("/monitoring/overview")
def get_monitoring_overview():
    """
    Enhanced monitoring: connection status (API, database, webserver) and live activity feed.
    Use for the monitoring UI that shows system health and "what the backend is doing".
    """
    import threading
    import queue as queue_module

    connections: Dict[str, Any] = {"api": "ok"}
    db_status = "unknown"
    try:
        result_queue = queue_module.Queue()
        exception_queue = queue_module.Queue()

        def db_check():
            try:
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    conn.close()
                    result_queue.put(True)
                else:
                    result_queue.put(False)
            except Exception as e:
                exception_queue.put(e)

        thread = threading.Thread(target=db_check, daemon=True)
        thread.start()
        thread.join(timeout=2)
        if thread.is_alive():
            db_status = "timeout"
        elif not exception_queue.empty():
            db_status = "unhealthy"
        elif not result_queue.empty() and result_queue.get():
            db_status = "healthy"
        else:
            db_status = "unhealthy"
    except Exception:
        db_status = "unhealthy"
    connections["database"] = db_status

    webserver: Dict[str, Any] = {}
    try:
        from shared.services.route_supervisor import get_route_supervisor
        supervisor = get_route_supervisor()
        if supervisor.frontend_health:
            f = supervisor.frontend_health
            webserver = {
                "status": f.status.value if hasattr(f.status, "value") else str(f.status),
                "response_time_ms": getattr(f, "response_time_ms", None),
                "api_connection": getattr(f, "api_connection", None),
                "url": getattr(f, "url", None),
                "last_check": f.last_check.isoformat() if getattr(f, "last_check", None) else None,
            }
    except Exception as e:
        webserver = {"status": "unknown", "error": str(e)[:80]}
    connections["webserver"] = webserver

    activities: Dict[str, Any] = {}
    try:
        from services.activity_feed_service import get_activity_feed
        activities = get_activity_feed().get_snapshot(recent_limit=50)
    except Exception as e:
        logger.debug("Activity feed: %s", e)
        activities = {"current": [], "recent": []}

    return {
        "success": True,
        "connections": connections,
        "activities": activities,
        "timestamp": datetime.now().isoformat(),
    }


def _get_last_run_from_db(phase_name: str) -> Optional[datetime]:
    """Latest finished_at for this phase from automation_run_history (survives restart)."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT finished_at FROM automation_run_history WHERE phase_name = %s ORDER BY finished_at DESC LIMIT 1",
                    (phase_name,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


@router.get("/automation/status")
def get_automation_status(request: Request) -> Dict[str, Any]:
    """
    AutomationManager status for monitoring: is_running, queue_size, active_workers,
    and per-phase last_run + interval so the UI can show phase timeline and next-due.
    last_run is augmented from automation_run_history when in-memory is missing (survives API restart).
    """
    automation = getattr(request.app.state, "automation", None)
    if automation is None or not hasattr(automation, "get_status"):
        return {
            "success": True,
            "data": {
                "is_running": False,
                "queue_size": 0,
                "active_workers": 0,
                "phases": [],
                "message": "Automation manager not available",
            },
        }
    try:
        status = automation.get_status()
        schedules = status.get("schedules") or {}
        phase_group_labels = {
            0: "Monitoring",
            1: "Data collection & context",
            2: "Articles, context & events",
            3: "Event review & ML",
            4: "ML & entity (parallel)",
            5: "Topic clustering",
            6: "Summaries",
            7: "Storylines",
            8: "RAG enhancement",
            9: "Events, timelines & enrichment",
            10: "Maintenance",
            11: "Digests",
            12: "Watchlist & patterns",
            99: "Maintenance",
        }
        phases = []
        for name, sched in schedules.items():
            if not isinstance(sched, dict):
                continue
            last_run = sched.get("last_run")
            # Use DB last_run when in-memory is missing (e.g. after API restart)
            if last_run is None:
                db_last = _get_last_run_from_db(name)
                if db_last is not None:
                    last_run = db_last
            phase_num = sched.get("phase")
            phases.append({
                "name": name,
                "last_run": last_run.isoformat() if hasattr(last_run, "isoformat") else str(last_run) if last_run else None,
                "interval_seconds": sched.get("interval"),
                "enabled": sched.get("enabled", True),
                "phase": phase_num,
                "phase_group_label": phase_group_labels.get(phase_num, f"Phase {phase_num}"),
                "parallel_group": sched.get("parallel_group"),
            })
        phases.sort(key=lambda p: (p.get("phase") or 0, p.get("name") or ""))
        return {
            "success": True,
            "data": {
                "is_running": status.get("is_running", False),
                "queue_size": status.get("queue_size", 0),
                "active_workers": status.get("active_workers", 0),
                "phases": phases,
            },
        }
    except Exception as e:
        logger.warning("get_automation_status failed: %s", e)
        return {"success": False, "data": {}, "error": str(e)[:200]}


@router.get("/sources_collected")
async def get_sources_collected(
    minutes: int = Query(30, ge=1, le=1440, description="Look back window in minutes"),
) -> Dict[str, Any]:
    """
    List all data sources that were actually pulled from in the last N minutes.
    Includes: RSS feeds (per feed, from last_fetched_at), orchestrator collection
    sources (rss, gold, silver, platinum from last_collection_times), and pipeline
    stages that ran (e.g. rss_collection from pipeline_checkpoints).
    """
    from datetime import timezone as tz
    cutoff = datetime.now(tz.utc) - timedelta(minutes=minutes)
    cutoff_iso = cutoff.isoformat()

    out = {
        "window_minutes": minutes,
        "cutoff_utc": cutoff_iso,
        "rss_feeds": [],
        "orchestrator_sources": [],
        "pipeline_stages": [],
        "summary": [],
    }

    # 1) RSS feeds: any feed with last_fetched_at in the window (per-domain tables)
    conn = get_db_connection()
    if conn:
        try:
            for schema, domain_key in [("politics", "politics"), ("finance", "finance"), ("science_tech", "science-tech")]:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT feed_name, feed_url, last_fetched_at
                            FROM {schema}.rss_feeds
                            WHERE is_active = true
                              AND last_fetched_at IS NOT NULL
                              AND last_fetched_at >= %s
                            ORDER BY last_fetched_at DESC
                            """,
                            (cutoff,),
                        )
                        for row in cur.fetchall():
                            out["rss_feeds"].append({
                                "feed_name": row[0] or "",
                                "feed_url": (row[1] or "")[:200],
                                "domain": domain_key,
                                "last_fetched_at": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                            })
                except Exception as e:
                    logger.debug("sources_collected rss %s: %s", schema, e)
            conn.close()
        except Exception as e:
            logger.debug("sources_collected db: %s", e)
            try:
                conn.close()
            except Exception:
                pass

    # 2) Orchestrator collection sources (rss, gold, silver, platinum) from last_collection_times
    try:
        from services import orchestrator_state
        state = orchestrator_state.get_controller_state()
        times = state.get("last_collection_times") or {}
        for source_id, last_iso in times.items():
            if not last_iso:
                continue
            try:
                # Parse and compare (last_iso may be with or without Z)
                last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=tz.utc)
                if last_dt >= cutoff:
                    out["orchestrator_sources"].append({
                        "source_id": source_id,
                        "last_collected_at": last_iso,
                    })
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.debug("sources_collected orchestrator_state: %s", e)

    # 3) Pipeline stages that ran in the window (e.g. rss_collection)
    conn2 = get_db_connection()
    if conn2:
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT stage, MAX(timestamp) AS last_ts
                    FROM pipeline_checkpoints
                    WHERE timestamp >= %s
                    GROUP BY stage
                    ORDER BY last_ts DESC
                    """,
                    (cutoff,),
                )
                for row in cur.fetchall():
                    out["pipeline_stages"].append({
                        "stage": row[0],
                        "last_run_at": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
                    })
            conn2.close()
        except Exception as e:
            logger.debug("sources_collected pipeline_checkpoints: %s", e)
            try:
                conn2.close()
            except Exception:
                pass

    # Summary line for UI
    n_rss = len(out["rss_feeds"])
    n_orch = len(out["orchestrator_sources"])
    n_stages = len(out["pipeline_stages"])
    parts = []
    if n_rss:
        parts.append(f"{n_rss} RSS feed(s)")
    if n_orch:
        parts.append(f"{n_orch} orchestrator source(s): {', '.join(s['source_id'] for s in out['orchestrator_sources'])}")
    if n_stages:
        parts.append(f"pipeline stages: {', '.join(s['stage'] for s in out['pipeline_stages'])}")
    out["summary"] = parts if parts else ["No sources collected in the last {} minutes".format(minutes)]

    return {"success": True, "data": out}


@router.post("/monitoring/trigger_phase")
async def trigger_phase(request: Request, body: Dict[str, Any] = Body(..., embed=False)):
    """
    Request that the AutomationManager run a phase (e.g. rss_processing).
    The task is enqueued and will show in Current activity while it runs.
    Adds a "Requested: {phase} — queued" entry immediately so the Monitor shows it.
    """
    phase = (body.get("phase") or "").strip()
    if not phase:
        raise HTTPException(status_code=400, detail="phase required (e.g. rss_processing)")
    automation = getattr(request.app.state, "automation", None)
    if automation is None or not hasattr(automation, "request_phase"):
        raise HTTPException(status_code=503, detail="Automation manager not available")
    import time
    requested_activity_id = f"requested_{phase}_{int(time.time())}"
    try:
        from services.activity_feed_service import get_activity_feed
        get_activity_feed().add_current(
            requested_activity_id,
            f"Requested: {phase} — queued",
            phase=phase,
        )
    except Exception as e:
        logger.debug("Activity feed add_current (requested): %s", e)
    try:
        automation.request_phase(
            phase,
            domain=body.get("domain"),
            storyline_id=body.get("storyline_id"),
            requested_activity_id=requested_activity_id,
        )
    except Exception as e:
        logger.warning("trigger_phase failed: %s", e)
        try:
            from services.activity_feed_service import get_activity_feed
            get_activity_feed().complete(requested_activity_id, success=False, error_message=str(e)[:200])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    msg = f"Phase {phase} requested; check Current activity on Monitor."
    warning = None
    if hasattr(automation, "get_phase_request_warning"):
        try:
            warning = automation.get_phase_request_warning(phase)
        except Exception:
            pass
    if warning:
        msg += f" {warning}"
    return {"success": True, "message": msg, "warning": warning}


@router.get("/fast_stats")
@cached_response(ttl=60)  # Cache stats for 1 minute (dashboard refreshes frequently)
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
@cached_response(ttl=30)  # Cache metrics for 30 seconds
async def get_system_metrics(
    metric_name: Optional[str] = None,
    hours: int = 24,
    limit: int = Query(100, ge=1, le=200)  # Max 200 for performance
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
    limit: int = Query(50, ge=1, le=100)  # Max 100 for performance
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


# =============================================================================
# ANOMALY MONITORING (data-flow anomalies: volume, source, storyline)
# =============================================================================

@router.get("/anomalies")
async def get_anomalies(
    domain: Optional[str] = Query(None, description="politics, finance, or science-tech; omit for all"),
    hours: int = Query(24, ge=1, le=168),
    sensitivity: float = Query(2.0, ge=0.5, le=5.0),
    include_investigated: bool = Query(False, description="Include anomalies already marked investigated"),
):
    """List data-flow anomalies (article volume, source behavior, storyline growth). Uses IntelligenceAnalysisService."""
    try:
        from services.intelligence_analysis_service import get_intelligence_service
        svc = get_intelligence_service()
        domains_to_check = [domain] if domain else ["politics", "finance", "science_tech"]
        all_anomalies = []
        for d in domains_to_check:
            try:
                anomalies = svc.detect_anomalies(d, hours=hours, sensitivity=sensitivity)
                for a in anomalies:
                    all_anomalies.append({
                        "domain": d,
                        "entity_type": a.entity_type,
                        "entity_id": a.entity_id,
                        "anomaly_type": a.anomaly_type,
                        "severity": a.severity,
                        "description": a.description,
                        "detected_value": a.detected_value,
                        "expected_range": list(a.expected_range),
                        "evidence": a.supporting_evidence,
                        "detected_at": a.detected_at.isoformat(),
                    })
            except Exception as e:
                logger.debug("detect_anomalies %s: %s", d, e)
        if not include_investigated and all_anomalies:
            try:
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT domain, entity_type, entity_id FROM intelligence.anomaly_investigations
                            WHERE investigated_at > NOW() - INTERVAL '7 days'
                            """
                        )
                        investigated = {(r[0], r[1], r[2]) for r in cur.fetchall()}
                    conn.close()
                    all_anomalies = [
                        a for a in all_anomalies
                        if (a["domain"], a["entity_type"], a["entity_id"]) not in investigated
                    ]
            except Exception:
                pass
        severity_counts = defaultdict(int)
        for a in all_anomalies:
            severity_counts[a["severity"]] += 1
        return {
            "success": True,
            "data": {
                "anomalies": all_anomalies,
                "total": len(all_anomalies),
                "severity_breakdown": dict(severity_counts),
                "requires_attention": severity_counts.get("critical", 0) + severity_counts.get("high", 0) > 0,
            },
            "message": None,
        }
    except Exception as e:
        logger.error("get_anomalies failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investigate_anomaly")
async def investigate_anomaly(
    domain: str = Body(..., embed=True),
    entity_type: str = Body(..., embed=True),
    entity_id: int = Body(..., embed=True),
    action: str = Body("investigated", embed=True),
    note: Optional[str] = Body(None, embed=True),
    anomaly_type: Optional[str] = Body(None, embed=True),
):
    """Record that an anomaly was reviewed (investigated, dismissed, or escalated)."""
    if action not in ("investigated", "dismissed", "escalated"):
        raise HTTPException(status_code=400, detail="action must be investigated, dismissed, or escalated")
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=503, detail="Database unavailable")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.anomaly_investigations
                (domain, entity_type, entity_id, anomaly_type, action, note)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (domain, entity_type, entity_id, anomaly_type or "", action, note),
            )
            row = cur.fetchone()
        conn.commit()
        conn.close()
        return {
            "success": True,
            "data": {"id": row[0], "action": action},
            "message": None,
        }
    except Exception as e:
        logger.warning("investigate_anomaly failed: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
@cached_response(ttl=30)  # Cache system status for 30 seconds
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

                # Get GPU info if available (nvidia-smi or GPUtil)
                gpu = _get_gpu_metrics()
                gpu_vram_percent = gpu.get("gpu_vram_percent")
                gpu_utilization_percent = gpu.get("gpu_utilization_percent")

                # OPTIMIZED: Get all database metrics in a single query (reduces round-trips)
                week_ago = datetime.now() - timedelta(days=7)
                cur.execute("""
                    SELECT 
                        -- Total counts
                        (SELECT COUNT(*) FROM politics.articles) +
                        (SELECT COUNT(*) FROM finance.articles) +
                        (SELECT COUNT(*) FROM science_tech.articles) as total_articles,
                        (SELECT COUNT(*) FROM politics.storylines) +
                        (SELECT COUNT(*) FROM finance.storylines) +
                        (SELECT COUNT(*) FROM science_tech.storylines) as total_storylines,
                        (SELECT COUNT(*) FROM politics.rss_feeds WHERE is_active = true) +
                        (SELECT COUNT(*) FROM finance.rss_feeds WHERE is_active = true) +
                        (SELECT COUNT(*) FROM science_tech.rss_feeds WHERE is_active = true) as active_feeds,
                        -- Time-based counts
                        (SELECT COUNT(*) FROM politics.articles WHERE created_at >= %s) +
                        (SELECT COUNT(*) FROM finance.articles WHERE created_at >= %s) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE created_at >= %s) as articles_this_week,
                        (SELECT COUNT(*) FROM politics.articles WHERE DATE(created_at) = CURRENT_DATE) +
                        (SELECT COUNT(*) FROM finance.articles WHERE DATE(created_at) = CURRENT_DATE) +
                        (SELECT COUNT(*) FROM science_tech.articles WHERE DATE(created_at) = CURRENT_DATE) as articles_today
                """, (week_ago, week_ago, week_ago))
                stats = cur.fetchone()
                total_articles = stats[0] if stats and stats[0] else 0
                total_storylines = stats[1] if stats and stats[1] else 0
                active_feeds = stats[2] if stats and stats[2] else 0
                articles_this_week = stats[3] if stats and stats[3] else 0
                articles_today = stats[4] if stats and stats[4] else 0
                
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
                
                # Redis removed from architecture
                return {
                    "success": True,
                    "data": {
                        "system": {
                            "cpu_percent": cpu_percent,
                            "memory_percent": memory.percent,
                            "disk_percent": disk.percent,
                            "gpu_vram_percent": gpu_vram_percent,
                            "gpu_utilization_percent": gpu_utilization_percent,
                            "gpu_temperature_c": gpu.get("gpu_temperature_c"),
                            "gpu_memory_used_mb": gpu.get("gpu_memory_used_mb"),
                            "gpu_memory_total_mb": gpu.get("gpu_memory_total_mb"),
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
                            "status": "not_used",
                            "host": "",
                            "port": 0
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
@cached_response(ttl=60)  # Cache dashboard metrics for 1 minute
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

@router.post("/apply_migration_128")
async def apply_migration_128():
    """
    Apply migration 128: Add Official Government and SEC RSS Feeds
    This adds official government feeds to finance, politics, and science_tech domains
    """
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Migration SQL
        migration_sql = """
-- Migration 128: Add Official Government and SEC RSS Feeds
INSERT INTO finance.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
    ('SEC Press Releases', 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom', true, 3600, NOW()),
    ('Federal Reserve Press Releases', 'https://www.federalreserve.gov/feeds/press_all.xml', true, 3600, NOW()),
    ('Treasury Direct Announcements', 'https://www.treasurydirect.gov/rss/announcements.xml', true, 3600, NOW()),
    ('FDIC News Releases', 'https://www.fdic.gov/news/news/press/feed.xml', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;

INSERT INTO politics.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
    ('White House Briefings', 'https://www.whitehouse.gov/briefing-room/feed/', true, 3600, NOW()),
    ('Department of State Press Releases', 'https://www.state.gov/rss-feed/press-releases/feed/', true, 3600, NOW()),
    ('Department of Justice Press Releases', 'https://www.justice.gov/opa/rss/doj-press-releases.xml', true, 3600, NOW()),
    ('Department of Defense News', 'https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=944&max=20', true, 3600, NOW()),
    ('Congressional Research Service', 'https://crsreports.congress.gov/rss', true, 3600, NOW()),
    ('GAO Reports', 'https://www.gao.gov/rss/reports.xml', true, 3600, NOW()),
    ('CBO Publications', 'https://www.cbo.gov/rss/publications.xml', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;

INSERT INTO science_tech.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
    ('NASA News', 'https://www.nasa.gov/rss/dyn/breaking_news.rss', true, 3600, NOW()),
    ('NIST News', 'https://www.nist.gov/news-events/news/feed', true, 3600, NOW()),
    ('Department of Energy News', 'https://www.energy.gov/feeds/all', true, 3600, NOW()),
    ('NIH News Releases', 'https://www.nih.gov/news-events/news-releases/rss', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;
"""
        
        try:
            cur = conn.cursor()
            cur.execute(migration_sql)
            conn.commit()
            
            # Verify feeds were added
            cur.execute("SELECT COUNT(*) FROM finance.rss_feeds WHERE feed_name LIKE 'SEC%' OR feed_name LIKE 'Federal Reserve%' OR feed_name LIKE 'Treasury%' OR feed_name LIKE 'FDIC%'")
            finance_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM politics.rss_feeds WHERE feed_name LIKE 'White House%' OR feed_name LIKE 'Department%' OR feed_name LIKE 'Congressional%' OR feed_name LIKE 'GAO%' OR feed_name LIKE 'CBO%'")
            politics_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM science_tech.rss_feeds WHERE feed_name LIKE 'NASA%' OR feed_name LIKE 'NIST%' OR feed_name LIKE 'Department of Energy%' OR feed_name LIKE 'NIH%'")
            science_count = cur.fetchone()[0]
            
            return {
                "success": True,
                "message": "Migration 128 applied successfully",
                "feeds_added": {
                    "finance": finance_count,
                    "politics": politics_count,
                    "science_tech": science_count
                },
                "total": finance_count + politics_count + science_count
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error applying migration: {e}")
            raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in apply_migration_128: {e}")
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

                # Get GPU info if available (nvidia-smi or GPUtil)
                gpu = _get_gpu_metrics()

                # Store metrics in database
                metrics = [
                    ("cpu_percent", cpu_percent, "percent"),
                    ("memory_percent", memory.percent, "percent"),
                    ("disk_percent", disk.percent, "percent"),
                    ("memory_available", memory.available, "bytes"),
                    ("disk_free", disk.free, "bytes")
                ]
                if gpu.get("gpu_utilization_percent") is not None:
                    metrics.append(("gpu_utilization_percent", gpu["gpu_utilization_percent"], "percent"))
                if gpu.get("gpu_vram_percent") is not None:
                    metrics.append(("gpu_vram_percent", gpu["gpu_vram_percent"], "percent"))
                
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

@router.post("/pipeline/trigger")
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
            from domains.content_analysis.services.topic_filter_rules import filter_topic_list
            from shared.database.connection import get_db_connection
            
            extractor = AdvancedTopicExtractor(get_db_connection)
            topics = extractor.extract_topics_from_articles(time_period_hours=24)
            # Apply date/country filter - exclude dates, months, country names from topics
            if topics:
                topics = filter_topic_list(topics, name_key="name")
            
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
    """Log pipeline trace to database. Uses pipeline_traces + pipeline_checkpoints schema."""
    import json
    import uuid
    try:
        conn = get_db_connection()
        if not conn:
            return

        metadata = metadata or {}
        checkpoint_status = "failed" if status == "error" else status  # pipeline_checkpoints uses 'failed' not 'error'
        error_msg = str(metadata.get("error", "")) if status == "error" else None
        perf_json = json.dumps(metadata)

        try:
            with conn.cursor() as cur:
                # Ensure pipeline_traces row exists
                cur.execute("""
                    INSERT INTO pipeline_traces (trace_id, start_time)
                    VALUES (%s, NOW())
                    ON CONFLICT (trace_id) DO NOTHING
                """, (trace_id,))

                # Log stage to pipeline_checkpoints (has stage, status, error_message)
                checkpoint_id = f"{trace_id}_{stage}_{uuid.uuid4().hex[:12]}"
                cur.execute("""
                    INSERT INTO pipeline_checkpoints (checkpoint_id, trace_id, stage, status, timestamp, error_message, metadata)
                    VALUES (%s, %s, %s, %s, NOW(), %s, %s::jsonb)
                """, (checkpoint_id, trace_id, stage, checkpoint_status, error_msg, perf_json))

                # On completion or error, update pipeline_traces
                if status in ("completed", "error"):
                    cur.execute("""
                        UPDATE pipeline_traces
                        SET end_time = NOW(),
                            success = (%s = 'completed'),
                            error_stage = CASE WHEN %s = 'error' THEN %s ELSE NULL END,
                            performance_metrics = COALESCE(performance_metrics, '{}'::jsonb) || %s::jsonb
                        WHERE trace_id = %s
                    """, (status, status, stage, perf_json, trace_id))
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error logging pipeline trace: {e}")


@router.post("/logs")
async def ingest_client_log(log_entry: Dict[str, Any] = Body(...)):
    """
    Receive a single client log entry from the frontend (errors, warnings).
    Persists to activity.jsonl with component=client.
    """
    try:
        from shared.logging.activity_logger import log_activity
        level = log_entry.get("level", "info")
        message = log_entry.get("message", "Client log")
        context = {k: v for k, v in log_entry.items() if k not in ("level", "message")}
        log_activity(
            component="client",
            event_type="log",
            status=level,
            message=message,
            **context,
        )
        return {"success": True}
    except Exception as e:
        logger.warning("Client log ingestion failed: %s", e)
        return {"success": False, "error": str(e)}


@router.post("/logs/batch")
async def ingest_client_logs_batch(batch: Dict[str, Any] = Body(...)):
    """
    Receive batch of client log entries from the frontend.
    Persists each to activity.jsonl with component=client.
    """
    logs = batch.get("logs", [])
    if not isinstance(logs, list):
        return {"success": False, "error": "logs must be an array"}
    try:
        from shared.logging.activity_logger import log_activity
        for entry in logs[:100]:  # Cap at 100 per batch
            level = entry.get("level", "info")
            message = entry.get("message", "Client log")
            context = {k: v for k, v in entry.items() if k not in ("level", "message")}
            try:
                log_activity(
                    component="client",
                    event_type="log",
                    status=level,
                    message=message,
                    **context,
                )
            except Exception:
                pass
        return {"success": True, "count": min(len(logs), 100)}
    except Exception as e:
        logger.warning("Client log batch ingestion failed: %s", e)
        return {"success": False, "error": str(e)}


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


@router.get("/process_run_summary")
def get_process_run_summary(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Look back window in hours"),
    activity_lines: int = Query(80, ge=0, le=200, description="Max lines from activity.jsonl (0 = skip)"),
) -> Dict[str, Any]:
    """
    Review what has been running and what has not been triggered recently.
    Uses automation_run_history (DB) so "last 24h" is chronological, not since API restart.
    Returns: phases run in last N hours, phases not run (or never), pipeline checkpoints in window,
    and recent activity log entries (from activity.jsonl) when available.
    """
    from datetime import timezone as tz
    cutoff = datetime.now(tz.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    out = {
        "window_hours": hours,
        "cutoff_utc": cutoff_iso,
        "phases_run_recently": [],
        "phases_not_run_recently": [],
        "pipeline_checkpoints_recent": [],
        "recent_activity": [],
        "activity_file_used": None,
    }

    # 1) Automation phases: run recently vs not (from automation_run_history — survives restart)
    conn = get_db_connection()
    run_in_window = {}  # phase_name -> last finished_at in window
    last_run_ever = {}  # phase_name -> last finished_at (any time)
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT phase_name, finished_at
                    FROM automation_run_history
                    WHERE finished_at >= %s
                    ORDER BY finished_at DESC
                    """,
                    (cutoff,),
                )
                for row in cur.fetchall():
                    name, finished = row[0], row[1]
                    if name not in run_in_window:
                        run_in_window[name] = finished
                cur.execute(
                    """
                    SELECT phase_name, MAX(finished_at) AS last_finished
                    FROM automation_run_history
                    GROUP BY phase_name
                    """
                )
                for row in cur.fetchall():
                    last_run_ever[row[0]] = row[1]
        except Exception as e:
            logger.debug("process_run_summary automation_run_history: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # Build list of known phase names (from in-memory schedules if available, else from DB)
    schedule_names = set()
    schedule_info = {}  # name -> { interval, phase }
    automation = getattr(request.app.state, "automation", None)
    if automation and hasattr(automation, "get_status"):
        try:
            status = automation.get_status()
            schedules = status.get("schedules") or {}
            for name, sched in schedules.items():
                if isinstance(sched, dict) and sched.get("enabled", True):
                    schedule_names.add(name)
                    schedule_info[name] = {"interval": sched.get("interval"), "phase": sched.get("phase")}
        except Exception as e:
            logger.debug("process_run_summary schedules: %s", e)
    if not schedule_names and last_run_ever:
        schedule_names = set(last_run_ever.keys())

    for name in sorted(schedule_names):
        info = schedule_info.get(name, {})
        last_ts = last_run_ever.get(name)
        last_iso = last_ts.isoformat() if last_ts and hasattr(last_ts, "isoformat") else (str(last_ts) if last_ts else None)
        entry = {
            "name": name,
            "last_run": last_iso,
            "interval_seconds": info.get("interval"),
            "phase": info.get("phase"),
        }
        if name in run_in_window:
            out["phases_run_recently"].append(entry)
        else:
            out["phases_not_run_recently"].append(entry)
    out["phases_run_recently"].sort(key=lambda x: (x.get("phase") or 0, x.get("name") or ""))
    out["phases_not_run_recently"].sort(key=lambda x: (x.get("phase") or 0, x.get("name") or ""))

    # 2) Pipeline checkpoints in the window
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT stage, status, timestamp
                    FROM pipeline_checkpoints
                    WHERE timestamp >= %s
                    ORDER BY timestamp DESC
                    LIMIT 200
                    """,
                    (cutoff,),
                )
                for row in cur.fetchall():
                    out["pipeline_checkpoints_recent"].append({
                        "stage": row[0],
                        "status": row[1],
                        "timestamp": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                    })
            conn.close()
        except Exception as e:
            logger.debug("process_run_summary pipeline_checkpoints: %s", e)
            try:
                conn.close()
            except Exception:
                pass

    # 3) Recent activity from activity.jsonl (if present)
    if activity_lines > 0:
        log_path = None
        try:
            from pathlib import Path
            try:
                from config.paths import LOG_DIR
                log_path = Path(LOG_DIR) / "activity.jsonl"
            except Exception:
                log_path = Path(__file__).resolve().parents[4] / "logs" / "activity.jsonl"
            if log_path.exists():
                with open(log_path, "r") as f:
                    lines = [ln.strip() for ln in f.readlines() if ln.strip()]
                for line in lines[-activity_lines:]:
                    try:
                        import json
                        obj = json.loads(line)
                        out["recent_activity"].append({
                            "timestamp": obj.get("timestamp"),
                            "component": obj.get("component"),
                            "event_type": obj.get("event_type"),
                            "status": obj.get("status"),
                            "message": obj.get("message"),
                        })
                    except (json.JSONDecodeError, TypeError):
                        pass
                out["activity_file_used"] = str(log_path)
        except Exception as e:
            logger.debug("process_run_summary activity.jsonl: %s", e)

    return {"success": True, "data": out}


@router.get("/logs/realtime")
async def get_realtime_logs(limit: int = Query(50, ge=1, le=100)):  # Max 100 for performance
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

@router.get("/articles/analyze")
async def analyze_existing_articles(
    source: Optional[str] = Query(None, description="Filter by source name (e.g., 'telegraph')"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Limit articles analyzed per domain"),
    domains: Optional[str] = Query(None, description="Comma-separated list of domains to analyze (default: all active)"),
    sample_size: int = Query(20, ge=1, le=100, description="Number of sample articles to return")
):
    """
    Analyze existing articles against current filtering criteria.
    Identifies articles that would be filtered by current RSS collector logic.
    """
    if not FILTERING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Filtering functions not available")
    
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Get active domain schemas
            with conn.cursor() as cur:
                if domains:
                    domain_list = [d.strip() for d in domains.split(',')]
                    placeholders = ','.join(['%s'] * len(domain_list))
                    cur.execute(f"""
                        SELECT schema_name FROM domains 
                        WHERE schema_name IN ({placeholders}) AND is_active = true
                    """, domain_list)
                else:
                    cur.execute("SELECT schema_name FROM domains WHERE is_active = true")
                schemas = [row[0] for row in cur.fetchall()]
            
            if not schemas:
                raise HTTPException(status_code=404, detail="No active domains found")
            
            all_filtered = []
            all_stats = {}
            
            for schema in schemas:
                # Build query
                query = f"""
                    SELECT 
                        id, title, url, content, summary, source_domain, source, 
                        feed_name, created_at, published_at, processing_status
                    FROM {schema}.articles
                    WHERE 1=1
                """
                
                params = []
                if source:
                    query += " AND (source_domain ILIKE %s OR source ILIKE %s OR feed_name ILIKE %s)"
                    pattern = f"%{source}%"
                    params = [pattern, pattern, pattern]
                
                query += " ORDER BY created_at DESC"
                
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)
                
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    articles = cur.fetchall()
                
                # Analyze articles
                filtered_articles = []
                stats = defaultdict(int)
                stats['total'] = len(articles)
                
                for row in articles:
                    article = {
                        'id': row[0],
                        'title': row[1] or '',
                        'url': row[2] or '',
                        'content': row[3] or '',
                        'summary': row[4] or '',
                        'source_domain': row[5] or '',
                        'source': row[6] or '',
                        'feed_name': row[7] or '',
                        'created_at': row[8],
                        'published_at': row[9],
                        'processing_status': row[10] or ''
                    }
                    
                    # Apply filters
                    title = article['title']
                    content = article['content'] or article['summary']
                    url = article['url']
                    feed_name = article['feed_name']
                    source_name = article['source_domain'] or article['source']
                    
                    excluded_content = is_excluded_content(title, content, feed_name, url)
                    clickbait = is_clickbait_title(title)
                    advertisement = is_advertisement(title, content, url)
                    
                    quality_score = calculate_article_quality_score(title, content, source_name)
                    impact_score = calculate_article_impact_score(title, content)
                    
                    low_quality = quality_score < 0.4
                    low_impact = impact_score < 0.4
                    
                    would_filter = excluded_content or clickbait or advertisement or low_quality or low_impact
                    
                    if would_filter:
                        reasons = []
                        if excluded_content:
                            reasons.append('excluded_content')
                        if clickbait:
                            reasons.append('clickbait')
                        if advertisement:
                            reasons.append('advertisement')
                        if low_quality:
                            reasons.append(f'low_quality_{quality_score:.2f}')
                        if low_impact:
                            reasons.append(f'low_impact_{impact_score:.2f}')
                        
                        filtered_articles.append({
                            'article_id': article['id'],
                            'title': title[:100],
                            'source': source_name or feed_name or 'Unknown',
                            'url': url,
                            'reasons': reasons,
                            'quality_score': round(quality_score, 2),
                            'impact_score': round(impact_score, 2),
                            'schema': schema,
                            'created_at': article['created_at'].isoformat() if article['created_at'] else None
                        })
                        
                        stats['filtered'] += 1
                        if excluded_content:
                            stats['excluded_content'] += 1
                        if clickbait:
                            stats['clickbait'] += 1
                        if advertisement:
                            stats['advertisement'] += 1
                        if low_quality:
                            stats['low_quality'] += 1
                        if low_impact:
                            stats['low_impact'] += 1
                
                all_filtered.extend(filtered_articles)
                all_stats[schema] = dict(stats)
            
            # Calculate overall statistics
            total_articles = sum(s['total'] for s in all_stats.values())
            total_filtered = sum(s['filtered'] for s in all_stats.values())
            
            # Get top sources with filtered articles
            source_counts = defaultdict(int)
            for article in all_filtered:
                source_counts[article['source']] += 1
            
            top_sources = [
                {'source': source, 'count': count}
                for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            ]
            
            return {
                'success': True,
                'data': {
                    'summary': {
                        'total_articles': total_articles,
                        'total_filtered': total_filtered,
                        'filtered_percentage': round(total_filtered / total_articles * 100, 1) if total_articles > 0 else 0,
                        'total_passing': total_articles - total_filtered,
                        'passing_percentage': round((total_articles - total_filtered) / total_articles * 100, 1) if total_articles > 0 else 0
                    },
                    'by_domain': all_stats,
                    'top_sources': top_sources,
                    'sample_articles': all_filtered[:sample_size],
                    'total_filtered_articles': len(all_filtered)
                },
                'timestamp': datetime.now().isoformat()
            }
            
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze articles: {str(e)}")
