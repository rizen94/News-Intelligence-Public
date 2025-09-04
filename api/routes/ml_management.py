"""
ML Service Management API Routes for News Intelligence System v3.0
Provides ML pipeline management, model status, and processing capabilities
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from config.database import get_db_connection

router = APIRouter()

# Enums
class MLServiceStatus(str, Enum):
    """ML service status"""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    LOADING = "loading"

class ProcessingStatus(str, Enum):
    """Processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Pydantic models
class MLModelInfo(BaseModel):
    """ML model information"""
    name: str = Field(..., description="Model name")
    version: str = Field(..., description="Model version")
    status: MLServiceStatus = Field(..., description="Model status")
    last_updated: datetime = Field(..., description="Last update timestamp")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")

class MLPipelineStatus(BaseModel):
    """ML pipeline status"""
    status: MLServiceStatus = Field(..., description="Overall pipeline status")
    queue_size: int = Field(..., description="Processing queue size")
    processing_rate: float = Field(..., description="Processing rate (articles/hour)")
    models_status: Dict[str, MLModelInfo] = Field(..., description="Individual model status")
    last_processed: Optional[datetime] = Field(None, description="Last processing timestamp")
    total_processed: int = Field(0, description="Total articles processed")
    success_rate: float = Field(0.0, description="Success rate percentage")

class ProcessingJob(BaseModel):
    """Processing job model"""
    id: int = Field(..., description="Job ID")
    article_id: int = Field(..., description="Article ID")
    job_type: str = Field(..., description="Job type")
    status: ProcessingStatus = Field(..., description="Job status")
    created_at: datetime = Field(..., description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")

class ProcessingRequest(BaseModel):
    """Processing request model"""
    article_ids: List[int] = Field(..., description="Article IDs to process")
    job_type: str = Field("full_processing", description="Type of processing")
    priority: int = Field(1, ge=1, le=5, description="Processing priority")

class MLStats(BaseModel):
    """ML statistics model"""
    total_processed: int = Field(..., description="Total articles processed")
    processing_rate: float = Field(..., description="Current processing rate")
    success_rate: float = Field(..., description="Success rate")
    avg_processing_time: float = Field(..., description="Average processing time")
    queue_size: int = Field(..., description="Current queue size")
    model_performance: Dict[str, Dict[str, Any]] = Field(..., description="Model performance metrics")
    recent_jobs: List[Dict[str, Any]] = Field(..., description="Recent processing jobs")

# API Endpoints

@router.get("/status", response_model=MLPipelineStatus)
async def get_ml_status():
    """Get ML pipeline status and model information"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get processing queue size
        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'pending'")
        queue_size = cursor.fetchone()[0]
        
        # Get processing rate (articles processed in last hour)
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE ml_processed_at >= %s AND status = 'processed'
        """, (datetime.utcnow() - timedelta(hours=1),))
        recent_processed = cursor.fetchone()[0]
        
        # Get last processed timestamp
        cursor.execute("""
            SELECT MAX(ml_processed_at) FROM articles 
            WHERE ml_processed_at IS NOT NULL
        """)
        last_processed = cursor.fetchone()[0]
        
        # Get total processed
        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'processed'")
        total_processed = cursor.fetchone()[0]
        
        # Get success rate
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as successful
            FROM articles 
            WHERE created_at >= %s
        """, (datetime.utcnow() - timedelta(days=7),))
        
        row = cursor.fetchone()
        success_rate = (row[1] / row[0] * 100) if row[0] > 0 else 0.0
        
        # Mock model status (in production, this would check actual ML services)
        models_status = {
            "summarization": MLModelInfo(
                name="Article Summarizer",
                version="1.2.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "accuracy": 0.92,
                    "speed": "2.3s/article",
                    "memory_usage": "1.2GB"
                }
            ),
            "entity_extraction": MLModelInfo(
                name="Entity Extractor",
                version="2.1.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "precision": 0.89,
                    "recall": 0.91,
                    "f1_score": 0.90
                }
            ),
            "sentiment_analysis": MLModelInfo(
                name="Sentiment Analyzer",
                version="1.5.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "accuracy": 0.87,
                    "confidence": 0.85
                }
            ),
            "clustering": MLModelInfo(
                name="Content Clusterer",
                version="1.0.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "silhouette_score": 0.75,
                    "clusters_created": 45
                }
            )
        }
        
        # Determine overall status
        overall_status = MLServiceStatus.ONLINE
        if queue_size > 100:
            overall_status = MLServiceStatus.LOADING
        elif success_rate < 80:
            overall_status = MLServiceStatus.ERROR
        
        cursor.close()
        conn.close()
        
        return MLPipelineStatus(
            status=overall_status,
            queue_size=queue_size,
            processing_rate=float(recent_processed),
            models_status=models_status,
            last_processed=last_processed,
            total_processed=total_processed,
            success_rate=success_rate
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ML status: {str(e)}"
        )

@router.post("/process")
async def trigger_ml_processing(processing_request: ProcessingRequest):
    """Trigger ML processing for articles"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Validate article IDs
        placeholders = ','.join(['%s'] * len(processing_request.article_ids))
        cursor.execute(f"""
            SELECT id FROM articles 
            WHERE id IN ({placeholders}) AND status IN ('pending', 'processing')
        """, processing_request.article_ids)
        
        valid_article_ids = [row[0] for row in cursor.fetchall()]
        
        if not valid_article_ids:
            raise HTTPException(status_code=400, detail="No valid articles found for processing")
        
        # Create processing jobs
        job_ids = []
        for article_id in valid_article_ids:
            cursor.execute("""
                INSERT INTO ml_processing_jobs (
                    article_id, job_type, status, priority, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                article_id,
                processing_request.job_type,
                ProcessingStatus.PENDING.value,
                processing_request.priority,
                datetime.utcnow()
            ))
            job_ids.append(cursor.fetchone()[0])
        
        # Update article status
        cursor.execute(f"""
            UPDATE articles 
            SET status = 'processing', updated_at = %s
            WHERE id IN ({placeholders})
        """, [datetime.utcnow()] + valid_article_ids)
        
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # In production, this would trigger the actual ML processing
        return {
            "message": f"ML processing triggered for {len(valid_article_ids)} articles",
            "job_ids": job_ids,
            "articles_queued": len(valid_article_ids),
            "status": "queued"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger ML processing: {str(e)}"
        )

@router.get("/jobs", response_model=List[ProcessingJob])
async def get_processing_jobs(
    status: Optional[ProcessingStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Number of jobs to return")
):
    """Get ML processing jobs"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        where_clause = ""
        params = []
        
        if status:
            where_clause = "WHERE status = %s"
            params.append(status.value)
        
        cursor.execute(f"""
            SELECT 
                id, article_id, job_type, status, created_at,
                started_at, completed_at, error_message, processing_time
            FROM ml_processing_jobs 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """, params + [limit])
        
        jobs = []
        for row in cursor.fetchall():
            job = ProcessingJob(
                id=row[0],
                article_id=row[1],
                job_type=row[2],
                status=row[3],
                created_at=row[4],
                started_at=row[5],
                completed_at=row[6],
                error_message=row[7],
                processing_time=row[8]
            )
            jobs.append(job)
        
        cursor.close()
        conn.close()
        
        return jobs
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch processing jobs: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=ProcessingJob)
async def get_processing_job(job_id: int = Path(..., description="Job ID")):
    """Get specific processing job"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, article_id, job_type, status, created_at,
                started_at, completed_at, error_message, processing_time
            FROM ml_processing_jobs 
            WHERE id = %s
        """, (job_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Processing job not found")
        
        job = ProcessingJob(
            id=row[0],
            article_id=row[1],
            job_type=row[2],
            status=row[3],
            created_at=row[4],
            started_at=row[5],
            completed_at=row[6],
            error_message=row[7],
            processing_time=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch processing job: {str(e)}"
        )

@router.get("/models", response_model=Dict[str, MLModelInfo])
async def get_ml_models():
    """Get available ML models and their status"""
    try:
        # In production, this would query actual ML service status
        models = {
            "summarization": MLModelInfo(
                name="Article Summarizer",
                version="1.2.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "accuracy": 0.92,
                    "speed": "2.3s/article",
                    "memory_usage": "1.2GB",
                    "articles_processed": 15420
                }
            ),
            "entity_extraction": MLModelInfo(
                name="Entity Extractor",
                version="2.1.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "precision": 0.89,
                    "recall": 0.91,
                    "f1_score": 0.90,
                    "entities_extracted": 89234
                }
            ),
            "sentiment_analysis": MLModelInfo(
                name="Sentiment Analyzer",
                version="1.5.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "accuracy": 0.87,
                    "confidence": 0.85,
                    "articles_analyzed": 12890
                }
            ),
            "clustering": MLModelInfo(
                name="Content Clusterer",
                version="1.0.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "silhouette_score": 0.75,
                    "clusters_created": 45,
                    "articles_clustered": 5670
                }
            ),
            "deduplication": MLModelInfo(
                name="Duplicate Detector",
                version="1.3.0",
                status=MLServiceStatus.ONLINE,
                last_updated=datetime.utcnow(),
                performance_metrics={
                    "precision": 0.94,
                    "recall": 0.91,
                    "duplicates_found": 1234
                }
            )
        }
        
        return models
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ML models: {str(e)}"
        )

@router.post("/retrain")
async def retrain_models(
    model_names: List[str] = Body(..., description="Models to retrain"),
    force: bool = Body(False, description="Force retrain even if recent")
):
    """Trigger model retraining"""
    try:
        # In production, this would trigger actual model retraining
        retrain_results = {}
        
        for model_name in model_names:
            retrain_results[model_name] = {
                "status": "queued",
                "estimated_time": "2-4 hours",
                "message": f"Retraining queued for {model_name}"
            }
        
        return {
            "message": f"Model retraining triggered for {len(model_names)} models",
            "results": retrain_results,
            "status": "queued"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger model retraining: {str(e)}"
        )

@router.get("/performance", response_model=MLStats)
async def get_ml_performance():
    """Get ML performance metrics and statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get total processed
        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'processed'")
        total_processed = cursor.fetchone()[0]
        
        # Get processing rate (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE ml_processed_at >= %s AND status = 'processed'
        """, (datetime.utcnow() - timedelta(hours=24),))
        recent_processed = cursor.fetchone()[0]
        
        # Get success rate
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as successful
            FROM articles 
            WHERE created_at >= %s
        """, (datetime.utcnow() - timedelta(days=7),))
        
        row = cursor.fetchone()
        success_rate = (row[1] / row[0] * 100) if row[0] > 0 else 0.0
        
        # Get average processing time
        cursor.execute("""
            SELECT AVG(processing_time) FROM ml_processing_jobs 
            WHERE processing_time IS NOT NULL AND completed_at >= %s
        """, (datetime.utcnow() - timedelta(days=7),))
        avg_processing_time = float(cursor.fetchone()[0] or 0)
        
        # Get queue size
        cursor.execute("SELECT COUNT(*) FROM articles WHERE status = 'pending'")
        queue_size = cursor.fetchone()[0]
        
        # Get recent jobs
        cursor.execute("""
            SELECT 
                j.id, j.article_id, j.job_type, j.status, j.created_at,
                a.title
            FROM ml_processing_jobs j
            JOIN articles a ON j.article_id = a.id
            ORDER BY j.created_at DESC
            LIMIT 10
        """)
        
        recent_jobs = [
            {
                "id": row[0],
                "article_id": row[1],
                "job_type": row[2],
                "status": row[3],
                "created_at": row[4],
                "article_title": row[5]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        # Mock model performance (in production, this would be real metrics)
        model_performance = {
            "summarization": {
                "accuracy": 0.92,
                "throughput": 156.7,
                "latency": 2.3,
                "memory_usage": 1.2
            },
            "entity_extraction": {
                "precision": 0.89,
                "recall": 0.91,
                "f1_score": 0.90,
                "throughput": 203.4
            },
            "sentiment_analysis": {
                "accuracy": 0.87,
                "confidence": 0.85,
                "throughput": 189.2,
                "latency": 1.8
            }
        }
        
        return MLStats(
            total_processed=total_processed,
            processing_rate=float(recent_processed),
            success_rate=success_rate,
            avg_processing_time=avg_processing_time,
            queue_size=queue_size,
            model_performance=model_performance,
            recent_jobs=recent_jobs
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ML performance: {str(e)}"
        )
