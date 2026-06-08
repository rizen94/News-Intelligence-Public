"""ML processing queue monitoring — aligns with web ML Processing / Monitor UI."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from shared.database.connection import (
    get_db_connection_context,
    get_ui_db_connection_context,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system_monitoring", tags=["System Monitoring"])


class MLQueueRequest(BaseModel):
    article_id: int = Field(..., ge=1)
    operation: str = Field(..., min_length=1, max_length=100)
    priority: str = Field("normal", max_length=32)
    model: str | None = None


def _priority_value(priority: str) -> int:
    mapping = {"low": 0, "normal": 5, "high": 10, "urgent": 20}
    return mapping.get((priority or "normal").lower(), 5)


@router.get("/ml/queue_status")
async def ml_queue_status() -> dict[str, Any]:
    """Queue aggregates from public.ml_processing_queue."""
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, operation_type, model_name,
                           COUNT(*) AS count,
                           AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - queued_at))) AS avg_wait
                    FROM public.ml_processing_queue
                    GROUP BY status, operation_type, model_name
                    ORDER BY status, operation_type
                    """
                )
                queue_stats = [
                    {
                        "status": row[0],
                        "operation_type": row[1],
                        "model_name": row[2],
                        "count": row[3],
                        "avg_wait_time_seconds": float(row[4]) if row[4] is not None else 0,
                    }
                    for row in cur.fetchall()
                ]
                cur.execute(
                    """
                    SELECT COUNT(*) FILTER (WHERE status = 'queued'),
                           COUNT(*) FILTER (WHERE status = 'processing'),
                           COUNT(*) FILTER (WHERE status = 'completed'),
                           COUNT(*) FILTER (WHERE status = 'failed')
                    FROM public.ml_processing_queue
                    """
                )
                q, p, c, f = cur.fetchone() or (0, 0, 0, 0)
        return {
            "success": True,
            "queue_status": {
                "queue_stats": queue_stats,
                "worker_stats": {
                    "is_running": (q or 0) > 0 or (p or 0) > 0,
                    "active_workers": int(p or 0),
                    "queue_size": int(q or 0),
                    "total_processed": int(c or 0) + int(f or 0),
                    "successful": int(c or 0),
                    "failed": int(f or 0),
                    "avg_processing_time": 0,
                },
            },
        }
    except Exception as e:
        logger.warning("ml_queue_status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ml/processing_status")
async def ml_processing_status(limit: int = 25) -> dict[str, Any]:
    """Recent ML queue rows for the processing activity table."""
    limit = max(1, min(limit, 100))
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT queue_id, article_id, operation_type, model_name,
                           status, queued_at, started_at, completed_at, error_message
                    FROM public.ml_processing_queue
                    ORDER BY queued_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                articles = [
                    {
                        "queue_id": row[0],
                        "article_id": row[1],
                        "operation_type": row[2],
                        "model_name": row[3],
                        "status": row[4],
                        "queued_at": row[5].isoformat() if row[5] else None,
                        "started_at": row[6].isoformat() if row[6] else None,
                        "completed_at": row[7].isoformat() if row[7] else None,
                        "error_message": row[8],
                    }
                    for row in cur.fetchall()
                ]
                cur.execute("SELECT COUNT(*) FROM public.ml_processing_queue")
                total = int(cur.fetchone()[0] or 0)
        return {"success": True, "status": {"articles": articles, "total_count": total}}
    except Exception as e:
        logger.warning("ml_processing_status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ml/timing_stats")
async def ml_timing_stats() -> dict[str, Any]:
    """Average processing duration by operation (completed rows only)."""
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT operation_type,
                           COUNT(*) AS completed,
                           AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_seconds
                    FROM public.ml_processing_queue
                    WHERE status = 'completed'
                      AND started_at IS NOT NULL
                      AND completed_at IS NOT NULL
                    GROUP BY operation_type
                    ORDER BY completed DESC
                    """
                )
                timing_stats = [
                    {
                        "operation_type": row[0],
                        "completed": row[1],
                        "avg_seconds": float(row[2]) if row[2] is not None else 0,
                    }
                    for row in cur.fetchall()
                ]
                cur.execute(
                    """
                    SELECT queue_id, article_id, operation_type, status,
                           completed_at, error_message
                    FROM public.ml_processing_queue
                    WHERE status IN ('completed', 'failed')
                    ORDER BY COALESCE(completed_at, queued_at) DESC
                    LIMIT 20
                    """
                )
                recent_logs = [
                    {
                        "queue_id": row[0],
                        "article_id": row[1],
                        "operation_type": row[2],
                        "status": row[3],
                        "completed_at": row[4].isoformat() if row[4] else None,
                        "error_message": row[5],
                    }
                    for row in cur.fetchall()
                ]
        return {"success": True, "timing_stats": timing_stats, "recent_logs": recent_logs}
    except Exception as e:
        logger.warning("ml_timing_stats failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/ml/queue")
async def ml_queue_article(body: MLQueueRequest) -> dict[str, Any]:
    """Enqueue an article for ML processing."""
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.ml_processing_queue
                        (article_id, operation_type, model_name, priority, status)
                    VALUES (%s, %s, %s, %s, 'queued')
                    RETURNING queue_id
                    """,
                    (
                        body.article_id,
                        body.operation,
                        body.model,
                        _priority_value(body.priority),
                    ),
                )
                queue_id = cur.fetchone()[0]
            conn.commit()
        return {"success": True, "queue_id": queue_id}
    except Exception as e:
        logger.warning("ml_queue_article failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/feedback_loop/status")
async def feedback_loop_status() -> dict[str, Any]:
    """Deprecated — use Monitor → Processing progress (include_pending_metrics) for pipeline health."""
    return {
        "success": True,
        "running": False,
        "deprecated": True,
        "message": (
            "Feedback loop UI is legacy. Pipeline enrichment runs via AutomationManager; "
            "see GET /api/system_monitoring/processing_progress?include_pending_metrics=true."
        ),
    }


@router.post("/feedback_loop/start")
async def feedback_loop_start() -> dict[str, Any]:
    return {
        "success": True,
        "running": False,
        "deprecated": True,
        "message": "Feedback loop start is not supported; use Monitor → Trigger pipeline.",
    }


@router.post("/feedback_loop/stop")
async def feedback_loop_stop() -> dict[str, Any]:
    return {
        "success": True,
        "running": False,
        "deprecated": True,
        "message": "Feedback loop stop is not supported.",
    }


@router.post("/ai-analysis/run")
async def ai_analysis_run() -> dict[str, Any]:
    """On-demand sentiment batch placeholder — use Monitor → Trigger pipeline for phases."""
    return {
        "success": True,
        "message": "Use Monitor → Trigger pipeline to run sentiment_analysis (automation phase).",
    }
