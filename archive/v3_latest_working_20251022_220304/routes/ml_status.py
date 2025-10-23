"""
News Intelligence System v3.0 - ML Processing Status API
Handles ML processing status, queue position, and timing information
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from config.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class MLStatusResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class MLQueueItem(BaseModel):
    storyline_id: str
    title: str
    status: str
    queue_position: int
    article_count: int
    last_article_added: Optional[datetime]
    created_at: datetime

class MLProcessingStatus(BaseModel):
    storyline_id: str
    status: str
    queue_position: int
    last_processed: Optional[datetime]
    processing_duration: Optional[int]
    next_estimate: Optional[datetime]
    attempts: int
    last_error: Optional[str]
    article_count: int

@router.get("/status/", response_model=MLStatusResponse)
async def get_ml_system_status():
    """Get overall ML system status and statistics"""
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Get ML processing statistics
            stats_query = text("""
                SELECT 
                    COUNT(*) as total_storylines,
                    COUNT(CASE WHEN ml_processing_status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN ml_processing_status = 'queued' THEN 1 END) as queued_count,
                    COUNT(CASE WHEN ml_processing_status = 'processing' THEN 1 END) as processing_count,
                    COUNT(CASE WHEN ml_processing_status = 'completed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN ml_processing_status = 'failed' THEN 1 END) as failed_count,
                    AVG(ml_processing_duration) as avg_processing_duration,
                    MAX(ml_last_processed) as last_system_processing
                FROM storylines
            """)
            
            stats_result = db.execute(stats_query).fetchone()
            
            # Get queue information
            queue_query = text("""
                SELECT * FROM get_ml_processing_queue()
                ORDER BY ml_queue_position ASC
                LIMIT 10
            """)
            
            queue_results = db.execute(queue_query).fetchall()
            queue_items = [
                {
                    "storyline_id": row.storyline_id,
                    "title": row.title,
                    "status": row.ml_processing_status,
                    "queue_position": row.ml_queue_position,
                    "article_count": row.article_count,
                    "last_article_added": row.last_article_added,
                    "created_at": row.created_at
                }
                for row in queue_results
            ]
            
            # Get next processing estimate
            estimate_query = text("SELECT estimate_next_ml_processing()")
            next_estimate = db.execute(estimate_query).fetchone()[0]
            
            return MLStatusResponse(
                success=True,
                message="ML system status retrieved successfully",
                data={
                    "statistics": {
                        "total_storylines": stats_result.total_storylines,
                        "pending": stats_result.pending_count,
                        "queued": stats_result.queued_count,
                        "processing": stats_result.processing_count,
                        "completed": stats_result.completed_count,
                        "failed": stats_result.failed_count,
                        "avg_processing_duration": float(stats_result.avg_processing_duration) if stats_result.avg_processing_duration else None,
                        "last_system_processing": stats_result.last_system_processing
                    },
                    "queue": queue_items,
                    "next_processing_estimate": next_estimate,
                    "timestamp": datetime.now()
                }
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting ML system status: {e}")
        return MLStatusResponse(
            success=False,
            message="Failed to retrieve ML system status",
            error=str(e)
        )

@router.get("/storyline/{storyline_id}/status/", response_model=MLStatusResponse)
async def get_storyline_ml_status(storyline_id: str):
    """Get ML processing status for a specific storyline"""
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Get storyline ML status
            status_query = text("""
                SELECT 
                    id, title, ml_processing_status, ml_queue_position,
                    ml_last_processed, ml_processing_duration, ml_next_processing_estimate,
                    ml_processing_attempts, ml_last_error, article_count
                FROM storylines
                WHERE id = :storyline_id
            """)
            
            result = db.execute(status_query, {"storyline_id": storyline_id}).fetchone()
            
            if not result:
                return MLStatusResponse(
                    success=False,
                    message="Storyline not found",
                    error="Storyline not found"
                )
            
            # Calculate time since last processing
            time_since_last = None
            if result.ml_last_processed:
                time_since_last = (datetime.now() - result.ml_last_processed).total_seconds()
            
            # Calculate estimated wait time
            estimated_wait = None
            if result.ml_processing_status in ['pending', 'queued'] and result.ml_queue_position > 0:
                # Get average processing duration
                avg_duration_query = text("""
                    SELECT AVG(ml_processing_duration) 
                    FROM storylines 
                    WHERE ml_processing_duration IS NOT NULL
                """)
                avg_duration = db.execute(avg_duration_query).fetchone()[0]
                if avg_duration:
                    estimated_wait = int(avg_duration * result.ml_queue_position)
            
            return MLStatusResponse(
                success=True,
                message="Storyline ML status retrieved successfully",
                data={
                    "storyline_id": result.id,
                    "title": result.title,
                    "status": result.ml_processing_status,
                    "queue_position": result.ml_queue_position,
                    "last_processed": result.ml_last_processed,
                    "processing_duration": result.ml_processing_duration,
                    "next_estimate": result.ml_next_processing_estimate,
                    "attempts": result.ml_processing_attempts,
                    "last_error": result.ml_last_error,
                    "article_count": result.article_count,
                    "time_since_last_processing": time_since_last,
                    "estimated_wait_seconds": estimated_wait,
                    "timestamp": datetime.now()
                }
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting storyline ML status: {e}")
        return MLStatusResponse(
            success=False,
            message="Failed to retrieve storyline ML status",
            error=str(e)
        )

@router.post("/queue/update/", response_model=MLStatusResponse)
async def update_ml_queue():
    """Update ML processing queue positions"""
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Update queue positions
            update_query = text("SELECT update_ml_queue_positions()")
            updated_count = db.execute(update_query).fetchone()[0]
            db.commit()
            
            return MLStatusResponse(
                success=True,
                message=f"ML queue updated successfully",
                data={
                    "updated_storylines": updated_count,
                    "timestamp": datetime.now()
                }
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error updating ML queue: {e}")
        return MLStatusResponse(
            success=False,
            message="Failed to update ML queue",
            error=str(e)
        )

@router.get("/queue/", response_model=MLStatusResponse)
async def get_ml_queue():
    """Get current ML processing queue"""
    try:
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Get queue
            queue_query = text("SELECT * FROM get_ml_processing_queue()")
            queue_results = db.execute(queue_query).fetchall()
            
            queue_items = [
                {
                    "storyline_id": row.storyline_id,
                    "title": row.title,
                    "status": row.ml_processing_status,
                    "queue_position": row.ml_queue_position,
                    "article_count": row.article_count,
                    "last_article_added": row.last_article_added,
                    "created_at": row.created_at
                }
                for row in queue_results
            ]
            
            return MLStatusResponse(
                success=True,
                message="ML queue retrieved successfully",
                data={
                    "queue": queue_items,
                    "queue_size": len(queue_items),
                    "timestamp": datetime.now()
                }
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting ML queue: {e}")
        return MLStatusResponse(
            success=False,
            message="Failed to retrieve ML queue",
            error=str(e)
        )

@router.get("/health/")
async def health_check():
    """Health check for ML status API"""
    return {
        "status": "healthy",
        "service": "ml_status",
        "message": "ML Status API is running"
    }
