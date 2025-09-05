#!/usr/bin/env python3
"""
Automated Data Ingestion Pipeline Orchestrator
Coordinates the complete flow from RSS collection to ML summarization
"""

import os
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Import our existing modules
from ..data_collection.rss_feed_service import RSSFeedService
from ..data_collection.feed_scheduler import FeedScheduler
from ..intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from ..prioritization.content_prioritization_manager import ContentPrioritizationManager
from ..prioritization.rag_context_builder import RAGContextBuilder
from ..ml.summarization_service import MLSummarizationService
from .enhanced_preprocessor import EnhancedPreprocessor
from .living_story_narrator import LivingStoryNarrator

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """Orchestrates the complete automated data ingestion pipeline"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.running = False
        self.pipeline_thread = None
        
        # Initialize services
        self.rss_service = RSSFeedService(db_config)
        self.feed_scheduler = FeedScheduler(db_config)
        self.intelligence_orchestrator = IntelligenceOrchestrator(db_config)
        self.prioritization_manager = ContentPrioritizationManager(db_config)
        self.rag_builder = RAGContextBuilder(db_config)
        self.summarization_service = MLSummarizationService()
        self.enhanced_preprocessor = EnhancedPreprocessor(db_config)
        self.living_story_narrator = LivingStoryNarrator(db_config)
        
        # Pipeline configuration
        self.config = {
            'rss_interval_minutes': 60,  # Collect RSS every hour
            'preprocessing_batch_size': 50,
            'clustering_threshold': 0.7,
            'auto_story_creation': True,
            'ml_summarization': True,
            'rag_context_building': True,
            'max_articles_per_feed': 50
        }
        
        # Pipeline statistics
        self.stats = {
            'pipeline_runs': 0,
            'articles_collected': 0,
            'articles_processed': 0,
            'story_threads_created': 0,
            'summaries_generated': 0,
            'rag_contexts_built': 0,
            'last_run': None,
            'start_time': None,
            'errors': []
        }
    
    def start_automated_pipeline(self):
        """Start the automated pipeline using Living Story Narrator"""
        if self.running:
            logger.warning("Pipeline is already running")
            return False
        
        try:
            logger.info("🚀 Starting Living Story Narrator pipeline...")
            
            # Start the Living Story Narrator (includes RSS collection, preprocessing, etc.)
            success = self.living_story_narrator.start_automated_pipeline()
            
            if success:
                self.running = True
                self.stats['start_time'] = datetime.now()
                logger.info("✅ Living Story Narrator pipeline started successfully")
                logger.info("📡 RSS Collection: Every hour")
                logger.info("🔄 Preprocessing: Every 2 hours")
                logger.info("🌙 Story Consolidation: Daily at 2 AM")
                logger.info("📰 Daily Digest: Daily at 6 AM")
                logger.info("🧹 Database Cleanup: Daily at 3 AM")
                return True
            else:
                logger.error("Failed to start Living Story Narrator")
                return False
            
        except Exception as e:
            logger.error(f"Failed to start automated pipeline: {e}")
            self.running = False
            return False
    
    def stop_automated_pipeline(self):
        """Stop the automated pipeline"""
        if not self.running:
            return
        
        try:
            logger.info("🛑 Stopping Living Story Narrator pipeline...")
            self.running = False
            
            # Stop the Living Story Narrator
            self.living_story_narrator.stop_automated_pipeline()
            
            logger.info("✅ Living Story Narrator pipeline stopped")
            
        except Exception as e:
            logger.error(f"Error stopping automated pipeline: {e}")
    
    def _pipeline_loop(self):
        """Main pipeline processing loop"""
        last_processing_run = datetime.now() - timedelta(hours=2)  # Allow immediate run
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Run processing pipeline every 2 hours
                if (current_time - last_processing_run).total_seconds() >= 7200:  # 2 hours
                    logger.info("🔄 Starting automated processing pipeline...")
                    
                    try:
                        self._run_processing_pipeline()
                        last_processing_run = current_time
                        self.stats['pipeline_runs'] += 1
                        self.stats['last_run'] = current_time
                        
                    except Exception as e:
                        error_msg = f"Processing pipeline error: {e}"
                        logger.error(error_msg)
                        self.stats['errors'].append({
                            'timestamp': current_time.isoformat(),
                            'error': error_msg,
                            'type': 'processing_pipeline'
                        })
                
                # Sleep for 5 minutes before next check
                time.sleep(300)
                
            except Exception as e:
                logger.error(f"Pipeline loop error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _run_processing_pipeline(self):
        """Run the complete processing pipeline"""
        pipeline_start = datetime.now()
        logger.info("🔄 Starting processing pipeline...")
        
        try:
            # Step 1: Enhanced preprocessing (deduplication, consolidation, tagging)
            logger.info("📝 Step 1: Enhanced preprocessing...")
            preprocessing_result = self.enhanced_preprocessor.process_new_articles(
                self.config['preprocessing_batch_size']
            )
            
            if preprocessing_result.get('success'):
                self.stats['articles_processed'] += preprocessing_result.get('articles_processed', 0)
                logger.info(f"✅ Enhanced preprocessing: {preprocessing_result.get('master_articles_created', 0)} master articles created")
            else:
                logger.warning(f"⚠️ Enhanced preprocessing failed: {preprocessing_result.get('error', 'Unknown error')}")
            
            # Step 2: Create/update content clusters
            logger.info("🔗 Step 2: Creating content clusters...")
            clusters_created = self._create_content_clusters()
            logger.info(f"✅ Created/updated {clusters_created} content clusters")
            
            # Step 3: Auto-create story threads from clusters
            if self.config['auto_story_creation']:
                logger.info("📰 Step 3: Creating story threads...")
                threads_created = self._create_auto_story_threads()
                self.stats['story_threads_created'] += threads_created
                logger.info(f"✅ Created {threads_created} story threads")
            
            # Step 4: ML Summarization for story threads
            if self.config['ml_summarization']:
                logger.info("🤖 Step 4: Generating ML summaries...")
                summaries_generated = self._generate_story_summaries()
                self.stats['summaries_generated'] += summaries_generated
                logger.info(f"✅ Generated {summaries_generated} ML summaries")
            
            # Step 5: Build RAG context for active story threads
            if self.config['rag_context_building']:
                logger.info("🧠 Step 5: Building RAG context...")
                rag_contexts_built = self._build_rag_contexts()
                self.stats['rag_contexts_built'] += rag_contexts_built
                logger.info(f"✅ Built {rag_contexts_built} RAG contexts")
            
            # Step 6: Update pipeline statistics
            pipeline_duration = (datetime.now() - pipeline_start).total_seconds()
            logger.info(f"🎉 Processing pipeline completed in {pipeline_duration:.1f} seconds")
            
        except Exception as e:
            logger.error(f"Processing pipeline failed: {e}")
            raise
    
    def _get_unprocessed_articles(self) -> List[Dict]:
        """Get articles that need processing"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get articles that haven't been processed yet
            cursor.execute("""
                SELECT id, title, content, source, category, published_at
                FROM articles 
                WHERE processing_status IS NULL OR processing_status = 'pending'
                ORDER BY published_at DESC
                LIMIT %s
            """, (self.config['preprocessing_batch_size'],))
            
            articles = cursor.fetchall()
            conn.close()
            
            return [dict(article) for article in articles]
            
        except Exception as e:
            logger.error(f"Error getting unprocessed articles: {e}")
            return []
    
    def _process_articles_batch(self, articles: List[Dict]) -> int:
        """Process a batch of articles"""
        try:
            processed_count = 0
            
            for article in articles:
                try:
                    # Process article through intelligence orchestrator
                    result = self.intelligence_orchestrator.process_single_article(article['id'])
                    
                    if 'error' not in result:
                        # Update article processing status
                        self._update_article_status(article['id'], 'ml_processed')
                        processed_count += 1
                    else:
                        self._update_article_status(article['id'], 'processing_error')
                        
                except Exception as e:
                    logger.warning(f"Error processing article {article['id']}: {e}")
                    self._update_article_status(article['id'], 'processing_error')
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing articles batch: {e}")
            return 0
    
    def _create_content_clusters(self) -> int:
        """Create content clusters from processed articles"""
        try:
            # Use the intelligence orchestrator to create clusters
            result = self.intelligence_orchestrator.run_full_intelligence_pipeline(
                batch_size=self.config['preprocessing_batch_size']
            )
            
            return result.get('clusters_created', 0)
            
        except Exception as e:
            logger.error(f"Error creating content clusters: {e}")
            return 0
    
    def _create_auto_story_threads(self) -> int:
        """Automatically create story threads from content clusters"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get clusters that don't have associated story threads
            cursor.execute("""
                SELECT ac.id, ac.topic, ac.summary, ac.article_count, ac.cohesion_score
                FROM article_clusters ac
                LEFT JOIN story_threads st ON st.title LIKE '%' || ac.topic || '%'
                WHERE st.id IS NULL 
                AND ac.article_count >= 3
                AND ac.cohesion_score >= %s
                ORDER BY ac.cohesion_score DESC
            """, (self.config['clustering_threshold'],))
            
            clusters = cursor.fetchall()
            threads_created = 0
            
            for cluster in clusters:
                try:
                    # Create story thread from cluster
                    thread_title = f"Auto: {cluster['topic']}"
                    thread_description = cluster['summary'] or f"Automatically generated from {cluster['article_count']} related articles"
                    
                    # Determine category based on topic keywords
                    category = self._determine_category(cluster['topic'])
                    
                    # Create the story thread
                    thread_result = self.prioritization_manager.engine.create_story_thread(
                        title=thread_title,
                        description=thread_description,
                        category=category,
                        priority_level_name='medium',
                        keywords=self._extract_keywords(cluster['topic']),
                        user_created=False
                    )
                    
                    if thread_result and 'thread_id' in thread_result:
                        # Associate articles with the new thread
                        self._associate_cluster_with_thread(cluster['id'], thread_result['thread_id'])
                        threads_created += 1
                        
                except Exception as e:
                    logger.warning(f"Error creating story thread for cluster {cluster['id']}: {e}")
            
            conn.close()
            return threads_created
            
        except Exception as e:
            logger.error(f"Error creating auto story threads: {e}")
            return 0
    
    def _generate_story_summaries(self) -> int:
        """Generate ML summaries for story threads"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get story threads that need summaries
            cursor.execute("""
                SELECT st.id, st.title, st.description, st.category
                FROM story_threads st
                LEFT JOIN story_summaries ss ON ss.thread_id = st.id
                WHERE st.status = 'active'
                AND (ss.id IS NULL OR ss.updated_at < st.updated_at)
                ORDER BY st.priority_level_id DESC, st.updated_at DESC
                LIMIT 10
            """)
            
            threads = cursor.fetchall()
            summaries_generated = 0
            
            for thread in threads:
                try:
                    # Get articles for this thread
                    cursor.execute("""
                        SELECT a.id, a.title, a.content, a.summary
                        FROM articles a
                        JOIN content_priority_assignments cpa ON cpa.article_id = a.id
                        WHERE cpa.thread_id = %s
                        AND a.processing_status = 'ml_processed'
                        ORDER BY a.published_at DESC
                        LIMIT 20
                    """, (thread['id'],))
                    
                    articles = cursor.fetchall()
                    
                    if articles:
                        # Generate summary using ML service
                        summary_result = self.summarization_service.generate_story_summary(
                            thread_id=thread['id'],
                            articles=[dict(article) for article in articles],
                            summary_type='comprehensive'
                        )
                        
                        if summary_result and 'summary' in summary_result:
                            # Store the summary
                            self._store_story_summary(thread['id'], summary_result)
                            summaries_generated += 1
                            
                except Exception as e:
                    logger.warning(f"Error generating summary for thread {thread['id']}: {e}")
            
            conn.close()
            return summaries_generated
            
        except Exception as e:
            logger.error(f"Error generating story summaries: {e}")
            return 0
    
    def _build_rag_contexts(self) -> int:
        """Build RAG context for active story threads"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get active story threads that need RAG context updates
            cursor.execute("""
                SELECT st.id, st.title, st.updated_at
                FROM story_threads st
                WHERE st.status = 'active'
                AND st.updated_at >= NOW() - INTERVAL '24 hours'
                ORDER BY st.priority_level_id DESC
                LIMIT 5
            """)
            
            threads = cursor.fetchall()
            contexts_built = 0
            
            for thread in threads:
                try:
                    # Build RAG context
                    context_result = self.rag_builder.build_context_for_thread(thread['id'])
                    
                    if context_result and 'context_summary' in context_result:
                        contexts_built += 1
                        
                except Exception as e:
                    logger.warning(f"Error building RAG context for thread {thread['id']}: {e}")
            
            conn.close()
            return contexts_built
            
        except Exception as e:
            logger.error(f"Error building RAG contexts: {e}")
            return 0
    
    def _determine_category(self, topic: str) -> str:
        """Determine category based on topic keywords"""
        topic_lower = topic.lower()
        
        if any(word in topic_lower for word in ['politics', 'election', 'government', 'congress', 'senate', 'president']):
            return 'Politics'
        elif any(word in topic_lower for word in ['health', 'medical', 'disease', 'vaccine', 'covid', 'pandemic']):
            return 'Health'
        elif any(word in topic_lower for word in ['science', 'research', 'technology', 'ai', 'space', 'climate']):
            return 'Science & Technology'
        elif any(word in topic_lower for word in ['economy', 'business', 'market', 'finance', 'trade']):
            return 'Business & Economy'
        elif any(word in topic_lower for word in ['war', 'conflict', 'military', 'defense', 'security']):
            return 'International Affairs'
        elif any(word in topic_lower for word in ['disaster', 'earthquake', 'flood', 'fire', 'storm']):
            return 'Disasters & Events'
        else:
            return 'General'
    
    def _extract_keywords(self, topic: str) -> List[str]:
        """Extract keywords from topic"""
        import re
        
        # Remove common words and extract meaningful terms
        common_words = {'the', 'and', 'for', 'with', 'this', 'that', 'have', 'been', 'will', 'from', 'auto'}
        words = re.findall(r'\b\w+\b', topic.lower())
        
        keywords = [word for word in words if len(word) > 3 and word not in common_words]
        return keywords[:5]  # Limit to 5 keywords
    
    def _associate_cluster_with_thread(self, cluster_id: int, thread_id: int):
        """Associate cluster articles with story thread"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get articles in the cluster
            cursor.execute("""
                SELECT ca.article_id
                FROM cluster_articles ca
                WHERE ca.cluster_id = %s
            """, (cluster_id,))
            
            article_ids = [row[0] for row in cursor.fetchall()]
            
            # Associate articles with the story thread
            for article_id in article_ids:
                cursor.execute("""
                    INSERT INTO content_priority_assignments (article_id, thread_id, priority_level_id)
                    VALUES (%s, %s, 2)
                    ON CONFLICT (article_id, thread_id) DO NOTHING
                """, (article_id, thread_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error associating cluster with thread: {e}")
    
    def _update_article_status(self, article_id: int, status: str):
        """Update article processing status"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE articles 
                SET processing_status = %s, updated_at = NOW()
                WHERE id = %s
            """, (status, article_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating article status: {e}")
    
    def _store_story_summary(self, thread_id: int, summary_result: Dict):
        """Store story summary in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Create story_summaries table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS story_summaries (
                    id SERIAL PRIMARY KEY,
                    thread_id INTEGER REFERENCES story_threads(id) ON DELETE CASCADE,
                    summary_type VARCHAR(50) DEFAULT 'comprehensive',
                    summary_text TEXT NOT NULL,
                    key_points TEXT[],
                    confidence_score DECIMAL(3,2),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Insert or update summary
            cursor.execute("""
                INSERT INTO story_summaries (thread_id, summary_type, summary_text, key_points, confidence_score)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (thread_id, summary_type) 
                DO UPDATE SET 
                    summary_text = EXCLUDED.summary_text,
                    key_points = EXCLUDED.key_points,
                    confidence_score = EXCLUDED.confidence_score,
                    updated_at = NOW()
            """, (
                thread_id,
                summary_result.get('summary_type', 'comprehensive'),
                summary_result.get('summary', ''),
                summary_result.get('key_points', []),
                summary_result.get('confidence_score', 0.8)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing story summary: {e}")
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        try:
            # Get RSS scheduler status
            rss_status = self.feed_scheduler.get_status()
            
            # Get intelligence orchestrator status
            intelligence_status = self.intelligence_orchestrator.get_intelligence_status()
            
            # Get database statistics
            db_stats = self._get_database_statistics()
            
            return {
                'pipeline': {
                    'running': self.running,
                    'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
                    'last_run': self.stats['last_run'].isoformat() if self.stats['last_run'] else None,
                    'pipeline_runs': self.stats['pipeline_runs'],
                    'configuration': self.config,
                    'statistics': self.stats
                },
                'rss_collection': rss_status,
                'intelligence_processing': intelligence_status,
                'database': db_stats,
                'system_health': self._assess_system_health()
            }
            
        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            return {'error': str(e)}
    
    def _get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            stats = {}
            
            # Article statistics
            cursor.execute("SELECT COUNT(*) as total FROM articles")
            stats['total_articles'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as processed FROM articles WHERE processing_status = 'ml_processed'")
            stats['processed_articles'] = cursor.fetchone()['processed']
            
            # Story thread statistics
            cursor.execute("SELECT COUNT(*) as total FROM story_threads")
            stats['total_story_threads'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as active FROM story_threads WHERE status = 'active'")
            stats['active_story_threads'] = cursor.fetchone()['active']
            
            # Cluster statistics
            cursor.execute("SELECT COUNT(*) as total FROM article_clusters")
            stats['total_clusters'] = cursor.fetchone()['total']
            
            # Summary statistics
            cursor.execute("SELECT COUNT(*) as total FROM story_summaries")
            stats['total_summaries'] = cursor.fetchone()['total']
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {}
    
    def _assess_system_health(self) -> str:
        """Assess overall system health"""
        try:
            # Check for recent errors
            recent_errors = [e for e in self.stats['errors'] 
                           if datetime.fromisoformat(e['timestamp']) > datetime.now() - timedelta(hours=1)]
            
            if len(recent_errors) > 5:
                return 'critical'
            elif len(recent_errors) > 2:
                return 'warning'
            else:
                return 'healthy'
                
        except Exception:
            return 'unknown'
    
    def trigger_manual_collection(self) -> Dict[str, Any]:
        """Trigger manual RSS collection"""
        try:
            logger.info("🔄 Triggering manual RSS collection...")
            result = self.feed_scheduler.collect_now()
            
            if result.get('feeds_successful', 0) > 0:
                self.stats['articles_collected'] += result.get('new_articles', 0)
                logger.info(f"✅ Manual collection completed: {result.get('new_articles', 0)} new articles")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in manual collection: {e}")
            return {'error': str(e)}
    
    def trigger_manual_processing(self) -> Dict[str, Any]:
        """Trigger manual processing pipeline"""
        try:
            logger.info("🔄 Triggering manual processing pipeline...")
            self._run_processing_pipeline()
            
            return {
                'success': True,
                'message': 'Manual processing completed',
                'statistics': self.stats
            }
            
        except Exception as e:
            logger.error(f"Error in manual processing: {e}")
            return {'error': str(e)}
    
    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """Update pipeline configuration"""
        try:
            # Validate configuration
            if 'rss_interval_minutes' in new_config:
                if new_config['rss_interval_minutes'] < 5:
                    logger.warning("RSS interval too short, minimum is 5 minutes")
                    return False
            
            # Update configuration
            self.config.update(new_config)
            
            # Restart RSS scheduler if interval changed
            if 'rss_interval_minutes' in new_config and self.running:
                self.feed_scheduler.update_collection_interval(new_config['rss_interval_minutes'])
            
            logger.info(f"Pipeline configuration updated: {new_config}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    def close(self):
        """Close all connections and stop services"""
        try:
            self.stop_automated_pipeline()
            self.intelligence_orchestrator.close()
            logger.info("Pipeline orchestrator closed")
        except Exception as e:
            logger.error(f"Error closing pipeline orchestrator: {e}")
