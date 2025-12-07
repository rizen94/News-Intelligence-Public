"""
Topic Clustering and Auto-Tagging Service with Iterative Learning
Uses LLM to intelligently cluster articles by topic and learn from feedback
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import httpx
import asyncio

logger = logging.getLogger(__name__)

class TopicClusteringService:
    """
    Intelligent topic clustering service using LLM with iterative learning
    """
    
    def __init__(self, db_config: Dict[str, str], ollama_url: str = "http://localhost:11434"):
        """
        Initialize the topic clustering service
        
        Args:
            db_config: Database configuration dictionary
            ollama_url: URL of the Ollama service
        """
        self.db_config = db_config
        self.ollama_url = ollama_url
        self.model_name = "llama3.1:8b"
        self.timeout = 120  # 2 minutes timeout
        
    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.db_config.get('host', 'localhost'),
            database=self.db_config.get('database', 'news_intelligence'),
            user=self.db_config.get('user', 'newsapp'),
            password=self.db_config.get('password', 'newsapp_password'),
            port=self.db_config.get('port', 5432)
        )
    
    async def _call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """
        Make a call to Ollama API
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Generated text response
        """
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent results
                    "top_p": 0.9,
                    "num_predict": 1500,
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            logger.info(f"🤖 Calling Ollama for topic clustering with model: {self.model_name}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '').strip()
                    logger.info(f"✅ Ollama response received for topic clustering")
                    return response_text
                else:
                    logger.error(f"❌ Ollama API error: {response.status_code} - {response.text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"❌ Ollama API error: {e}")
            return ""
    
    async def extract_topics_from_article(self, article: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract topics from a single article using LLM
        
        Args:
            article: Article dictionary with title, content, etc.
            
        Returns:
            List of topic dictionaries with name, confidence, and keywords
        """
        try:
            title = article.get('title', '')
            content = article.get('content', '') or article.get('excerpt', '')
            existing_topics = article.get('topics', []) or []
            
            # Limit content length for LLM
            content_preview = content[:2000] if len(content) > 2000 else content
            
            system_prompt = """You are an expert news analyst specializing in topic extraction and categorization.
Your task is to identify the main topics and themes in news articles.
Return your response as a JSON array of topics, each with: name, confidence (0-1), keywords (array), and category."""
            
            prompt = f"""Analyze the following news article and extract the main topics.

Article Title: {title}

Article Content:
{content_preview}

Existing Topics (if any): {json.dumps(existing_topics)}

Instructions:
1. Identify 2-5 main topics that best describe this article
2. For each topic, provide:
   - name: A clear, concise topic name (2-4 words)
   - confidence: Your confidence in this topic (0.0 to 1.0)
   - keywords: 3-5 related keywords
   - category: One of: politics, business, technology, health, environment, international, sports, entertainment, other

3. Focus on specific, meaningful topics (not generic terms like "news" or "article")
4. Consider the article's main subject, key entities, and themes

Return ONLY a JSON array in this exact format:
[
  {{
    "name": "Topic Name",
    "confidence": 0.85,
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "category": "politics"
  }}
]

JSON Response:"""
            
            response = await self._call_ollama(prompt, system_prompt)
            
            if not response:
                return []
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                try:
                    topics = json.loads(json_match.group())
                    # Validate and clean topics
                    validated_topics = []
                    for topic in topics:
                        if isinstance(topic, dict) and 'name' in topic:
                            validated_topics.append({
                                'name': topic.get('name', '').strip(),
                                'confidence': float(topic.get('confidence', 0.5)),
                                'keywords': topic.get('keywords', []),
                                'category': topic.get('category', 'other')
                            })
                    return validated_topics
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from LLM response: {e}")
                    logger.debug(f"Response was: {response[:500]}")
            
            return []
            
        except Exception as e:
            logger.error(f"Error extracting topics from article: {e}")
            return []
    
    async def assign_topics_to_article(self, article_id: int, topics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assign topics to an article, creating new topics if needed
        
        Args:
            article_id: ID of the article
            topics: List of topic dictionaries from extraction
            
        Returns:
            Dictionary with assignment results
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            assigned_topics = []
            created_topics = []
            
            for topic_data in topics:
                topic_name = topic_data.get('name', '').strip()
                if not topic_name:
                    continue
                
                # Check if topic exists
                cur.execute(
                    "SELECT id, confidence_score, accuracy_score FROM topics WHERE name = %s",
                    (topic_name,)
                )
                existing_topic = cur.fetchone()
                
                if existing_topic:
                    topic_id = existing_topic[0]
                    # Use existing topic's confidence as base, blend with new confidence
                    existing_confidence = existing_topic[1] or 0.5
                    new_confidence = topic_data.get('confidence', 0.5)
                    blended_confidence = (existing_confidence * 0.7) + (new_confidence * 0.3)
                else:
                    # Create new topic
                    cur.execute("""
                        INSERT INTO topics (
                            name, description, category, keywords, 
                            confidence_score, is_auto_generated, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        topic_name,
                        f"Auto-generated topic: {topic_name}",
                        topic_data.get('category', 'other'),
                        topic_data.get('keywords', []),
                        topic_data.get('confidence', 0.5),
                        True,
                        'active'
                    ))
                    topic_id = cur.fetchone()[0]
                    created_topics.append(topic_name)
                    blended_confidence = topic_data.get('confidence', 0.5)
                
                # Check if assignment already exists
                cur.execute("""
                    SELECT id FROM article_topic_assignments 
                    WHERE article_id = %s AND topic_id = %s
                """, (article_id, topic_id))
                
                if cur.fetchone():
                    # Update existing assignment
                    cur.execute("""
                        UPDATE article_topic_assignments
                        SET confidence_score = %s,
                            relevance_score = %s,
                            assignment_context = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE article_id = %s AND topic_id = %s
                    """, (
                        blended_confidence,
                        topic_data.get('confidence', 0.5),
                        Json(topic_data),
                        article_id,
                        topic_id
                    ))
                else:
                    # Create new assignment
                    cur.execute("""
                        INSERT INTO article_topic_assignments (
                            article_id, topic_id, confidence_score, 
                            relevance_score, assignment_method, 
                            assignment_context, model_version
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        article_id,
                        topic_id,
                        blended_confidence,
                        topic_data.get('confidence', 0.5),
                        'auto',
                        Json(topic_data),
                        self.model_name
                    ))
                
                assigned_topics.append({
                    'topic_id': topic_id,
                    'topic_name': topic_name,
                    'confidence': blended_confidence
                })
            
            # Update article's topics JSONB field
            cur.execute("""
                UPDATE articles
                SET topics = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                Json([t['topic_name'] for t in assigned_topics]),
                article_id
            ))
            
            conn.commit()
            
            return {
                'success': True,
                'article_id': article_id,
                'assigned_topics': assigned_topics,
                'created_topics': created_topics,
                'total_assigned': len(assigned_topics)
            }
            
        except Exception as e:
            logger.error(f"Error assigning topics to article {article_id}: {e}")
            if conn:
                conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if conn:
                cur.close()
                conn.close()
    
    async def process_article(self, article_id: int) -> Dict[str, Any]:
        """
        Process a single article: extract topics and assign them
        
        Args:
            article_id: ID of the article to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get article
            cur.execute("""
                SELECT id, title, content, excerpt, topics, 
                       published_at, source_domain
                FROM articles
                WHERE id = %s
            """, (article_id,))
            
            article = cur.fetchone()
            if not article:
                return {'success': False, 'error': 'Article not found'}
            
            article_dict = dict(article)
            
            # Extract topics using LLM
            logger.info(f"🔍 Extracting topics for article {article_id}: {article_dict.get('title', '')[:50]}")
            extracted_topics = await self.extract_topics_from_article(article_dict)
            
            if not extracted_topics:
                logger.warning(f"⚠️ No topics extracted for article {article_id}")
                return {
                    'success': True,
                    'article_id': article_id,
                    'assigned_topics': [],
                    'message': 'No topics extracted'
                }
            
            # Assign topics
            assignment_result = await self.assign_topics_to_article(article_id, extracted_topics)
            
            logger.info(f"✅ Processed article {article_id}: {assignment_result.get('total_assigned', 0)} topics assigned")
            
            return assignment_result
            
        except Exception as e:
            logger.error(f"Error processing article {article_id} for topic clustering: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if conn:
                cur.close()
                conn.close()
    
    def record_feedback(self, assignment_id: int, is_correct: bool, 
                       feedback_notes: str = None, validated_by: str = None) -> Dict[str, Any]:
        """
        Record feedback on a topic assignment for iterative learning
        
        Args:
            assignment_id: ID of the article_topic_assignment
            is_correct: Whether the assignment was correct
            feedback_notes: Optional feedback notes
            validated_by: Who validated this (user ID or name)
            
        Returns:
            Dictionary with feedback recording results
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Update assignment
            cur.execute("""
                UPDATE article_topic_assignments
                SET is_validated = TRUE,
                    is_correct = %s,
                    feedback_notes = %s,
                    validated_at = CURRENT_TIMESTAMP,
                    validated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING topic_id
            """, (is_correct, feedback_notes, validated_by, assignment_id))
            
            result = cur.fetchone()
            if not result:
                return {'success': False, 'error': 'Assignment not found'}
            
            topic_id = result[0]
            
            # The trigger will automatically update topic accuracy
            conn.commit()
            
            # Get updated topic metrics
            cur.execute("""
                SELECT accuracy_score, confidence_score, review_count,
                       correct_assignments, incorrect_assignments
                FROM topics
                WHERE id = %s
            """, (topic_id,))
            
            topic_metrics = cur.fetchone()
            
            return {
                'success': True,
                'assignment_id': assignment_id,
                'topic_id': topic_id,
                'updated_accuracy': float(topic_metrics[0]) if topic_metrics[0] else 0.5,
                'updated_confidence': float(topic_metrics[1]) if topic_metrics[1] else 0.5,
                'review_count': topic_metrics[2] or 0,
                'correct_assignments': topic_metrics[3] or 0,
                'incorrect_assignments': topic_metrics[4] or 0
            }
            
        except Exception as e:
            logger.error(f"Error recording feedback for assignment {assignment_id}: {e}")
            if conn:
                conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if conn:
                cur.close()
                conn.close()
    
    def get_topics_needing_review(self, threshold: float = 0.6, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get topics that need review based on accuracy
        
        Args:
            threshold: Accuracy threshold (topics below this need review)
            limit: Maximum number of topics to return
            
        Returns:
            List of topic dictionaries needing review
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM get_topics_needing_review(%s)
                LIMIT %s
            """, (threshold, limit))
            
            topics = [dict(row) for row in cur.fetchall()]
            return topics
            
        except Exception as e:
            logger.error(f"Error getting topics needing review: {e}")
            return []
        finally:
            if conn:
                cur.close()
                conn.close()


