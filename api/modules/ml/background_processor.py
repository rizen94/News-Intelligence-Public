"""
Background ML Processing Service for News Intelligence System
Handles asynchronous ML processing with timing tracking and queue management
"""

import threading
import time
import logging
import psycopg2
from datetime import datetime
from typing import Dict, List, Optional, Any
from queue import Queue, Empty
import json

from shared.database.connection import get_db_connection
from .summarization_service import MLSummarizationService

logger = logging.getLogger(__name__)

# Domain-scoped article tables (not public.articles).
_DOMAIN_ARTICLE_SCHEMAS = ("politics", "finance", "science_tech")


class BackgroundMLProcessor:
    """
    Background processor for ML operations with timing tracking
    """
    
    def __init__(self, db_config: Dict[str, str], ollama_url: str = "http://localhost:11434"):
        """
        Initialize the background ML processor
        
        Args:
            db_config: Database configuration dictionary
            ollama_url: URL of the Ollama service
        """
        self.db_config = db_config
        self.ollama_url = ollama_url
        self.ml_service = MLSummarizationService(ollama_url)
        
        # Processing queue and thread management
        self.processing_queue = Queue()
        self.worker_threads = []
        self.is_running = False
        self.max_workers = 2  # Limit concurrent ML operations
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'avg_processing_time': 0.0
        }

    @staticmethod
    def _resolve_article_schema(article_id: int) -> Optional[str]:
        """Return which domain schema owns this article id, or None."""
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                return None
            with conn.cursor() as cursor:
                for schema in _DOMAIN_ARTICLE_SCHEMAS:
                    cursor.execute(
                        f"SELECT 1 FROM {schema}.articles WHERE id = %s LIMIT 1",
                        (article_id,),
                    )
                    if cursor.fetchone():
                        return schema
        except Exception as e:
            logger.error("Error resolving schema for article %s: %s", article_id, e)
            return None
        finally:
            if conn is not None:
                conn.close()
        return None
    
    def start_workers(self):
        """Start background worker threads"""
        if self.is_running:
            logger.warning("Background processor is already running")
            return
        
        self.is_running = True
        logger.info(f"Starting {self.max_workers} background ML worker threads")
        
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"MLWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        # Start queue monitor thread
        monitor = threading.Thread(
            target=self._queue_monitor,
            name="MLQueueMonitor",
            daemon=True
        )
        monitor.start()
        self.worker_threads.append(monitor)
    
    def stop_workers(self):
        """Stop background worker threads"""
        if not self.is_running:
            return
        
        logger.info("Stopping background ML workers...")
        self.is_running = False
        
        # Wait for workers to finish current tasks
        for worker in self.worker_threads:
            worker.join(timeout=30)
        
        self.worker_threads.clear()
        logger.info("Background ML workers stopped")
    
    def _worker_loop(self):
        """Main worker loop for processing ML tasks"""
        while self.is_running:
            try:
                # Get next task from queue
                task = self.processing_queue.get(timeout=1)
                if task is None:
                    continue
                
                self._process_task(task)
                self.processing_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(1)
    
    def _queue_monitor(self):
        """Monitor database queue and add tasks to processing queue"""
        while self.is_running:
            try:
                # Check for queued tasks in database
                queued_tasks = self._get_queued_tasks()
                
                for task in queued_tasks:
                    # Add to processing queue if not already there
                    if not self._is_task_in_queue(task['queue_id']):
                        self.processing_queue.put(task)
                        self._update_queue_status(task['queue_id'], 'processing')
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in queue monitor: {e}")
                time.sleep(10)
    
    def _process_task(self, task: Dict[str, Any]):
        """Process a single ML task"""
        queue_id = task['queue_id']
        article_id = task['article_id']
        operation_type = task['operation_type']
        model_name = task['model_name']
        schema: Optional[str] = None

        logger.info(f"Processing ML task {queue_id}: {operation_type} for article {article_id}")
        
        try:
            schema = self._resolve_article_schema(article_id)
            if not schema:
                raise Exception(
                    f"Article {article_id} not found in domain schemas "
                    f"{_DOMAIN_ARTICLE_SCHEMAS}"
                )

            # Get article data
            article_data = self._get_article_data(article_id, schema)
            if not article_data:
                raise Exception(f"Article {article_id} not found")
            
            # Update article processing status
            self._update_article_processing_status(article_id, 'processing', schema=schema)
            
            # Start timing
            start_time = time.time()
            self._log_processing_start(article_id, operation_type, model_name, start_time)
            
            # Process based on operation type
            result = self._execute_ml_operation(
                operation_type, 
                article_data, 
                model_name
            )
            
            # Calculate timing
            end_time = time.time()
            duration = end_time - start_time
            
            # Update article with results
            self._update_article_with_results(
                article_id, 
                operation_type, 
                result, 
                duration, 
                model_name,
                schema=schema,
            )
            
            # Log processing completion
            self._log_processing_completion(
                article_id, 
                operation_type, 
                model_name, 
                start_time, 
                end_time, 
                duration, 
                result
            )
            
            # Update queue status
            self._update_queue_status(queue_id, 'completed', result)
            
            # Update statistics
            self._update_stats(duration, True)
            
            logger.info(f"Completed ML task {queue_id} in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing ML task {queue_id}: {e}")
            
            # Update article processing status
            self._update_article_processing_status(
                article_id, "failed", str(e), schema=schema
            )
            
            # Update queue status
            self._update_queue_status(queue_id, 'failed', error=str(e))
            
            # Update statistics
            self._update_stats(0, False)
    
    def _execute_ml_operation(self, operation_type: str, article_data: Dict, model_name: str) -> Dict:
        """Execute the specific ML operation"""
        content = article_data.get('content', '')
        title = article_data.get('title', '')
        
        if operation_type == 'summarization':
            return self.ml_service.generate_summary(content, title)
        elif operation_type == 'key_points':
            return self.ml_service.extract_key_points(content, title)
        elif operation_type == 'argument_analysis':
            return self.ml_service.analyze_arguments(content, title)
        elif operation_type == 'sentiment':
            return self.ml_service.analyze_sentiment(content)
        elif operation_type == 'full_analysis':
            # Perform all operations
            summary = self.ml_service.generate_summary(content, title)
            key_points = self.ml_service.extract_key_points(content, title)
            arguments = self.ml_service.analyze_arguments(content, title)
            sentiment = self.ml_service.analyze_sentiment(content)
            
            return {
                'summary': summary,
                'key_points': key_points,
                'arguments': arguments,
                'sentiment': sentiment,
                'status': 'success'
            }
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")
    
    def queue_article_for_processing(self, article_id: int, operation_type: str = 'full_analysis', 
                                   priority: int = 0, model_name: str = None) -> int:
        """
        Queue an article for ML processing
        
        Args:
            article_id: ID of the article to process
            operation_type: Type of ML operation to perform
            priority: Priority level (higher = more important)
            model_name: Specific model to use (optional)
            
        Returns:
            Queue ID of the created task
        """
        if not model_name:
            model_name = self.ml_service.model_name
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO ml_processing_queue 
                        (article_id, operation_type, model_name, priority, status)
                        VALUES (%s, %s, %s, %s, 'queued')
                        RETURNING queue_id
                    """, (article_id, operation_type, model_name, priority))
                    
                    queue_id = cursor.fetchone()[0]
                    conn.commit()
                    
                    logger.info(f"Queued article {article_id} for {operation_type} processing (queue_id: {queue_id})")
                    return queue_id
                    
        except Exception as e:
            logger.error(f"Error queueing article {article_id}: {e}")
            raise
        finally:
            if conn is not None:
                conn.close()
    
    def get_processing_status(self, article_id: int = None) -> Dict[str, Any]:
        """Get processing status for articles or specific article"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    if article_id:
                        sch = self._resolve_article_schema(article_id)
                        if not sch:
                            return {"error": "Article not found in domain schemas"}
                        cursor.execute(f"""
                            SELECT 
                                a.id, a.title, a.ml_processing_status,
                                a.ml_processing_started_at, a.ml_processing_completed_at,
                                a.ml_processing_duration_seconds, a.ml_processing_error,
                                a.ml_model_used
                            FROM {sch}.articles a
                            WHERE a.id = %s
                        """, (article_id,))
                        results = cursor.fetchall()
                        if not results:
                            return {"error": "Article not found"}
                        row = results[0]
                        return {
                            'article_id': row[0],
                            'title': row[1],
                            'status': row[2],
                            'started_at': row[3].isoformat() if row[3] else None,
                            'completed_at': row[4].isoformat() if row[4] else None,
                            'duration_seconds': float(row[5]) if row[5] else None,
                            'error': row[6],
                            'model_used': row[7]
                        }

                    subqueries = []
                    for sch in _DOMAIN_ARTICLE_SCHEMAS:
                        subqueries.append(f"""
                            SELECT 
                                a.id, a.title, a.ml_processing_status,
                                a.ml_processing_started_at, a.ml_processing_completed_at,
                                a.ml_processing_duration_seconds, a.ml_processing_error,
                                a.ml_model_used
                            FROM {sch}.articles a
                            WHERE a.ml_processing_status IS NOT NULL
                        """)
                    union_sql = " UNION ALL ".join(subqueries)
                    cursor.execute(f"""
                        SELECT * FROM (
                            {union_sql}
                        ) u
                        ORDER BY ml_processing_started_at DESC NULLS LAST
                        LIMIT 100
                    """)
                    results = cursor.fetchall()
                    articles = []
                    for row in results:
                        articles.append({
                            'article_id': row[0],
                            'title': row[1],
                            'status': row[2],
                            'started_at': row[3].isoformat() if row[3] else None,
                            'completed_at': row[4].isoformat() if row[4] else None,
                            'duration_seconds': float(row[5]) if row[5] else None,
                            'error': row[6],
                            'model_used': row[7]
                        })

                    return {
                        'articles': articles,
                        'total_count': len(articles),
                    }

        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return {'error': str(e)}
        finally:
            if conn is not None:
                conn.close()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            status, operation_type, model_name,
                            COUNT(*) as count,
                            AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - queued_at))) as avg_wait_time
                        FROM ml_processing_queue 
                        GROUP BY status, operation_type, model_name
                        ORDER BY status, operation_type
                    """)
                    
                    queue_stats = []
                    for row in cursor.fetchall():
                        queue_stats.append({
                            'status': row[0],
                            'operation_type': row[1],
                            'model_name': row[2],
                            'count': row[3],
                            'avg_wait_time_seconds': float(row[4]) if row[4] else 0
                        })
                    
                    return {
                        'queue_stats': queue_stats,
                        'worker_stats': {
                            'is_running': self.is_running,
                            'active_workers': len([w for w in self.worker_threads if w.is_alive()]),
                            'queue_size': self.processing_queue.qsize(),
                            'total_processed': self.stats['total_processed'],
                            'successful': self.stats['successful'],
                            'failed': self.stats['failed'],
                            'avg_processing_time': self.stats['avg_processing_time']
                        }
                    }
                    
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {'error': str(e)}
        finally:
            if conn is not None:
                conn.close()
    
    # Database helper methods
    def _get_queued_tasks(self) -> List[Dict]:
        """Get queued tasks from database"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT queue_id, article_id, operation_type, model_name, priority
                        FROM ml_processing_queue 
                        WHERE status = 'queued'
                        ORDER BY priority DESC, queued_at ASC
                        LIMIT 10
                    """)
                    
                    tasks = []
                    for row in cursor.fetchall():
                        tasks.append({
                            'queue_id': row[0],
                            'article_id': row[1],
                            'operation_type': row[2],
                            'model_name': row[3],
                            'priority': row[4]
                        })
                    
                    return tasks
                    
        except Exception as e:
            logger.error(f"Error getting queued tasks: {e}")
            return []
        finally:
            if conn is not None:
                conn.close()
    
    def _is_task_in_queue(self, queue_id: int) -> bool:
        """Check if task is already in processing queue"""
        # This is a simplified check - in production, you'd want a more robust solution
        return False
    
    def _get_article_data(self, article_id: int, schema: str) -> Optional[Dict]:
        """Get article data from database"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT id, title, content, url,
                               COALESCE(source, source_domain) AS src
                        FROM {schema}.articles 
                        WHERE id = %s
                    """, (article_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        return {
                            'id': row[0],
                            'title': row[1],
                            'content': row[2],
                            'url': row[3],
                            'source': row[4]
                        }
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting article data: {e}")
            return None
        finally:
            if conn is not None:
                conn.close()
    
    def _update_article_processing_status(
        self,
        article_id: int,
        status: str,
        error: str = None,
        schema: Optional[str] = None,
    ):
        """Update article processing status"""
        conn = None
        sch = schema or self._resolve_article_schema(article_id)
        if not sch:
            logger.warning(
                "Skip ml_processing_status update: no schema for article %s",
                article_id,
            )
            return
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    if status == 'processing':
                        cursor.execute(f"""
                            UPDATE {sch}.articles 
                            SET ml_processing_status = %s, ml_processing_started_at = %s
                            WHERE id = %s
                        """, (status, datetime.now(), article_id))
                    elif status in ['completed', 'failed']:
                        cursor.execute(f"""
                            UPDATE {sch}.articles 
                            SET ml_processing_status = %s, ml_processing_completed_at = %s,
                                ml_processing_error = %s
                            WHERE id = %s
                        """, (status, datetime.now(), error, article_id))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error updating article processing status: {e}")
        finally:
            if conn is not None:
                conn.close()
    
    def _update_article_with_results(
        self,
        article_id: int,
        operation_type: str,
        result: Dict,
        duration: float,
        model_name: str,
        schema: Optional[str] = None,
    ):
        """Update article with ML processing results"""
        conn = None
        sch = schema or self._resolve_article_schema(article_id)
        if not sch:
            logger.warning(
                "Skip ML result write: no schema for article %s",
                article_id,
            )
            return
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    # Update basic processing info
                    cursor.execute(f"""
                        UPDATE {sch}.articles 
                        SET ml_processing_status = 'completed',
                            ml_processing_completed_at = %s,
                            ml_processing_duration_seconds = %s,
                            ml_model_used = %s
                        WHERE id = %s
                    """, (datetime.now(), duration, model_name, article_id))
                    
                    # Update content based on operation type
                    if operation_type == 'summarization' and result.get('summary'):
                        cursor.execute(f"""
                            UPDATE {sch}.articles 
                            SET summary = %s
                            WHERE id = %s
                        """, (result['summary'], article_id))
                    
                    # Store ML data in JSONB field
                    cursor.execute(f"""
                        UPDATE {sch}.articles 
                        SET ml_processing_metadata = %s
                        WHERE id = %s
                    """, (json.dumps(result), article_id))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error updating article with results: {e}")
        finally:
            if conn is not None:
                conn.close()
    
    def _log_processing_start(self, article_id: int, operation_type: str, 
                            model_name: str, start_time: float):
        """Log processing start to database"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO ml_processing_logs 
                        (article_id, operation_type, model_name, started_at, status)
                        VALUES (%s, %s, %s, %s, 'processing')
                    """, (article_id, operation_type, model_name, datetime.fromtimestamp(start_time)))
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error logging processing start: {e}")
        finally:
            if conn is not None:
                conn.close()
    
    def _log_processing_completion(self, article_id: int, operation_type: str, 
                                 model_name: str, start_time: float, end_time: float, 
                                 duration: float, result: Dict):
        """Log processing completion to database"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE ml_processing_logs 
                        SET completed_at = %s, duration_seconds = %s, status = 'completed',
                            input_length = %s, output_length = %s, processing_metadata = %s
                        WHERE article_id = %s AND operation_type = %s AND started_at = %s
                    """, (
                        datetime.fromtimestamp(end_time),
                        duration,
                        len(result.get('content', '')),
                        len(result.get('summary', '')),
                        json.dumps(result),
                        article_id,
                        operation_type,
                        datetime.fromtimestamp(start_time)
                    ))
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error logging processing completion: {e}")
        finally:
            if conn is not None:
                conn.close()
    
    def _update_queue_status(self, queue_id: int, status: str, result: Dict = None, error: str = None):
        """Update queue item status"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                    if status == 'processing':
                        cursor.execute("""
                            UPDATE ml_processing_queue 
                            SET status = %s, started_at = %s
                            WHERE queue_id = %s
                        """, (status, datetime.now(), queue_id))
                    elif status in ['completed', 'failed']:
                        cursor.execute("""
                            UPDATE ml_processing_queue 
                            SET status = %s, completed_at = %s, result_data = %s, error_message = %s
                            WHERE queue_id = %s
                        """, (status, datetime.now(), json.dumps(result) if result else None, error, queue_id))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Error updating queue status: {e}")
        finally:
            if conn is not None:
                conn.close()
    
    def _update_stats(self, duration: float, success: bool):
        """Update processing statistics"""
        self.stats['total_processed'] += 1
        if success:
            self.stats['successful'] += 1
            # Update average processing time
            total_time = self.stats['avg_processing_time'] * (self.stats['successful'] - 1)
            self.stats['avg_processing_time'] = (total_time + duration) / self.stats['successful']
        else:
            self.stats['failed'] += 1
