import logging
import psycopg2
import re
from typing import Dict, Any, List
from datetime import datetime
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

class IntelligentTaggingService:
    """
    Service for intelligent tag extraction and management.
    Automatically extracts, scores, and updates tags based on content analysis.
    """
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.logger = logger
        
        # Basic patterns for tag extraction
        self.tech_keywords = [
            'artificial intelligence', 'machine learning', 'blockchain', 'cryptocurrency',
            'climate change', 'renewable energy', 'cybersecurity', 'quantum computing',
            'space exploration', 'biotechnology', 'nanotechnology', 'robotics',
            'automation', 'digital transformation', 'sustainability'
        ]
        
        self.locations = [
            'United States', 'USA', 'China', 'Russia', 'Ukraine', 'Germany', 'France',
            'United Kingdom', 'UK', 'Japan', 'South Korea', 'North Korea', 'India',
            'Brazil', 'Canada', 'Australia', 'Israel', 'Palestine', 'Iran', 'Iraq',
            'Syria', 'Afghanistan', 'Turkey', 'Saudi Arabia', 'Egypt', 'South Africa'
        ]
        
        self.organizations = [
            'NATO', 'UN', 'UNESCO', 'WHO', 'WTO', 'IMF', 'World Bank', 'EU',
            'European Union', 'ASEAN', 'G7', 'G20', 'OPEC', 'FBI', 'CIA', 'NSA',
            'Pentagon', 'White House', 'Congress', 'Senate', 'House', 'Parliament'
        ]
        
        self.tech_terms = [
            'AI', 'ML', 'NLP', 'GPT', 'ChatGPT', 'LLM', 'API', 'SaaS', 'PaaS',
            'IaaS', 'IoT', '5G', '6G', 'WiFi', 'Bluetooth', 'NFC', 'RFID',
            'QR', 'AR', 'VR', 'MR', 'XR', 'blockchain', 'bitcoin', 'ethereum'
        ]
    
    def extract_tags_from_content(self, content: str, title: str = '', max_tags: int = 20) -> List[Dict[str, Any]]:
        """
        Extract intelligent tags from article content and title.
        """
        try:
            full_text = f"{title} {content}".lower()
            all_tags = []
            
            # Extract technology keywords
            for keyword in self.tech_keywords:
                if keyword.lower() in full_text:
                    all_tags.append({
                        'name': keyword,
                        'category': 'keywords',
                        'weight': 1.5,
                        'source': 'content_analysis'
                    })
            
            # Extract locations
            for location in self.locations:
                if location.lower() in full_text:
                    all_tags.append({
                        'name': location,
                        'category': 'locations',
                        'weight': 1.2,
                        'source': 'content_analysis'
                    })
            
            # Extract organizations
            for org in self.organizations:
                if org.lower() in full_text:
                    all_tags.append({
                        'name': org,
                        'category': 'organizations',
                        'weight': 1.3,
                        'source': 'content_analysis'
                    })
            
            # Extract tech terms
            for term in self.tech_terms:
                if term.lower() in full_text:
                    all_tags.append({
                        'name': term,
                        'category': 'technologies',
                        'weight': 1.1,
                        'source': 'content_analysis'
                    })
            
            # Extract proper nouns (entities)
            entity_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
            entities = re.findall(entity_pattern, content)
            for entity in entities[:10]:  # Limit to avoid too many
                if len(entity) >= 3:
                    all_tags.append({
                        'name': entity,
                        'category': 'entities',
                        'weight': 1.0,
                        'source': 'content_analysis'
                    })
            
            # Score and rank tags
            tag_scores = {}
            for tag in all_tags:
                name_lower = tag['name'].lower()
                if name_lower not in tag_scores:
                    tag_scores[name_lower] = {
                        'name': tag['name'],
                        'category': tag['category'],
                        'score': 0,
                        'frequency': 0
                    }
                tag_scores[name_lower]['score'] += tag['weight']
                tag_scores[name_lower]['frequency'] += 1
            
            # Convert to list and sort
            scored_tags = list(tag_scores.values())
            scored_tags.sort(key=lambda x: x['score'], reverse=True)
            
            return scored_tags[:max_tags]
            
        except Exception as e:
            self.logger.error(f"Error extracting tags: {e}")
            return []
    
    def analyze_story_thread_tags(self, thread_id: int) -> Dict[str, Any]:
        """
        Analyze and suggest tags for a story thread based on all its articles.
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT a.id, a.title, a.content, a.summary
                FROM articles a
                JOIN content_priority_assignments cpa ON a.id = cpa.article_id
                WHERE cpa.thread_id = %s
                ORDER BY a.published_date DESC
            """, (thread_id,))
            
            articles = cursor.fetchall()
            
            if not articles:
                return {'error': 'No articles found for this thread'}
            
            # Extract tags from all articles
            all_tags = []
            for article in articles:
                article_id, title, content, summary = article
                text_content = summary if summary else content
                tags = self.extract_tags_from_content(text_content, title)
                all_tags.extend(tags)
            
            # Aggregate tags
            tag_aggregation = defaultdict(lambda: {
                'name': '',
                'category': '',
                'total_score': 0,
                'frequency': 0
            })
            
            for tag in all_tags:
                name_lower = tag['name'].lower()
                tag_aggregation[name_lower]['name'] = tag['name']
                tag_aggregation[name_lower]['category'] = tag['category']
                tag_aggregation[name_lower]['total_score'] += tag['score']
                tag_aggregation[name_lower]['frequency'] += 1
            
            # Sort by score
            aggregated_tags = list(tag_aggregation.values())
            aggregated_tags.sort(key=lambda x: x['total_score'], reverse=True)
            
            # Get current tags
            cursor.execute("""
                SELECT keyword, weight FROM story_thread_keywords 
                WHERE thread_id = %s
            """, (thread_id,))
            
            current_tags = {row[0].lower(): row[1] for row in cursor.fetchall()}
            
            # Find new tags
            new_tags = []
            for tag in aggregated_tags[:10]:
                name_lower = tag['name'].lower()
                if name_lower not in current_tags:
                    new_tags.append({
                        'keyword': tag['name'],
                        'weight': min(tag['total_score'] / 10, 1.0),
                        'category': tag['category'],
                        'frequency': tag['frequency']
                    })
            
            conn.close()
            
            return {
                'thread_id': thread_id,
                'analysis_date': datetime.now().isoformat(),
                'articles_analyzed': len(articles),
                'new_tags': new_tags,
                'updated_tags': [],
                'top_tags': aggregated_tags[:10],
                'current_tags_count': len(current_tags),
                'suggested_tags_count': len(new_tags)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing thread tags: {e}")
            return {'error': str(e)}
    
    def update_thread_tags(self, thread_id: int, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update story thread tags based on analysis results.
        """
        try:
            if 'error' in analysis_result:
                return analysis_result
            
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            updates_made = 0
            
            # Add new tags
            for tag in analysis_result.get('new_tags', []):
                cursor.execute("""
                    INSERT INTO story_thread_keywords (thread_id, keyword, weight, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (thread_id, keyword) DO UPDATE SET
                    weight = EXCLUDED.weight,
                    created_at = NOW()
                """, (thread_id, tag['keyword'], tag['weight']))
                updates_made += 1
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'thread_id': thread_id,
                'updates_made': updates_made,
                'new_tags_added': len(analysis_result.get('new_tags', [])),
                'message': f'Updated {updates_made} tags for thread {thread_id}'
            }
            
        except Exception as e:
            self.logger.error(f"Error updating thread tags: {e}")
            return {'error': str(e)}
    
    def get_thread_tag_analytics(self, thread_id: int) -> Dict[str, Any]:
        """
        Get analytics about thread tags.
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT stk.keyword, stk.weight, stk.created_at
                FROM story_thread_keywords stk
                WHERE stk.thread_id = %s
                ORDER BY stk.weight DESC
            """, (thread_id,))
            
            tags = []
            for row in cursor.fetchall():
                tags.append({
                    'keyword': row[0],
                    'weight': float(row[1]),
                    'created_at': row[2].isoformat() if row[2] else None
                })
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_tags,
                    AVG(weight) as avg_weight,
                    MAX(weight) as max_weight,
                    MIN(weight) as min_weight
                FROM story_thread_keywords 
                WHERE thread_id = %s
            """, (thread_id,))
            
            stats_row = cursor.fetchone()
            stats = {
                'total_tags': stats_row[0],
                'avg_weight': float(stats_row[1]) if stats_row[1] else 0,
                'max_weight': float(stats_row[2]) if stats_row[2] else 0,
                'min_weight': float(stats_row[3]) if stats_row[3] else 0
            }
            
            conn.close()
            
            return {
                'thread_id': thread_id,
                'tags': tags,
                'statistics': stats,
                'analysis_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting thread tag analytics: {e}")
            return {'error': str(e)}