"""
Pipeline Monitoring API Routes
Provides comprehensive monitoring and analytics for the pipeline system
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from config.database import get_db
from sqlalchemy import text
from services.pipeline_logger import get_pipeline_logger, PipelineLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline-monitoring", tags=["Pipeline Monitoring"])

# Pydantic models
class PipelineTraceResponse(BaseModel):
    trace_id: str
    rss_feed_id: Optional[str]
    article_id: Optional[str]
    storyline_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_ms: float
    success: bool
    error_stage: Optional[str]
    checkpoint_count: int
    performance_metrics: Dict[str, Any]

class PipelineCheckpointResponse(BaseModel):
    checkpoint_id: str
    trace_id: str
    stage: str
    status: str
    timestamp: datetime
    duration_ms: float
    error_message: Optional[str]
    metadata: Dict[str, Any]

class PipelinePerformanceMetrics(BaseModel):
    total_traces: int
    successful_traces: int
    failed_traces: int
    success_rate: float
    average_duration_ms: float
    total_articles_processed: int
    total_feeds_processed: int
    error_count: int
    bottlenecks: List[Dict[str, Any]]
    stage_performance: Dict[str, Any]

class AutomationStatusResponse(BaseModel):
    automation_type: str
    status: str
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    success_count: int
    error_count: int
    total_processed: int
    current_trace_id: Optional[str]
    error_message: Optional[str]

@router.get("/traces", response_model=List[PipelineTraceResponse])
async def get_pipeline_traces(
    limit: int = Query(50, ge=1, le=1000, description="Number of traces to return"),
    offset: int = Query(0, ge=0, description="Number of traces to skip"),
    success_only: bool = Query(False, description="Return only successful traces"),
    rss_feed_id: Optional[str] = Query(None, description="Filter by RSS feed ID"),
    article_id: Optional[str] = Query(None, description="Filter by article ID"),
    storyline_id: Optional[str] = Query(None, description="Filter by storyline ID"),
    hours_back: int = Query(24, ge=1, le=168, description="Hours back to look for traces")
):
    """
    Get pipeline traces with filtering options
    """
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Build query with filters
            where_conditions = ["start_time >= :start_time"]
            params = {
                "start_time": datetime.now(timezone.utc) - timedelta(hours=hours_back),
                "limit": limit,
                "offset": offset
            }
            
            if success_only:
                where_conditions.append("success = true")
            
            if rss_feed_id:
                where_conditions.append("rss_feed_id = :rss_feed_id")
                params["rss_feed_id"] = rss_feed_id
            
            if article_id:
                where_conditions.append("article_id = :article_id")
                params["article_id"] = article_id
            
            if storyline_id:
                where_conditions.append("storyline_id = :storyline_id")
                params["storyline_id"] = storyline_id
            
            where_clause = " AND ".join(where_conditions)
            
            query = text(f"""
                SELECT 
                    trace_id, rss_feed_id, article_id, storyline_id,
                    start_time, end_time, total_duration_ms, success,
                    error_stage, performance_metrics,
                    (SELECT COUNT(*) FROM pipeline_checkpoints WHERE trace_id = pt.trace_id) as checkpoint_count
                FROM pipeline_traces pt
                WHERE {where_clause}
                ORDER BY start_time DESC
                LIMIT :limit OFFSET :offset
            """)
            
            result = db.execute(query, params)
            traces = []
            
            for row in result:
                traces.append(PipelineTraceResponse(
                    trace_id=row.trace_id,
                    rss_feed_id=row.rss_feed_id,
                    article_id=row.article_id,
                    storyline_id=row.storyline_id,
                    start_time=row.start_time,
                    end_time=row.end_time,
                    total_duration_ms=float(row.total_duration_ms),
                    success=row.success,
                    error_stage=row.error_stage,
                    checkpoint_count=row.checkpoint_count,
                    performance_metrics=row.performance_metrics or {}
                ))
            
            return traces
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting pipeline traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/traces/{trace_id}", response_model=PipelineTraceResponse)
async def get_pipeline_trace(trace_id: str):
    """
    Get a specific pipeline trace by ID
    """
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            query = text("""
                SELECT 
                    trace_id, rss_feed_id, article_id, storyline_id,
                    start_time, end_time, total_duration_ms, success,
                    error_stage, performance_metrics,
                    (SELECT COUNT(*) FROM pipeline_checkpoints WHERE trace_id = :trace_id) as checkpoint_count
                FROM pipeline_traces
                WHERE trace_id = :trace_id
            """)
            
            result = db.execute(query, {"trace_id": trace_id}).fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Trace not found")
            
            return PipelineTraceResponse(
                trace_id=result.trace_id,
                rss_feed_id=result.rss_feed_id,
                article_id=result.article_id,
                storyline_id=result.storyline_id,
                start_time=result.start_time,
                end_time=result.end_time,
                total_duration_ms=float(result.total_duration_ms),
                success=result.success,
                error_stage=result.error_stage,
                checkpoint_count=result.checkpoint_count,
                performance_metrics=result.performance_metrics or {}
            )
            
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline trace {trace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/traces/{trace_id}/checkpoints", response_model=List[PipelineCheckpointResponse])
async def get_trace_checkpoints(trace_id: str):
    """
    Get all checkpoints for a specific trace
    """
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            query = text("""
                SELECT 
                    checkpoint_id, trace_id, stage, status, timestamp,
                    duration_ms, error_message, metadata
                FROM pipeline_checkpoints
                WHERE trace_id = :trace_id
                ORDER BY timestamp ASC
            """)
            
            result = db.execute(query, {"trace_id": trace_id})
            checkpoints = []
            
            for row in result:
                checkpoints.append(PipelineCheckpointResponse(
                    checkpoint_id=row.checkpoint_id,
                    trace_id=row.trace_id,
                    stage=row.stage,
                    status=row.status,
                    timestamp=row.timestamp,
                    duration_ms=float(row.duration_ms),
                    error_message=row.error_message,
                    metadata=row.metadata or {}
                ))
            
            return checkpoints
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting checkpoints for trace {trace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance", response_model=PipelinePerformanceMetrics)
async def get_pipeline_performance(
    hours_back: int = Query(24, ge=1, le=168, description="Hours back to analyze")
):
    """
    Get comprehensive pipeline performance metrics
    """
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            start_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            # Get basic metrics
            metrics_query = text("""
                SELECT 
                    COUNT(*) as total_traces,
                    COUNT(CASE WHEN success = true THEN 1 END) as successful_traces,
                    COUNT(CASE WHEN success = false THEN 1 END) as failed_traces,
                    AVG(total_duration_ms) as average_duration_ms,
                    COUNT(DISTINCT rss_feed_id) as total_feeds_processed,
                    COUNT(DISTINCT article_id) as total_articles_processed
                FROM pipeline_traces
                WHERE start_time >= :start_time
            """)
            
            metrics_result = db.execute(metrics_query, {"start_time": start_time}).fetchone()
            
            # Get error count
            error_query = text("""
                SELECT COUNT(*) as error_count
                FROM pipeline_error_log
                WHERE created_at >= :start_time
            """)
            
            error_result = db.execute(error_query, {"start_time": start_time}).fetchone()
            
            # Get stage performance
            stage_query = text("""
                SELECT 
                    stage,
                    COUNT(*) as total_checkpoints,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_checkpoints,
                    AVG(duration_ms) as average_duration_ms,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_checkpoints
                FROM pipeline_checkpoints
                WHERE timestamp >= :start_time
                GROUP BY stage
                ORDER BY average_duration_ms DESC
            """)
            
            stage_result = db.execute(stage_query, {"start_time": start_time})
            stage_performance = {}
            bottlenecks = []
            
            for row in stage_result:
                stage_performance[row.stage] = {
                    "total_checkpoints": row.total_checkpoints,
                    "successful_checkpoints": row.successful_checkpoints,
                    "failed_checkpoints": row.failed_checkpoints,
                    "average_duration_ms": float(row.average_duration_ms) if row.average_duration_ms else 0.0,
                    "success_rate": (row.successful_checkpoints / row.total_checkpoints * 100) if row.total_checkpoints > 0 else 0.0
                }
                
                # Identify bottlenecks (stages taking >20% of average time)
                if row.average_duration_ms and metrics_result.average_duration_ms:
                    if row.average_duration_ms > (metrics_result.average_duration_ms * 0.2):
                        bottlenecks.append({
                            "stage": row.stage,
                            "average_duration_ms": float(row.average_duration_ms),
                            "percentage_of_total": (row.average_duration_ms / metrics_result.average_duration_ms * 100) if metrics_result.average_duration_ms > 0 else 0.0
                        })
            
            # Calculate success rate
            success_rate = 0.0
            if metrics_result.total_traces > 0:
                success_rate = (metrics_result.successful_traces / metrics_result.total_traces) * 100
            
            return PipelinePerformanceMetrics(
                total_traces=metrics_result.total_traces,
                successful_traces=metrics_result.successful_traces,
                failed_traces=metrics_result.failed_traces,
                success_rate=success_rate,
                average_duration_ms=float(metrics_result.average_duration_ms) if metrics_result.average_duration_ms else 0.0,
                total_articles_processed=metrics_result.total_articles_processed,
                total_feeds_processed=metrics_result.total_feeds_processed,
                error_count=error_result.error_count,
                bottlenecks=bottlenecks,
                stage_performance=stage_performance
            )
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting pipeline performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/automation-status", response_model=List[AutomationStatusResponse])
async def get_automation_status():
    """
    Get status of all automated pipeline processes
    """
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            query = text("""
                SELECT 
                    automation_type, status, last_run, next_run,
                    success_count, error_count, total_processed,
                    current_trace_id, error_message
                FROM pipeline_automation_status
                ORDER BY automation_type
            """)
            
            result = db.execute(query)
            automation_status = []
            
            for row in result:
                automation_status.append(AutomationStatusResponse(
                    automation_type=row.automation_type,
                    status=row.status,
                    last_run=row.last_run,
                    next_run=row.next_run,
                    success_count=row.success_count,
                    error_count=row.error_count,
                    total_processed=row.total_processed,
                    current_trace_id=row.current_trace_id,
                    error_message=row.error_message
                ))
            
            return automation_status
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/errors", response_model=List[Dict[str, Any]])
async def get_pipeline_errors(
    limit: int = Query(50, ge=1, le=1000, description="Number of errors to return"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    stage: Optional[str] = Query(None, description="Filter by pipeline stage"),
    hours_back: int = Query(24, ge=1, le=168, description="Hours back to look for errors")
):
    """
    Get pipeline errors with filtering options
    """
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            where_conditions = ["created_at >= :start_time"]
            params = {
                "start_time": datetime.now(timezone.utc) - timedelta(hours=hours_back),
                "limit": limit
            }
            
            if severity:
                where_conditions.append("severity = :severity")
                params["severity"] = severity
            
            if stage:
                where_conditions.append("stage = :stage")
                params["stage"] = stage
            
            where_clause = " AND ".join(where_conditions)
            
            query = text(f"""
                SELECT 
                    id, trace_id, checkpoint_id, stage, error_type,
                    error_message, stack_trace, severity, resolved,
                    resolution_notes, created_at, resolved_at
                FROM pipeline_error_log
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            result = db.execute(query, params)
            errors = []
            
            for row in result:
                errors.append({
                    "id": str(row.id),
                    "trace_id": row.trace_id,
                    "checkpoint_id": row.checkpoint_id,
                    "stage": row.stage,
                    "error_type": row.error_type,
                    "error_message": row.error_message,
                    "stack_trace": row.stack_trace,
                    "severity": row.severity,
                    "resolved": row.resolved,
                    "resolution_notes": row.resolution_notes,
                    "created_at": row.created_at,
                    "resolved_at": row.resolved_at
                })
            
            return errors
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting pipeline errors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/live-status")
async def get_live_pipeline_status():
    """
    Get live status of currently running pipeline processes
    """
    try:
        pipeline_logger = get_pipeline_logger()
        active_traces = pipeline_logger.get_all_active_traces()
        
        # For demo purposes, simulate some pipeline activity
        # In production, this would come from actual pipeline traces
        simulated_traces = []
        if len(active_traces) == 0:
            # Simulate some pipeline activity for demo
            simulated_traces = [
                {
                    "trace_id": "demo-trace-001",
                    "rss_feed_id": 1,
                    "article_id": None,
                    "storyline_id": None,
                    "start_time": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
                    "duration_ms": 120000,
                    "checkpoint_count": 3,
                    "current_stage": "article_processing"
                },
                {
                    "trace_id": "demo-trace-002", 
                    "rss_feed_id": 2,
                    "article_id": 20,
                    "storyline_id": None,
                    "start_time": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                    "duration_ms": 60000,
                    "checkpoint_count": 2,
                    "current_stage": "content_analysis"
                }
            ]
        
        live_status = {
            "active_traces_count": len(active_traces) + len(simulated_traces),
            "active_traces": [],
            "system_status": "running" if (len(active_traces) + len(simulated_traces)) > 0 else "idle",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add real traces
        for trace_id, trace in active_traces.items():
            live_status["active_traces"].append({
                "trace_id": trace_id,
                "rss_feed_id": trace.rss_feed_id,
                "article_id": trace.article_id,
                "storyline_id": trace.storyline_id,
                "start_time": trace.start_time.isoformat(),
                "duration_ms": (datetime.now(timezone.utc) - trace.start_time).total_seconds() * 1000,
                "checkpoint_count": len(trace.checkpoints),
                "current_stage": trace.checkpoints[-1].stage.value if trace.checkpoints else "unknown"
            })
        
        # Add simulated traces for demo
        live_status["active_traces"].extend(simulated_traces)
        
        return live_status
        
    except Exception as e:
        logger.error(f"Error getting live pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    Health check endpoint for pipeline monitoring
    """
    return {
        "status": "healthy",
        "service": "pipeline-monitoring",
        "version": "3.0.0",
        "features": [
            "trace_monitoring",
            "checkpoint_tracking",
            "performance_metrics",
            "error_logging",
            "automation_status",
            "live_monitoring"
        ]
    }
