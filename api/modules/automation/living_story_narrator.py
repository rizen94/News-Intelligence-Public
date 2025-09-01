#!/usr/bin/env python3
"""
Living Story Narrator
Automated system for continuous story consolidation, evolution, and cleanup
"""

import os
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, time
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict, Counter
import schedule
import threading
import time as time_module

# Import our services
from .enhanced_preprocessor import EnhancedPreprocessor
from ..ml.summarization_service import MLSummarizationService
from ..prioritization.rag_context_builder import RAGContextBuilder
from ..prioritization.content_prioritization_manager import ContentPrioritizationManager

logger = logging.getLogger(__name__)

class LivingStoryNarrator:
    """Living Story Narrator - Automated story consolidation and evolution system"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.running = False
        self.scheduler_thread = None
        
        # Initialize services
        self.preprocessor = EnhancedPreprocessor(db_config)
        self.ml_service = MLSummarizationService()
        self.rag_builder = RAGContextBuilder(db_config)
        self.prioritization_manager = ContentPrioritizationManager(db_config)
        
        # Configuration
        self.config = {
            # Pipeline timing
            'rss_collection_interval_hours': 1,  # Collect RSS every hour
            'preprocessing_interval_hours': 2,   # Process new articles every 2 hours
            'story_consolidation_time': '02:00', # Overnight consolidation at 2 AM
            'daily_digest_time': '06:00',        # Daily digest at 6 AM
            'cleanup_time': '03:00',             # Database cleanup at 3 AM
            
            # Processing parameters
            'max_articles_per_batch': 100,
            'story_similarity_threshold': 0.8,
            'min_sources_for_story': 2,
            'max_daily_digest_stories': 20,
            'story_evolution_window_days': 7,
            
            # Cleanup parameters
            'archive_old_articles_days': 30,
            'remove_orphaned_articles_days': 7,
            'consolidate_old_stories_days': 14
        }
        
        # Statistics
        self.stats = {
            'total_pipeline_runs': 0,
            'articles_processed': 0,
            'stories_consolidated': 0,
            'daily_digests_generated': 0,
            'database_cleanups': 0,
            'last_rss_collection': None,
            'last_preprocessing': None,
            'last_consolidation': None,
            'last_digest': None,
            'last_cleanup': None
        }
    
    def start_automated_pipeline(self) -> bool:
        """Start the fully automated living story narrator pipeline"""
        try:
            if self.running:
                logger.warning("Living Story Narrator is already running")
                return False
            
            logger.info("🚀 Starting Living Story Narrator...")
            
            # Schedule all automated tasks
            self._schedule_automated_tasks()
            
            # Start the scheduler in a separate thread
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            # Run initial processing
            self._run_initial_processing()
            
            logger.info("✅ Living Story Narrator started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Living Story Narrator: {e}")
            return False
    
    def stop_automated_pipeline(self):
        """Stop the automated pipeline"""
        try:
            logger.info("🛑 Stopping Living Story Narrator...")
            self.running = False
            
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=5)
            
            schedule.clear()
            logger.info("✅ Living Story Narrator stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Living Story Narrator: {e}")
    
    def _schedule_automated_tasks(self):
        """Schedule all automated tasks"""
        try:
            # Clear existing schedules
            schedule.clear()
            
            # RSS Collection - Every hour
            schedule.every(self.config['rss_collection_interval_hours']).hours.do(
                self._scheduled_rss_collection
            )
            
            # Preprocessing - Every 2 hours
            schedule.every(self.config['preprocessing_interval_hours']).hours.do(
                self._scheduled_preprocessing
            )
            
            # Overnight Story Consolidation - 2 AM daily
            schedule.every().day.at(self.config['story_consolidation_time']).do(
                self._scheduled_story_consolidation
            )
            
            # Daily Digest Generation - 6 AM daily
            schedule.every().day.at(self.config['daily_digest_time']).do(
                self._scheduled_daily_digest
            )
            
            # Database Cleanup - 3 AM daily
            schedule.every().day.at(self.config['cleanup_time']).do(
                self._scheduled_database_cleanup
            )
            
            logger.info("📅 Scheduled automated tasks:")
            logger.info(f"   - RSS Collection: Every {self.config['rss_collection_interval_hours']} hours")
            logger.info(f"   - Preprocessing: Every {self.config['preprocessing_interval_hours']} hours")
            logger.info(f"   - Story Consolidation: Daily at {self.config['story_consolidation_time']}")
            logger.info(f"   - Daily Digest: Daily at {self.config['daily_digest_time']}")
            logger.info(f"   - Database Cleanup: Daily at {self.config['cleanup_time']}")
            
        except Exception as e:
            logger.error(f"Error scheduling automated tasks: {e}")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.running:
            try:
                schedule.run_pending()
                time_module.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time_module.sleep(60)
    
    def _run_initial_processing(self):
        """Run initial processing when the system starts"""
        try:
            logger.info("🔄 Running initial processing...")
            
            # Process any existing unprocessed articles
            self._scheduled_preprocessing()
            
            # Generate daily digest if it's past the scheduled time
            current_time = datetime.now().time()
            digest_time = datetime.strptime(self.config['daily_digest_time'], '%H:%M').time()
            
            if current_time > digest_time:
                logger.info("📰 Generating initial daily digest...")
                self._scheduled_daily_digest()
            
        except Exception as e:
            logger.error(f"Error in initial processing: {e}")
    
    def _scheduled_rss_collection(self):
        """Scheduled RSS collection task"""
        try:
            logger.info("📡 Scheduled RSS collection starting...")
            
            # Import here to avoid circular imports
            from ..data_collection.rss_feed_service import RSSFeedService
            
            rss_service = RSSFeedService(self.db_config)
            result = rss_service.collect_all_feeds()
            
            if result.get('success'):
                self.stats['last_rss_collection'] = datetime.now()
                logger.info(f"✅ RSS collection completed: {result.get('articles_collected', 0)} new articles")
            else:
                logger.warning(f"⚠️ RSS collection failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled RSS collection: {e}")
    
    def _scheduled_preprocessing(self):
        """Scheduled preprocessing task"""
        try:
            logger.info("📝 Scheduled preprocessing starting...")
            
            result = self.preprocessor.process_new_articles(
                self.config['max_articles_per_batch']
            )
            
            if result.get('success'):
                self.stats['articles_processed'] += result.get('articles_processed', 0)
                self.stats['last_preprocessing'] = datetime.now()
                logger.info(f"✅ Preprocessing completed: {result.get('master_articles_created', 0)} master articles")
            else:
                logger.warning(f"⚠️ Preprocessing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled preprocessing: {e}")
    
    def _scheduled_story_consolidation(self):
        """Scheduled overnight story consolidation"""
        try:
            logger.info("🌙 Scheduled story consolidation starting...")
            
            # Consolidate stories from the past week
            consolidation_result = self._consolidate_evolving_stories()
            
            if consolidation_result.get('success'):
                self.stats['stories_consolidated'] += consolidation_result.get('stories_consolidated', 0)
                self.stats['last_consolidation'] = datetime.now()
                logger.info(f"✅ Story consolidation completed: {consolidation_result.get('stories_consolidated', 0)} stories consolidated")
            else:
                logger.warning(f"⚠️ Story consolidation failed: {consolidation_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled story consolidation: {e}")
    
    def _scheduled_daily_digest(self):
        """Scheduled daily digest generation"""
        try:
            logger.info("📰 Scheduled daily digest generation starting...")
            
            digest_result = self._generate_daily_digest()
            
            if digest_result.get('success'):
                self.stats['daily_digests_generated'] += 1
                self.stats['last_digest'] = datetime.now()
                logger.info(f"✅ Daily digest generated: {digest_result.get('stories_included', 0)} stories")
            else:
                logger.warning(f"⚠️ Daily digest generation failed: {digest_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled daily digest: {e}")
    
    def _scheduled_database_cleanup(self):
        """Scheduled database cleanup"""
        try:
            logger.info("🧹 Scheduled database cleanup starting...")
            
            cleanup_result = self._perform_database_cleanup()
            
            if cleanup_result.get('success'):
                self.stats['database_cleanups'] += 1
                self.stats['last_cleanup'] = datetime.now()
                logger.info(f"✅ Database cleanup completed: {cleanup_result.get('articles_archived', 0)} articles archived")
            else:
                logger.warning(f"⚠️ Database cleanup failed: {cleanup_result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in scheduled database cleanup: {e}")
    
    def _consolidate_evolving_stories(self) -> Dict[str, Any]:
        """Consolidate evolving stories over time"""
        try:
            logger.info("🔄 Consolidating evolving stories...")
            
            # Get stories from the past week that might need consolidation
            cutoff_date = datetime.now() - timedelta(days=self.config['story_evolution_window_days'])
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Find stories that might be related
            cursor.execute("""
                SELECT id, title, content, summary, sources, source_count, 
                       source_priority, category, published_at, tags
                FROM master_articles
                WHERE published_at >= %s
                AND source_count >= %s
                ORDER BY source_priority DESC, published_at DESC
            """, (cutoff_date, self.config['min_sources_for_story']))
            
            recent_stories = cursor.fetchall()
            
            if not recent_stories:
                conn.close()
                return {'success': True, 'stories_consolidated': 0, 'message': 'No stories to consolidate'}
            
            # Group similar stories using content similarity
            story_groups = self._group_similar_stories([dict(story) for story in recent_stories])
            
            consolidated_count = 0
            
            for group in story_groups:
                if len(group) > 1:
                    # Consolidate similar stories
                    consolidated_story = self._create_evolved_story(group)
                    
                    if consolidated_story:
                        # Store the evolved story
                        story_id = self._store_evolved_story(consolidated_story, group)
                        
                        if story_id:
                            consolidated_count += 1
                            logger.info(f"📰 Consolidated {len(group)} stories into evolved story: {consolidated_story['title'][:50]}...")
            
            conn.close()
            
            return {
                'success': True,
                'stories_consolidated': consolidated_count,
                'groups_processed': len(story_groups)
            }
            
        except Exception as e:
            logger.error(f"Error consolidating evolving stories: {e}")
            return {'success': False, 'error': str(e)}
    
    def _group_similar_stories(self, stories: List[Dict]) -> List[List[Dict]]:
        """Group similar stories for consolidation"""
        try:
            if len(stories) < 2:
                return [stories]
            
            # Use the same similarity approach as the preprocessor
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            from sklearn.cluster import DBSCAN
            
            # Prepare text for similarity analysis
            story_texts = []
            for story in stories:
                text = f"{story['title']} {story.get('content', '') or story.get('summary', '')}"
                story_texts.append(text)
            
            # Calculate similarity
            vectorizer = TfidfVectorizer(max_features=1000, stop_words='english', ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(story_texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Cluster similar stories
            distance_matrix = 1 - similarity_matrix
            clustering = DBSCAN(
                eps=1 - self.config['story_similarity_threshold'],
                min_samples=1,
                metric='precomputed'
            )
            
            cluster_labels = clustering.fit_predict(distance_matrix)
            
            # Group stories by cluster
            groups = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                if label != -1:  # Ignore noise
                    groups[label].append(stories[i])
            
            return list(groups.values())
            
        except Exception as e:
            logger.error(f"Error grouping similar stories: {e}")
            return [stories]
    
    def _create_evolved_story(self, story_group: List[Dict]) -> Optional[Dict]:
        """Create an evolved story from a group of similar stories"""
        try:
            if not story_group:
                return None
            
            # Sort by source priority and recency
            story_group.sort(key=lambda x: (x.get('source_priority', 0), x.get('published_at', datetime.min)), reverse=True)
            
            base_story = story_group[0]
            
            # Combine all sources
            all_sources = set()
            for story in story_group:
                sources = story.get('sources', [])
                if isinstance(sources, str):
                    sources = json.loads(sources)
                all_sources.update(sources)
            
            # Calculate evolved priority
            evolved_priority = min(3.0, base_story.get('source_priority', 1.0) + (len(story_group) - 1) * 0.3)
            
            # Generate evolved summary
            evolved_summary = self._generate_evolved_summary(story_group)
            
            # Combine tags
            all_tags = []
            for story in story_group:
                tags = story.get('tags', [])
                if isinstance(tags, str):
                    tags = json.loads(tags)
                all_tags.extend(tags)
            
            # Rank and deduplicate tags
            tag_counts = Counter([tag.get('text', '') for tag in all_tags if tag.get('text')])
            evolved_tags = []
            
            for tag_text, count in tag_counts.most_common():
                score = min(1.0, count / len(story_group) + 0.2)
                evolved_tags.append({
                    'text': tag_text,
                    'type': 'evolved',
                    'score': score,
                    'frequency': count,
                    'story_count': len(story_group)
                })
            
            evolved_story = {
                'title': f"{base_story['title']} (Evolved Story)",
                'content': self._combine_story_content(story_group),
                'summary': evolved_summary,
                'source': f"Evolved ({len(all_sources)} sources)",
                'sources': list(all_sources),
                'source_count': len(all_sources),
                'source_priority': evolved_priority,
                'category': base_story.get('category', 'General'),
                'published_at': base_story['published_at'],
                'url': base_story.get('url', ''),
                'tags': evolved_tags[:10],  # Top 10 tags
                'preprocessing_status': 'evolved',
                'evolution_metadata': {
                    'original_stories': [story['id'] for story in story_group],
                    'evolution_date': datetime.now().isoformat(),
                    'stories_consolidated': len(story_group)
                },
                'created_at': datetime.now()
            }
            
            return evolved_story
            
        except Exception as e:
            logger.error(f"Error creating evolved story: {e}")
            return None
    
    def _generate_evolved_summary(self, story_group: List[Dict]) -> str:
        """Generate an evolved summary from multiple stories"""
        try:
            # Prepare content for ML summarization
            combined_text = ""
            
            for story in story_group:
                title = story.get('title', '')
                content = story.get('content') or story.get('summary', '')
                
                if content:
                    combined_text += f"Story: {title}\nContent: {content}\n\n"
            
            if not combined_text.strip():
                return f"Evolved story consolidating {len(story_group)} related stories"
            
            # Use ML service to generate evolved summary
            summary_result = self.ml_service.generate_summary(
                article_content=combined_text,
                article_title=f"Evolved story from {len(story_group)} sources"
            )
            
            if summary_result and 'summary' in summary_result:
                return summary_result['summary']
            else:
                return f"Evolved story consolidating {len(story_group)} related stories covering: {story_group[0].get('title', 'Unknown topic')}"
                
        except Exception as e:
            logger.error(f"Error generating evolved summary: {e}")
            return f"Evolved story from {len(story_group)} sources"
    
    def _combine_story_content(self, story_group: List[Dict]) -> str:
        """Combine content from multiple stories"""
        try:
            content_parts = []
            
            for story in story_group:
                content = story.get('content') or story.get('summary', '')
                if content and len(content.strip()) > 100:
                    content_parts.append(content.strip())
            
            # Remove duplicates and combine
            unique_content = []
            seen_content = set()
            
            for content in content_parts:
                content_hash = hash(content[:500])  # Use first 500 chars for deduplication
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    unique_content.append(content)
            
            # Combine with separators
            combined = "\n\n--- Story Evolution ---\n\n".join(unique_content)
            
            # Limit total length
            max_length = 15000
            if len(combined) > max_length:
                combined = combined[:max_length] + "..."
            
            return combined
            
        except Exception as e:
            logger.error(f"Error combining story content: {e}")
            return story_group[0].get('content', '') if story_group else ''
    
    def _store_evolved_story(self, evolved_story: Dict, original_stories: List[Dict]) -> Optional[int]:
        """Store the evolved story in the database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insert evolved story
            cursor.execute("""
                INSERT INTO master_articles (
                    title, content, summary, source, sources, source_count,
                    source_priority, category, published_at, url, tags,
                    preprocessing_status, consolidation_metadata, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                evolved_story['title'],
                evolved_story['content'],
                evolved_story['summary'],
                evolved_story['source'],
                json.dumps(evolved_story['sources']),
                evolved_story['source_count'],
                evolved_story['source_priority'],
                evolved_story['category'],
                evolved_story['published_at'],
                evolved_story['url'],
                json.dumps(evolved_story['tags']),
                evolved_story['preprocessing_status'],
                json.dumps(evolved_story.get('evolution_metadata', {})),
                evolved_story['created_at']
            ))
            
            evolved_story_id = cursor.fetchone()[0]
            
            # Mark original stories as evolved
            for story in original_stories:
                cursor.execute("""
                    UPDATE master_articles 
                    SET preprocessing_status = 'evolved', 
                        consolidation_metadata = jsonb_set(
                            COALESCE(consolidation_metadata, '{}'), 
                            '{evolved_into}', 
                            %s::jsonb
                        )
                    WHERE id = %s
                """, (json.dumps(evolved_story_id), story['id']))
            
            conn.commit()
            conn.close()
            
            return evolved_story_id
            
        except Exception as e:
            logger.error(f"Error storing evolved story: {e}")
            return None
    
    def _generate_daily_digest(self) -> Dict[str, Any]:
        """Generate daily digest of top stories"""
        try:
            logger.info("📰 Generating daily digest...")
            
            # Get top stories from the past 24 hours
            cutoff_date = datetime.now() - timedelta(days=1)
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT id, title, summary, source, sources, source_count,
                       source_priority, category, published_at, tags
                FROM master_articles
                WHERE published_at >= %s
                AND source_count >= %s
                ORDER BY source_priority DESC, source_count DESC, published_at DESC
                LIMIT %s
            """, (cutoff_date, self.config['min_sources_for_story'], self.config['max_daily_digest_stories']))
            
            top_stories = cursor.fetchall()
            
            if not top_stories:
                conn.close()
                return {'success': True, 'stories_included': 0, 'message': 'No stories for daily digest'}
            
            # Generate digest content
            digest_content = self._create_digest_content([dict(story) for story in top_stories])
            
            # Store digest
            digest_id = self._store_daily_digest(digest_content, [dict(story) for story in top_stories])
            
            conn.close()
            
            return {
                'success': True,
                'stories_included': len(top_stories),
                'digest_id': digest_id,
                'digest_content': digest_content
            }
            
        except Exception as e:
            logger.error(f"Error generating daily digest: {e}")
            return {'success': False, 'error': str(e)}
    
    def _create_digest_content(self, stories: List[Dict]) -> str:
        """Create digest content from top stories"""
        try:
            digest_lines = [
                f"# Daily News Digest - {datetime.now().strftime('%B %d, %Y')}",
                "",
                f"## Top {len(stories)} Stories",
                ""
            ]
            
            for i, story in enumerate(stories, 1):
                digest_lines.extend([
                    f"### {i}. {story['title']}",
                    f"**Sources:** {story['source_count']} ({', '.join(story.get('sources', []))})",
                    f"**Priority:** {story.get('source_priority', 1.0):.1f}",
                    f"**Category:** {story.get('category', 'General')}",
                    "",
                    story.get('summary', 'No summary available'),
                    "",
                    "---",
                    ""
                ])
            
            digest_lines.extend([
                "## Summary",
                f"Today's digest includes {len(stories)} stories from multiple sources, ",
                f"prioritized by source coverage and relevance.",
                "",
                f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ])
            
            return "\n".join(digest_lines)
            
        except Exception as e:
            logger.error(f"Error creating digest content: {e}")
            return f"Daily digest for {datetime.now().strftime('%B %d, %Y')} - Error generating content"
    
    def _store_daily_digest(self, content: str, stories: List[Dict]) -> Optional[int]:
        """Store daily digest in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO daily_digests (
                    title, content, stories_included, digest_date, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                f"Daily Digest - {datetime.now().strftime('%B %d, %Y')}",
                content,
                len(stories),
                datetime.now().date(),
                datetime.now()
            ))
            
            digest_id = cursor.fetchone()[0]
            
            # Link stories to digest
            for story in stories:
                cursor.execute("""
                    INSERT INTO digest_stories (digest_id, story_id)
                    VALUES (%s, %s)
                """, (digest_id, story['id']))
            
            conn.commit()
            conn.close()
            
            return digest_id
            
        except Exception as e:
            logger.error(f"Error storing daily digest: {e}")
            return None
    
    def _perform_database_cleanup(self) -> Dict[str, Any]:
        """Perform database cleanup and noise reduction"""
        try:
            logger.info("🧹 Performing database cleanup...")
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cleanup_stats = {
                'articles_archived': 0,
                'orphaned_articles_removed': 0,
                'old_stories_consolidated': 0
            }
            
            # Archive old articles
            archive_cutoff = datetime.now() - timedelta(days=self.config['archive_old_articles_days'])
            cursor.execute("""
                UPDATE articles 
                SET preprocessing_status = 'archived'
                WHERE published_at < %s 
                AND preprocessing_status NOT IN ('archived', 'evolved')
            """, (archive_cutoff,))
            cleanup_stats['articles_archived'] = cursor.rowcount
            
            # Remove orphaned articles (not linked to master articles)
            orphan_cutoff = datetime.now() - timedelta(days=self.config['remove_orphaned_articles_days'])
            cursor.execute("""
                DELETE FROM articles 
                WHERE published_at < %s 
                AND master_article_id IS NULL
                AND preprocessing_status IS NULL
            """, (orphan_cutoff,))
            cleanup_stats['orphaned_articles_removed'] = cursor.rowcount
            
            # Consolidate old stories
            old_story_cutoff = datetime.now() - timedelta(days=self.config['consolidate_old_stories_days'])
            cursor.execute("""
                UPDATE master_articles 
                SET preprocessing_status = 'consolidated'
                WHERE published_at < %s 
                AND source_count = 1
                AND preprocessing_status = 'processed'
            """, (old_story_cutoff,))
            cleanup_stats['old_stories_consolidated'] = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cleanup completed: {cleanup_stats}")
            
            return {
                'success': True,
                'cleanup_stats': cleanup_stats
            }
            
        except Exception as e:
            logger.error(f"Error performing database cleanup: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        try:
            return {
                'running': self.running,
                'configuration': self.config,
                'statistics': self.stats,
                'next_scheduled_tasks': self._get_next_scheduled_tasks()
            }
            
        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            return {'error': str(e)}
    
    def _get_next_scheduled_tasks(self) -> List[Dict]:
        """Get next scheduled tasks"""
        try:
            next_tasks = []
            
            for job in schedule.jobs:
                next_tasks.append({
                    'job': str(job.job_func),
                    'next_run': job.next_run.isoformat() if job.next_run else None
                })
            
            return next_tasks
            
        except Exception as e:
            logger.error(f"Error getting next scheduled tasks: {e}")
            return []
