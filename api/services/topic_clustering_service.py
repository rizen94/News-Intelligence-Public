"""
News Intelligence System v3.0 - Simplified Topic Clustering Service
Uses Ollama LLM to extract topics from headlines and content
"""

import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import text
from config.database import get_db

logger = logging.getLogger(__name__)

class TopicClusteringService:
    """Service for topic extraction and clustering using Ollama LLM"""
    
    def __init__(self, ollama_host: str = "localhost", ollama_port: int = 11434):
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.model = "llama3.1:70b"
        
    async def extract_topics_from_article(self, title: str, content: str = None) -> Dict[str, Any]:
        """Extract topics from a single article using Ollama"""
        try:
            # Prepare content for analysis
            analysis_content = f"Title: {title}"
            if content:
                content_preview = content[:2000] if len(content) > 2000 else content
                analysis_content += f"\n\nContent: {content_preview}"
            
            prompt = f"""Analyze the following news article and extract the main topics and themes. 
            Return your analysis as a JSON object with the following structure:
            
            {{
                "primary_topic": "Main topic (e.g., 'Election 2024', 'Climate Change', 'Tech Regulation')",
                "secondary_topics": ["Topic 2", "Topic 3"],
                "keywords": ["keyword1", "keyword2", "keyword3"],
                "entities": ["Person", "Organization", "Location"],
                "category": "Politics|Economy|Technology|Climate|World|Business|Health|Science",
                "subcategory": "More specific category",
                "sentiment": "positive|negative|neutral",
                "urgency": "breaking|urgent|normal|low",
                "geographic_scope": "local|national|international",
                "confidence": 0.85
            }}
            
            Article to analyze:
            {analysis_content}
            
            JSON Response:"""

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "max_tokens": 500
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()
                
                # Try to extract JSON from response
                try:
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        topic_data = json.loads(json_str)
                        
                        # Validate and clean the data
                        topic_data = self._validate_topic_data(topic_data)
                        
                        return {
                            "success": True,
                            "data": topic_data,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        raise ValueError("No valid JSON found in response")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse JSON from Ollama response: {e}")
                    return self._extract_fallback_topics(title, content)
                    
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._extract_fallback_topics(title, content)
                
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return self._extract_fallback_topics(title, content)
    
    def _validate_topic_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean topic data"""
        validated = {
            "primary_topic": data.get("primary_topic", "General News"),
            "secondary_topics": data.get("secondary_topics", []),
            "keywords": data.get("keywords", []),
            "entities": data.get("entities", []),
            "category": data.get("category", "General"),
            "subcategory": data.get("subcategory", ""),
            "sentiment": data.get("sentiment", "neutral"),
            "urgency": data.get("urgency", "normal"),
            "geographic_scope": data.get("geographic_scope", "national"),
            "confidence": min(max(data.get("confidence", 0.5), 0.0), 1.0)
        }
        
        # Ensure lists are properly formatted
        for key in ["secondary_topics", "keywords", "entities"]:
            if not isinstance(validated[key], list):
                validated[key] = []
        
        return validated
    
    def _extract_fallback_topics(self, title: str, content: str = None) -> Dict[str, Any]:
        """Fallback topic extraction when Ollama fails"""
        # Simple keyword-based extraction
        keywords = []
        
        # Extract basic keywords from title
        title_words = title.lower().split()
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in title_words if word not in common_words and len(word) > 3]
        
        # Basic category detection
        category = "General"
        if any(word in title.lower() for word in ['election', 'vote', 'campaign', 'president', 'senate', 'congress']):
            category = "Politics"
        elif any(word in title.lower() for word in ['climate', 'environment', 'carbon', 'emissions']):
            category = "Climate"
        elif any(word in title.lower() for word in ['tech', 'ai', 'software', 'digital', 'cyber']):
            category = "Technology"
        elif any(word in title.lower() for word in ['economy', 'market', 'stock', 'inflation', 'gdp']):
            category = "Economy"
        
        return {
            "success": True,
            "data": {
                "primary_topic": f"{category} News",
                "secondary_topics": [],
                "keywords": keywords[:5],
                "entities": [],
                "category": category,
                "subcategory": "",
                "sentiment": "neutral",
                "urgency": "normal",
                "geographic_scope": "national",
                "confidence": 0.3
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def cluster_articles_by_topic(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cluster multiple articles by topic using Ollama"""
        try:
            # Prepare articles for clustering
            articles_text = ""
            for i, article in enumerate(articles[:10]):  # Limit to 10 articles for clustering
                articles_text += f"Article {i+1}: {article.get('title', '')}\n"
                if article.get('content'):
                    content_preview = article['content'][:500] if len(article['content']) > 500 else article['content']
                    articles_text += f"Content: {content_preview}\n"
                articles_text += "\n"
            
            prompt = f"""Analyze the following articles and group them into topics. 
            Return your analysis as a JSON object with the following structure:
            
            {{
                "topics": [
                    {{
                        "topic_name": "Topic Name",
                        "description": "Brief description of the topic",
                        "article_indices": [0, 2, 5],
                        "keywords": ["keyword1", "keyword2"],
                        "category": "Politics|Economy|Technology|Climate|World|Business|Health|Science",
                        "urgency": "breaking|urgent|normal|low"
                    }}
                ],
                "unclustered_articles": [3, 7],
                "total_topics": 2
            }}
            
            Articles to analyze:
            {articles_text}
            
            JSON Response:"""

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "max_tokens": 800
                    }
                },
                timeout=45
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()
                
                try:
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        cluster_data = json.loads(json_str)
                        
                        return {
                            "success": True,
                            "data": cluster_data,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        raise ValueError("No valid JSON found in response")
                        
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse clustering JSON: {e}")
                    return self._fallback_clustering(articles)
                    
            else:
                logger.error(f"Ollama clustering API error: {response.status_code}")
                return self._fallback_clustering(articles)
                
        except Exception as e:
            logger.error(f"Error clustering articles: {e}")
            return self._fallback_clustering(articles)
    
    def _fallback_clustering(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback clustering when Ollama fails"""
        # Simple keyword-based clustering
        topics = []
        topic_keywords = {}
        
        for i, article in enumerate(articles):
            title = article.get('title', '').lower()
            
            # Simple topic detection
            if any(word in title for word in ['election', 'vote', 'campaign', 'president']):
                topic_name = "Election 2024"
                if topic_name not in topic_keywords:
                    topic_keywords[topic_name] = []
                topic_keywords[topic_name].append(i)
            elif any(word in title for word in ['climate', 'environment', 'carbon']):
                topic_name = "Climate Change"
                if topic_name not in topic_keywords:
                    topic_keywords[topic_name] = []
                topic_keywords[topic_name].append(i)
            elif any(word in title for word in ['tech', 'ai', 'software', 'digital']):
                topic_name = "Technology"
                if topic_name not in topic_keywords:
                    topic_keywords[topic_name] = []
                topic_keywords[topic_name].append(i)
            else:
                topic_name = "General News"
                if topic_name not in topic_keywords:
                    topic_keywords[topic_name] = []
                topic_keywords[topic_name].append(i)
        
        # Convert to expected format
        topics = []
        for topic_name, article_indices in topic_keywords.items():
            topics.append({
                "topic_name": topic_name,
                "description": f"Articles related to {topic_name}",
                "article_indices": article_indices,
                "keywords": [topic_name.lower()],
                "category": "General",
                "urgency": "normal"
            })
        
        return {
            "success": True,
            "data": {
                "topics": topics,
                "unclustered_articles": [],
                "total_topics": len(topics)
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def save_topics_to_database(self, topics_data: Dict[str, Any], articles: List[Dict[str, Any]]) -> bool:
        """Save topic clustering results to database"""
        try:
            db = next(get_db())
            
            for topic_info in topics_data.get("topics", []):
                topic_name = topic_info["topic_name"]
                article_indices = topic_info["article_indices"]
                
                # Create cluster ID
                cluster_id = hash(topic_name) % 1000000
                
                # Insert cluster assignments for articles in this topic
                for j, i in enumerate(article_indices):
                    if i < len(articles):
                        db.execute(text("""
                            INSERT INTO article_clusters (cluster_id, article_id, similarity_score, cluster_rank, created_at)
                            VALUES (:cluster_id, :article_id, :similarity_score, :cluster_rank, :created_at)
                            ON CONFLICT (cluster_id, article_id) DO NOTHING
                        """), {
                            "cluster_id": cluster_id,
                            "article_id": articles[i]["id"],
                            "similarity_score": 0.8,
                            "cluster_rank": j,
                            "created_at": datetime.now()
                        })
                        
                        # Update articles with cluster_id
                        db.execute(text("""
                            UPDATE articles 
                            SET cluster_id = :cluster_id, 
                                category = :category,
                                subcategory = :subcategory
                            WHERE id = :article_id
                        """), {
                            "cluster_id": cluster_id,
                            "category": topic_info.get("category", "General"),
                            "subcategory": topic_info.get("description", ""),
                            "article_id": articles[i]["id"]
                        })
            
            db.commit()
            logger.info(f"Saved {len(topics_data.get('topics', []))} topic clusters to database")
            return True
            
        except Exception as e:
            logger.error(f"Error saving topics to database: {e}")
            db.rollback()
            return False
        finally:
            db.close()

# Global instance
topic_clustering_service = TopicClusteringService()
