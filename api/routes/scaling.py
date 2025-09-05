#!/usr/bin/env python3
"""
Scaling Management API Routes
Provides endpoints for managing large-scale processing and system monitoring
"""

from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from modules.scaling.scaling_manager import ScalingManager, ScalingMetrics, BatchProcessingConfig
from config.database import get_db_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scaling"])

# Global scaling manager instance
scaling_manager: Optional[ScalingManager] = None

def get_scaling_manager() -> ScalingManager:
    """Get or create scaling manager instance"""
    global scaling_manager
    if scaling_manager is None:
        db_config = get_db_config()
        scaling_manager = ScalingManager(db_config)
        scaling_manager.start_monitoring()
    return scaling_manager

# Pydantic models
class BatchCreationRequest(BaseModel):
    """Request model for creating processing batches"""
    article_ids: List[int] = Field(..., description="List of article IDs to process")
    batch_type: str = Field(default="manual", description="Type of batch processing")
    priority: int = Field(default=2, ge=1, le=4, description="Batch priority (1-4)")

class BatchStatusResponse(BaseModel):
    """Response model for batch status"""
    batch_id: str
    batch_type: str
    total_articles: int
    processed_articles: int
    failed_articles: int
    status: str
    priority: int
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    progress_percentage: float

class ScalingMetricsResponse(BaseModel):
    """Response model for scaling metrics"""
    total_articles: int
    raw_articles: int
    processing_articles: int
    completed_articles: int
    failed_articles: int
    total_timeline_events: int
    active_storylines: int
    queue_size: int
    running_tasks: int
    database_size_bytes: int
    avg_processing_time_seconds: float
    success_rate: float
    timestamp: str

@router.get("/metrics", response_model=ScalingMetricsResponse)
async def get_scaling_metrics():
    """Get current system scaling metrics"""
    try:
        manager = get_scaling_manager()
        metrics = manager.get_scaling_metrics()
        
        return ScalingMetricsResponse(
            total_articles=metrics.total_articles,
            raw_articles=metrics.raw_articles,
            processing_articles=metrics.processing_articles,
            completed_articles=metrics.completed_articles,
            failed_articles=metrics.failed_articles,
            total_timeline_events=metrics.total_timeline_events,
            active_storylines=metrics.active_storylines,
            queue_size=metrics.queue_size,
            running_tasks=metrics.running_tasks,
            database_size_bytes=metrics.database_size_bytes,
            avg_processing_time_seconds=metrics.avg_processing_time_seconds,
            success_rate=metrics.success_rate,
            timestamp=metrics.timestamp.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error getting scaling metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage", response_model=Dict[str, Any])
async def get_storage_usage():
    """Get current storage usage statistics"""
    try:
        manager = get_scaling_manager()
        usage = manager.get_storage_usage()
        return usage
        
    except Exception as e:
        logger.error(f"Error getting storage usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/create", response_model=Dict[str, str])
async def create_processing_batch(request: BatchCreationRequest):
    """Create a new processing batch for multiple articles"""
    try:
        # Check rate limit
        manager = get_scaling_manager()
        if not manager.check_rate_limit('ml_processing', 'batch_creation'):
            raise HTTPException(status_code=429, detail="Rate limit exceeded for batch creation")
        
        # Validate article count
        if len(request.article_ids) > 1000:
            raise HTTPException(status_code=400, detail="Batch size too large. Maximum 1000 articles per batch.")
        
        if len(request.article_ids) == 0:
            raise HTTPException(status_code=400, detail="No articles provided")
        
        # Create batch
        batch_id = manager.create_processing_batch(
            article_ids=request.article_ids,
            batch_type=request.batch_type,
            priority=request.priority
        )
        
        return {
            "success": "true",
            "batch_id": batch_id,
            "message": f"Batch created with {len(request.article_ids)} articles"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating processing batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/{batch_id}/process", response_model=Dict[str, Any])
async def process_batch(batch_id: str, background_tasks: BackgroundTasks):
    """Process a batch of articles (runs in background)"""
    try:
        manager = get_scaling_manager()
        
        # Check if batch exists
        batch_status = manager.get_batch_status(batch_id)
        if not batch_status:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        if batch_status["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Batch is already {batch_status['status']}")
        
        # Start processing in background
        background_tasks.add_task(manager.process_batch_intelligently, batch_id)
        
        return {
            "success": True,
            "batch_id": batch_id,
            "message": "Batch processing started in background"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str):
    """Get the status of a processing batch"""
    try:
        manager = get_scaling_manager()
        status = manager.get_batch_status(batch_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        return BatchStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batches", response_model=List[BatchStatusResponse])
async def list_batches(
    status: Optional[str] = Query(None, description="Filter by batch status"),
    batch_type: Optional[str] = Query(None, description="Filter by batch type"),
    limit: int = Query(50, description="Maximum number of batches to return"),
    offset: int = Query(0, description="Number of batches to skip")
):
    """List processing batches with optional filtering"""
    try:
        import psycopg2
        
        db_config = get_db_config()
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("status = %s")
            params.append(status)
        
        if batch_type:
            where_conditions.append("batch_type = %s")
            params.append(batch_type)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        query = f"""
            SELECT 
                batch_id, batch_type, total_articles, processed_articles, failed_articles,
                status, priority, created_at, started_at, completed_at, error_message, metadata
            FROM article_processing_batches
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        
        params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        batches = []
        for row in rows:
            batches.append(BatchStatusResponse(
                batch_id=row[0],
                batch_type=row[1],
                total_articles=row[2],
                processed_articles=row[3],
                failed_articles=row[4],
                status=row[5],
                priority=row[6],
                created_at=row[7].isoformat() if row[7] else None,
                started_at=row[8].isoformat() if row[8] else None,
                completed_at=row[9].isoformat() if row[9] else None,
                error_message=row[10],
                progress_percentage=(row[3] + row[4]) / row[2] * 100 if row[2] > 0 else 0
            ))
        
        return batches
        
    except Exception as e:
        logger.error(f"Error listing batches: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup/run", response_model=Dict[str, Any])
async def run_cleanup_policies():
    """Run storage cleanup policies"""
    try:
        manager = get_scaling_manager()
        results = manager.run_cleanup_policies()
        
        return {
            "success": True,
            "cleanup_results": results,
            "message": "Cleanup policies executed"
        }
        
    except Exception as e:
        logger.error(f"Error running cleanup policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rate-limit/check")
async def check_rate_limit(
    resource_type: str = Query(..., description="Type of resource to check"),
    resource_key: str = Query(..., description="Resource identifier")
):
    """Check if a request is within rate limits"""
    try:
        manager = get_scaling_manager()
        allowed = manager.check_rate_limit(resource_type, resource_key)
        
        return {
            "allowed": allowed,
            "resource_type": resource_type,
            "resource_key": resource_key
        }
        
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=Dict[str, Any])
async def get_scaling_health():
    """Get scaling system health status"""
    try:
        manager = get_scaling_manager()
        metrics = manager.get_scaling_metrics()
        storage = manager.get_storage_usage()
        
        # Determine health status
        health_status = "healthy"
        warnings = []
        
        # Check database size
        db_size_gb = metrics.database_size_bytes / (1024**3)
        if db_size_gb > 10:
            health_status = "warning"
            warnings.append(f"Large database size: {db_size_gb:.2f}GB")
        
        # Check processing backlog
        if metrics.raw_articles > 1000:
            health_status = "warning"
            warnings.append(f"Large processing backlog: {metrics.raw_articles} articles")
        
        # Check success rate
        if metrics.success_rate < 80 and metrics.success_rate > 0:
            health_status = "warning"
            warnings.append(f"Low success rate: {metrics.success_rate:.1f}%")
        
        return {
            "status": health_status,
            "warnings": warnings,
            "metrics": {
                "total_articles": metrics.total_articles,
                "raw_articles": metrics.raw_articles,
                "database_size_gb": db_size_gb,
                "success_rate": metrics.success_rate
            },
            "storage": storage,
            "timestamp": metrics.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting scaling health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk-process", response_model=Dict[str, Any])
async def bulk_process_articles(
    article_ids: List[int] = Query(..., description="List of article IDs to process"),
    batch_size: int = Query(100, description="Size of each batch"),
    priority: int = Query(2, description="Processing priority")
):
    """Process a large number of articles by automatically creating and managing batches"""
    try:
        if len(article_ids) == 0:
            raise HTTPException(status_code=400, detail="No articles provided")
        
        if len(article_ids) > 10000:
            raise HTTPException(status_code=400, detail="Too many articles. Maximum 10,000 per request.")
        
        manager = get_scaling_manager()
        
        # Split into batches
        batches = []
        for i in range(0, len(article_ids), batch_size):
            batch_article_ids = article_ids[i:i + batch_size]
            batch_id = manager.create_processing_batch(
                article_ids=batch_article_ids,
                batch_type="bulk_process",
                priority=priority
            )
            batches.append(batch_id)
        
        return {
            "success": True,
            "total_articles": len(article_ids),
            "batch_count": len(batches),
            "batch_ids": batches,
            "message": f"Created {len(batches)} batches for {len(article_ids)} articles"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
