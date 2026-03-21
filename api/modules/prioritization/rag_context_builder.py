#!/usr/bin/env python3
"""
RAG Context Builder
Retrieves historical context and related content based on user interests and story threads
"""

import logging
import psycopg2
from shared.database.connection import get_db_connection
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import re
from modules.intelligent_tagging_service import IntelligentTaggingService

logger = logging.getLogger(__name__)

class RAGContextBuilder:
    """Builds RAG context by retrieving relevant historical content"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize RAG context builder
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        
        # Initialize intelligent tagging service
        self.tagging_service = IntelligentTaggingService(db_config)
        
        # Configuration
        self.config = {
            'max_context_articles': 20,
            'max_context_length': 5000,
            'similarity_threshold': 0.6,
            'max_historical_days': 365,
            'context_types': ['historical', 'related', 'background', 'timeline'],
            'auto_tagging_enabled': True
        }
    
    def build_context_for_thread(self, thread_id: int, 
                                context_type: str = 'historical',
                                max_articles: int = None) -> Dict[str, Any]:
        """
        Build context for a specific story thread
        
        Args:
            thread_id: Story thread ID
            context_type: Type of context to build
            max_articles: Maximum number of articles to include
            
        Returns:
            Dictionary with context information
        """
        try:
            if max_articles is None:
                max_articles = self.config['max_context_articles']
            
            # Get thread information
            thread_info = self._get_thread_info(thread_id)
            if not thread_info:
                return {'error': 'Thread not found'}
            
            # Build context based on type
            if context_type == 'historical':
                context = self._build_historical_context(thread_info, max_articles)
            elif context_type == 'related':
                context = self._build_related_context(thread_info, max_articles)
            elif context_type == 'background':
                context = self._build_background_context(thread_info, max_articles)
            elif context_type == 'timeline':
                context = self._build_timeline_context(thread_info, max_articles)
            else:
                context = self._build_general_context(thread_info, max_articles)
            
            # Create RAG context request record
            self._log_context_request(thread_id, context_type, context)
            
            # Auto-tagging: Analyze and update tags if enabled
            if self.config.get('auto_tagging_enabled', True):
                try:
                    tag_analysis = self.tagging_service.analyze_story_thread_tags(thread_id)
                    if 'error' not in tag_analysis:
                        tag_update_result = self.tagging_service.update_thread_tags(thread_id, tag_analysis)
                        context['auto_tagging'] = {
                            'enabled': True,
                            'analysis': tag_analysis,
                            'update_result': tag_update_result
                        }
                        self.logger.info(f"Auto-tagging completed for thread {thread_id}: {tag_update_result.get('updates_made', 0)} updates")
                    else:
                        context['auto_tagging'] = {
                            'enabled': True,
                            'error': tag_analysis['error']
                        }
                except Exception as e:
                    self.logger.error(f"Auto-tagging failed for thread {thread_id}: {e}")
                    context['auto_tagging'] = {
                        'enabled': True,
                        'error': str(e)
                    }
            else:
                context['auto_tagging'] = {'enabled': False}
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building context for thread {thread_id}: {e}")
            return {'error': str(e)}
    
    def build_context_for_topic(self, topic: str, keywords: List[str],
                               context_type: str = 'general',
                               max_articles: int = None) -> Dict[str, Any]:
        """
        Build context for a general topic
        
        Args:
            topic: Topic name
            keywords: List of keywords to search for
            context_type: Type of context to build
            max_articles: Maximum number of articles to include
            
        Returns:
            Dictionary with context information
        """
        try:
            if max_articles is None:
                max_articles = self.config['max_context_articles']
            
            # Search for relevant articles
            relevant_articles = self._search_relevant_articles(keywords, max_articles)
            
            # Build context
            context = {
                'topic': topic,
                'keywords': keywords,
                'context_type': context_type,
                'articles_found': len(relevant_articles),
                'context_summary': self._generate_context_summary(relevant_articles),
                'key_entities': self._extract_key_entities(relevant_articles),
                'timeline': self._build_timeline_from_articles(relevant_articles),
                'related_topics': self._find_related_topics(relevant_articles),
                'articles': relevant_articles[:max_articles]
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building context for topic {topic}: {e}")
            return {'error': str(e)}
    
    def _get_thread_info(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """Get story thread information"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT st.id, st.title, st.description, st.category, st.priority_level_id,
                       cpl.name as priority_level, st.created_at, st.updated_at
                FROM story_threads st
                JOIN content_priority_levels cpl ON st.priority_level_id = cpl.id
                WHERE st.id = %s
            """, (thread_id,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'category': row[3],
                    'priority_level_id': row[4],
                    'priority_level': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting thread info: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def _build_historical_context(self, thread_info: Dict[str, Any], 
                                 max_articles: int) -> Dict[str, Any]:
        """Build historical context for a story thread"""
        try:
            # Get thread keywords
            keywords = self._get_thread_keywords(thread_info['id'])
            
            # Search for historical articles
            historical_articles = self._search_historical_articles(
                keywords, 
                thread_info['category'],
                max_articles,
                before_date=thread_info['created_at']
            )
            
            # Build historical context
            context = {
                'thread_id': thread_info['id'],
                'thread_title': thread_info['title'],
                'context_type': 'historical',
                'historical_period': self._calculate_historical_period(thread_info['created_at']),
                'articles_found': len(historical_articles),
                'context_summary': self._generate_historical_summary(historical_articles),
                'key_events': self._extract_key_events(historical_articles),
                'evolution_timeline': self._build_evolution_timeline(historical_articles),
                'articles': historical_articles
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building historical context: {e}")
            return {'error': str(e)}
    
    def _build_related_context(self, thread_info: Dict[str, Any], 
                               max_articles: int) -> Dict[str, Any]:
        """Build related context for a story thread"""
        try:
            # Get thread keywords
            keywords = self._get_thread_keywords(thread_info['id'])
            
            # Search for related articles
            related_articles = self._search_related_articles(
                keywords,
                thread_info['category'],
                max_articles,
                exclude_thread_id=thread_info['id']
            )
            
            # Build related context
            context = {
                'thread_id': thread_info['id'],
                'thread_title': thread_info['title'],
                'context_type': 'related',
                'articles_found': len(related_articles),
                'context_summary': self._generate_related_summary(related_articles),
                'connection_points': self._find_connection_points(related_articles, thread_info),
                'related_threads': self._find_related_threads(related_articles),
                'articles': related_articles
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building related context: {e}")
            return {'error': str(e)}
    
    def _build_background_context(self, thread_info: Dict[str, Any], 
                                 max_articles: int) -> Dict[str, Any]:
        """Build background context for a story thread"""
        try:
            # Get thread keywords
            keywords = self._get_thread_keywords(thread_info['id'])
            
            # Search for background articles
            background_articles = self._search_background_articles(
                keywords,
                thread_info['category'],
                max_articles
            )
            
            # Build background context
            context = {
                'thread_id': thread_info['id'],
                'thread_title': thread_info['title'],
                'context_type': 'background',
                'articles_found': len(background_articles),
                'context_summary': self._generate_background_summary(background_articles),
                'key_concepts': self._extract_key_concepts(background_articles),
                'expertise_level': self._assess_expertise_level(background_articles),
                'articles': background_articles
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building background context: {e}")
            return {'error': str(e)}
    
    def _build_timeline_context(self, thread_info: Dict[str, Any], 
                               max_articles: int) -> Dict[str, Any]:
        """Build timeline context for a story thread"""
        try:
            # Get all articles in the thread
            thread_articles = self._get_thread_articles(thread_info['id'], max_articles)
            
            # Build timeline
            timeline = self._build_timeline_from_articles(thread_articles)
            
            # Build timeline context
            context = {
                'thread_id': thread_info['id'],
                'thread_title': thread_info['title'],
                'context_type': 'timeline',
                'articles_found': len(thread_articles),
                'timeline_period': self._calculate_timeline_period(thread_articles),
                'key_milestones': self._extract_key_milestones(thread_articles),
                'development_phases': self._identify_development_phases(thread_articles),
                'timeline': timeline,
                'articles': thread_articles
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building timeline context: {e}")
            return {'error': str(e)}
    
    def _build_general_context(self, thread_info: Dict[str, Any], max_articles: int) -> Dict[str, Any]:
        """Build general context for a story thread"""
        try:
            # Get thread keywords
            keywords = self._get_thread_keywords(thread_info['id'])
            
            # Search for relevant articles
            relevant_articles = self._search_relevant_articles(keywords, max_articles)
            
            # Build general context
            context = {
                'thread_id': thread_info['id'],
                'thread_title': thread_info['title'],
                'context_type': 'general',
                'articles_found': len(relevant_articles),
                'context_summary': self._generate_context_summary(relevant_articles),
                'key_entities': self._extract_key_entities(relevant_articles),
                'timeline': self._build_timeline_from_articles(relevant_articles),
                'related_topics': self._find_related_topics(relevant_articles),
                'articles': relevant_articles
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error building general context: {e}")
            return {'error': str(e)}
    
    def _get_thread_keywords(self, thread_id: int) -> List[str]:
        """Get keywords for a story thread"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT keyword, weight
                FROM story_thread_keywords
                WHERE thread_id = %s AND is_active = TRUE
                ORDER BY weight DESC
            """, (thread_id,))
            
            keywords = [row[0] for row in cursor.fetchall()]
            
            return keywords
            
        except Exception as e:
            self.logger.error(f"Error getting thread keywords: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _search_historical_articles(self, keywords: List[str], category: str,
                                   max_articles: int, before_date: datetime) -> List[Dict[str, Any]]:
        """Search for historical articles before a specific date"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Build search query
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(f"(LOWER(title) LIKE '%{keyword.lower()}%' OR LOWER(content) LIKE '%{keyword.lower()}%')")
            
            keyword_query = " OR ".join(keyword_conditions) if keyword_conditions else "1=1"
            
            query = f"""
                SELECT id, title, content, source, published_at, category, url
                FROM articles
                WHERE ({keyword_query})
                AND published_at < %s
                AND category = %s
                AND deduplication_status = 'unique'
                ORDER BY published_at DESC
                LIMIT %s
            """
            
            cursor.execute(query, (before_date, category, max_articles))
            
            articles = []
            for row in cursor.fetchall():
                try:
                    content = row[2] if row[2] else ""
                    content_preview = content[:500] + '...' if len(content) > 500 else content
                    
                    articles.append({
                        'id': row[0],
                        'title': row[1] if row[1] else "",
                        'content': content_preview,
                        'source': row[3] if row[3] else "",
                        'published_at': row[4].isoformat() if row[4] else None,
                        'category': row[5] if row[5] else "",
                        'url': row[6] if row[6] else ""
                    })
                except Exception as e:
                    self.logger.warning(f"Error processing article row: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error searching historical articles: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _search_related_articles(self, keywords: List[str], category: str,
                                max_articles: int, exclude_thread_id: int) -> List[Dict[str, Any]]:
        """Search for related articles"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Build search query
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(f"(LOWER(title) LIKE '%{keyword.lower()}%' OR LOWER(content) LIKE '%{keyword.lower()}%')")
            
            keyword_query = " OR ".join(keyword_conditions) if keyword_conditions else "1=1"
            
            query = f"""
                SELECT id, title, content, source, published_at, category, url
                FROM articles
                WHERE ({keyword_query})
                AND category = %s
                AND deduplication_status = 'unique'
                AND id NOT IN (
                    SELECT DISTINCT article_id 
                    FROM content_priority_assignments 
                    WHERE thread_id = %s
                )
                ORDER BY published_at DESC
                LIMIT %s
            """
            
            cursor.execute(query, (category, exclude_thread_id, max_articles))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2][:500] + '...' if len(row[2]) > 500 else row[2],
                    'source': row[3],
                    'published_at': row[4].isoformat() if row[4] else None,
                    'category': row[5],
                    'url': row[6]
                })
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error searching related articles: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _search_background_articles(self, keywords: List[str], category: str,
                                   max_articles: int) -> List[Dict[str, Any]]:
        """Search for background/educational articles"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Build search query for background content
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(f"(LOWER(title) LIKE '%{keyword.lower()}%' OR LOWER(content) LIKE '%{keyword.lower()}%')")
            
            keyword_query = " OR ".join(keyword_conditions) if keyword_conditions else "1=1"
            
            query = f"""
                SELECT id, title, content, source, published_at, category, url
                FROM articles
                WHERE ({keyword_query})
                AND category = %s
                AND deduplication_status = 'unique'
                AND (
                    LOWER(title) LIKE '%introduction%' OR
                    LOWER(title) LIKE '%guide%' OR
                    LOWER(title) LIKE '%overview%' OR
                    LOWER(title) LIKE '%basics%' OR
                    LOWER(title) LIKE '%fundamentals%'
                )
                ORDER BY published_at DESC
                LIMIT %s
            """
            
            cursor.execute(query, (category, max_articles))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2][:500] + '...' if len(row[2]) > 500 else row[2],
                    'source': row[3],
                    'published_at': row[4].isoformat() if row[4] else None,
                    'category': row[5],
                    'url': row[6]
                })
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error searching background articles: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _search_relevant_articles(self, keywords: List[str], max_articles: int) -> List[Dict[str, Any]]:
        """Search for relevant articles based on keywords"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Build search query
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(f"(LOWER(title) LIKE '%{keyword.lower()}%' OR LOWER(content) LIKE '%{keyword.lower()}%')")
            
            keyword_query = " OR ".join(keyword_conditions) if keyword_conditions else "1=1"
            
            query = f"""
                SELECT id, title, content, source, published_at, category, url
                FROM articles
                WHERE ({keyword_query})
                AND deduplication_status = 'unique'
                ORDER BY published_at DESC
                LIMIT %s
            """
            
            cursor.execute(query, (max_articles,))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2][:500] + '...' if len(row[2]) > 500 else row[2],
                    'source': row[3],
                    'published_at': row[4].isoformat() if row[4] else None,
                    'category': row[5],
                    'url': row[6]
                })
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error searching relevant articles: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _get_thread_articles(self, thread_id: int, max_articles: int) -> List[Dict[str, Any]]:
        """Get articles assigned to a specific thread"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT a.id, a.title, a.content, a.source, a.published_at, a.category, a.url
                FROM articles a
                JOIN content_priority_assignments cpa ON a.id = cpa.article_id
                WHERE cpa.thread_id = %s
                AND a.deduplication_status = 'unique'
                ORDER BY a.published_at ASC
                LIMIT %s
            """
            
            cursor.execute(query, (thread_id, max_articles))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2][:500] + '...' if len(row[2]) > 500 else row[2],
                    'source': row[3],
                    'published_at': row[4].isoformat() if row[4] else None,
                    'category': row[5],
                    'url': row[6]
                })
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error getting thread articles: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _generate_context_summary(self, articles: List[Dict[str, Any]]) -> str:
        """Generate a summary of the context articles"""
        try:
            if not articles:
                return "No context articles found."
            
            # Extract key themes
            themes = self._extract_themes(articles)
            
            # Count sources
            sources = {}
            for article in articles:
                source = article.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            # Generate summary
            summary = f"Found {len(articles)} context articles covering {len(themes)} main themes. "
            summary += f"Key themes: {', '.join(themes[:5])}. "
            summary += f"Sources include: {', '.join(list(sources.keys())[:3])}."
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating context summary: {e}")
            return "Error generating context summary."
    
    def _generate_historical_summary(self, articles: List[Dict[str, Any]]) -> str:
        """Generate a summary of historical context articles"""
        try:
            if not articles:
                return "No historical context articles found."
            
            # Extract key themes
            themes = self._extract_themes(articles)
            
            # Count sources
            sources = {}
            for article in articles:
                source = article.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            # Generate summary
            summary = f"Found {len(articles)} historical context articles covering {len(themes)} main themes. "
            summary += f"Key themes: {', '.join(themes[:5])}. "
            summary += f"Sources include: {', '.join(list(sources.keys())[:3])}."
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating historical summary: {e}")
            return "Error generating historical summary."
    
    def _generate_related_summary(self, articles: List[Dict[str, Any]]) -> str:
        """Generate a summary of related context articles"""
        try:
            if not articles:
                return "No related context articles found."
            
            # Extract key themes
            themes = self._extract_themes(articles)
            
            # Count sources
            sources = {}
            for article in articles:
                source = article.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            # Generate summary
            summary = f"Found {len(articles)} related context articles covering {len(themes)} main themes. "
            summary += f"Key themes: {', '.join(themes[:5])}. "
            summary += f"Sources include: {', '.join(list(sources.keys())[:3])}."
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating related summary: {e}")
            return "Error generating related summary."
    
    def _generate_background_summary(self, articles: List[Dict[str, Any]]) -> str:
        """Generate a summary of background context articles"""
        try:
            if not articles:
                return "No background context articles found."
            
            # Extract key themes
            themes = self._extract_themes(articles)
            
            # Count sources
            sources = {}
            for article in articles:
                source = article.get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1
            
            # Generate summary
            summary = f"Found {len(articles)} background context articles covering {len(themes)} main themes. "
            summary += f"Key themes: {', '.join(themes[:5])}. "
            summary += f"Sources include: {', '.join(list(sources.keys())[:3])}."
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating background summary: {e}")
            return "Error generating background summary."
    
    def _extract_themes(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract common themes from articles"""
        try:
            # Simple theme extraction based on common words
            word_freq = {}
            for article in articles:
                title = article.get('title', '').lower()
                content = article.get('content', '').lower()
                
                # Extract meaningful words
                words = re.findall(r'\b\w{4,}\b', title + ' ' + content)
                for word in words:
                    if word not in ['this', 'that', 'with', 'from', 'they', 'have', 'been', 'will', 'were']:
                        word_freq[word] = word_freq.get(word, 0) + 1
            
            # Return top themes
            themes = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [theme[0] for theme in themes[:10]]
            
        except Exception as e:
            self.logger.error(f"Error extracting themes: {e}")
            return []
    
    def _extract_key_events(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key events from historical articles"""
        try:
            events = []
            for article in articles:
                title = article.get('title', '')
                if any(word in title.lower() for word in ['breakthrough', 'discovery', 'announcement', 'launch', 'release']):
                    events.append(title)
            
            return events[:10]  # Limit to 10 events
            
        except Exception as e:
            self.logger.error(f"Error extracting key events: {e}")
            return []
    
    def _extract_key_concepts(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key concepts from background articles"""
        try:
            concepts = []
            for article in articles:
                title = article.get('title', '')
                if any(word in title.lower() for word in ['introduction', 'guide', 'overview', 'basics', 'fundamentals']):
                    concepts.append(title)
            
            return concepts[:10]  # Limit to 10 concepts
            
        except Exception as e:
            self.logger.error(f"Error extracting key concepts: {e}")
            return []
    
    def _extract_key_milestones(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key milestones from timeline articles"""
        try:
            milestones = []
            for article in articles:
                title = article.get('title', '')
                if any(word in title.lower() for word in ['breakthrough', 'launch', 'release', 'announcement', 'milestone']):
                    milestones.append(title)
            
            return milestones[:10]  # Limit to 10 milestones
            
        except Exception as e:
            self.logger.error(f"Error extracting key milestones: {e}")
            return []
    
    def _extract_key_entities(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key entities from articles"""
        try:
            entities = []
            # Simple entity extraction based on capitalization patterns
            for article in articles:
                title = article.get('title', '')
                content = article.get('content', '')
                
                # Extract capitalized words (potential entities)
                words = re.findall(r'\b[A-Z][a-z]+\b', title + ' ' + content)
                for word in words:
                    if len(word) > 2 and word not in entities:
                        entities.append(word)
                        if len(entities) >= 20:  # Limit entities
                            break
                
                if len(entities) >= 20:
                    break
            
            return entities[:20]
            
        except Exception as e:
            self.logger.error(f"Error extracting key entities: {e}")
            return []
    
    def _find_related_topics(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Find related topics from articles"""
        try:
            topics = []
            # Extract topics from article categories and titles
            for article in articles:
                category = article.get('category', '')
                title = article.get('title', '')
                
                if category and category not in topics:
                    topics.append(category)
                
                # Extract potential topics from title
                title_words = title.split()
                for word in title_words:
                    word_clean = re.sub(r'[^\w]', '', word.lower())
                    if len(word_clean) > 4 and word_clean not in topics:
                        topics.append(word_clean)
                        if len(topics) >= 10:  # Limit topics
                            break
                
                if len(topics) >= 10:
                    break
            
            return topics[:10]
            
        except Exception as e:
            self.logger.error(f"Error finding related topics: {e}")
            return []
    
    def _find_connection_points(self, articles: List[Dict[str, Any]], thread_info: Dict[str, Any]) -> List[str]:
        """Find connection points between related articles and thread"""
        try:
            connections = []
            thread_keywords = [thread_info['title'].lower().split()]
            
            for article in articles:
                title = article.get('title', '').lower()
                content = article.get('content', '').lower()
                
                # Check for keyword overlaps
                for keyword_list in thread_keywords:
                    for keyword in keyword_list:
                        if keyword in title or keyword in content:
                            connections.append(f"Keyword overlap: {keyword}")
                            break
                
                if len(connections) >= 5:  # Limit connections
                    break
            
            return connections
            
        except Exception as e:
            self.logger.error(f"Error finding connection points: {e}")
            return []
    
    def _find_related_threads(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find related story threads based on articles"""
        try:
            # This would require a more sophisticated analysis
            # For now, return empty list
            return []
            
        except Exception as e:
            self.logger.error(f"Error finding related threads: {e}")
            return []
    
    def _assess_expertise_level(self, articles: List[Dict[str, Any]]) -> str:
        """Assess the expertise level of background articles"""
        try:
            # Simple assessment based on title keywords
            beginner_keywords = ['introduction', 'basics', 'fundamentals', 'guide', 'overview']
            advanced_keywords = ['advanced', 'expert', 'professional', 'research']
            
            beginner_count = 0
            advanced_count = 0
            
            for article in articles:
                title = article.get('title', '').lower()
                if any(word in title for word in beginner_keywords):
                    beginner_count += 1
                elif any(word in title for word in advanced_keywords):
                    advanced_count += 1
            
            if beginner_count > advanced_count:
                return "beginner"
            elif advanced_count > beginner_count:
                return "advanced"
            else:
                return "intermediate"
                
        except Exception as e:
            self.logger.error(f"Error assessing expertise level: {e}")
            return "unknown"
    
    def _identify_development_phases(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Identify development phases from timeline articles"""
        try:
            phases = []
            # Simple phase identification based on article count
            if len(articles) >= 10:
                phases = ["Research & Development", "Prototype", "Testing", "Launch", "Growth"]
            elif len(articles) >= 5:
                phases = ["Development", "Testing", "Launch"]
            else:
                phases = ["Initial Development"]
            
            return phases
            
        except Exception as e:
            self.logger.error(f"Error identifying development phases: {e}")
            return []
    
    def _build_evolution_timeline(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build evolution timeline from historical articles"""
        return self._build_timeline_from_articles(articles)
    
    def _build_timeline_from_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build a timeline from articles"""
        try:
            timeline = []
            for article in articles:
                published_at = article.get('published_at')
                if published_at:
                    try:
                        date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        timeline.append({
                            'date': published_at,
                            'title': article.get('title', ''),
                            'source': article.get('source', ''),
                            'summary': article.get('content', '')[:200] + '...' if len(article.get('content', '')) > 200 else article.get('content', ''),
                            'url': article.get('url', '')
                        })
                    except:
                        continue
            
            # Sort by date
            timeline.sort(key=lambda x: x['date'])
            return timeline
            
        except Exception as e:
            self.logger.error(f"Error building timeline: {e}")
            return []
    
    def _log_context_request(self, thread_id: int, context_type: str, 
                            context: Dict[str, Any]) -> None:
        """Log a RAG context request"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO rag_context_requests 
                (article_id, context_type, context_description, priority, status, context_data, sources_used, confidence_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                None,
                context_type,
                f"Context request for thread {thread_id}: {context.get('context_summary', 'Context generated')}",
                1,
                'completed',
                json.dumps(context),
                [],
                0.95
            ))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error logging context request: {e}")
        finally:
            if conn:
                conn.close()
    
    def _calculate_historical_period(self, created_date: datetime) -> str:
        """Calculate the historical period for context"""
        try:
            now = datetime.now()
            if created_date.tzinfo:
                now = now.replace(tzinfo=created_date.tzinfo)
            
            days_diff = (now - created_date).days
            
            if days_diff < 7:
                return "Last week"
            elif days_diff < 30:
                return "Last month"
            elif days_diff < 90:
                return "Last quarter"
            elif days_diff < 365:
                return "Last year"
            else:
                return f"{days_diff // 365} years ago"
                
        except Exception as e:
            self.logger.error(f"Error calculating historical period: {e}")
            return "Unknown period"
    
    def _calculate_timeline_period(self, articles: List[Dict[str, Any]]) -> str:
        """Calculate the timeline period for articles"""
        try:
            if not articles:
                return "No timeline available"
            
            dates = []
            for article in articles:
                published_at = article.get('published_at')
                if published_at:
                    try:
                        date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        dates.append(date_obj)
                    except:
                        continue
            
            if not dates:
                return "No timeline available"
            
            min_date = min(dates)
            max_date = max(dates)
            days_diff = (max_date - min_date).days
            
            if days_diff < 1:
                return "Same day"
            elif days_diff < 7:
                return f"{days_diff} days"
            elif days_diff < 30:
                return f"{days_diff // 7} weeks"
            elif days_diff < 365:
                return f"{days_diff // 30} months"
            else:
                return f"{days_diff // 365} years"
                
        except Exception as e:
            self.logger.error(f"Error calculating timeline period: {e}")
            return "Unknown period"
