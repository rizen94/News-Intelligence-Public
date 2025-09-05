#!/usr/bin/env python3
"""
Feedback Loop System for News Intelligence System v3.0
Implements the closed feedback loop for continuous story enhancement and context growth
"""

import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import threading
import time
import schedule

from .story_control_system import StoryControlSystem, StoryExpectation
from .story_discovery_system import StoryDiscoverySystem, WeeklyDigest
from ..ml.iterative_rag_service import IterativeRAGService, RAGDossier

logger = logging.getLogger(__name__)

@dataclass
class FeedbackLoopStatus:
    """Status of the feedback loop system"""
    is_running: bool
    last_run: str
    stories_being_tracked: int
    articles_processed_today: int
    rag_enhancements_triggered: int
    new_articles_found: int
    context_growth_percentage: float
    next_scheduled_run: str

class FeedbackLoopSystem:
    """
    Closed feedback loop system for continuous story enhancement and context growth
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize feedback loop system
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        
        # Initialize subsystems
        self.story_control = StoryControlSystem(db_config)
        self.story_discovery = StoryDiscoverySystem(db_config)
        self.rag_service = IterativeRAGService(db_config)
        
        # Feedback loop state
        self.is_running = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        
        # Statistics
        self.stats = {
            'stories_tracked': 0,
            'articles_processed': 0,
            'rag_enhancements': 0,
            'new_articles_found': 0,
            'context_growth': 0.0,
            'last_run': None
        }
        
        # Initialize database tables
        self._init_database_tables()
    
    def _init_database_tables(self):
        """Initialize database tables for feedback loop"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Feedback loop status table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback_loop_status (
                    status_id SERIAL PRIMARY KEY,
                    is_running BOOLEAN DEFAULT false,
                    last_run TIMESTAMP,
                    stories_being_tracked INTEGER DEFAULT 0,
                    articles_processed_today INTEGER DEFAULT 0,
                    rag_enhancements_triggered INTEGER DEFAULT 0,
                    new_articles_found INTEGER DEFAULT 0,
                    context_growth_percentage DECIMAL(5,2) DEFAULT 0.0,
                    next_scheduled_run TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Story enhancement log table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_enhancement_log (
                    log_id SERIAL PRIMARY KEY,
                    story_id VARCHAR(50) NOT NULL,
                    article_id INTEGER,
                    enhancement_type VARCHAR(50) NOT NULL,
                    triggered_at TIMESTAMP DEFAULT NOW(),
                    status VARCHAR(20) DEFAULT 'pending',
                    results JSONB,
                    error_message TEXT
                )
            """)
            
            # Context growth tracking table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS context_growth_tracking (
                    tracking_id SERIAL PRIMARY KEY,
                    story_id VARCHAR(50) NOT NULL,
                    week_start TIMESTAMP NOT NULL,
                    initial_article_count INTEGER,
                    final_article_count INTEGER,
                    new_articles_found INTEGER,
                    context_enhancements INTEGER,
                    growth_percentage DECIMAL(5,2),
                    tracked_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            
            self.logger.info("Feedback loop database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize feedback loop database: {e}")
            raise
    
    def start_feedback_loop(self):
        """Start the feedback loop system"""
        try:
            if self.is_running:
                self.logger.warning("Feedback loop is already running")
                return
            
            self.is_running = True
            self.stop_event.clear()
            
            # Start worker thread
            self.worker_thread = threading.Thread(
                target=self._feedback_loop_worker,
                name="FeedbackLoopWorker",
                daemon=True
            )
            self.worker_thread.start()
            
            # Schedule regular tasks
            self._schedule_tasks()
            
            self.logger.info("Feedback loop system started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start feedback loop: {e}")
            raise
    
    def stop_feedback_loop(self):
        """Stop the feedback loop system"""
        try:
            if not self.is_running:
                return
            
            self.is_running = False
            self.stop_event.set()
            
            # Wait for worker thread to finish
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=30)
            
            self.logger.info("Feedback loop system stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop feedback loop: {e}")
    
    def _feedback_loop_worker(self):
        """Main worker loop for the feedback system"""
        while self.is_running and not self.stop_event.is_set():
            try:
                # Run feedback loop cycle
                self._run_feedback_cycle()
                
                # Update statistics
                self._update_statistics()
                
                # Wait before next cycle (5 minutes)
                self.stop_event.wait(300)
                
            except Exception as e:
                self.logger.error(f"Error in feedback loop worker: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _run_feedback_cycle(self):
        """Run a single feedback cycle"""
        try:
            self.logger.info("Starting feedback loop cycle")
            
            # Step 1: Process new articles for existing stories
            self._process_new_articles_for_stories()
            
            # Step 2: Trigger RAG enhancements for updated stories
            self._trigger_rag_enhancements()
            
            # Step 3: Update story contexts
            self._update_story_contexts()
            
            # Step 4: Search for new related articles
            self._search_for_new_related_articles()
            
            # Step 5: Update context growth tracking
            self._update_context_growth_tracking()
            
            self.logger.info("Feedback loop cycle completed")
            
        except Exception as e:
            self.logger.error(f"Error in feedback cycle: {e}")
    
    def _process_new_articles_for_stories(self):
        """Process new articles against existing story expectations"""
        try:
            # Get active stories
            active_stories = self.story_control.get_active_stories()
            
            if not active_stories:
                return
            
            # Get new articles from last 24 hours
            since_date = datetime.now() - timedelta(hours=24)
            new_articles = self._get_new_articles(since_date)
            
            if not new_articles:
                return
            
            self.logger.info(f"Processing {len(new_articles)} new articles against {len(active_stories)} active stories")
            
            # Process each article against each story
            for article in new_articles:
                for story in active_stories:
                    # Evaluate article against story
                    match_result = self.story_control.evaluate_article_for_story(
                        article['id'], story.story_id
                    )
                    
                    if match_result.get('match', False):
                        self.logger.info(f"Article {article['id']} matches story {story.story_id}")
                        
                        # Add article to story thread
                        self._add_article_to_story_thread(story.story_id, article['id'])
                        
                        # Update statistics
                        self.stats['articles_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Error processing new articles for stories: {e}")
    
    def _trigger_rag_enhancements(self):
        """Trigger RAG enhancements for stories with new articles"""
        try:
            # Get stories that need enhancement
            stories_to_enhance = self._get_stories_needing_enhancement()
            
            for story_id in stories_to_enhance:
                try:
                    # Trigger RAG enhancement
                    self._enhance_story_with_rag(story_id)
                    
                    # Update statistics
                    self.stats['rag_enhancements'] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error enhancing story {story_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error triggering RAG enhancements: {e}")
    
    def _enhance_story_with_rag(self, story_id: str):
        """Enhance a story using RAG service"""
        try:
            # Get story context
            story_context = self._get_story_context(story_id)
            
            if not story_context:
                return
            
            # Create or update RAG dossier
            dossier = self.rag_service.create_dossier(
                article_id=story_context['primary_article_id'],
                initial_keywords=story_context['keywords']
            )
            
            # Run iterative RAG enhancement
            enhancement_result = self.rag_service.enhance_dossier_iteratively(
                dossier.dossier_id,
                max_iterations=5
            )
            
            if enhancement_result.get('success', False):
                # Find new related articles
                new_articles = self._find_related_articles_from_rag(
                    story_id, enhancement_result
                )
                
                # Add new articles to story
                for article_id in new_articles:
                    self._add_article_to_story_thread(story_id, article_id)
                
                # Update statistics
                self.stats['new_articles_found'] += len(new_articles)
                
                self.logger.info(f"Enhanced story {story_id} with {len(new_articles)} new articles")
            
        except Exception as e:
            self.logger.error(f"Error enhancing story with RAG: {e}")
    
    def _update_story_contexts(self):
        """Update story contexts with new information"""
        try:
            # Get all active stories
            active_stories = self.story_control.get_active_stories()
            
            for story in active_stories:
                # Update story context
                self._update_story_context(story.story_id)
            
        except Exception as e:
            self.logger.error(f"Error updating story contexts: {e}")
    
    def _search_for_new_related_articles(self):
        """Search for new related articles using enhanced contexts"""
        try:
            # Get stories with enhanced contexts
            enhanced_stories = self._get_stories_with_enhanced_contexts()
            
            for story_id in enhanced_stories:
                # Search for new articles using enhanced context
                new_articles = self._search_articles_with_enhanced_context(story_id)
                
                # Add new articles to story
                for article_id in new_articles:
                    self._add_article_to_story_thread(story_id, article_id)
                
                # Update statistics
                self.stats['new_articles_found'] += len(new_articles)
            
        except Exception as e:
            self.logger.error(f"Error searching for new related articles: {e}")
    
    def _update_context_growth_tracking(self):
        """Update context growth tracking for all stories"""
        try:
            # Get all active stories
            active_stories = self.story_control.get_active_stories()
            
            for story in active_stories:
                # Calculate context growth
                growth_data = self._calculate_context_growth(story.story_id)
                
                if growth_data:
                    # Store growth tracking data
                    self._store_context_growth_tracking(story.story_id, growth_data)
            
        except Exception as e:
            self.logger.error(f"Error updating context growth tracking: {e}")
    
    def _schedule_tasks(self):
        """Schedule regular tasks for the feedback loop"""
        try:
            # Schedule weekly digest generation (every Monday at 9 AM)
            schedule.every().monday.at("09:00").do(self._generate_weekly_digest_task)
            
            # Schedule story discovery (every Tuesday at 10 AM)
            schedule.every().tuesday.at("10:00").do(self._run_story_discovery_task)
            
            # Schedule context growth analysis (every Friday at 2 PM)
            schedule.every().friday.at("14:00").do(self._analyze_context_growth_task)
            
            self.logger.info("Scheduled tasks configured")
            
        except Exception as e:
            self.logger.error(f"Error scheduling tasks: {e}")
    
    def _generate_weekly_digest_task(self):
        """Generate weekly digest (scheduled task)"""
        try:
            self.logger.info("Generating weekly digest...")
            digest = self.story_discovery.generate_weekly_digest()
            self.logger.info(f"Weekly digest generated: {digest.digest_id}")
        except Exception as e:
            self.logger.error(f"Error generating weekly digest: {e}")
    
    def _run_story_discovery_task(self):
        """Run story discovery (scheduled task)"""
        try:
            self.logger.info("Running story discovery...")
            # This would analyze new content and suggest new stories
            # Implementation depends on your specific needs
            self.logger.info("Story discovery completed")
        except Exception as e:
            self.logger.error(f"Error running story discovery: {e}")
    
    def _analyze_context_growth_task(self):
        """Analyze context growth (scheduled task)"""
        try:
            self.logger.info("Analyzing context growth...")
            # This would analyze how much context has grown for each story
            # Implementation depends on your specific needs
            self.logger.info("Context growth analysis completed")
        except Exception as e:
            self.logger.error(f"Error analyzing context growth: {e}")
    
    def get_feedback_loop_status(self) -> FeedbackLoopStatus:
        """Get current feedback loop status"""
        try:
            return FeedbackLoopStatus(
                is_running=self.is_running,
                last_run=self.stats['last_run'],
                stories_being_tracked=self.stats['stories_tracked'],
                articles_processed_today=self.stats['articles_processed'],
                rag_enhancements_triggered=self.stats['rag_enhancements'],
                new_articles_found=self.stats['new_articles_found'],
                context_growth_percentage=self.stats['context_growth'],
                next_scheduled_run=self._get_next_scheduled_run()
            )
        except Exception as e:
            self.logger.error(f"Error getting feedback loop status: {e}")
            return FeedbackLoopStatus(
                is_running=False,
                last_run=None,
                stories_being_tracked=0,
                articles_processed_today=0,
                rag_enhancements_triggered=0,
                new_articles_found=0,
                context_growth_percentage=0.0,
                next_scheduled_run=None
            )
    
    def _get_new_articles(self, since_date: datetime) -> List[Dict[str, Any]]:
        """Get new articles since a specific date"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, title, content, summary, source, category, published_date,
                       quality_score, sentiment_score, url
                FROM articles
                WHERE published_date >= %s
                ORDER BY published_date DESC
            """, (since_date,))
            
            articles = []
            for row in cur.fetchall():
                article = {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'summary': row[3],
                    'source': row[4],
                    'category': row[5],
                    'published_date': row[6],
                    'quality_score': row[7],
                    'sentiment_score': row[8],
                    'url': row[9]
                }
                articles.append(article)
            
            cur.close()
            conn.close()
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error getting new articles: {e}")
            return []
    
    def _add_article_to_story_thread(self, story_id: str, article_id: int):
        """Add article to story thread"""
        try:
            # This would add the article to the story thread
            # Implementation depends on your story thread system
            self.logger.info(f"Added article {article_id} to story thread {story_id}")
        except Exception as e:
            self.logger.error(f"Error adding article to story thread: {e}")
    
    def _get_stories_needing_enhancement(self) -> List[str]:
        """Get stories that need RAG enhancement"""
        try:
            # This would identify stories that have new articles and need enhancement
            # Implementation depends on your specific logic
            return []
        except Exception as e:
            self.logger.error(f"Error getting stories needing enhancement: {e}")
            return []
    
    def _get_story_context(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Get story context for RAG enhancement"""
        try:
            # This would get the current context for a story
            # Implementation depends on your story context system
            return None
        except Exception as e:
            self.logger.error(f"Error getting story context: {e}")
            return None
    
    def _find_related_articles_from_rag(self, story_id: str, rag_result: Dict[str, Any]) -> List[int]:
        """Find related articles from RAG enhancement result"""
        try:
            # This would extract article IDs from RAG enhancement results
            # Implementation depends on your RAG service
            return []
        except Exception as e:
            self.logger.error(f"Error finding related articles from RAG: {e}")
            return []
    
    def _get_stories_with_enhanced_contexts(self) -> List[str]:
        """Get stories with enhanced contexts"""
        try:
            # This would identify stories with recently enhanced contexts
            # Implementation depends on your context enhancement system
            return []
        except Exception as e:
            self.logger.error(f"Error getting stories with enhanced contexts: {e}")
            return []
    
    def _search_articles_with_enhanced_context(self, story_id: str) -> List[int]:
        """Search for articles using enhanced context"""
        try:
            # This would search for new articles using the enhanced context
            # Implementation depends on your search system
            return []
        except Exception as e:
            self.logger.error(f"Error searching articles with enhanced context: {e}")
            return []
    
    def _update_story_context(self, story_id: str):
        """Update story context with new information"""
        try:
            # This would update the story context with new information
            # Implementation depends on your context update system
            pass
        except Exception as e:
            self.logger.error(f"Error updating story context: {e}")
    
    def _calculate_context_growth(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Calculate context growth for a story"""
        try:
            # This would calculate how much the context has grown
            # Implementation depends on your growth calculation logic
            return None
        except Exception as e:
            self.logger.error(f"Error calculating context growth: {e}")
            return None
    
    def _store_context_growth_tracking(self, story_id: str, growth_data: Dict[str, Any]):
        """Store context growth tracking data"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO context_growth_tracking 
                (story_id, week_start, initial_article_count, final_article_count,
                 new_articles_found, context_enhancements, growth_percentage)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                story_id,
                growth_data.get('week_start'),
                growth_data.get('initial_article_count', 0),
                growth_data.get('final_article_count', 0),
                growth_data.get('new_articles_found', 0),
                growth_data.get('context_enhancements', 0),
                growth_data.get('growth_percentage', 0.0)
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error storing context growth tracking: {e}")
    
    def _update_statistics(self):
        """Update feedback loop statistics"""
        try:
            self.stats['last_run'] = datetime.now().isoformat()
            self.stats['stories_tracked'] = len(self.story_control.get_active_stories())
            
            # Store statistics in database
            self._store_feedback_loop_status()
            
        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")
    
    def _store_feedback_loop_status(self):
        """Store feedback loop status in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO feedback_loop_status 
                (is_running, last_run, stories_being_tracked, articles_processed_today,
                 rag_enhancements_triggered, new_articles_found, context_growth_percentage)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                self.is_running,
                self.stats['last_run'],
                self.stats['stories_tracked'],
                self.stats['articles_processed'],
                self.stats['rag_enhancements'],
                self.stats['new_articles_found'],
                self.stats['context_growth']
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error storing feedback loop status: {e}")
    
    def _get_next_scheduled_run(self) -> Optional[str]:
        """Get next scheduled run time"""
        try:
            # This would get the next scheduled run time
            # Implementation depends on your scheduling system
            return None
        except Exception as e:
            self.logger.error(f"Error getting next scheduled run: {e}")
            return None
