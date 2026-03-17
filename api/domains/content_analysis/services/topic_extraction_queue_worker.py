"""
Topic Extraction Queue Worker
Processes queued articles for LLM-based topic extraction.
Runs as background task to ensure all articles eventually get processed.

Concurrency design:
- Multiple workers (one per domain schema) share a single asyncio event loop
  in a background thread.
- A module-level asyncio.Semaphore ensures only ONE worker calls Ollama at a
  time.  Ollama is single-threaded so parallel requests just queue inside it
  while holding the GIL; the semaphore lets waiting workers yield so the main
  uvicorn thread can process HTTP requests.
- Each article is followed by a short asyncio.sleep to release the GIL and a
  should_yield_to_api() check so user page-loads always take priority.
"""

import logging
import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import psycopg2

from domains.content_analysis.services.llm_topic_extractor import LLMTopicExtractor
from domains.content_analysis.services.llm_activity_tracker import get_llm_activity_tracker
from domains.content_analysis.services.topic_filter_rules import filter_topic_list
from services.article_entity_extraction_service import get_article_entity_extraction_service
import uuid

logger = logging.getLogger(__name__)

STARTUP_DELAY_SECONDS = 45
_ollama_semaphore: Optional[asyncio.Semaphore] = None


def _get_ollama_semaphore() -> asyncio.Semaphore:
    """Lazy-init a shared semaphore so only one worker calls Ollama at a time."""
    global _ollama_semaphore
    if _ollama_semaphore is None:
        _ollama_semaphore = asyncio.Semaphore(1)
    return _ollama_semaphore


class TopicExtractionQueueWorker:
    """
    Background worker that processes articles queued for LLM topic extraction.
    Ensures eventual consistency - all articles get processed when LLM is available.
    """
    
    def __init__(self, db_connection_func, schema: str = "politics", ollama_url: str = "http://localhost:11434"):
        self.get_db_connection = db_connection_func
        self.schema = schema
        self.ollama_url = ollama_url
        self.is_running = False
        self.batch_size = 10
        self.poll_interval = 60
        self.poll_interval_busy = 10
        self.max_retries = 10
        
        self.extractor = LLMTopicExtractor(db_connection_func, schema=schema, ollama_url=ollama_url)
        self.entity_service = get_article_entity_extraction_service()
    
    async def start(self):
        """Start the queue worker after a startup delay."""
        if self.is_running:
            logger.warning("Queue worker already running")
            return
        
        logger.info("⏳ Queue worker %s: waiting %ss for API startup…", self.schema, STARTUP_DELAY_SECONDS)
        await asyncio.sleep(STARTUP_DELAY_SECONDS)

        self._reset_stale_processing_records()

        self.is_running = True
        logger.info("🚀 Starting topic extraction queue worker for schema: %s", self.schema)
        
        while self.is_running:
            try:
                had_work = await self._process_queue_batch()
                interval = self.poll_interval_busy if had_work else self.poll_interval
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in queue worker loop: {e}")
                await asyncio.sleep(self.poll_interval)

    def _reset_stale_processing_records(self):
        """Reset records stuck in 'processing' from a previous crash back to 'pending'."""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            try:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        UPDATE {self.schema}.topic_extraction_queue
                        SET status = 'pending', started_at = NULL
                        WHERE status = 'processing'
                    """)
                    reset_count = cur.rowcount
                    conn.commit()
                    if reset_count:
                        logger.info("♻️ Reset %d stale 'processing' records to 'pending' for %s", reset_count, self.schema)
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Could not reset stale processing records for %s: %s", self.schema, e)
    
    def stop(self):
        """Stop the queue worker"""
        self.is_running = False
        logger.info("🛑 Stopping topic extraction queue worker")
    
    async def _process_queue_batch(self) -> bool:
        """Process a batch of queued articles; find unprocessed if queue empty. Returns True if work was done."""
        try:
            from shared.services.api_request_tracker import should_yield_to_api
            if should_yield_to_api():
                logger.debug("Yielding to API — skipping topic extraction this cycle for %s", self.schema)
                return False

            sem = _get_ollama_semaphore()
            async with sem:
                return await self._process_queue_batch_inner(should_yield_to_api)

        except Exception as e:
            logger.error("Error processing queue batch for %s: %s", self.schema, e)
            return False

    async def _process_queue_batch_inner(self, should_yield_to_api) -> bool:
        """Inner batch logic, called while holding the Ollama semaphore."""
        conn = self.get_db_connection()
        if not conn:
            logger.warning("Cannot process queue: database connection failed")
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema}, public")

                cur.execute(f"""
                    SELECT tq.id, tq.article_id, tq.retry_count
                    FROM {self.schema}.topic_extraction_queue tq
                    WHERE tq.status = 'pending'
                    AND tq.retry_count < %s
                    AND (tq.next_retry_at IS NULL OR tq.next_retry_at <= NOW())
                    ORDER BY tq.priority DESC, tq.created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                """, (self.max_retries, self.batch_size))

                queued_items = cur.fetchall()

                if not queued_items:
                    logger.debug("Queue empty for %s, finding unprocessed articles…", self.schema)
                    cur.execute(f"""
                        SELECT a.id
                        FROM {self.schema}.articles a
                        LEFT JOIN {self.schema}.topic_extraction_queue tq ON a.id = tq.article_id
                        WHERE a.content IS NOT NULL
                        AND LENGTH(a.content) > 100
                        AND tq.id IS NULL
                        ORDER BY a.created_at DESC
                        LIMIT %s
                    """, (self.batch_size * 2,))

                    unprocessed = cur.fetchall()

                    if unprocessed:
                        logger.info("📋 Found %d unprocessed articles, queueing them…", len(unprocessed))
                        for (article_id,) in unprocessed:
                            try:
                                cur.execute(f"""
                                    INSERT INTO {self.schema}.topic_extraction_queue
                                    (article_id, status, priority, created_at)
                                    VALUES (%s, 'pending', 2, NOW())
                                    ON CONFLICT (article_id) DO NOTHING
                                """, (article_id,))
                            except Exception as e:
                                logger.debug("Could not queue article %s: %s", article_id, e)

                        conn.commit()

                        cur.execute(f"""
                            SELECT tq.id, tq.article_id, tq.retry_count
                            FROM {self.schema}.topic_extraction_queue tq
                            WHERE tq.status = 'pending'
                            AND tq.retry_count < %s
                            AND (tq.next_retry_at IS NULL OR tq.next_retry_at <= NOW())
                            ORDER BY tq.priority DESC, tq.created_at ASC
                            LIMIT %s
                            FOR UPDATE SKIP LOCKED
                        """, (self.max_retries, self.batch_size))
                        queued_items = cur.fetchall()

                if not queued_items:
                    return False

                logger.info("📋 Processing %d queued articles for topic extraction (%s)", len(queued_items), self.schema)

                for queue_id, article_id, retry_count in queued_items:
                    # --- per-article yield: time.sleep guarantees GIL release so
                    # the main uvicorn thread can process HTTP requests ---
                    time.sleep(0.5)
                    if should_yield_to_api():
                        logger.debug("Yielding mid-batch to API for %s", self.schema)
                        return True

                    try:
                        cur.execute(f"""
                            UPDATE {self.schema}.topic_extraction_queue
                            SET status = 'processing', started_at = NOW()
                            WHERE id = %s
                        """, (queue_id,))
                        conn.commit()

                        cur.execute(f"""
                            SELECT id, title, content, summary, published_at, sentiment_score, source_domain
                            FROM {self.schema}.articles
                            WHERE id = %s
                              AND (enrichment_status IS NULL OR enrichment_status != 'removed')
                        """, (article_id,))

                        article = cur.fetchone()
                        if not article:
                            cur.execute(f"""
                                UPDATE {self.schema}.topic_extraction_queue
                                SET status = 'completed', completed_at = NOW(),
                                    error_message = 'Article not found'
                                WHERE id = %s
                            """, (queue_id,))
                            conn.commit()
                            continue

                        article_id, title, content, summary, published_at, sentiment_score, source_domain = article
                        content = content or ""

                        try:
                            if not self.entity_service.entity_extraction_done(conn, self.schema, article_id):
                                result = await self.entity_service.extract_and_store(
                                    article_id, title, content, schema=self.schema
                                )
                                if result.get("success") and result.get("counts"):
                                    logger.debug("Entity extraction for %s: %s", article_id, result["counts"])
                        except Exception as ent_err:
                            logger.debug("Entity extraction skipped for %s: %s", article_id, ent_err)

                        tracker = get_llm_activity_tracker()
                        queue_task_id = f"queue_{queue_id}_{uuid.uuid4()}"
                        tracker.start_task(
                            task_id=queue_task_id,
                            task_type='queue_topic_extraction',
                            article_id=article_id,
                            domain=self.schema,
                            metadata={'queue_id': queue_id, 'retry_count': retry_count, 'title': title[:100]}
                        )

                        try:
                            topics = await self.extractor._extract_topics_from_single_article(
                                article_id, title, content, summary
                            )
                            tracker.complete_task(queue_task_id, success=True)
                        except Exception as extract_error:
                            tracker.complete_task(queue_task_id, success=False, error=str(extract_error))
                            raise

                        if topics:
                            topics = filter_topic_list(topics, name_key="name")
                        if topics:
                            success = self.extractor.save_topics_to_database(topics)
                            if success:
                                cur.execute(f"""
                                    UPDATE {self.schema}.topic_extraction_queue
                                    SET status = 'completed', completed_at = NOW(),
                                        metadata = jsonb_build_object('topics_extracted', %s)
                                    WHERE id = %s
                                """, (len(topics), queue_id))
                                conn.commit()
                                logger.info("✅ Successfully processed article %s (extracted %d topics)", article_id, len(topics))
                            else:
                                raise Exception("Failed to save topics to database")
                        else:
                            cur.execute(f"""
                                UPDATE {self.schema}.topic_extraction_queue
                                SET status = 'completed', completed_at = NOW(),
                                    metadata = jsonb_build_object('topics_extracted', 0)
                                WHERE id = %s
                            """, (queue_id,))
                            conn.commit()
                            logger.info("✅ Processed article %s (no topics found)", article_id)

                    except Exception as article_error:
                        logger.error("Error processing article %s: %s", article_id, article_error)

                        new_retry_count = retry_count + 1
                        backoff_minutes = min(60 * 2 ** min(new_retry_count, 8), 480)
                        next_retry = datetime.now() + timedelta(minutes=backoff_minutes)

                        if new_retry_count >= self.max_retries:
                            cur.execute(f"""
                                UPDATE {self.schema}.topic_extraction_queue
                                SET status = 'failed', last_error = %s,
                                    last_attempt_at = NOW()
                                WHERE id = %s
                            """, (str(article_error), queue_id))
                            logger.error("❌ Article %s failed after %d retries", article_id, new_retry_count)
                        else:
                            cur.execute(f"""
                                UPDATE {self.schema}.topic_extraction_queue
                                SET status = 'pending', retry_count = %s,
                                    next_retry_at = %s, last_error = %s,
                                    last_attempt_at = NOW()
                                WHERE id = %s
                            """, (new_retry_count, next_retry, str(article_error), queue_id))
                            logger.info("🔄 Queued article %s for retry %d (next: %s)", article_id, new_retry_count, next_retry)

                        conn.commit()

                    # Brief GIL release after error handling DB writes
                    time.sleep(0.3)

        finally:
            conn.close()
        return True

    async def _process_queue_batch_legacy(self) -> bool:
        """Unused — kept temporarily for reference during transition."""
        return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the queue"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return {"error": "Database connection failed"}
            
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {self.schema}, public")
                    
                    # Get queue statistics
                    cur.execute(f"""
                        SELECT 
                            COUNT(*) FILTER (WHERE status = 'pending') as pending,
                            COUNT(*) FILTER (WHERE status = 'processing') as processing,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            AVG(retry_count) FILTER (WHERE status = 'pending') as avg_retries
                        FROM {self.schema}.topic_extraction_queue
                    """)
                    
                    row = cur.fetchone()
                    return {
                        "schema": self.schema,
                        "pending": row[0] or 0,
                        "processing": row[1] or 0,
                        "completed": row[2] or 0,
                        "failed": row[3] or 0,
                        "avg_retries": float(row[4]) if row[4] else 0.0
                }
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {"error": str(e)}

