#!/usr/bin/env python3
"""
Content Prioritization Manager
High-level interface for managing content priority, story threads, and RAG context
"""

import logging
import psycopg2
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import time
import re

from modules.content_prioritization_engine import ContentPrioritizationEngine
from modules.rag_context_builder import RAGContextBuilder

logger = logging.getLogger(__name__)

class ContentPrioritizationManager:
    """Manages content prioritization, story threads, and RAG context building"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize content prioritization manager
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.engine = ContentPrioritizationEngine(db_config)
        self.rag_builder = RAGContextBuilder(db_config)
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'total_articles_processed': 0,
            'priority_assignments_made': 0,
            'story_threads_created': 0,
            'rag_contexts_built': 0,
            'processing_time': 0.0,
            'last_run': None
        }
    
    def process_article_with_priority(self, article_data: Dict[str, Any], 
                                    profile_name: str = 'default') -> Dict[str, Any]:
        """
        Process an article with priority calculation and story thread assignment
        
        Args:
            article_data: Article data from RSS feed
            profile_name: User profile name to apply rules from
            
        Returns:
            Dictionary with priority results and processing data
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Processing article with priority: {article_data.get('title', 'Unknown')}")
            
            # Step 1: Calculate priority
            priority_result = self.engine.calculate_article_priority(article_data, profile_name)
            
            # Step 2: Check for story thread matches
            thread_matches = priority_result.get('thread_matches', [])
            
            # Step 3: Assign priority to database
            if priority_result['should_collect']:
                article_id = self._store_article_with_priority(article_data, priority_result)
                
                # Step 4: Assign to story thread if matches found
                if thread_matches:
                    best_match = max(thread_matches, key=lambda x: x['match_weight'])
                    self._assign_article_to_thread(article_id, best_match['thread_id'], priority_result)
                
                # Step 5: Create new story thread if no matches and high priority
                elif priority_result['priority_score'] >= 75:
                    new_thread = self._create_auto_story_thread(article_data, priority_result)
                    if new_thread and 'id' in new_thread:
                        self._assign_article_to_thread(article_id, new_thread['id'], priority_result)
                
                processed_data = {
                    'should_store': True,
                    'article_id': article_id,
                    'priority_result': priority_result,
                    'thread_matches': thread_matches,
                    'processing_time': time.time() - start_time
                }
                
                self.stats['priority_assignments_made'] += 1
                
            else:
                processed_data = {
                    'should_store': False,
                    'priority_result': priority_result,
                    'reason': f"Article deprioritized: {priority_result.get('reasoning', [])}",
                    'processing_time': time.time() - start_time
                }
            
            self.stats['total_articles_processed'] += 1
            self.stats['processing_time'] += processed_data['processing_time']
            self.stats['last_run'] = datetime.now()
            
            self.logger.info(f"Article processed with priority: {priority_result['priority_level_name']} "
                           f"({processed_data['processing_time']:.3f}s)")
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Error processing article with priority: {e}")
            return {
                'should_store': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def create_story_thread(self, title: str, description: str, category: str,
                           priority_level_name: str = 'medium', 
                           keywords: List[str] = None,
                           user_created: bool = True) -> Dict[str, Any]:
        """
        Create a new story thread
        
        Args:
            title: Thread title
            description: Thread description
            category: Thread category
            priority_level_name: Priority level name
            keywords: List of keywords for automatic detection
            user_created: Whether created by user or system
            
        Returns:
            Dictionary with thread information
        """
        try:
            self.logger.info(f"Creating story thread: {title}")
            
            thread_result = self.engine.create_story_thread(
                title, description, category, priority_level_name, keywords, user_created
            )
            
            if 'error' not in thread_result:
                self.stats['story_threads_created'] += 1
                self.logger.info(f"Story thread created successfully: {title} (ID: {thread_result['id']})")
            else:
                self.logger.error(f"Failed to create story thread: {thread_result['error']}")
            
            return thread_result
            
        except Exception as e:
            self.logger.error(f"Error creating story thread: {e}")
            return {'error': str(e)}
    
    def add_user_interest_rule(self, profile_name: str, rule_type: str, rule_value: str,
                               priority_level_name: str, action: str = 'track',
                               weight: float = 1.0) -> Dict[str, Any]:
        """
        Add a user interest rule
        
        Args:
            profile_name: User profile name
            rule_type: Type of rule (keyword, source, category, topic)
            rule_value: Rule value to match
            priority_level_name: Priority level name
            action: Action to take (track, avoid, boost, suppress)
            weight: Rule weight (0.0 to 1.0)
            
        Returns:
            Dictionary with rule information
        """
        try:
            self.logger.info(f"Adding user interest rule: {rule_type}={rule_value} -> {action}")
            
            rule_result = self.engine.add_user_interest_rule(
                profile_name, rule_type, rule_value, priority_level_name, action, weight
            )
            
            if 'error' not in rule_result:
                self.logger.info(f"User interest rule added successfully: {rule_result['id']}")
            else:
                self.logger.error(f"Failed to add user interest rule: {rule_result['error']}")
            
            return rule_result
            
        except Exception as e:
            self.logger.error(f"Error adding user interest rule: {e}")
            return {'error': str(e)}
    
    def build_rag_context(self, thread_id: int, context_type: str = 'historical',
                          max_articles: int = None) -> Dict[str, Any]:
        """
        Build RAG context for a story thread
        
        Args:
            thread_id: Story thread ID
            context_type: Type of context to build
            max_articles: Maximum number of articles to include
            
        Returns:
            Dictionary with RAG context information
        """
        try:
            self.logger.info(f"Building RAG context for thread {thread_id}: {context_type}")
            
            context_result = self.rag_builder.build_context_for_thread(
                thread_id, context_type, max_articles
            )
            
            if 'error' not in context_result:
                self.stats['rag_contexts_built'] += 1
                self.logger.info(f"RAG context built successfully: {context_type} for thread {thread_id}")
            else:
                self.logger.error(f"Failed to build RAG context: {context_result['error']}")
            
            return context_result
            
        except Exception as e:
            self.logger.error(f"Error building RAG context: {e}")
            return {'error': str(e)}
    
    def get_story_threads(self, status: str = 'active', 
                          priority_level_name: str = None) -> List[Dict[str, Any]]:
        """
        Get story threads with optional filtering
        
        Args:
            status: Thread status filter
            priority_level_name: Priority level filter
            
        Returns:
            List of story threads
        """
        try:
            threads = self.engine.get_story_threads(status, priority_level_name)
            self.logger.info(f"Retrieved {len(threads)} story threads (status: {status})")
            return threads
            
        except Exception as e:
            self.logger.error(f"Error getting story threads: {e}")
            return []
    
    def get_priority_statistics(self) -> Dict[str, Any]:
        """Get statistics about content priority distribution"""
        try:
            stats = self.engine.get_priority_statistics()
            if 'error' not in stats:
                self.logger.info("Priority statistics retrieved successfully")
            else:
                self.logger.error(f"Failed to get priority statistics: {stats['error']}")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting priority statistics: {e}")
            return {'error': str(e)}
    
    def process_existing_articles_priority(self, batch_size: int = 50,
                                         max_articles: Optional[int] = None) -> Dict[str, Any]:
        """
        Process existing articles for priority assignment
        
        Args:
            batch_size: Number of articles to process per batch
            max_articles: Maximum total articles to process (None for all)
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting priority processing of existing articles (batch_size={batch_size})")
            
            # Get articles that need priority assignment
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, content, source, category, published_at
                FROM articles 
                WHERE deduplication_status = 'unique'
                AND id NOT IN (
                    SELECT DISTINCT article_id 
                    FROM content_priority_assignments
                )
                ORDER BY created_at ASC
            """)
            
            articles = cursor.fetchall()
            conn.close()
            
            if max_articles:
                articles = articles[:max_articles]
            
            total_articles = len(articles)
            self.logger.info(f"Found {total_articles} articles to process for priority")
            
            if total_articles == 0:
                return {
                    'total_articles': 0,
                    'batches_processed': 0,
                    'total_processing_time': 0.0,
                    'message': 'No articles need priority assignment'
                }
            
            # Process in batches
            results = {
                'total_articles': total_articles,
                'batches_processed': 0,
                'total_processing_time': 0.0,
                'priority_assignments_made': 0,
                'story_threads_created': 0,
                'total_errors': 0,
                'batch_results': []
            }
            
            for i in range(0, total_articles, batch_size):
                batch_articles = articles[i:i + batch_size]
                batch_start = time.time()
                
                self.logger.info(f"Processing batch {i//batch_size + 1}: articles {i+1}-{min(i+batch_size, total_articles)}")
                
                # Process batch
                batch_result = self._process_batch_priority(batch_articles)
                batch_result['batch_number'] = i//batch_size + 1
                batch_result['processing_time'] = time.time() - batch_start
                
                results['batch_results'].append(batch_result)
                results['priority_assignments_made'] += batch_result['priority_assignments_made']
                results['story_threads_created'] += batch_result['story_threads_created']
                results['total_errors'] += batch_result['errors']
                results['batches_processed'] += 1
                
                self.logger.info(f"Batch {i//batch_size + 1} completed: "
                               f"{batch_result['priority_assignments_made']} assignments, "
                               f"{batch_result['story_threads_created']} threads, "
                               f"{batch_result['processing_time']:.3f}s")
            
            results['total_processing_time'] = time.time() - start_time
            
            self.logger.info(f"Priority processing completed: {results['priority_assignments_made']} assignments, "
                           f"{results['story_threads_created']} threads, "
                           f"{results['total_processing_time']:.3f}s total")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing existing articles for priority: {e}")
            return {
                'error': str(e),
                'total_processing_time': time.time() - start_time
            }
    
    def _process_batch_priority(self, articles: List[Tuple]) -> Dict[str, Any]:
        """Process a batch of articles for priority assignment"""
        results = {
            'priority_assignments_made': 0,
            'story_threads_created': 0,
            'errors': 0,
            'details': []
        }
        
        for article_data in articles:
            try:
                # Convert tuple to dictionary
                article_dict = {
                    'id': article_data[0],
                    'title': article_data[1],
                    'content': article_data[2],
                    'source': article_data[3],
                    'category': article_data[4],
                    'published_at': article_data[5]
                }
                
                # Process article
                priority_result = self.engine.calculate_article_priority(article_dict)
                
                # Update article priority in database
                if priority_result['should_collect']:
                    self._update_article_priority(article_dict['id'], priority_result)
                    results['priority_assignments_made'] += 1
                    
                    # Check for story thread matches
                    thread_matches = priority_result.get('thread_matches', [])
                    if thread_matches:
                        best_match = max(thread_matches, key=lambda x: x['match_weight'])
                        self._assign_article_to_thread(article_dict['id'], best_match['thread_id'], priority_result)
                    
                    # Create new thread if high priority and no matches
                    elif priority_result['priority_score'] >= 75:
                        new_thread = self._create_auto_story_thread(article_dict, priority_result)
                        if new_thread and 'id' in new_thread:
                            self._assign_article_to_thread(article_dict['id'], new_thread['id'], priority_result)
                            results['story_threads_created'] += 1
                
                results['details'].append({
                    'article_id': article_dict['id'],
                    'title': article_dict['title'],
                    'priority_result': priority_result
                })
                
            except Exception as e:
                self.logger.error(f"Error processing article {article_data[0]}: {e}")
                results['errors'] += 1
        
        return results
    
    def _store_article_with_priority(self, article_data: Dict[str, Any], 
                                   priority_result: Dict[str, Any]) -> int:
        """Store article with priority information"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Check if article already exists
            cursor.execute("""
                SELECT id FROM articles WHERE url = %s
            """, (article_data['url'],))
            
            existing_article = cursor.fetchone()
            if existing_article:
                article_id = existing_article[0]
                self.logger.info(f"Article already exists with ID: {article_id}")
            else:
                # Insert new article
                cursor.execute("""
                    INSERT INTO articles
                    (title, url, content, summary, published_at, created_at, source, category,
                     content_hash, normalized_content, deduplication_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    article_data['title'],
                    article_data['url'],
                    article_data['content'],
                    None,
                    article_data['published_at'],
                    datetime.now(),
                    article_data['source'],
                    article_data['category'],
                    article_data.get('content_hash', ''),
                    article_data.get('normalized_content', ''),
                    'unique'
                ))
                
                article_id = cursor.fetchone()[0]
                self.logger.info(f"New article inserted with ID: {article_id}")
            
            # Check if priority assignment already exists
            cursor.execute("""
                SELECT id FROM content_priority_assignments WHERE article_id = %s
            """, (article_id,))
            
            existing_assignment = cursor.fetchone()
            if not existing_assignment:
                # Create priority assignment
                cursor.execute("""
                    INSERT INTO content_priority_assignments
                    (article_id, priority_level_id, assigned_by, confidence_score, reasoning)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    article_id,
                    priority_result['priority_level_id'],
                    'system',
                    1.0,
                    '; '.join(priority_result.get('reasoning', []))
                ))
                
                self.logger.info(f"Priority assignment created for article {article_id}")
            
            conn.commit()
            conn.close()
            
            return article_id
            
        except Exception as e:
            self.logger.error(f"Error storing article with priority: {e}")
            raise
    
    def _update_article_priority(self, article_id: int, priority_result: Dict[str, Any]) -> None:
        """Update article priority in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO content_priority_assignments
                (article_id, priority_level_id, assigned_by, confidence_score, reasoning)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (article_id) DO UPDATE SET
                priority_level_id = EXCLUDED.priority_level_id,
                confidence_score = EXCLUDED.confidence_score,
                reasoning = EXCLUDED.reasoning
            """, (
                article_id,
                priority_result['priority_level_id'],
                'system',
                1.0,
                '; '.join(priority_result.get('reasoning', []))
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error updating article priority: {e}")
            raise
    
    def _assign_article_to_thread(self, article_id: int, thread_id: int, 
                                 priority_result: Dict[str, Any]) -> None:
        """Assign article to a story thread"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE content_priority_assignments
                SET thread_id = %s
                WHERE article_id = %s
            """, (thread_id, article_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error assigning article to thread: {e}")
            raise
    
    def _create_auto_story_thread(self, article_data: Dict[str, Any], 
                                 priority_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create an automatic story thread for high-priority articles"""
        try:
            # Extract keywords from title and content
            title_words = article_data['title'].split()
            content_words = article_data['content'].split()
            
            # Get meaningful keywords (words > 3 characters, not common words)
            common_words = {'the', 'and', 'for', 'with', 'this', 'that', 'have', 'been', 'will', 'from'}
            keywords = []
            
            for word in title_words + content_words:
                word_clean = re.sub(r'[^\w]', '', word.lower())
                if len(word_clean) > 3 and word_clean not in common_words:
                    keywords.append(word_clean)
                    if len(keywords) >= 5:  # Limit to 5 keywords
                        break
            
            # Create thread
            thread_title = f"Auto: {article_data['title'][:50]}..."
            thread_description = f"Automatically generated thread for {article_data['source']} article"
            
            thread_result = self.engine.create_story_thread(
                thread_title,
                thread_description,
                article_data['category'],
                'high',
                keywords,
                user_created=False
            )
            
            return thread_result
            
        except Exception as e:
            self.logger.error(f"Error creating auto story thread: {e}")
            return None
    
    def get_manager_statistics(self) -> Dict[str, Any]:
        """Get comprehensive manager statistics"""
        try:
            stats = {
                'manager_stats': self.stats,
                'priority_stats': self.engine.get_priority_statistics(),
                'story_threads': self.engine.get_story_threads(),
                'total_story_threads': len(self.engine.get_story_threads()),
                'total_priority_levels': len(self.engine.priority_levels),
                'total_user_rules': sum(len(rules) for rules in self.engine.user_rules.values()),
                'total_collection_rules': len(self.engine.collection_rules)
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting manager statistics: {e}")
            return {'error': str(e)}
