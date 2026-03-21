"""
LLM Activity Monitoring Routes
Provides real-time visibility into LLM usage and current processing
"""

import logging
from datetime import datetime

from domains.content_analysis.services.llm_activity_tracker import get_llm_activity_tracker
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api", tags=["LLM Activity Monitoring"], responses={404: {"description": "Not found"}}
)


@router.get("/content_analysis/llm/activity")
async def get_llm_activity(
    include_history: bool = Query(False, description="Include recent task history"),
    history_limit: int = Query(20, ge=1, le=100, description="Number of recent tasks to include"),
):
    """
    Get real-time LLM activity and current processing status

    Returns:
    - Active tasks currently being processed
    - Overall statistics
    - LLM availability status
    - Recent task history (optional)
    """
    try:
        tracker = get_llm_activity_tracker()
        stats = tracker.get_stats()

        response = {
            "success": True,
            "llm_status": {
                "available": stats["llm_available"],
                "last_check": stats["last_llm_check"].isoformat()
                if stats["last_llm_check"]
                else None,
                "last_activity": stats["last_activity"].isoformat()
                if stats["last_activity"]
                else None,
            },
            "current_processing": {
                "active_tasks": len(stats["active_tasks"]),
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "task_type": task["task_type"],
                        "article_id": task.get("article_id"),
                        "domain": task.get("domain"),
                        "status": task["status"],
                        "started_at": task["started_at"].isoformat(),
                        "duration_seconds": task.get("duration", 0),
                        "metadata": task.get("metadata", {}),
                    }
                    for task in stats["active_tasks"]
                ],
            },
            "statistics": {
                "total_tasks": stats["total_tasks"],
                "completed_tasks": stats["completed_tasks"],
                "failed_tasks": stats["failed_tasks"],
                "success_rate": (
                    stats["completed_tasks"] / stats["total_tasks"]
                    if stats["total_tasks"] > 0
                    else 0.0
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

        if include_history:
            history = tracker.get_recent_history(limit=history_limit)
            response["recent_history"] = [
                {
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "article_id": task.get("article_id"),
                    "domain": task.get("domain"),
                    "status": task.get("status", "completed"),
                    "success": task.get("success", True),
                    "started_at": task["started_at"].isoformat(),
                    "completed_at": task.get("completed_at").isoformat()
                    if task.get("completed_at")
                    else None,
                    "duration_seconds": task.get("duration", 0),
                    "error": task.get("error"),
                }
                for task in history
            ]

        return response

    except Exception as e:
        logger.error(f"Error getting LLM activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content_analysis/llm/status")
async def get_llm_status():
    """
    Quick status check for LLM availability and current activity
    """
    try:
        tracker = get_llm_activity_tracker()
        stats = tracker.get_stats()
        active_tasks = tracker.get_active_tasks()

        return {
            "success": True,
            "llm_available": stats["llm_available"],
            "active_tasks": len(active_tasks),
            "last_activity": stats["last_activity"].isoformat() if stats["last_activity"] else None,
            "current_tasks": [
                {
                    "type": task["task_type"],
                    "article_id": task.get("article_id"),
                    "domain": task.get("domain"),
                    "duration_seconds": task.get("duration", 0),
                }
                for task in active_tasks[:5]  # Show top 5
            ],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting LLM status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/llm/activity")
async def get_domain_llm_activity(
    domain: str,
    include_history: bool = Query(False, description="Include recent task history"),
    history_limit: int = Query(20, ge=1, le=100, description="Number of recent tasks to include"),
):
    """
    Get LLM activity for a specific domain
    """
    try:
        from shared.services.domain_aware_service import validate_domain

        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        tracker = get_llm_activity_tracker()
        stats = tracker.get_stats()

        # Filter active tasks by domain
        domain_schema = domain.replace("-", "_")
        domain_tasks = [
            task for task in stats["active_tasks"] if task.get("domain") == domain_schema
        ]

        response = {
            "success": True,
            "domain": domain,
            "llm_status": {
                "available": stats["llm_available"],
                "last_check": stats["last_llm_check"].isoformat()
                if stats["last_llm_check"]
                else None,
            },
            "current_processing": {
                "active_tasks": len(domain_tasks),
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "task_type": task["task_type"],
                        "article_id": task.get("article_id"),
                        "status": task["status"],
                        "started_at": task["started_at"].isoformat(),
                        "duration_seconds": task.get("duration", 0),
                        "metadata": task.get("metadata", {}),
                    }
                    for task in domain_tasks
                ],
            },
            "timestamp": datetime.now().isoformat(),
        }

        if include_history:
            history = tracker.get_recent_history(limit=history_limit)
            domain_history = [task for task in history if task.get("domain") == domain_schema]
            response["recent_history"] = [
                {
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "article_id": task.get("article_id"),
                    "status": task.get("status", "completed"),
                    "success": task.get("success", True),
                    "started_at": task["started_at"].isoformat(),
                    "completed_at": task.get("completed_at").isoformat()
                    if task.get("completed_at")
                    else None,
                    "duration_seconds": task.get("duration", 0),
                    "error": task.get("error"),
                }
                for task in domain_history
            ]

        return response

    except Exception as e:
        logger.error(f"Error getting domain LLM activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content_analysis/llm/dashboard")
async def get_llm_dashboard():
    """
    Comprehensive LLM dashboard showing all activity, queue status, and system health
    """
    try:
        tracker = get_llm_activity_tracker()
        stats = tracker.get_stats()
        active_tasks = tracker.get_active_tasks()

        # Get queue status for all domains
        from shared.database.connection import get_db_connection

        queue_stats = {}
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    for schema in ["politics", "finance", "science_tech"]:
                        try:
                            cur.execute(f"""
                                SELECT
                                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                                FROM {schema}.topic_extraction_queue
                            """)
                            row = cur.fetchone()
                            if row:
                                queue_stats[schema] = {
                                    "pending": row[0] or 0,
                                    "processing": row[1] or 0,
                                    "completed": row[2] or 0,
                                    "failed": row[3] or 0,
                                }
                        except Exception:
                            # Table might not exist
                            queue_stats[schema] = {
                                "pending": 0,
                                "processing": 0,
                                "completed": 0,
                                "failed": 0,
                            }
            finally:
                conn.close()

        return {
            "success": True,
            "llm_status": {
                "available": stats["llm_available"],
                "last_check": stats["last_llm_check"].isoformat()
                if stats["last_llm_check"]
                else None,
                "last_activity": stats["last_activity"].isoformat()
                if stats["last_activity"]
                else None,
                "is_active": len(active_tasks) > 0,
            },
            "current_processing": {
                "active_tasks_count": len(active_tasks),
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "task_type": task["task_type"],
                        "article_id": task.get("article_id"),
                        "domain": task.get("domain"),
                        "started_at": task["started_at"].isoformat(),
                        "duration_seconds": round(task.get("duration", 0), 2),
                        "metadata": task.get("metadata", {}),
                    }
                    for task in active_tasks
                ],
            },
            "statistics": {
                "total_tasks": stats["total_tasks"],
                "completed_tasks": stats["completed_tasks"],
                "failed_tasks": stats["failed_tasks"],
                "success_rate": round(
                    stats["completed_tasks"] / stats["total_tasks"]
                    if stats["total_tasks"] > 0
                    else 0.0,
                    3,
                ),
            },
            "queue_status": queue_stats,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting LLM dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))
