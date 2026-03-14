#!/usr/bin/env python3
"""
ML Processing Worker
Processes articles from the ml_task_queue
"""

import os
import sys
import time
import logging
import psycopg2
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class MLWorker:
    def __init__(self):
        from shared.database.connection import get_db_config
        self.db_config = get_db_config()
        self.is_running = False
        
    def get_db_connection(self):
        """Get database connection from shared pool (DB_* env / .env)."""
        from shared.database.connection import get_db_connection as _get_conn
        return _get_conn()
    
    def process_article(self, article_id: int):
        """Process a single article with basic ML operations"""
        logger.info(f"Processing article {article_id}")
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get article data
            cursor.execute("""
                SELECT id, title, content, source, published_at
                FROM articles 
                WHERE id = %s
            """, (article_id,))
            
            article = cursor.fetchone()
            if not article:
                logger.error(f"Article {article_id} not found")
                return False
                
            article_id, title, content, source, published_at = article
            
            # Basic processing - update quality score and processing status
            # This is a simplified version - in production you'd use actual ML models
            
            # Calculate basic quality score based on content length and source
            quality_score = 0.5  # Base score
            
            if content and len(content) > 100:
                quality_score += 0.2
            if content and len(content) > 500:
                quality_score += 0.2
            if source in ['BBC News', 'Reuters', 'NPR News']:
                quality_score += 0.1
                
            # Cap at 1.0
            quality_score = min(quality_score, 1.0)
            
            # Extract basic entities (simplified)
            entities = []
            if content:
                # Simple keyword extraction
                words = content.lower().split()
                common_entities = ['ai', 'artificial intelligence', 'technology', 'news', 'government', 'economy', 'business']
                for entity in common_entities:
                    if entity in content.lower():
                        entities.append(entity)
            
            # Update article with processing results
            cursor.execute("""
                UPDATE articles 
                SET processing_status = 'processed',
                    quality_score = %s,
                    entities_extracted = %s,
                    processing_completed_at = %s,
                    updated_at = %s
                WHERE id = %s
            """, (
                quality_score,
                entities,
                datetime.utcnow(),
                datetime.utcnow(),
                article_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully processed article {article_id} with quality score {quality_score}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing article {article_id}: {str(e)}")
            return False
    
    def process_pending_tasks(self):
        """Process all pending tasks in the queue"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get pending tasks
            cursor.execute("""
                SELECT id, task_id, article_id, task_type
                FROM ml_task_queue 
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 10
            """)
            
            tasks = cursor.fetchall()
            
            if not tasks:
                logger.info("No pending tasks found")
                return 0
                
            logger.info(f"Found {len(tasks)} pending tasks")
            
            processed_count = 0
            for task_id, task_uuid, article_id, task_type in tasks:
                try:
                    # Update task status to running
                    cursor.execute("""
                        UPDATE ml_task_queue 
                        SET status = 'running', started_at = %s
                        WHERE id = %s
                    """, (datetime.utcnow(), task_id))
                    conn.commit()
                    
                    # Process the article
                    success = self.process_article(article_id)
                    
                    if success:
                        # Mark task as completed
                        cursor.execute("""
                            UPDATE ml_task_queue 
                            SET status = 'completed', completed_at = %s, result = %s
                            WHERE id = %s
                        """, (datetime.utcnow(), '{"status": "success"}', task_id))
                        processed_count += 1
                    else:
                        # Mark task as failed
                        cursor.execute("""
                            UPDATE ml_task_queue 
                            SET status = 'failed', completed_at = %s, error = %s
                            WHERE id = %s
                        """, (datetime.utcnow(), 'Processing failed', task_id))
                    
                    conn.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing task {task_id}: {str(e)}")
                    # Mark task as failed
                    cursor.execute("""
                        UPDATE ml_task_queue 
                        SET status = 'failed', completed_at = %s, error = %s
                        WHERE id = %s
                    """, (datetime.utcnow(), str(e), task_id))
                    conn.commit()
            
            conn.close()
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing pending tasks: {str(e)}")
            return 0
    
    def run_worker_loop(self):
        """Run the worker in a continuous loop"""
        logger.info("Starting ML worker...")
        self.is_running = True
        
        while self.is_running:
            try:
                processed = self.process_pending_tasks()
                if processed > 0:
                    logger.info(f"Processed {processed} articles")
                else:
                    logger.info("No tasks to process, waiting...")
                    time.sleep(5)
            except KeyboardInterrupt:
                logger.info("Worker stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                time.sleep(10)
        
        logger.info("ML worker stopped")

def main():
    """Main entry point"""
    worker = MLWorker()
    
    try:
        worker.run_worker_loop()
    except KeyboardInterrupt:
        logger.info("Worker stopped")
    except Exception as e:
        logger.error(f"Worker failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
