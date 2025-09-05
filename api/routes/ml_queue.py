#!/usr/bin/env python3
"""
ML Queue Management API Routes
Provides endpoints for managing ML task queue and monitoring
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from modules.ml.ml_queue_manager import MLQueueManager, MLTask, TaskType, TaskPriority, TaskStatus
from config.database import get_db_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ml-queue"])

# Global ML Queue Manager instance
ml_queue_manager: Optional[MLQueueManager] = None

def get_ml_queue_manager() -> MLQueueManager:
    """Get or create ML queue manager instance"""
    global ml_queue_manager
    if ml_queue_manager is None:
        db_config = get_db_config()
        ml_queue_manager = MLQueueManager(db_config)
        ml_queue_manager.start()
    return ml_queue_manager

# Pydantic models
class TaskSubmissionRequest(BaseModel):
    """Request model for submitting ML tasks"""
    task_type: str = Field(..., description="Type of ML task")
    priority: int = Field(default=2, description="Task priority (1-4)")
    storyline_id: Optional[str] = Field(None, description="Storyline ID if applicable")
    article_id: Optional[int] = Field(None, description="Article ID if applicable")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task payload")
    estimated_duration: int = Field(default=30, description="Estimated duration in seconds")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")

class TaskResponse(BaseModel):
    """Response model for ML tasks"""
    task_id: str
    task_type: str
    priority: int
    storyline_id: Optional[str]
    article_id: Optional[int]
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int

class QueueStatusResponse(BaseModel):
    """Response model for queue status"""
    is_running: bool
    queue_size: int
    running_tasks: int
    completed_tasks: int
    max_concurrent: int
    resource_usage: Dict[str, float]
    task_types: Dict[str, int]

@router.post("/submit", response_model=Dict[str, str])
async def submit_task(request: TaskSubmissionRequest):
    """Submit a new ML task to the queue"""
    try:
        # Validate task type
        try:
            task_type = TaskType(request.task_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid task type: {request.task_type}")
        
        # Validate priority
        if not 1 <= request.priority <= 4:
            raise HTTPException(status_code=400, detail="Priority must be between 1 and 4")
        
        # Create task
        task = MLTask(
            task_id=f"{task_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(request.payload)) % 10000}",
            task_type=task_type,
            priority=TaskPriority(request.priority),
            storyline_id=request.storyline_id,
            article_id=request.article_id,
            payload=request.payload,
            estimated_duration=request.estimated_duration,
            resource_requirements=request.resource_requirements
        )
        
        # Submit task
        queue_manager = get_ml_queue_manager()
        task_id = queue_manager.submit_task(task)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Task submitted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """Get the status of a specific task"""
    try:
        queue_manager = get_ml_queue_manager()
        task = queue_manager.get_task_status(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(
            task_id=task.task_id,
            task_type=task.task_type.value,
            priority=task.priority.value,
            storyline_id=task.storyline_id,
            article_id=task.article_id,
            status=task.status.value,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            result=task.result,
            error=task.error,
            retry_count=task.retry_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status():
    """Get current queue status and statistics"""
    try:
        queue_manager = get_ml_queue_manager()
        status = queue_manager.get_queue_status()
        
        return QueueStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/start")
async def start_queue():
    """Start the ML queue manager"""
    try:
        queue_manager = get_ml_queue_manager()
        queue_manager.start()
        
        return {
            "success": True,
            "message": "ML queue manager started"
        }
        
    except Exception as e:
        logger.error(f"Error starting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/stop")
async def stop_queue():
    """Stop the ML queue manager"""
    try:
        queue_manager = get_ml_queue_manager()
        queue_manager.stop()
        
        return {
            "success": True,
            "message": "ML queue manager stopped"
        }
        
    except Exception as e:
        logger.error(f"Error stopping queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or running task"""
    try:
        queue_manager = get_ml_queue_manager()
        success = queue_manager.cancel_task(task_id)
        
        if success:
            return {
                "success": True,
                "message": f"Task {task_id} cancelled"
            }
        else:
            raise HTTPException(status_code=404, detail="Task not found or could not be cancelled")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by task status"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    limit: int = Query(50, description="Maximum number of tasks to return"),
    offset: int = Query(0, description="Number of tasks to skip")
):
    """List tasks with optional filtering"""
    try:
        # This would need to be implemented in the MLQueueManager
        # For now, return a placeholder response
        return []
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/timeline/generate")
async def generate_timeline_task(
    storyline_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_events: int = 50,
    priority: int = 2
):
    """Submit a timeline generation task"""
    try:
        # Get storyline data
        from routes.storyline_timeline import _get_storyline_data
        storyline_data = await _get_storyline_data(storyline_id)
        
        if not storyline_data:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        # Create task submission request
        request = TaskSubmissionRequest(
            task_type="timeline_generation",
            priority=priority,
            storyline_id=storyline_id,
            payload={
                "storyline_data": storyline_data,
                "start_date": start_date,
                "end_date": end_date,
                "max_events": max_events
            },
            estimated_duration=60,  # 1 minute for timeline generation
            resource_requirements={
                "max_cpu_usage": 70.0,
                "max_memory_usage": 80.0,
                "max_gpu_usage": 60.0
            }
        )
        
        # Submit task
        result = await submit_task(request)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting timeline generation task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
