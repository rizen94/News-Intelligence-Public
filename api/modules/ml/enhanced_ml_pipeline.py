#!/usr/bin/env python3
"""
Enhanced ML Pipeline with Queue Management
Integrates with ML queue system for intelligent processing
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import psycopg2
import json

from modules.ml_queue_manager import MLQueueManager, MLTask, TaskType, TaskPriority
from modules.timeline_generator import TimelineGenerator

logger = logging.getLogger(__name__)

class EnhancedMLPipeline:
    """Enhanced ML Pipeline with intelligent queue management"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.queue_manager = MLQueueManager(db_config)
        self.timeline_generator = TimelineGenerator(db_config)
        
        # Start the queue manager
        self.queue_manager.start()
    
    async def process_article_intelligently(self, article_id: int, priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Process an article through the intelligent ML pipeline"""
        try:
            # Get article data
            article = self._get_article(article_id)
            if not article:
                raise ValueError(f"Article {article_id} not found")
            
            # Create a workflow of tasks
            workflow_tasks = []
            
            # 1. Content Analysis (high priority for new articles)
            content_analysis_task = MLTask(
                task_id=f"content_analysis_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.CONTENT_ANALYSIS,
                priority=TaskPriority.HIGH,
                article_id=article_id,
                payload={
                    "article_data": article,
                    "analysis_type": "comprehensive"
                },
                estimated_duration=30,
                resource_requirements={"max_cpu_usage": 60.0, "max_memory_usage": 70.0}
            )
            workflow_tasks.append(content_analysis_task)
            
            # 2. Entity Extraction (depends on content analysis)
            entity_extraction_task = MLTask(
                task_id=f"entity_extraction_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.ENTITY_EXTRACTION,
                priority=priority,
                article_id=article_id,
                payload={
                    "article_data": article,
                    "extraction_types": ["person", "organization", "location", "event"]
                },
                estimated_duration=20,
                resource_requirements={"max_cpu_usage": 50.0, "max_memory_usage": 60.0}
            )
            workflow_tasks.append(entity_extraction_task)
            
            # 3. Sentiment Analysis
            sentiment_task = MLTask(
                task_id=f"sentiment_analysis_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.SENTIMENT_ANALYSIS,
                priority=priority,
                article_id=article_id,
                payload={
                    "article_data": article,
                    "analysis_depth": "comprehensive"
                },
                estimated_duration=15,
                resource_requirements={"max_cpu_usage": 40.0, "max_memory_usage": 50.0}
            )
            workflow_tasks.append(sentiment_task)
            
            # 4. Quality Scoring
            quality_task = MLTask(
                task_id=f"quality_scoring_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.QUALITY_SCORING,
                priority=priority,
                article_id=article_id,
                payload={
                    "article_data": article,
                    "scoring_criteria": ["reliability", "completeness", "objectivity", "relevance"]
                },
                estimated_duration=25,
                resource_requirements={"max_cpu_usage": 45.0, "max_memory_usage": 55.0}
            )
            workflow_tasks.append(quality_task)
            
            # 5. Article Summarization (depends on content analysis)
            summary_task = MLTask(
                task_id=f"article_summarization_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.ARTICLE_SUMMARIZATION,
                priority=priority,
                article_id=article_id,
                payload={
                    "article_data": article,
                    "summary_length": "medium",
                    "include_key_points": True
                },
                estimated_duration=45,
                resource_requirements={"max_cpu_usage": 70.0, "max_memory_usage": 80.0}
            )
            workflow_tasks.append(summary_task)
            
            # Submit all tasks
            submitted_tasks = []
            for task in workflow_tasks:
                task_id = self.queue_manager.submit_task(task)
                submitted_tasks.append(task_id)
            
            # Update article status
            self._update_article_status(article_id, "ml_processing")
            
            logger.info(f"Submitted {len(submitted_tasks)} ML tasks for article {article_id}")
            return f"Article {article_id} submitted for intelligent processing with {len(submitted_tasks)} tasks"
            
        except Exception as e:
            logger.error(f"Error processing article {article_id} intelligently: {e}")
            raise
    
    async def generate_timeline_intelligently(self, storyline_id: str, priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Generate timeline events intelligently using the queue system"""
        try:
            # Get storyline data
            storyline_data = await self._get_storyline_data(storyline_id)
            if not storyline_data:
                raise ValueError(f"Storyline {storyline_id} not found")
            
            # Create timeline generation task
            timeline_task = MLTask(
                task_id=f"timeline_generation_{storyline_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.TIMELINE_GENERATION,
                priority=priority,
                storyline_id=storyline_id,
                payload={
                    "storyline_data": storyline_data,
                    "generation_type": "intelligent",
                    "max_events": 50,
                    "use_llm": True
                },
                estimated_duration=120,  # 2 minutes for timeline generation
                resource_requirements={
                    "max_cpu_usage": 80.0,
                    "max_memory_usage": 85.0,
                    "max_gpu_usage": 70.0
                }
            )
            
            # Submit task
            task_id = self.queue_manager.submit_task(timeline_task)
            
            logger.info(f"Timeline generation task submitted for storyline {storyline_id}")
            return f"Timeline generation task submitted for storyline {storyline_id}"
            
        except Exception as e:
            logger.error(f"Error generating timeline intelligently for {storyline_id}: {e}")
            raise
    
    async def process_storyline_intelligently(self, storyline_id: str, priority: TaskPriority = TaskPriority.HIGH) -> str:
        """Process a storyline intelligently with comprehensive analysis"""
        try:
            # Get storyline data
            storyline_data = await self._get_storyline_data(storyline_id)
            if not storyline_data:
                raise ValueError(f"Storyline {storyline_id} not found")
            
            # Get related articles
            articles = self._get_storyline_articles(storyline_id)
            
            # Create storyline analysis task
            analysis_task = MLTask(
                task_id=f"storyline_analysis_{storyline_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                task_type=TaskType.STORYLINE_ANALYSIS,
                priority=priority,
                storyline_id=storyline_id,
                payload={
                    "storyline_data": storyline_data,
                    "related_articles": articles,
                    "analysis_type": "comprehensive",
                    "include_trends": True,
                    "include_sentiment_analysis": True
                },
                estimated_duration=180,  # 3 minutes for comprehensive analysis
                resource_requirements={
                    "max_cpu_usage": 85.0,
                    "max_memory_usage": 90.0,
                    "max_gpu_usage": 75.0
                }
            )
            
            # Submit task
            task_id = self.queue_manager.submit_task(analysis_task)
            
            logger.info(f"Storyline analysis task submitted for {storyline_id}")
            return f"Storyline analysis task submitted for {storyline_id}"
            
        except Exception as e:
            logger.error(f"Error processing storyline intelligently for {storyline_id}: {e}")
            raise
    
    async def batch_process_articles(self, article_ids: List[int], priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Process multiple articles in batch with intelligent resource management"""
        try:
            # Group articles by priority and resource requirements
            high_priority_articles = []
            normal_priority_articles = []
            
            for article_id in article_ids:
                article = self._get_article(article_id)
                if not article:
                    continue
                
                # Determine priority based on article characteristics
                if self._is_high_priority_article(article):
                    high_priority_articles.append(article_id)
                else:
                    normal_priority_articles.append(article_id)
            
            # Process high priority articles first
            for article_id in high_priority_articles:
                await self.process_article_intelligently(article_id, TaskPriority.HIGH)
            
            # Process normal priority articles
            for article_id in normal_priority_articles:
                await self.process_article_intelligently(article_id, priority)
            
            logger.info(f"Batch processing initiated for {len(article_ids)} articles")
            return f"Batch processing initiated for {len(article_ids)} articles ({len(high_priority_articles)} high priority, {len(normal_priority_articles)} normal priority)"
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status and statistics"""
        try:
            queue_status = self.queue_manager.get_queue_status()
            
            # Get additional statistics
            stats = self._get_processing_statistics()
            
            return {
                "queue_status": queue_status,
                "processing_statistics": stats,
                "system_health": self._get_system_health()
            }
            
        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return {"error": str(e)}
    
    def _get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get article data from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, title, content, summary, source, url, published_at,
                       category, processing_status, created_at
                FROM articles
                WHERE id = %s
            """, (article_id,))
            
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "summary": row[3],
                    "source": row[4],
                    "url": row[5],
                    "published_at": row[6],
                    "category": row[7],
                    "processing_status": row[8],
                    "created_at": row[9]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting article {article_id}: {e}")
            return None
    
    async def _get_storyline_data(self, storyline_id: str) -> Optional[Dict[str, Any]]:
        """Get storyline data from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT story_id, name, description, keywords, entities, priority_level,
                       quality_threshold, max_articles_per_day, is_active
                FROM story_expectations
                WHERE story_id = %s AND is_active = true
            """, (storyline_id,))
            
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return {
                    "story_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "keywords": row[3] if row[3] else [],
                    "entities": row[4] if row[4] else [],
                    "priority_level": row[5],
                    "quality_threshold": row[6],
                    "max_articles_per_day": row[7],
                    "is_active": row[8]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting storyline {storyline_id}: {e}")
            return None
    
    def _get_storyline_articles(self, storyline_id: str) -> List[Dict[str, Any]]:
        """Get articles related to a storyline"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Get storyline keywords
            cur.execute("""
                SELECT keywords FROM story_expectations WHERE story_id = %s
            """, (storyline_id,))
            
            row = cur.fetchone()
            if not row or not row[0]:
                return []
            
            keywords = row[0]
            
            # Find articles matching keywords
            keyword_conditions = []
            params = []
            
            for keyword in keywords:
                keyword_conditions.append("(title ILIKE %s OR content ILIKE %s OR summary ILIKE %s)")
                keyword_term = f"%{keyword}%"
                params.extend([keyword_term, keyword_term, keyword_term])
            
            where_clause = " OR ".join(keyword_conditions)
            
            cur.execute(f"""
                SELECT id, title, content, summary, source, published_at, category
                FROM articles
                WHERE {where_clause} AND processing_status = 'completed'
                ORDER BY published_at DESC
                LIMIT 100
            """, params)
            
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            articles = []
            for row in rows:
                articles.append({
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "summary": row[3],
                    "source": row[4],
                    "published_at": row[5],
                    "category": row[6]
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"Error getting storyline articles for {storyline_id}: {e}")
            return []
    
    def _is_high_priority_article(self, article: Dict[str, Any]) -> bool:
        """Determine if an article should be processed with high priority"""
        # High priority criteria
        high_priority_keywords = [
            "breaking", "urgent", "crisis", "emergency", "major", "significant",
            "victory", "defeat", "attack", "casualties", "death", "killed"
        ]
        
        title = article.get("title", "").lower()
        content = article.get("content", "").lower()
        
        # Check for high priority keywords
        for keyword in high_priority_keywords:
            if keyword in title or keyword in content:
                return True
        
        # Check for recent articles (within last 24 hours)
        published_at = article.get("published_at")
        if published_at:
            time_diff = datetime.now() - published_at
            if time_diff.total_seconds() < 86400:  # 24 hours
                return True
        
        return False
    
    def _update_article_status(self, article_id: int, status: str):
        """Update article processing status"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE articles
                SET processing_status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, article_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating article status: {e}")
    
    def _get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Get task statistics
            cur.execute("""
                SELECT 
                    task_type,
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_tasks,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration
                FROM ml_task_queue
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY task_type
            """)
            
            task_stats = {}
            for row in cur.fetchall():
                task_stats[row[0]] = {
                    "total_tasks": row[1],
                    "completed_tasks": row[2],
                    "failed_tasks": row[3],
                    "avg_duration": row[4] if row[4] else 0
                }
            
            # Get article processing statistics
            cur.execute("""
                SELECT 
                    processing_status,
                    COUNT(*) as count
                FROM articles
                GROUP BY processing_status
            """)
            
            article_stats = {}
            for row in cur.fetchall():
                article_stats[row[0]] = row[1]
            
            cur.close()
            conn.close()
            
            return {
                "task_statistics": task_stats,
                "article_statistics": article_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {e}")
            return {}
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            import psutil
            
            return {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {"error": str(e)}
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.queue_manager:
                self.queue_manager.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
