"""
ML API Routes for News Intelligence System v3.0
Provides ML pipeline management and AI services
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
class MLStatus(str, Enum):
    """ML processing status"""
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    COMPLETED = "completed"

# Pydantic models
class MLPipelineStatus(BaseModel):
    """ML pipeline status model"""
    status: str = Field(..., description="Pipeline status")
    queue_size: int = Field(..., description="Queue size")
    processing_rate: float = Field(..., description="Processing rate")
    models_status: Dict[str, str] = Field(..., description="Models status")

class MLProcessingStatus(BaseModel):
    """ML processing status model"""
    status: MLStatus = Field(..., description="Processing status")
    queue_size: int = Field(0, description="Queue size")
    processing_rate: float = Field(0.0, description="Processing rate")
    last_processed: Optional[datetime] = Field(None, description="Last processed time")
    total_processed: int = Field(0, description="Total processed")

class MLQueueStatus(BaseModel):
    """ML queue status model"""
    queue_size: int = Field(..., description="Queue size")
    processing: int = Field(0, description="Currently processing")
    pending: int = Field(0, description="Pending articles")
    completed_today: int = Field(0, description="Completed today")
    avg_processing_time: float = Field(0.0, description="Average processing time")

class MLTimingStats(BaseModel):
    """ML timing statistics model"""
    avg_processing_time: float = Field(0.0, description="Average processing time")
    min_processing_time: float = Field(0.0, description="Minimum processing time")
    max_processing_time: float = Field(0.0, description="Maximum processing time")
    total_processing_time: float = Field(0.0, description="Total processing time")
    articles_processed: int = Field(0, description="Articles processed")

# API Endpoints

@router.get("/status", response_model=MLPipelineStatus)
async def get_ml_pipeline_status():
    """Get ML pipeline status"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get processing queue size
        cursor.execute("SELECT COUNT(*) FROM articles WHERE processing_status = 'raw'")
        queue_size = cursor.fetchone()[0]
        
        # Get processing rate (articles processed in last hour)
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE processing_completed_at >= %s AND processing_status = 'processed'
        """, (datetime.utcnow() - timedelta(hours=1),))
        recent_processed = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return MLPipelineStatus(
            status="active" if queue_size > 0 else "idle",
            queue_size=queue_size,
            processing_rate=float(recent_processed),
            models_status={"llama": "ready", "rag": "ready", "summarization": "ready"}
        )
        
    except Exception as e:
        return MLPipelineStatus(
            status="error",
            queue_size=0,
            processing_rate=0.0,
            models_status={"error": str(e)}
        )

@router.get("/processing-status", response_model=MLProcessingStatus)
async def get_ml_processing_status():
    """Get detailed ML processing status"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get processing queue size
        cursor.execute("SELECT COUNT(*) FROM articles WHERE processing_status = 'raw'")
        queue_size = cursor.fetchone()[0]
        
        # Get processing rate (articles processed in last hour)
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE processing_completed_at >= %s AND processing_status = 'processed'
        """, (datetime.utcnow() - timedelta(hours=1),))
        recent_processed = cursor.fetchone()[0]
        
        # Get last processed timestamp
        cursor.execute("""
            SELECT MAX(processing_completed_at) FROM articles 
            WHERE processing_completed_at IS NOT NULL
        """)
        last_processed = cursor.fetchone()[0]
        
        # Get total processed
        cursor.execute("SELECT COUNT(*) FROM articles WHERE processing_status = 'processed'")
        total_processed = cursor.fetchone()[0]
        
        # Determine status
        status = MLStatus.IDLE
        if queue_size > 0:
            status = MLStatus.PROCESSING
        
        cursor.close()
        conn.close()
        
        return MLProcessingStatus(
            status=status,
            queue_size=queue_size,
            processing_rate=float(recent_processed),
            last_processed=last_processed,
            total_processed=total_processed
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ML processing status: {str(e)}"
        )

@router.get("/queue-status", response_model=MLQueueStatus)
async def get_ml_queue_status():
    """Get ML queue status"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get queue statistics
        cursor.execute("SELECT COUNT(*) FROM articles WHERE processing_status = 'raw'")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM articles WHERE processing_status = 'processing'")
        processing = cursor.fetchone()[0]
        
        # Get completed today
        cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE DATE(processing_completed_at) = %s AND processing_status = 'processed'
        """, (datetime.utcnow().date(),))
        completed_today = cursor.fetchone()[0]
        
        # Get average processing time
        cursor.execute("""
            SELECT AVG(EXTRACT(EPOCH FROM (processing_completed_at - created_at))) 
            FROM articles 
            WHERE processing_completed_at IS NOT NULL AND processing_status = 'processed'
        """)
        avg_processing_time = cursor.fetchone()[0] or 0
        
        cursor.close()
        conn.close()
        
        return MLQueueStatus(
            queue_size=pending + processing,
            processing=processing,
            pending=pending,
            completed_today=completed_today,
            avg_processing_time=float(avg_processing_time)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ML queue status: {str(e)}"
        )

@router.get("/timing-stats", response_model=MLTimingStats)
async def get_ml_timing_stats():
    """Get ML timing statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get timing statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as articles_processed,
                AVG(EXTRACT(EPOCH FROM (processing_completed_at - created_at))) as avg_time,
                MIN(EXTRACT(EPOCH FROM (processing_completed_at - created_at))) as min_time,
                MAX(EXTRACT(EPOCH FROM (processing_completed_at - created_at))) as max_time,
                SUM(EXTRACT(EPOCH FROM (processing_completed_at - created_at))) as total_time
            FROM articles 
            WHERE processing_completed_at IS NOT NULL AND processing_status = 'processed'
        """)
        
        row = cursor.fetchone()
        if row:
            articles_processed, avg_time, min_time, max_time, total_time = row
            
            return MLTimingStats(
                avg_processing_time=float(avg_time or 0),
                min_processing_time=float(min_time or 0),
                max_processing_time=float(max_time or 0),
                total_processing_time=float(total_time or 0),
                articles_processed=articles_processed or 0
            )
        else:
            return MLTimingStats()
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ML timing stats: {str(e)}"
        )

@router.post("/process")
async def trigger_ml_processing():
    """Trigger ML processing for pending articles"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get pending articles
        cursor.execute("SELECT id FROM articles WHERE processing_status = 'raw' LIMIT 10")
        pending_articles = [row[0] for row in cursor.fetchall()]
        
        if not pending_articles:
            return {"message": "No pending articles to process", "processed": 0}
        
        # Update articles to processing status
        cursor.execute("""
            UPDATE articles 
            SET status = 'processing', updated_at = %s
            WHERE id = ANY(%s)
        """, (datetime.utcnow(), pending_articles))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": f"ML processing triggered for {len(pending_articles)} articles",
            "processed": len(pending_articles),
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger ML processing: {str(e)}"
        )

@router.post("/process-all")
async def process_all_articles():
    """Process all pending articles"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get all pending articles
        cursor.execute("SELECT id FROM articles WHERE processing_status = 'raw'")
        pending_articles = [row[0] for row in cursor.fetchall()]
        
        if not pending_articles:
            return {"message": "No pending articles to process", "processed": 0}
        
        # Update articles to processing status
        cursor.execute("""
            UPDATE articles 
            SET status = 'processing', updated_at = %s
            WHERE id = ANY(%s)
        """, (datetime.utcnow(), pending_articles))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "message": f"ML processing triggered for {len(pending_articles)} articles",
            "processed": len(pending_articles),
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process all articles: {str(e)}"
        )

@router.get("/models")
async def get_ml_models():
    """Get available ML models"""
    try:
        # In production, this would query actual ML service status
        models = {
            "summarization": {
                "name": "Article Summarizer",
                "version": "1.2.0",
                "status": "active",
                "performance": {"accuracy": 0.92, "speed": "2.3s/article"}
            },
            "entity_extraction": {
                "name": "Entity Extractor", 
                "version": "2.1.0",
                "status": "active",
                "performance": {"precision": 0.89, "recall": 0.91}
            },
            "sentiment_analysis": {
                "name": "Sentiment Analyzer",
                "version": "1.5.0", 
                "status": "active",
                "performance": {"accuracy": 0.87, "confidence": 0.85}
            }
        }
        
        return {"models": models}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ML models: {str(e)}"
        )
