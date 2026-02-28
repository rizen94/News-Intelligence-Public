"""
Topic Extraction Queue Worker
Processes queued articles for LLM-based topic extraction
Runs as background task to ensure all articles eventually get processed
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import psycopg2

from domains.content_analysis.services.llm_topic_extractor import LLMTopicExtractor
from domains.content_analysis.services.llm_activity_tracker import get_llm_activity_tracker
from domains.content_analysis.services.topic_filter_rules import filter_topic_list
from services.article_entity_extraction_service import get_article_entity_extraction_service
import uuid

logger = logging.getLogger(__name__)

class TopicExtractionQueueWorker:
    """
    Background worker that processes articles queued for LLM topic extraction
    Ensures eventual consistency - all articles get processed when LLM is available
    """
    
    def __init__(self, db_connection_func, schema: str = "politics", ollama_url: str = "http://localhost:11434"):
        self.get_db_connection = db_connection_func
        self.schema = schema
        self.ollama_url = ollama_url
        self.is_running = False
        self.batch_size = 5  # Process 5 articles at a time
        self.poll_interval = 60  # Check queue every 60 seconds
        self.max_retries = 10
        
        # Initialize extractor
        self.extractor = LLMTopicExtractor(db_connection_func, schema=schema, ollama_url=ollama_url)
        self.entity_service = get_article_entity_extraction_service()
    
    async def start(self):
        """Start the queue worker"""
        if self.is_running:
            logger.warning("Queue worker already running")
            return
        
        self.is_running = True
        logger.info(f"🚀 Starting topic extraction queue worker for schema: {self.schema}")
        
        while self.is_running:
            try:
                await self._process_queue_batch()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in queue worker loop: {e}")
                await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the queue worker"""
        self.is_running = False
        logger.info("🛑 Stopping topic extraction queue worker")
    
    async def _process_queue_batch(self):
        """Process a batch of queued articles, and find unprocessed articles if queue is empty"""
        try:
            # Priority hierarchy: yield to web page loads — don't compete with API requests
            from shared.services.api_request_tracker import should_yield_to_api
            if should_yield_to_api():
                logger.debug(f"Yielding to API — skipping topic extraction this cycle for {self.schema}")
                return
            conn = self.get_db_connection()
            if not conn:
                logger.warning("Cannot process queue: database connection failed")
                return
            
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {self.schema}, public")
                    
                    # Get next batch of articles to process
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
                    
                    # If queue is empty, find unprocessed articles and queue them
                    if not queued_items:
                        logger.debug(f"Queue empty for {self.schema}, finding unprocessed articles...")
                        
                        # Find articles that haven't been queued yet
                        cur.execute(f"""
                            SELECT a.id
                            FROM {self.schema}.articles a
                            LEFT JOIN {self.schema}.topic_extraction_queue tq ON a.id = tq.article_id
                            WHERE a.content IS NOT NULL
                            AND LENGTH(a.content) > 100
                            AND tq.id IS NULL
                            ORDER BY a.created_at DESC
                            LIMIT %s
                        """, (self.batch_size * 2,))  # Queue more than batch_size to keep queue full
                        
                        unprocessed = cur.fetchall()
                        
                        if unprocessed:
                            logger.info(f"📋 Found {len(unprocessed)} unprocessed articles, queueing them...")
                            for (article_id,) in unprocessed:
                                try:
                                    cur.execute(f"""
                                        INSERT INTO {self.schema}.topic_extraction_queue
                                        (article_id, status, priority, created_at)
                                        VALUES (%s, 'pending', 2, NOW())
                                        ON CONFLICT (article_id) DO NOTHING
                                    """, (article_id,))
                                except Exception as e:
                                    logger.debug(f"Could not queue article {article_id}: {e}")
                            
                            conn.commit()
                            
                            # Re-fetch queued items after queueing
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
                        # Still no items to process
                        return
                    
                    logger.info(f"📋 Processing {len(queued_items)} queued articles for topic extraction")
                    
                    # Process each article
                    for queue_id, article_id, retry_count in queued_items:
                        try:
                            # Mark as processing
                            cur.execute(f"""
                                UPDATE {self.schema}.topic_extraction_queue
                                SET status = 'processing', started_at = NOW()
                                WHERE id = %s
                            """, (queue_id,))
                            conn.commit()
                            
                            # Get article data
                            cur.execute(f"""
                                SELECT id, title, content, summary, published_at, sentiment_score, source_domain
                                FROM {self.schema}.articles
                                WHERE id = %s
                            """, (article_id,))
                            
                            article = cur.fetchone()
                            if not article:
                                # Article doesn't exist, mark as completed
                                cur.execute(f"""
                                    UPDATE {self.schema}.topic_extraction_queue
                                    SET status = 'completed', completed_at = NOW(),
                                        error_message = 'Article not found'
                                    WHERE id = %s
                                """, (queue_id,))
                                conn.commit()
                                continue
                            
                            # Extract topics using LLM
                            article_id, title, content, summary, published_at, sentiment_score, source_domain = article
                            content = content or ""

                            # Run entity extraction first (populates article_entities, dates, times, countries)
                            try:
                                if not self.entity_service.entity_extraction_done(conn, self.schema, article_id):
                                    result = await self.entity_service.extract_and_store(
                                        article_id, title, content, schema=self.schema
                                    )
                                    if result.get("success") and result.get("counts"):
                                        c = result["counts"]
                                        logger.debug(f"Entity extraction for {article_id}: {c}")
                            except Exception as ent_err:
                                logger.debug(f"Entity extraction skipped for {article_id}: {ent_err}")
                                # Non-blocking: continue with topic extraction

                            # Track queue processing
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
                                # Apply date/country filter - exclude dates, months, country names from topics
                                topics = filter_topic_list(topics, name_key="name")
                            if topics:
                                # Save topics to database
                                success = self.extractor.save_topics_to_database(topics)
                                
                                if success:
                                    # Mark as completed
                                    cur.execute(f"""
                                        UPDATE {self.schema}.topic_extraction_queue
                                        SET status = 'completed', completed_at = NOW(),
                                            metadata = jsonb_build_object('topics_extracted', %s)
                                        WHERE id = %s
                                    """, (len(topics), queue_id))
                                    conn.commit()
                                    logger.info(f"✅ Successfully processed article {article_id} (extracted {len(topics)} topics)")
                                else:
                                    # Failed to save, queue for retry
                                    raise Exception("Failed to save topics to database")
                            else:
                                # No topics extracted, but processing succeeded
                                cur.execute(f"""
                                    UPDATE {self.schema}.topic_extraction_queue
                                    SET status = 'completed', completed_at = NOW(),
                                        metadata = jsonb_build_object('topics_extracted', 0)
                                    WHERE id = %s
                                """, (queue_id,))
                                conn.commit()
                                logger.info(f"✅ Processed article {article_id} (no topics found)")
                                
                        except Exception as article_error:
                            logger.error(f"Error processing article {article_id}: {article_error}")
                            
                            # Update retry count and schedule next retry
                            new_retry_count = retry_count + 1
                            backoff_minutes = min(60 * 2 ** min(new_retry_count, 8), 480)
                            next_retry = datetime.now() + timedelta(minutes=backoff_minutes)
                            
                            if new_retry_count >= self.max_retries:
                                # Max retries reached, mark as failed
                                cur.execute(f"""
                                    UPDATE {self.schema}.topic_extraction_queue
                                    SET status = 'failed', last_error = %s,
                                        last_attempt_at = NOW()
                                    WHERE id = %s
                                """, (str(article_error), queue_id))
                                logger.error(f"❌ Article {article_id} failed after {new_retry_count} retries")
                            else:
                                # Queue for retry
                                cur.execute(f"""
                                    UPDATE {self.schema}.topic_extraction_queue
                                    SET status = 'pending', retry_count = %s,
                                        next_retry_at = %s, last_error = %s,
                                        last_attempt_at = NOW()
                                    WHERE id = %s
                                """, (new_retry_count, next_retry, str(article_error), queue_id))
                                logger.info(f"🔄 Queued article {article_id} for retry {new_retry_count} (next: {next_retry})")
                            
                            conn.commit()
                            
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error processing queue batch: {e}")
    
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

