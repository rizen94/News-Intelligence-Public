"""
Advanced Topic Extraction Service
Creates dynamic word clouds and big picture topic analysis
"""

import re
import json
import logging
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import psycopg2
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TopicInsight:
    """Represents a topic insight with metadata"""
    name: str
    frequency: int
    relevance_score: float
    trend_direction: str  # 'rising', 'falling', 'stable'
    articles: List[int]
    keywords: List[str]
    sentiment: str
    category: str
    created_at: datetime

class AdvancedTopicExtractor:
    """Advanced topic extraction using multiple techniques"""
    
    def __init__(self, db_connection_func):
        self.get_db_connection = db_connection_func
        
        # Topic categories for better organization
        self.topic_categories = {
            'politics': ['election', 'president', 'congress', 'vote', 'campaign', 'policy', 'government'],
            'economy': ['market', 'economy', 'inflation', 'recession', 'gdp', 'unemployment', 'financial'],
            'technology': ['ai', 'tech', 'software', 'digital', 'innovation', 'cyber', 'data'],
            'environment': ['climate', 'environment', 'carbon', 'green', 'sustainability', 'renewable'],
            'health': ['health', 'medical', 'covid', 'vaccine', 'pandemic', 'healthcare', 'disease'],
            'international': ['war', 'conflict', 'military', 'defense', 'security', 'diplomacy'],
            'social': ['social', 'community', 'culture', 'society', 'education', 'justice'],
            'business': ['business', 'corporate', 'industry', 'trade', 'commerce', 'startup']
        }
        
        # Stop words to filter out common words
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
    
    def extract_topics_from_articles(self, time_period_hours: int = 24) -> List[TopicInsight]:
        """Extract topics from recent articles using multiple techniques"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return []
            
            try:
                with conn.cursor() as cur:
                    # Get recent articles
                    cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                    
                    cur.execute("""
                        SELECT id, title, content, summary, published_at, sentiment_score, source_domain
                        FROM articles 
                        WHERE created_at >= %s 
                        AND content IS NOT NULL 
                        AND LENGTH(content) > 100
                        ORDER BY published_at DESC
                    """, (cutoff_time,))
                    
                    articles = cur.fetchall()
                    
                    if not articles:
                        logger.info("No recent articles found for topic extraction")
                        return []
                    
                    # Extract topics using multiple techniques
                    topics = self._extract_topics_multi_technique(articles)
                    
                    # Analyze trends
                    topics = self._analyze_topic_trends(topics)
                    
                    # Categorize topics
                    topics = self._categorize_topics(topics)
                    
                    return topics
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return []
    
    def _extract_topics_multi_technique(self, articles: List[Tuple]) -> List[TopicInsight]:
        """Extract topics using multiple techniques"""
        topics = []
        
        # Technique 1: Keyword frequency analysis
        keyword_topics = self._extract_keyword_topics(articles)
        topics.extend(keyword_topics)
        
        # Technique 2: Phrase extraction
        phrase_topics = self._extract_phrase_topics(articles)
        topics.extend(phrase_topics)
        
        # Technique 3: Entity-based topics
        entity_topics = self._extract_entity_topics(articles)
        topics.extend(entity_topics)
        
        # Merge similar topics
        topics = self._merge_similar_topics(topics)
        
        return topics
    
    def _extract_keyword_topics(self, articles: List[Tuple]) -> List[TopicInsight]:
        """Extract topics based on keyword frequency"""
        word_freq = Counter()
        article_keywords = defaultdict(list)
        
        for article_id, title, content, summary, published_at, sentiment_score, source_domain in articles:
            # Combine title and content for analysis
            text = f"{title} {summary or ''} {content or ''}".lower()
            
            # Extract words (2+ characters, alphanumeric)
            words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
            
            # Filter stop words and count frequency
            filtered_words = [word for word in words if word not in self.stop_words]
            
            for word in filtered_words:
                word_freq[word] += 1
                article_keywords[word].append(article_id)
        
        # Create topics from frequent keywords
        topics = []
        for word, freq in word_freq.most_common(50):  # Top 50 keywords
            if freq >= 2:  # Minimum frequency threshold
                topics.append(TopicInsight(
                    name=word.title(),
                    frequency=freq,
                    relevance_score=min(freq / 10.0, 1.0),  # Normalize to 0-1
                    trend_direction='stable',
                    articles=article_keywords[word],
                    keywords=[word],
                    sentiment='neutral',
                    category='general',
                    created_at=datetime.now()
                ))
        
        return topics
    
    def _extract_phrase_topics(self, articles: List[Tuple]) -> List[TopicInsight]:
        """Extract topics based on common phrases"""
        phrase_freq = Counter()
        article_phrases = defaultdict(list)
        
        for article_id, title, content, summary, published_at, sentiment_score, source_domain in articles:
            text = f"{title} {summary or ''}".lower()
            
            # Extract 2-3 word phrases
            words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
            
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"
                if len(phrase) > 5 and not any(word in self.stop_words for word in phrase.split()):
                    phrase_freq[phrase] += 1
                    article_phrases[phrase].append(article_id)
        
        # Create topics from frequent phrases
        topics = []
        for phrase, freq in phrase_freq.most_common(30):  # Top 30 phrases
            if freq >= 2:
                topics.append(TopicInsight(
                    name=phrase.title(),
                    frequency=freq,
                    relevance_score=min(freq / 5.0, 1.0),
                    trend_direction='stable',
                    articles=article_phrases[phrase],
                    keywords=phrase.split(),
                    sentiment='neutral',
                    category='general',
                    created_at=datetime.now()
                ))
        
        return topics
    
    def _extract_entity_topics(self, articles: List[Tuple]) -> List[TopicInsight]:
        """Extract topics based on named entities (simplified)"""
        entity_freq = Counter()
        article_entities = defaultdict(list)
        
        # Simple entity extraction (capitalized words)
        for article_id, title, content, summary, published_at, sentiment_score, source_domain in articles:
            text = f"{title} {summary or ''}"
            
            # Find capitalized words (potential entities)
            entities = re.findall(r'\b[A-Z][a-z]+\b', text)
            
            for entity in entities:
                if len(entity) > 2 and entity.lower() not in self.stop_words:
                    entity_freq[entity] += 1
                    article_entities[entity].append(article_id)
        
        # Create topics from frequent entities
        topics = []
        for entity, freq in entity_freq.most_common(20):  # Top 20 entities
            if freq >= 2:
                topics.append(TopicInsight(
                    name=entity,
                    frequency=freq,
                    relevance_score=min(freq / 8.0, 1.0),
                    trend_direction='stable',
                    articles=article_entities[entity],
                    keywords=[entity],
                    sentiment='neutral',
                    category='entity',
                    created_at=datetime.now()
                ))
        
        return topics
    
    def _merge_similar_topics(self, topics: List[TopicInsight]) -> List[TopicInsight]:
        """Merge similar topics to avoid duplicates"""
        merged_topics = []
        processed = set()
        
        for topic in topics:
            if topic.name.lower() in processed:
                continue
            
            # Find similar topics
            similar_topics = [topic]
            for other_topic in topics:
                if (other_topic.name.lower() != topic.name.lower() and 
                    other_topic.name.lower() not in processed and
                    self._are_topics_similar(topic, other_topic)):
                    similar_topics.append(other_topic)
                    processed.add(other_topic.name.lower())
            
            # Merge similar topics
            if len(similar_topics) > 1:
                merged_topic = self._merge_topic_list(similar_topics)
                merged_topics.append(merged_topic)
            else:
                merged_topics.append(topic)
            
            processed.add(topic.name.lower())
        
        return merged_topics
    
    def _are_topics_similar(self, topic1: TopicInsight, topic2: TopicInsight) -> bool:
        """Check if two topics are similar enough to merge"""
        # Check keyword overlap
        keywords1 = set(topic1.keywords)
        keywords2 = set(topic2.keywords)
        
        overlap = len(keywords1.intersection(keywords2))
        total = len(keywords1.union(keywords2))
        
        similarity = overlap / total if total > 0 else 0
        return similarity > 0.3  # 30% similarity threshold
    
    def _merge_topic_list(self, topics: List[TopicInsight]) -> TopicInsight:
        """Merge a list of similar topics into one"""
        if not topics:
            return None
        
        # Use the most frequent topic as base
        base_topic = max(topics, key=lambda t: t.frequency)
        
        # Merge all data
        all_articles = []
        all_keywords = set()
        
        for topic in topics:
            all_articles.extend(topic.articles)
            all_keywords.update(topic.keywords)
        
        # Remove duplicates
        all_articles = list(set(all_articles))
        
        return TopicInsight(
            name=base_topic.name,
            frequency=len(all_articles),
            relevance_score=max(t.relevance_score for t in topics),
            trend_direction=base_topic.trend_direction,
            articles=all_articles,
            keywords=list(all_keywords),
            sentiment=base_topic.sentiment,
            category=base_topic.category,
            created_at=datetime.now()
        )
    
    def _analyze_topic_trends(self, topics: List[TopicInsight]) -> List[TopicInsight]:
        """Analyze trends for topics (simplified)"""
        # For now, mark all as stable
        # In a real implementation, you'd compare with historical data
        for topic in topics:
            topic.trend_direction = 'stable'
        
        return topics
    
    def _categorize_topics(self, topics: List[TopicInsight]) -> List[TopicInsight]:
        """Categorize topics based on keywords"""
        for topic in topics:
            topic.category = self._determine_category(topic.keywords)
        
        return topics
    
    def _determine_category(self, keywords: List[str]) -> str:
        """Determine the category for a topic based on keywords"""
        keyword_scores = defaultdict(int)
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for category, category_keywords in self.topic_categories.items():
                if keyword_lower in category_keywords:
                    keyword_scores[category] += 1
        
        if keyword_scores:
            return max(keyword_scores.items(), key=lambda x: x[1])[0]
        
        return 'general'
    
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
            # Add to word cloud
            word_cloud_data['words'].append({
                'text': topic.name,
                'size': min(topic.frequency * 10, 100),  # Scale for visualization
                'frequency': topic.frequency,
                'relevance': topic.relevance_score,
                'articles': len(topic.articles)
            })
            
            # Add to categories
            word_cloud_data['categories'][topic.category].append({
                'name': topic.name,
                'frequency': topic.frequency,
                'relevance': topic.relevance_score
            })
            
            # Add to trends
            word_cloud_data['trends'][topic.trend_direction].append({
                'name': topic.name,
                'frequency': topic.frequency
            })
        
        return word_cloud_data
    
    def save_topics_to_database(self, topics: List[TopicInsight]) -> bool:
        """Save extracted topics to database"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return False
            
            try:
                with conn.cursor() as cur:
                    for topic in topics:
                        # Insert or update topic cluster
                        cur.execute("""
                            INSERT INTO topic_clusters (cluster_name, cluster_description, cluster_type, is_active, metadata)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (cluster_name) DO UPDATE SET
                                cluster_description = EXCLUDED.cluster_description,
                                cluster_type = EXCLUDED.cluster_type,
                                metadata = EXCLUDED.metadata,
                                updated_at = CURRENT_TIMESTAMP
                            RETURNING id
                        """, (
                            topic.name,
                            f"Auto-extracted topic: {', '.join(topic.keywords[:5])}",
                            topic.category,
                            True,
                            json.dumps({
                                'keywords': topic.keywords,
                                'sentiment': topic.sentiment,
                                'trend_direction': topic.trend_direction,
                                'extraction_method': 'advanced_multi_technique',
                                'created_at': topic.created_at.isoformat()
                            })
                        ))
                        
                        topic_id = cur.fetchone()[0]
                        
                        # Insert article-topic relationships
                        for article_id in topic.articles:
                            cur.execute("""
                                INSERT INTO article_topic_clusters (article_id, topic_cluster_id, relevance_score)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
                                    relevance_score = EXCLUDED.relevance_score,
                                    assigned_at = CURRENT_TIMESTAMP
                            """, (article_id, topic_id, topic.relevance_score))
                    
                    conn.commit()
                    logger.info(f"Saved {len(topics)} topics to database")
                    return True
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error saving topics to database: {e}")
            return False
