"""
LLM-Based Topic Extraction Service
Uses existing Ollama infrastructure with resource management and fallback
"""

import logging
import asyncio
import uuid
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import psycopg2
from dataclasses import dataclass

# Import existing LLM services
import sys
import os

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(current_dir, '../../..')
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from modules.ml.entity_extractor import LocalEntityExtractor
from shared.services.llm_service import LLMService, TaskType
from domains.content_analysis.services.topic_clustering_service import TopicClusteringService
from domains.content_analysis.services.llm_activity_tracker import get_llm_activity_tracker

logger = logging.getLogger(__name__)

@dataclass
class TopicInsight:
    """Represents a topic insight with metadata"""
    name: str
    frequency: int
    relevance_score: float
    trend_direction: str
    articles: List[int]
    keywords: List[str]
    sentiment: str
    category: str
    entity_type: Optional[str] = None  # PERSON, ORGANIZATION, LOCATION, EVENT, etc.
    created_at: datetime = None

class LLMTopicExtractor:
    """
    LLM-based topic extraction using existing Ollama infrastructure
    Implements resource management, batching, and fallback to rule-based
    """
    
    def __init__(self, db_connection_func, schema: str = "politics", ollama_url: str = "http://localhost:11434"):
        self.get_db_connection = db_connection_func
        self.schema = schema
        self.ollama_url = ollama_url
        
        # Initialize LLM services (reuse existing infrastructure)
        self.entity_extractor = LocalEntityExtractor(ollama_url=ollama_url)
        self.llm_service = LLMService(ollama_base_url=ollama_url)
        
        # Resource management
        self.max_concurrent_extractions = 3  # Limit concurrent LLM calls
        self.batch_size = 5  # Process articles in batches
        self.cache_ttl = 3600  # 1 hour cache
        self.extraction_cache = {}  # Simple cache for article topic extraction
        
        # Fallback to rule-based if LLM unavailable
        self.use_llm = True
        self._test_llm_availability()
        
    def _test_llm_availability(self):
        """Test if LLM services are available"""
        tracker = get_llm_activity_tracker()
        try:
            # Quick test - try to extract entities from a simple text
            test_result = self.entity_extractor.extract_entities("Test", use_cache=False)
            self.use_llm = True
            tracker.update_llm_availability(True)
            logger.info("✅ LLM services available for topic extraction")
        except Exception as e:
            self.use_llm = False
            tracker.update_llm_availability(False)
            logger.warning(f"⚠️ LLM services unavailable, articles will be queued for later processing: {e}")
    
    def _queue_article_for_llm_extraction(self, article_id: int, priority: int = 2, error_message: str = None):
        """
        Queue an article for LLM-based topic extraction when LLM becomes available
        
        Args:
            article_id: ID of the article to queue
            priority: Priority level (1=low, 2=normal, 3=high, 4=urgent)
            error_message: Optional error message if this is a retry
        """
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.error("Cannot queue article: database connection failed")
                return False
            
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {self.schema}, public")
                    
                    # Calculate next retry time (exponential backoff)
                    retry_count = 0
                    if error_message:
                        # Get current retry count
                        cur.execute(f"""
                            SELECT retry_count FROM {self.schema}.topic_extraction_queue
                            WHERE article_id = %s
                        """, (article_id,))
                        result = cur.fetchone()
                        if result:
                            retry_count = result[0] + 1
                    
                    # Exponential backoff: 1min, 2min, 4min, 8min, 16min, 30min, 1hr, 2hr, 4hr, 8hr
                    backoff_minutes = min(60 * 2 ** min(retry_count, 8), 480)  # Max 8 hours
                    next_retry = datetime.now() + timedelta(minutes=backoff_minutes)
                    
                    # Insert or update queue entry
                    cur.execute(f"""
                        INSERT INTO {self.schema}.topic_extraction_queue
                            (article_id, status, priority, retry_count, next_retry_at, last_error, created_at)
                        VALUES (%s, 'pending', %s, %s, %s, %s, NOW())
                        ON CONFLICT (article_id) DO UPDATE SET
                            status = 'pending',
                            priority = GREATEST({self.schema}.topic_extraction_queue.priority, %s),
                            retry_count = %s,
                            next_retry_at = %s,
                            last_error = %s,
                            last_attempt_at = NOW()
                    """, (article_id, priority, retry_count, next_retry, error_message,
                          priority, retry_count, next_retry, error_message))
                    
                    conn.commit()
                    logger.info(f"✅ Queued article {article_id} for LLM topic extraction (retry {retry_count}, next retry: {next_retry})")
                    return True
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error queueing article {article_id} for LLM extraction: {e}")
            return False
    
    async def extract_topics_from_articles(self, time_period_hours: int = 24) -> List[TopicInsight]:
        """
        Extract topics from recent articles using LLM (with fallback)
        """
        try:
            conn = self.get_db_connection()
            if not conn:
                return []
            
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {self.schema}, public")
                    cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                    
                    # Build query as single line to avoid any formatting issues
                    query = (
                        f"SELECT id, title, content, summary, published_at, sentiment_score, source_domain "
                        f"FROM {self.schema}.articles "
                        f"WHERE created_at >= %s "
                        f"AND content IS NOT NULL "
                        f"AND LENGTH(content) > 100 "
                        f"ORDER BY published_at DESC "
                        f"LIMIT 100"
                    )
                    logger.debug(f"Executing query for schema {self.schema}")
                    cur.execute(query, (cutoff_time,))
                    
                    articles = cur.fetchall()
                    
                    if not articles:
                        logger.info("No recent articles found for topic extraction")
                        return []
                    
                    if self.use_llm:
                        # Use LLM-based extraction
                        topics = await self._extract_topics_with_llm(articles)
                    else:
                        # Queue articles for LLM processing when available
                        logger.info("LLM unavailable - queueing articles for later processing")
                        for article in articles:
                            article_id = article[0]
                            self._queue_article_for_llm_extraction(article_id, priority=2, 
                                                                  error_message="LLM service unavailable")
                        # Return empty topics - will be processed when LLM is available
                        topics = []
                    
                    return topics
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            logger.exception("Full traceback for extract_topics_from_articles:")
            return []
    
    async def _extract_topics_with_llm(self, articles: List[Tuple]) -> List[TopicInsight]:
        """
        Extract topics using LLM with batching and resource management
        """
        all_topics = []
        article_topics_map = defaultdict(list)  # article_id -> list of topics
        
        # Process articles in batches to manage resource usage
        for i in range(0, len(articles), self.batch_size):
            batch = articles[i:i + self.batch_size]
            logger.info(f"Processing topic extraction batch {i//self.batch_size + 1}/{(len(articles)-1)//self.batch_size + 1}")
            
            # Process batch with concurrency limit
            batch_tasks = []
            for article in batch:
                article_id, title, content, summary, published_at, sentiment_score, source_domain = article
                task = self._extract_topics_from_single_article(
                    article_id, title, content, summary
                )
                batch_tasks.append(task)
            
            # Process with semaphore to limit concurrent LLM calls
            semaphore = asyncio.Semaphore(self.max_concurrent_extractions)
            
            async def process_with_limit(task):
                async with semaphore:
                    return await task
            
            batch_results = await asyncio.gather(*[process_with_limit(t) for t in batch_tasks], return_exceptions=True)
            
            # Collect results
            for idx, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error extracting topics from article {batch[idx][0]}: {result}")
                    continue
                
                article_id = batch[idx][0]
                topics = result
                article_topics_map[article_id].extend(topics)
                all_topics.extend(topics)
            
            # Small delay between batches to prevent overload
            await asyncio.sleep(0.5)
        
        # Merge similar topics and aggregate by article
        merged_topics = self._merge_and_rank_topics(all_topics, article_topics_map)
        
        return merged_topics[:200]  # Return top 200 topics
    
    async def _extract_topics_from_single_article(self, article_id: int, title: str, content: str, summary: str) -> List[TopicInsight]:
        """
        Extract topics from a single article using LLM
        Combines entity extraction and topic clustering
        """
        task_id = str(uuid.uuid4())
        tracker = get_llm_activity_tracker()
        
        try:
            # Check cache first
            cache_key = f"{article_id}_{hash(title)}"
            if cache_key in self.extraction_cache:
                cached_time, cached_topics = self.extraction_cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                    return cached_topics
            
            # Track task start
            tracker.start_task(
                task_id=task_id,
                task_type='topic_extraction',
                article_id=article_id,
                domain=self.schema,
                metadata={'title': title[:100]}
            )
            
            # Combine text for analysis
            text = f"{title} {summary or ''} {content[:5000] if content else ''}"  # v7: full-text
            
            # Extract entities using NER (structured, fast)
            entities_result = self.entity_extractor.extract_entities(text, use_cache=True)
            
            # Extract topics using LLM (semantic understanding)
            # Use existing TopicClusteringService which has proper LLM integration
            try:
                topic_clustering = TopicClusteringService(
                    db_config={},  # Not needed for extraction only
                    ollama_url=self.ollama_url,
                    domain=self.schema
                )
                
                article_dict = {
                    'title': title,
                    'content': content[:5000] if content else '',  # v7: full-text
                    'excerpt': summary or ''
                }
                
                llm_topics = await topic_clustering.extract_topics_from_article(article_dict)
            except Exception as topic_error:
                logger.warning(f"TopicClusteringService failed, using direct LLM: {topic_error}")
                llm_topics = []
            
            # Combine entities and LLM topics
            topics = []
            
            # Add entities as topics
            for entity in entities_result.entities:
                if entity.confidence > 0.5:  # Filter low-confidence entities
                    topics.append(TopicInsight(
                        name=entity.text,
                        frequency=1,
                        relevance_score=entity.confidence,
                        trend_direction='stable',
                        articles=[article_id],
                        keywords=[entity.text],
                        sentiment='neutral',
                        category=self._map_entity_to_category(entity.label),
                        entity_type=entity.label,
                        created_at=datetime.now()
                    ))
            
            # Add LLM-extracted topics (only if article actually mentions the topic, and confidence sufficient)
            for llm_topic in llm_topics:
                topic_name = llm_topic.get('name', '')
                confidence = llm_topic.get('confidence', 0.7)
                if topic_name and len(topic_name) > 2 and confidence >= 0.5:
                    if not self._article_mentions_topic(text, topic_name, llm_topic.get('keywords', [topic_name])):
                        continue
                    topics.append(TopicInsight(
                        name=topic_name,
                        frequency=1,
                        relevance_score=confidence,
                        trend_direction='stable',
                        articles=[article_id],
                        keywords=llm_topic.get('keywords', [topic_name]),
                        sentiment='neutral',
                        category=llm_topic.get('category', 'general'),
                        created_at=datetime.now()
                    ))
            
            # Cache results
            self.extraction_cache[cache_key] = (datetime.now(), topics)
            
            # Track task completion
            tracker.complete_task(task_id, success=True)
            
            return topics
            
        except Exception as e:
            logger.error(f"Error extracting topics from article {article_id}: {e}")
            # Track task failure
            tracker.complete_task(task_id, success=False, error=str(e))
            # Queue article for retry
            self._queue_article_for_llm_extraction(article_id, priority=2, error_message=str(e))
            return []
    
    def _article_mentions_topic(self, article_text: str, topic_name: str, keywords: List[str]) -> bool:
        """
        Verify the article text actually mentions the topic (reduces false assignments).
        For multi-word topics: require at least 2 significant words from the topic in the article.
        For single-word topics: require that word to appear.
        """
        if not article_text or not topic_name:
            return False
        text_lower = article_text.lower()
        generic = {'the', 'and', 'for', 'new', 'says', 'said', 'news', 'article', 'report', 'year'}
        topic_words = [w for w in re.findall(r'[a-z0-9]+', topic_name.lower())
                      if len(w) >= 4 and w not in generic]
        kw_words = [w for kw in (keywords or []) if isinstance(kw, str)
                    for w in re.findall(r'[a-z0-9]+', str(kw).lower())
                    if len(w) >= 4 and w not in generic]
        candidates = list(dict.fromkeys(topic_words + kw_words))
        if not candidates:
            return True
        matches = sum(1 for w in candidates if w in text_lower)
        if len(topic_name.split()) >= 3:
            return matches >= 2
        return matches >= 1

    def _map_entity_to_category(self, entity_type: str) -> str:
        """Map entity type to topic category"""
        mapping = {
            'PERSON': 'politics',
            'ORGANIZATION': 'business',
            'LOCATION': 'international',
            'EVENT': 'general',
            'PRODUCT': 'technology',
            'TECHNOLOGY': 'technology',
            'DATE': 'general',
            'MONEY': 'economy',
            'PERCENT': 'economy',
            'QUANTITY': 'general'
        }
        return mapping.get(entity_type, 'general')
    
    def _merge_and_rank_topics(self, all_topics: List[TopicInsight], article_topics_map: Dict[int, List[TopicInsight]]) -> List[TopicInsight]:
        """
        Merge similar topics and aggregate by article count
        Filters out generic topics (dates, single-word locations, source names)
        """
        # Generic topic patterns to filter out
        generic_patterns = [
            r'^\d{4}$',  # Years like "2026", "2025"
            r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$',  # Days of week
            r'^(January|February|March|April|May|June|July|August|September|October|November|December)$',  # Months
            r'^(US|USA|UK|U\.S\.|U\.S\.A\.)$',  # Generic country abbreviations
        ]
        
        # Single-word topics that are likely generic (unless they're proper nouns)
        generic_single_words = {
            'news', 'article', 'report', 'story', 'update', 'breaking',
            'today', 'yesterday', 'tomorrow', 'week', 'month', 'year'
        }
        
        # Source names to filter (common news sources)
        source_names = {
            'breitbart', 'cnn', 'fox', 'bbc', 'reuters', 'ap', 'associated press',
            'npr', 'wsj', 'wall street journal', 'nytimes', 'new york times'
        }
        
        topic_map = {}  # topic_name -> TopicInsight
        
        for topic in all_topics:
            topic_key = topic.name.lower().strip()
            topic_name_lower = topic_key
            
            # Filter out generic topics
            is_generic = False
            
            # Check against patterns
            for pattern in generic_patterns:
                if re.match(pattern, topic_name_lower):
                    is_generic = True
                    break
            
            # Check single-word generic terms
            if not is_generic and len(topic_name_lower.split()) == 1:
                if topic_name_lower in generic_single_words:
                    is_generic = True
                # Filter single-letter or very short topics
                elif len(topic_name_lower) <= 2:
                    is_generic = True
            
            # Check source names
            if not is_generic and topic_name_lower in source_names:
                is_generic = True
            
            # Skip generic topics
            if is_generic:
                continue
            
            if topic_key in topic_map:
                # Merge: combine articles, update frequency, take max relevance
                existing = topic_map[topic_key]
                existing.articles = list(set(existing.articles + topic.articles))
                existing.frequency = len(existing.articles)
                existing.relevance_score = max(existing.relevance_score, topic.relevance_score)
                existing.keywords = list(set(existing.keywords + topic.keywords))
            else:
                # New topic
                topic.frequency = len(topic.articles)
                topic_map[topic_key] = topic
        
        # Sort by frequency and relevance
        merged_topics = sorted(
            topic_map.values(),
            key=lambda t: (t.frequency, t.relevance_score),
            reverse=True
        )
        
        return merged_topics
    
    def generate_word_cloud_data(self, topics: List[TopicInsight]) -> Dict[str, Any]:
        """Generate word cloud data for visualization"""
        word_cloud_data = {
            'words': [],
            'categories': defaultdict(list),
            'trends': {
                'rising': [],
                'falling': [],
                'stable': []
            },
            'summary': {
                'total_topics': len(topics),
                'total_articles': sum(t.frequency for t in topics),
                'categories': len(set(t.category for t in topics))
            }
        }
        
        for topic in topics:
            word_cloud_data['words'].append({
                'text': topic.name,
                'size': min(topic.frequency * 10, 100),
                'frequency': topic.frequency,
                'relevance': topic.relevance_score,
                'articles': len(topic.articles)
            })
            
            word_cloud_data['categories'][topic.category].append({
                'name': topic.name,
                'frequency': topic.frequency,
                'relevance': topic.relevance_score
            })
            
            word_cloud_data['trends'][topic.trend_direction].append({
                'name': topic.name,
                'frequency': topic.frequency
            })
        
        return word_cloud_data
    
    def save_topics_to_database(self, topics: List[TopicInsight]) -> bool:
        """
        Save extracted topics to database
        Reuses the same logic from advanced_topic_extractor
        """
        # Import and reuse existing save logic
        from domains.content_analysis.services.advanced_topic_extractor import AdvancedTopicExtractor
        fallback_extractor = AdvancedTopicExtractor(self.get_db_connection, schema=self.schema)
        return fallback_extractor.save_topics_to_database(topics)

