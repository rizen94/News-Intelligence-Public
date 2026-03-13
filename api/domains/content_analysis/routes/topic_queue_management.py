"""
Topic Extraction Queue Management Routes
Manages the queue of articles waiting for LLM topic extraction
"""

from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import asyncio

from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from domains.content_analysis.services.topic_extraction_queue_worker import TopicExtractionQueueWorker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Topic Extraction Queue"],
    responses={404: {"description": "Not found"}}
)

# Global worker instances (one per domain)
queue_workers: Dict[str, TopicExtractionQueueWorker] = {}
worker_tasks: Dict[str, asyncio.Task] = {}

@router.get("/{domain}/content_analysis/topics/queue/status")
async def get_queue_status(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """Get status of the topic extraction queue"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        worker = queue_workers.get(schema)
        
        if worker:
            stats = worker.get_queue_stats()
        else:
            # Get stats directly from database
            conn = get_db_connection()
            if not conn:
                raise HTTPException(status_code=500, detail="Database connection failed")
            
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {schema}, public")
                    cur.execute(f"""
                        SELECT 
                            COUNT(*) FILTER (WHERE status = 'pending') as pending,
                            COUNT(*) FILTER (WHERE status = 'processing') as processing,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            AVG(retry_count) FILTER (WHERE status = 'pending') as avg_retries
                        FROM {schema}.topic_extraction_queue
                    """)
                    row = cur.fetchone()
                    stats = {
                        "schema": schema,
                        "pending": row[0] or 0,
                        "processing": row[1] or 0,
                        "completed": row[2] or 0,
                        "failed": row[3] or 0,
                        "avg_retries": float(row[4]) if row[4] else 0.0
                    }
            finally:
                conn.close()
        
        return {
            "success": True,
            "domain": domain,
            "worker_running": schema in queue_workers and queue_workers[schema].is_running,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/content_analysis/topics/queue/start")
async def start_queue_worker(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Start the topic extraction queue worker for a domain"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        # Check if worker already running
        if schema in queue_workers and queue_workers[schema].is_running:
            return {
                "success": True,
                "message": "Queue worker already running",
                "domain": domain
            }
        
        # Create and start worker
        worker = TopicExtractionQueueWorker(get_db_connection, schema=schema)
        queue_workers[schema] = worker
        
        # Start worker in background
        background_tasks.add_task(worker.start)
        
        logger.info(f"✅ Started topic extraction queue worker for domain: {domain}")
        
        return {
            "success": True,
            "message": "Queue worker started",
            "domain": domain,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting queue worker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/content_analysis/topics/queue/stop")
async def stop_queue_worker(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """Stop the topic extraction queue worker for a domain"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        if schema not in queue_workers:
            return {
                "success": True,
                "message": "Queue worker not running",
                "domain": domain
            }
        
        worker = queue_workers[schema]
        worker.stop()
        
        # Remove from workers dict
        del queue_workers[schema]
        if schema in worker_tasks:
            worker_tasks[schema].cancel()
            del worker_tasks[schema]
        
        logger.info(f"🛑 Stopped topic extraction queue worker for domain: {domain}")
        
        return {
            "success": True,
            "message": "Queue worker stopped",
            "domain": domain,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error stopping queue worker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/content_analysis/topics/queue/queue_unprocessed")
async def queue_unprocessed_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of articles to queue")
):
    """Queue all unprocessed articles for LLM topic extraction"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Find articles that haven't been queued yet
                cur.execute(f"""
                    INSERT INTO {schema}.topic_extraction_queue
                    (article_id, status, priority, created_at)
                    SELECT a.id, 'pending', 2, NOW()
                    FROM {schema}.articles a
                    LEFT JOIN {schema}.topic_extraction_queue tq ON a.id = tq.article_id
                    WHERE a.content IS NOT NULL
                    AND LENGTH(a.content) > 100
                    AND tq.id IS NULL
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    ON CONFLICT (article_id) DO NOTHING
                """, (limit,))
                
                queued_count = cur.rowcount
                conn.commit()
                
                logger.info(f"✅ Queued {queued_count} unprocessed articles for {domain}")
                
                return {
                    "success": True,
                    "message": f"Queued {queued_count} unprocessed articles",
                    "domain": domain,
                    "queued_count": queued_count,
                    "timestamp": datetime.now().isoformat()
                }
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queueing unprocessed articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{domain}/content_analysis/topics/queue/process")
async def process_queue_manually(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    batch_size: int = Query(10, ge=1, le=50)
):
    """Manually trigger processing of queued articles"""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        
        # Create temporary worker for manual processing
        worker = TopicExtractionQueueWorker(get_db_connection, schema=schema)
        worker.batch_size = batch_size
        
        # Process one batch
        await worker._process_queue_batch()
        
        stats = worker.get_queue_stats()
        
        return {
            "success": True,
            "message": f"Processed queue batch (batch_size={batch_size})",
            "domain": domain,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing queue manually: {e}")
        raise HTTPException(status_code=500, detail=str(e))

