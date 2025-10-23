"""
Enhanced Topic Intelligence Service
Uses ML/LLM to intelligently filter and rank topics
"""

import re
import json
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
from collections import Counter
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class TopicIntelligenceService:
    """Intelligent topic filtering and ranking service"""
    
    def __init__(self):
        self.stop_words = self._load_stop_words()
        self.topic_patterns = self._load_topic_patterns()
        
    def _load_stop_words(self) -> set:
        """Load comprehensive stop words including common noise"""
        return {
            # Common web terms
            'www', 'http', 'https', 'com', 'org', 'net', 'html', 'php', 'asp',
            'url', 'link', 'website', 'site', 'page', 'web', 'online',
            
            # Days of the week
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun',
            
            # Months
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            
            # Common generic words
            'news', 'article', 'story', 'report', 'update', 'latest', 'breaking',
            'today', 'yesterday', 'tomorrow', 'week', 'month', 'year',
            'time', 'date', 'hour', 'minute', 'second',
            
            # Common verbs (too generic)
            'said', 'says', 'told', 'asked', 'added', 'noted', 'reported',
            'according', 'source', 'sources', 'official', 'officials',
            
            # Common adjectives (too generic)
            'new', 'old', 'good', 'bad', 'big', 'small', 'large', 'small',
            'first', 'last', 'next', 'previous', 'recent', 'latest',
            
            # Common nouns (too generic)
            'people', 'person', 'man', 'woman', 'child', 'children',
            'thing', 'things', 'stuff', 'item', 'items',
            
            # Common prepositions/conjunctions
            'and', 'or', 'but', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'down', 'out', 'off', 'over', 'under',
            
            # Common pronouns
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'her', 'its', 'our', 'their',
            
            # Common determiners
            'this', 'that', 'these', 'those', 'some', 'any', 'all', 'every', 'each',
            'no', 'none', 'other', 'another', 'same', 'different',
            
            # Numbers (usually not meaningful topics)
            'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
            'hundred', 'thousand', 'million', 'billion',
            
            # Common locations (too generic)
            'here', 'there', 'where', 'everywhere', 'nowhere', 'somewhere',
            'home', 'work', 'office', 'building', 'place', 'area', 'region',
            
            # Common actions (too generic)
            'go', 'come', 'get', 'give', 'take', 'make', 'do', 'have', 'be', 'is', 'are',
            'was', 'were', 'been', 'being', 'will', 'would', 'could', 'should',
        }
    
    def _load_topic_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for identifying meaningful topics"""
        return {
            'politics': [
                'election', 'vote', 'voting', 'campaign', 'candidate', 'president', 'senator',
                'congress', 'house', 'senate', 'government', 'policy', 'legislation', 'bill',
                'democrat', 'republican', 'party', 'political', 'politics'
            ],
            'business': [
                'economy', 'economic', 'market', 'stock', 'trading', 'investment', 'company',
                'corporation', 'business', 'finance', 'financial', 'bank', 'banking',
                'revenue', 'profit', 'loss', 'merger', 'acquisition'
            ],
            'technology': [
                'technology', 'tech', 'software', 'hardware', 'computer', 'internet', 'digital',
                'ai', 'artificial', 'intelligence', 'machine', 'learning', 'data', 'cyber',
                'security', 'privacy', 'innovation', 'startup', 'app', 'application'
            ],
            'health': [
                'health', 'healthcare', 'medical', 'medicine', 'doctor', 'patient', 'hospital',
                'disease', 'treatment', 'vaccine', 'vaccination', 'pandemic', 'covid',
                'research', 'study', 'clinical', 'therapy'
            ],
            'environment': [
                'climate', 'environment', 'environmental', 'green', 'sustainability', 'carbon',
                'emission', 'pollution', 'renewable', 'energy', 'solar', 'wind', 'electric',
                'conservation', 'biodiversity', 'ecosystem'
            ],
            'international': [
                'international', 'global', 'world', 'country', 'nation', 'foreign', 'diplomatic',
                'treaty', 'agreement', 'trade', 'export', 'import', 'sanction', 'embargo',
                'conflict', 'war', 'peace', 'security', 'defense', 'military'
            ]
        }
    
    def filter_intelligent_topics(self, topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter topics using intelligent ML/LLM-based criteria"""
        filtered_topics = []
        
        for topic in topics:
            topic_name = topic.get('name', '').lower().strip()
            
            # Skip if empty or too short
            if len(topic_name) < 3:
                continue
                
            # Skip if it's a stop word
            if topic_name in self.stop_words:
                continue
                
            # Skip if it's mostly numbers or special characters
            if re.match(r'^[\d\s\-_\.]+$', topic_name):
                continue
                
            # Skip if it's a URL fragment
            if any(fragment in topic_name for fragment in ['www', 'http', 'com', 'org', 'net']):
                continue
                
            # Calculate topic quality score
            quality_score = self._calculate_topic_quality(topic_name, topic)
            
            # Only include topics with meaningful quality scores
            if quality_score > 0.3:  # Threshold for meaningful topics
                topic['quality_score'] = quality_score
                topic['category'] = self._categorize_topic(topic_name)
                filtered_topics.append(topic)
        
        # Sort by quality score and relevance
        filtered_topics.sort(key=lambda x: (x.get('quality_score', 0), x.get('avg_confidence', 0)), reverse=True)
        
        return filtered_topics[:50]  # Limit to top 50 most meaningful topics
    
    def _calculate_topic_quality(self, topic_name: str, topic_data: Dict[str, Any]) -> float:
        """Calculate topic quality score using multiple criteria"""
        score = 0.0
        
        # Length bonus (meaningful topics are usually 4-20 characters)
        if 4 <= len(topic_name) <= 20:
            score += 0.2
        elif len(topic_name) > 20:
            score += 0.1
            
        # Confidence score from ML analysis
        confidence = topic_data.get('avg_confidence', 0)
        score += confidence * 0.3
        
        # Article count bonus (topics with more articles are more significant)
        article_count = topic_data.get('article_count', 0)
        if article_count > 10:
            score += 0.3
        elif article_count > 5:
            score += 0.2
        elif article_count > 2:
            score += 0.1
            
        # Category relevance bonus
        category = self._categorize_topic(topic_name)
        if category != 'other':
            score += 0.2
            
        # Pattern matching bonus
        for category, patterns in self.topic_patterns.items():
            if any(pattern in topic_name for pattern in patterns):
                score += 0.1
                break
                
        # Recency bonus (recent topics are more relevant)
        latest_article = topic_data.get('latest_article_date')
        if latest_article:
            try:
                article_date = datetime.fromisoformat(latest_article.replace('Z', '+00:00'))
                days_ago = (datetime.now() - article_date.replace(tzinfo=None)).days
                if days_ago < 7:
                    score += 0.2
                elif days_ago < 30:
                    score += 0.1
            except:
                pass
                
        return min(score, 1.0)  # Cap at 1.0
    
    def _categorize_topic(self, topic_name: str) -> str:
        """Categorize topic based on patterns"""
        topic_lower = topic_name.lower()
        
        for category, patterns in self.topic_patterns.items():
            if any(pattern in topic_lower for pattern in patterns):
                return category
                
        return 'other'
    
    def get_intelligent_word_cloud(self, limit: int = 30) -> Dict[str, Any]:
        """Generate intelligent word cloud data"""
        try:
            conn = psycopg2.connect(
                host='localhost',
                database='news_intelligence',
                user='newsapp',
                password='newsapp_password',
                port=5432
            )
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get topic clusters with article counts
                cur.execute("""
                    SELECT 
                        tc.cluster_name,
                        tc.cluster_description,
                        tc.cluster_type,
                        COUNT(atc.article_id) as article_count,
                        AVG(atc.relevance_score) as avg_confidence,
                        MAX(a.created_at) as latest_article_date
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    LEFT JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type
                    ORDER BY article_count DESC, avg_confidence DESC
                """)
                
                topics = []
                for row in cur.fetchall():
                    topics.append({
                        'name': row['cluster_name'],
                        'description': row['cluster_description'],
                        'type': row['cluster_type'],
                        'article_count': row['article_count'] or 0,
                        'avg_confidence': float(row['avg_confidence'] or 0),
                        'latest_article_date': row['latest_article_date'].isoformat() if row['latest_article_date'] else None
                    })
                
                # Apply intelligent filtering
                filtered_topics = self.filter_intelligent_topics(topics)
                
                # Generate word cloud data
                word_cloud_data = []
                for topic in filtered_topics[:limit]:
                    word_cloud_data.append({
                        'text': topic['name'],
                        'value': topic['article_count'],
                        'confidence': topic['avg_confidence'],
                        'category': topic['category'],
                        'quality_score': topic['quality_score']
                    })
                
                return {
                    'success': True,
                    'data': {
                        'word_cloud': word_cloud_data,
                        'total_topics': len(filtered_topics),
                        'filtered_from': len(topics),
                        'categories': self._get_category_stats(filtered_topics)
                    },
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error generating intelligent word cloud: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {'word_cloud': []}
            }
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _get_category_stats(self, topics: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get statistics by category"""
        category_stats = {}
        for topic in topics:
            category = topic.get('category', 'other')
            category_stats[category] = category_stats.get(category, 0) + 1
        return category_stats

# Global instance
topic_intelligence_service = TopicIntelligenceService()
