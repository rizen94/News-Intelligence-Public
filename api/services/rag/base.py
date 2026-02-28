"""
RAG Service Base - Core RAG Operations
Basic RAG functionality with Wikipedia and GDELT integration
Consolidated from rag_service.py
"""

import os
import json
import logging
import asyncio
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from urllib.parse import quote

logger = logging.getLogger(__name__)


class BaseRAGService:
    """
    Base RAG Service - Core RAG operations
    
    Provides:
    - Wikipedia API integration
    - GDELT API integration
    - Basic context enhancement
    - Entity and topic extraction
    - RAG context storage
    """
    
    def __init__(self, db_config: Dict[str, str] = None):
        """
        Initialize base RAG service
        
        Args:
            db_config: Database configuration (optional, uses env vars if not provided)
        """
        if db_config is None:
            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'database': os.getenv('DB_NAME', 'news_intelligence'),
                'user': os.getenv('DB_USER', 'newsapp'),
                'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
                'port': int(os.getenv('DB_PORT', '5433')),
            }
        
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'News Intelligence System v3.0 RAG Service'
        })
        
        # Wikipedia API configuration
        self.wikipedia_api_url = "https://en.wikipedia.org/api/rest_v1"
        
        # GDELT API configuration (using free tier)
        self.gdelt_api_url = "https://api.gdeltproject.org/api/v2"
        
        # Smart cache service
        self.cache_service = None
    
    def _get_cache_service(self):
        """Get smart cache service instance"""
        if self.cache_service is None:
            try:
                from services.smart_cache_service import get_smart_cache_service
                self.cache_service = get_smart_cache_service()
            except ImportError:
                logger.warning("Smart cache service not available")
                self.cache_service = None
        return self.cache_service
    
    async def enhance_storyline_context(
        self, 
        storyline_id: str, 
        storyline_title: str, 
        articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enhance storyline with RAG context from Wikipedia and GDELT"""
        try:
            logger.info(f"Enhancing storyline context for: {storyline_title}")
            
            # Extract key entities and topics from articles
            entities = self._extract_entities_from_articles(articles)
            topics = self._extract_topics_from_articles(articles)
            
            # Get Wikipedia context
            wikipedia_context = await self._get_wikipedia_context(topics, entities)
            
            # Get GDELT context
            gdelt_context = await self._get_gdelt_context(topics, entities)
            
            # Combine all context
            rag_context = {
                "wikipedia": wikipedia_context,
                "gdelt": gdelt_context,
                "extracted_entities": entities,
                "extracted_topics": topics,
                "enhanced_at": datetime.now(timezone.utc).isoformat(),
                "storyline_id": storyline_id
            }
            
            # Save RAG context to database
            await self._save_rag_context(storyline_id, rag_context)
            
            return rag_context
            
        except Exception as e:
            logger.error(f"Error enhancing storyline context: {e}")
            return {
                "error": str(e),
                "wikipedia": {},
                "gdelt": {},
                "extracted_entities": [],
                "extracted_topics": [],
                "enhanced_at": datetime.now(timezone.utc).isoformat(),
                "storyline_id": storyline_id
            }
    
    def _extract_entities_from_articles(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key entities from articles"""
        entities = set()
        
        for article in articles:
            # Extract from title
            title_entities = self._extract_entities_from_text(article.get('title', ''))
            entities.update(title_entities)
            
            # Extract from content
            content_entities = self._extract_entities_from_text(article.get('content', ''))
            entities.update(content_entities)
            
            # Extract from source
            if article.get('source'):
                entities.add(article['source'])
        
        # Filter and clean entities
        filtered_entities = []
        for entity in entities:
            if len(entity) > 2 and len(entity) < 50:  # Reasonable length
                # Remove common words
                if entity.lower() not in ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']:
                    filtered_entities.append(entity)
        
        return filtered_entities[:20]  # Limit to top 20 entities
    
    def _extract_topics_from_articles(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key topics from articles"""
        topics = set()
        
        for article in articles:
            # Extract from title
            title_topics = self._extract_topics_from_text(article.get('title', ''))
            topics.update(title_topics)
            
            # Extract from content
            content_topics = self._extract_topics_from_text(article.get('content', ''))
            topics.update(content_topics)
        
        return list(topics)[:15]  # Limit to top 15 topics
    
    def _extract_entities_from_text(self, text: str) -> List[str]:
        """Extract entities from text using simple pattern matching"""
        if not text:
            return []
        
        # Simple entity extraction - look for capitalized words and phrases
        entities = []
        
        # Find capitalized words (potential proper nouns)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', text)
        entities.extend(capitalized_words)
        
        # Find quoted phrases
        quoted_phrases = re.findall(r'"([^"]+)"', text)
        entities.extend(quoted_phrases)
        
        # Find company/product names (common patterns)
        company_patterns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        entities.extend(company_patterns)
        
        return entities
    
    def _extract_topics_from_text(self, text: str) -> List[str]:
        """Extract topics from text"""
        if not text:
            return []
        
        topics = []
        
        # Common tech/business topics
        topic_keywords = [
            'AI', 'artificial intelligence', 'machine learning', 'blockchain', 'cryptocurrency',
            'startup', 'funding', 'investment', 'venture capital', 'IPO', 'acquisition',
            'technology', 'innovation', 'digital', 'platform', 'app', 'software',
            'data', 'analytics', 'cloud', 'cybersecurity', 'privacy', 'regulation',
            'market', 'economy', 'business', 'finance', 'banking', 'fintech'
        ]
        
        text_lower = text.lower()
        for keyword in topic_keywords:
            if keyword.lower() in text_lower:
                topics.append(keyword)
        
        return topics
    
    async def _get_wikipedia_context(self, topics: List[str], entities: List[str]) -> Dict[str, Any]:
        """Get Wikipedia context for topics and entities with smart caching"""
        wikipedia_context = {
            "articles": [],
            "summaries": [],
            "error": None,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        try:
            cache_service = self._get_cache_service()
            
            # Search for each topic/entity
            search_terms = (topics + entities)[:10]  # Limit to 10 searches
            
            for term in search_terms:
                try:
                    # Check cache first
                    if cache_service:
                        cached_data = await cache_service.get('wikipedia', term)
                        
                        if cached_data:
                            wikipedia_context["articles"].extend(cached_data.get("articles", []))
                            wikipedia_context["summaries"].extend(cached_data.get("summaries", []))
                            wikipedia_context["cache_hits"] += 1
                            logger.debug(f"Wikipedia cache hit for: {term}")
                            continue
                    
                    # Cache miss - fetch from API
                    wikipedia_context["cache_misses"] += 1
                    
                    # Search for the term
                    search_url = f"{self.wikipedia_api_url}/page/summary/{quote(term)}"
                    response = self.session.get(search_url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if 'extract' in data:
                            article_data = {
                                "title": data.get('title', term),
                                "extract": data.get('extract', ''),
                                "url": data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                                "search_term": term
                            }
                            wikipedia_context["articles"].append(article_data)
                            
                            summary_data = {
                                "term": term,
                                "summary": data.get('extract', '')[:500] + "..." if len(data.get('extract', '')) > 500 else data.get('extract', '')
                            }
                            wikipedia_context["summaries"].append(summary_data)
                            
                            # Cache the result
                            if cache_service:
                                cache_data = {
                                    "articles": [article_data],
                                    "summaries": [summary_data]
                                }
                                await cache_service.set('wikipedia', term, cache_data)
                                logger.debug(f"Cached Wikipedia data for: {term}")
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Error fetching Wikipedia context for {term}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error in Wikipedia context retrieval: {e}")
            wikipedia_context["error"] = str(e)
        
        return wikipedia_context
    
    async def _get_gdelt_context(self, topics: List[str], entities: List[str]) -> Dict[str, Any]:
        """Get GDELT context for topics and entities with smart caching"""
        gdelt_context = {
            "events": [],
            "mentions": [],
            "error": None,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        try:
            cache_service = self._get_cache_service()
            
            # Search for recent events related to topics
            search_terms = (topics + entities)[:5]  # Limit to 5 searches
            
            for term in search_terms:
                try:
                    # Check cache first
                    if cache_service:
                        cached_data = await cache_service.get('gdelt', term)
                        
                        if cached_data:
                            gdelt_context["events"].extend(cached_data.get("events", []))
                            gdelt_context["mentions"].extend(cached_data.get("mentions", []))
                            gdelt_context["cache_hits"] += 1
                            logger.debug(f"GDELT cache hit for: {term}")
                            continue
                    
                    # Cache miss - fetch from API
                    gdelt_context["cache_misses"] += 1
                    
                    # Search GDELT for recent events
                    search_url = f"{self.gdelt_api_url}/doc/doc"
                    params = {
                        "query": term,
                        "format": "json",
                        "maxrecords": 10,
                        "startdatetime": (datetime.now() - timedelta(days=30)).strftime("%Y%m%d%H%M%S"),
                        "enddatetime": datetime.now().strftime("%Y%m%d%H%M%S")
                    }
                    
                    response = self.session.get(search_url, params=params, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        events = []
                        
                        if 'docs' in data:
                            for doc in data['docs'][:5]:  # Limit to 5 events per term
                                event_data = {
                                    "title": doc.get('title', ''),
                                    "url": doc.get('url', ''),
                                    "date": doc.get('date', ''),
                                    "source": doc.get('source', ''),
                                    "search_term": term
                                }
                                events.append(event_data)
                                gdelt_context["events"].append(event_data)
                        
                        # Cache the result
                        if cache_service:
                            cache_data = {
                                "events": events,
                                "mentions": []
                            }
                            await cache_service.set('gdelt', term, cache_data)
                            logger.debug(f"Cached GDELT data for: {term}")
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Error fetching GDELT context for {term}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error in GDELT context retrieval: {e}")
            gdelt_context["error"] = str(e)
        
        return gdelt_context
    
    async def _save_rag_context(self, storyline_id: str, rag_context: Dict[str, Any]):
        """Save RAG context to database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insert or update RAG context
            cursor.execute("""
                INSERT INTO storyline_rag_context (
                    storyline_id, rag_data, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s
                ) ON CONFLICT (storyline_id) 
                DO UPDATE SET 
                    rag_data = EXCLUDED.rag_data,
                    updated_at = EXCLUDED.updated_at
            """, (
                storyline_id,
                json.dumps(rag_context),
                datetime.now(timezone.utc),
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Saved RAG context for storyline {storyline_id}")
            
        except Exception as e:
            logger.error(f"Error saving RAG context: {e}")
    
    async def get_rag_context(self, storyline_id: str) -> Optional[Dict[str, Any]]:
        """Get RAG context for a storyline"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT rag_data FROM storyline_rag_context 
                WHERE storyline_id = %s
            """, (storyline_id,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result['rag_data']:
                # Handle both string and dict cases
                if isinstance(result['rag_data'], str):
                    return json.loads(result['rag_data'])
                elif isinstance(result['rag_data'], dict):
                    return result['rag_data']
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting RAG context: {e}")
            return None

