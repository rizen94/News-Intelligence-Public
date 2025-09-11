#!/usr/bin/env python3
"""
Timeline Generator Service
Uses ML/LLM to generate intelligent timeline events from articles
"""

import logging
import json
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import requests
import os

logger = logging.getLogger(__name__)

@dataclass
class TimelineEvent:
    """Represents a timeline event"""
    event_id: str
    title: str
    description: str
    event_date: str
    event_time: Optional[str]
    source: str
    url: Optional[str]
    importance_score: float
    event_type: str
    location: Optional[str]
    entities: List[str]
    tags: List[str]
    created_at: str
    source_article_ids: List[int] = None

class TimelineGenerator:
    """Generates intelligent timeline events using ML/LLM"""
    
    def __init__(self, db_config: Dict[str, str], ollama_url: str = "http://localhost:11434"):
        self.db_config = db_config
        self.ollama_url = ollama_url
        self.model_name = "llama3.1:70b-instruct-q4_K_M"  # Use the best available model
        
        # Update database config to use correct database name
        if self.db_config.get('database') == 'news_intelligence':
            self.db_config['database'] = 'news_system'
        
    def generate_timeline_events(
        self, 
        storyline_id: str, 
        storyline_data: Dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_events: int = 50
    ) -> List[TimelineEvent]:
        """
        Generate timeline events for a storyline using ML/LLM analysis
        
        Args:
            storyline_id: ID of the storyline
            storyline_data: Storyline configuration data
            start_date: Start date for timeline (YYYY-MM-DD)
            end_date: End date for timeline (YYYY-MM-DD)
            max_events: Maximum number of events to generate
            
        Returns:
            List of TimelineEvent objects
        """
        try:
            # Get relevant articles using intelligent filtering
            articles = self._get_relevant_articles(
                storyline_id, storyline_data, start_date, end_date, max_events * 3
            )
            
            if not articles:
                logger.warning(f"No relevant articles found for storyline {storyline_id}")
                return []
            
            # Group articles by date and analyze them
            events = []
            for date, date_articles in self._group_articles_by_date(articles).items():
                if len(events) >= max_events:
                    break
                    
                # Generate events for this date using LLM
                date_events = self._generate_events_for_date(
                    date, date_articles, storyline_data
                )
                events.extend(date_events)
            
            # Sort events by date and importance
            events.sort(key=lambda x: (x.event_date, -x.importance_score))
            
            # Store events in database
            stored_events = self._store_timeline_events(storyline_id, events)
            
            return stored_events[:max_events]
            
        except Exception as e:
            logger.error(f"Error generating timeline events: {e}")
            return []
    
    def _get_relevant_articles(
        self, 
        storyline_id: str, 
        storyline_data: Dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 150
    ) -> List[Dict[str, Any]]:
        """Get articles relevant to the storyline using intelligent filtering"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Build intelligent search query
            where_conditions = ["a.processing_status = 'completed'"]
            params = []
            param_count = 0
            
            # Date filtering
            if start_date:
                where_conditions.append(f"DATE(a.published_at) >= %s")
                params.append(start_date)
                param_count += 1
            
            if end_date:
                where_conditions.append(f"DATE(a.published_at) <= %s")
                params.append(end_date)
                param_count += 1
            
            # Intelligent content matching using storyline keywords and entities
            keyword_conditions = []
            for keyword in storyline_data.get('keywords', []):
                param_count += 1
                keyword_conditions.append(f"""
                    (a.title ILIKE %s OR 
                     a.content ILIKE %s OR 
                     a.summary ILIKE %s OR
                     a.entities_extracted::text ILIKE %s)
                """)
                keyword_term = f"%{keyword}%"
                params.extend([keyword_term, keyword_term, keyword_term, keyword_term])
            
            # Add entity matching
            for entity in storyline_data.get('entities', []):
                param_count += 1
                keyword_conditions.append(f"""
                    (a.title ILIKE %s OR 
                     a.content ILIKE %s OR 
                     a.summary ILIKE %s OR
                     a.entities_extracted::text ILIKE %s)
                """)
                entity_term = f"%{entity}%"
                params.extend([entity_term, entity_term, entity_term, entity_term])
            
            if keyword_conditions:
                where_conditions.append(f"({' OR '.join(keyword_conditions)})")
            
            where_clause = " AND ".join(where_conditions)
            
            # Query with relevance scoring
            query = f"""
                SELECT 
                    a.id,
                    a.title,
                    a.content,
                    a.summary,
                    a.source,
                    a.url,
                    a.published_at,
                    a.category,
                    a.engagement_score,
                    a.entities_extracted,
                    a.topics_extracted,
                    a.sentiment_score,
                    a.readability_score,
                    -- Calculate relevance score
                    (
                        CASE WHEN a.title ILIKE ANY(%s) THEN 3 ELSE 0 END +
                        CASE WHEN a.summary ILIKE ANY(%s) THEN 2 ELSE 0 END +
                        CASE WHEN a.content ILIKE ANY(%s) THEN 1 ELSE 0 END +
                        COALESCE(a.engagement_score, 0) * 2
                    ) as relevance_score
                FROM articles a
                WHERE {where_clause}
                ORDER BY relevance_score DESC, a.published_at DESC
                LIMIT %s
            """
            
            # Prepare search terms for relevance scoring
            search_terms = [f"%{kw}%" for kw in storyline_data.get('keywords', [])]
            if not search_terms:
                search_terms = [f"%{storyline_id.replace('_', ' ')}%"]
            
            params = [search_terms, search_terms, search_terms] + params + [limit]
            
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            articles = []
            for row in rows:
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'summary': row[3],
                    'source': row[4],
                    'url': row[5],
                    'published_at': row[6],
                    'category': row[7],
                    'engagement_score': row[8],
                    'entities_extracted': row[9],
                    'topics_extracted': row[10],
                    'sentiment_score': row[11],
                    'readability_score': row[12],
                    'relevance_score': row[13]
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"Error getting relevant articles: {e}")
            return []
    
    def _group_articles_by_date(self, articles: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group articles by publication date"""
        grouped = {}
        for article in articles:
            if article['published_at']:
                date_str = article['published_at'].strftime('%Y-%m-%d')
                if date_str not in grouped:
                    grouped[date_str] = []
                grouped[date_str].append(article)
        return grouped
    
    def _generate_events_for_date(
        self, 
        date: str, 
        articles: List[Dict[str, Any]], 
        storyline_data: Dict[str, Any]
    ) -> List[TimelineEvent]:
        """Generate timeline events for a specific date using LLM analysis"""
        try:
            if not articles:
                return []
            
            # Prepare context for LLM
            context = self._prepare_llm_context(date, articles, storyline_data)
            
            # Generate events using LLM
            events_data = self._call_llm_for_events(context)
            
            # Convert to TimelineEvent objects
            events = []
            for i, event_data in enumerate(events_data):
                # Find the most relevant article for this event
                best_article = self._find_best_article_for_event(event_data, articles)
                
                event = TimelineEvent(
                    event_id=f"{date}_{i}_{best_article['id']}",
                    title=event_data.get('title', 'Timeline Event'),
                    description=event_data.get('description', ''),
                    event_date=date,
                    event_time=event_data.get('time'),
                    source=best_article['source'],
                    url=best_article['url'],
                    importance_score=event_data.get('importance', 0.5),
                    event_type=event_data.get('type', 'general'),
                    location=event_data.get('location'),
                    entities=event_data.get('entities', []),
                    tags=event_data.get('tags', []),
                    created_at=datetime.now().isoformat()
                )
                
                # Add source article IDs for database relationships
                event.source_article_ids = [best_article['id']]
                events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"Error generating events for date {date}: {e}")
            return []
    
    def _prepare_llm_context(
        self, 
        date: str, 
        articles: List[Dict[str, Any]], 
        storyline_data: Dict[str, Any]
    ) -> str:
        """Prepare context for LLM analysis"""
        
        # Sort articles by relevance and importance
        articles.sort(key=lambda x: (x['relevance_score'], x['engagement_score']), reverse=True)
        
        context = f"""
STORYLINE: {storyline_data.get('name', 'Unknown')}
DESCRIPTION: {storyline_data.get('description', '')}
KEYWORDS: {', '.join(storyline_data.get('keywords', []))}
ENTITIES: {', '.join(storyline_data.get('entities', []))}
DATE: {date}

ARTICLES FOR ANALYSIS:
"""
        
        for i, article in enumerate(articles[:10]):  # Limit to top 10 articles
            context += f"""
Article {i+1}:
Title: {article['title']}
Source: {article['source']}
Summary: {article['summary'][:300] if article['summary'] else 'No summary'}
Relevance Score: {article['relevance_score']}
"""
        
        context += """
TASK: Analyze these articles and extract 1-3 key timeline events for this date that are directly related to the storyline. Each event should be:
1. A specific, factual event (not general news)
2. Directly related to the storyline keywords and entities
3. Have clear importance and impact
4. Include specific details like location, people involved, etc.

Return as JSON array with this format:
[
  {
    "title": "Brief event title",
    "description": "Detailed description of what happened",
    "type": "military|diplomatic|humanitarian|economic|political|other",
    "importance": 0.0-1.0,
    "time": "HH:MM" (if available),
    "location": "Location if mentioned",
    "entities": ["Person1", "Organization1"],
    "tags": ["tag1", "tag2"]
  }
]
"""
        
        return context
    
    def _call_llm_for_events(self, context: str) -> List[Dict[str, Any]]:
        """Call LLM to generate timeline events"""
        try:
            # Use Ollama API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": context,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temperature for more consistent output
                        "top_p": 0.9,
                        "max_tokens": 2000
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Extract JSON from response
                try:
                    # Find JSON array in response
                    start_idx = response_text.find('[')
                    end_idx = response_text.rfind(']') + 1
                    
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = response_text[start_idx:end_idx]
                        events = json.loads(json_str)
                        return events if isinstance(events, list) else []
                except json.JSONDecodeError:
                    logger.warning("Failed to parse LLM response as JSON")
                    return []
            
            logger.warning(f"LLM API call failed: {response.status_code}")
            return []
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            # Fallback to simple event generation
            return self._generate_fallback_events(context)
    
    def _generate_fallback_events(self, context: str) -> List[Dict[str, Any]]:
        """Generate basic timeline events without LLM when connection fails"""
        try:
            # Extract basic information from context
            events = []
            
            # Look for article information in the context
            lines = context.split('\n')
            current_article = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('Article '):
                    if current_article:
                        # Process the previous article
                        event = self._create_fallback_event(current_article)
                        if event:
                            events.append(event)
                    current_article = {}
                elif line.startswith('Title: '):
                    current_article['title'] = line.replace('Title: ', '')
                elif line.startswith('Source: '):
                    current_article['source'] = line.replace('Source: ', '')
                elif line.startswith('Summary: '):
                    current_article['summary'] = line.replace('Summary: ', '')
            
            # Process the last article
            if current_article:
                event = self._create_fallback_event(current_article)
                if event:
                    events.append(event)
            
            return events[:3]  # Limit to 3 events
            
        except Exception as e:
            logger.error(f"Error generating fallback events: {e}")
            return []
    
    def _create_fallback_event(self, article: Dict[str, str]) -> Dict[str, Any]:
        """Create a basic timeline event from article data"""
        try:
            title = article.get('title', '')
            summary = article.get('summary', '')
            source = article.get('source', 'Unknown')
            
            if not title:
                return None
            
            # Determine event type based on keywords
            event_type = 'general'
            if any(word in title.lower() for word in ['military', 'attack', 'defense', 'battle']):
                event_type = 'military'
            elif any(word in title.lower() for word in ['sanctions', 'economic', 'trade', 'aid']):
                event_type = 'economic'
            elif any(word in title.lower() for word in ['refugee', 'hospital', 'civilian', 'humanitarian']):
                event_type = 'humanitarian'
            elif any(word in title.lower() for word in ['nato', 'diplomatic', 'meeting', 'talks']):
                event_type = 'diplomatic'
            
            # Calculate importance score based on content
            importance = 0.5
            if any(word in title.lower() for word in ['major', 'significant', 'victory', 'breakthrough']):
                importance = 0.8
            elif any(word in title.lower() for word in ['strike', 'attack', 'casualties']):
                importance = 0.7
            
            return {
                'title': title,
                'description': summary[:200] if summary else title,
                'type': event_type,
                'importance': importance,
                'time': None,
                'location': None,
                'entities': [],
                'tags': []
            }
            
        except Exception as e:
            logger.error(f"Error creating fallback event: {e}")
            return None
    
    def _find_best_article_for_event(
        self, 
        event_data: Dict[str, Any], 
        articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Find the most relevant article for a timeline event"""
        if not articles:
            return {}
        
        # Simple scoring based on title and content similarity
        best_article = articles[0]
        best_score = 0
        
        event_title = event_data.get('title', '').lower()
        event_entities = [e.lower() for e in event_data.get('entities', [])]
        
        for article in articles:
            score = 0
            article_title = article['title'].lower()
            article_entities = [e.lower() for e in (article.get('entities_extracted') or [])]
            
            # Title similarity
            if event_title and any(word in article_title for word in event_title.split()):
                score += 2
            
            # Entity overlap
            entity_overlap = len(set(event_entities) & set(article_entities))
            score += entity_overlap
            
            # Relevance score
            score += article.get('relevance_score', 0)
            
            if score > best_score:
                best_score = score
                best_article = article
        
        return best_article
    
    def _store_timeline_events(self, storyline_id: str, events: List[TimelineEvent]) -> List[TimelineEvent]:
        """Store timeline events in the database with proper relationships"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            stored_events = []
            
            for event in events:
                # Insert timeline event
                insert_event_query = """
                    INSERT INTO timeline_events (
                        event_id, storyline_id, title, description, event_date, event_time,
                        source, url, importance_score, event_type, location, entities, tags,
                        ml_generated, confidence_score, source_article_ids, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (event_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        importance_score = EXCLUDED.importance_score,
                        event_type = EXCLUDED.event_type,
                        location = EXCLUDED.location,
                        entities = EXCLUDED.entities,
                        tags = EXCLUDED.tags,
                        confidence_score = EXCLUDED.confidence_score,
                        source_article_ids = EXCLUDED.source_article_ids,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id, event_id
                """
                
                # Prepare event data
                event_data = (
                    event.event_id,
                    storyline_id,
                    event.title,
                    event.description,
                    event.event_date,
                    event.event_time,
                    event.source,
                    event.url,
                    event.importance_score,
                    event.event_type,
                    event.location,
                    json.dumps(event.entities),
                    event.tags,
                    True,  # ml_generated
                    event.importance_score,  # confidence_score
                    [],  # source_article_ids (will be populated separately)
                    event.created_at,
                    event.created_at
                )
                
                cur.execute(insert_event_query, event_data)
                result = cur.fetchone()
                
                if result:
                    event_db_id, event_id = result
                    
                    # Store article relationships in timeline_event_sources
                    if hasattr(event, 'source_article_ids') and event.source_article_ids:
                        for article_id in event.source_article_ids:
                            insert_source_query = """
                                INSERT INTO timeline_event_sources (
                                    event_id, article_id, relevance_score, contribution_type, created_at
                                ) VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (event_id, article_id) DO UPDATE SET
                                    relevance_score = EXCLUDED.relevance_score,
                                    contribution_type = EXCLUDED.contribution_type
                            """
                            
                            cur.execute(insert_source_query, (
                                event_id,
                                article_id,
                                event.importance_score,
                                'primary',
                                event.created_at
                            ))
                    
                    stored_events.append(event)
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Stored {len(stored_events)} timeline events for storyline {storyline_id}")
            return stored_events
            
        except Exception as e:
            logger.error(f"Error storing timeline events: {e}")
            return events  # Return original events if storage fails
