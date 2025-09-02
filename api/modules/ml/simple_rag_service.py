"""
Simple RAG Service for News Intelligence System
Provides basic RAG enhancement without external API dependencies
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import psycopg2
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)

class SimpleRAGService:
    """Simple RAG service for demonstrating RAG enhancement concepts"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the Simple RAG Service
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        
    def enhance_article_with_context(self, article_id: int, keywords: List[str] = None) -> Dict[str, Any]:
        """
        Enhance an article with contextual information
        
        Args:
            article_id: ID of the article to enhance
            keywords: Optional keywords to use for context search
            
        Returns:
            Dict containing enhanced article data with context
        """
        try:
            start_time = time.time()
            
            # Get article data
            article_data = self._get_article_data(article_id)
            if not article_data:
                return {"error": f"Article {article_id} not found"}
            
            # Extract keywords if not provided
            if not keywords:
                keywords = self._extract_article_keywords(article_data)
            
            # Get related articles from database
            related_articles = self._get_related_articles(keywords, article_id)
            
            # Generate context summary
            context_summary = self._generate_context_summary(related_articles, keywords)
            
            # Extract entities and analyze
            entities = self._extract_entities_from_article(article_data)
            entity_analysis = self._analyze_entities(entities, related_articles)
            
            # Generate timeline of related events
            timeline = self._generate_timeline(related_articles)
            
            # Combine all enhancement data
            enhancement = {
                "article_id": article_id,
                "keywords": keywords,
                "related_articles": related_articles,
                "context_summary": context_summary,
                "entity_analysis": entity_analysis,
                "timeline": timeline,
                "enhancement_timestamp": datetime.now().isoformat(),
                "processing_time": time.time() - start_time
            }
            
            # Store enhancement in database
            self._store_enhancement(article_id, enhancement)
            
            # Update article with RAG enhancement flag
            self._update_article_rag_status(article_id, "rag_enhanced")
            
            logger.info(f"Enhanced article {article_id} with RAG context in {enhancement['processing_time']:.2f}s")
            
            return enhancement
            
        except Exception as e:
            logger.error(f"Error enhancing article {article_id} with RAG: {e}")
            return {"error": f"Error enhancing article with RAG: {str(e)}"}
    
    def _get_article_data(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get article data from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, content, summary, url, source, published_date, 
                       category, language, quality_score, processing_status, ml_data
                FROM articles 
                WHERE id = %s
            """, (article_id,))
            
            result = cursor.fetchone()
            if result:
                columns = [desc[0] for desc in cursor.description]
                article_data = dict(zip(columns, result))
                return article_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting article data: {e}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _extract_article_keywords(self, article_data: Dict[str, Any]) -> List[str]:
        """Extract keywords from article data"""
        text = f"{article_data.get('title', '')} {article_data.get('content', '')}"
        
        # Remove common words and extract meaningful terms
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        # Extract words (simple approach)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [word for word in words if word not in common_words]
        
        # Count frequency and return top keywords
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(10)]
    
    def _get_related_articles(self, keywords: List[str], exclude_id: int) -> List[Dict[str, Any]]:
        """Get related articles based on keywords"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Build keyword search query
            keyword_conditions = []
            params = []
            
            for keyword in keywords[:5]:  # Use top 5 keywords
                keyword_conditions.append("(title ILIKE %s OR content ILIKE %s)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            
            if not keyword_conditions:
                return []
            
            query = f"""
                SELECT id, title, content, summary, url, source, published_date, 
                       category, language, quality_score, processing_status
                FROM articles 
                WHERE id != %s AND ({' OR '.join(keyword_conditions)})
                ORDER BY published_date DESC
                LIMIT 10
            """
            
            cursor.execute(query, [exclude_id] + params)
            results = cursor.fetchall()
            
            columns = [desc[0] for desc in cursor.description]
            related_articles = [dict(zip(columns, result)) for result in results]
            
            return related_articles
            
        except Exception as e:
            logger.error(f"Error getting related articles: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _generate_context_summary(self, related_articles: List[Dict[str, Any]], keywords: List[str]) -> str:
        """Generate a context summary from related articles"""
        if not related_articles:
            return f"No related articles found for keywords: {', '.join(keywords)}"
        
        # Count articles by source
        source_counts = Counter(article['source'] for article in related_articles)
        top_sources = [source for source, count in source_counts.most_common(3)]
        
        # Get date range
        dates = [article['published_date'] for article in related_articles if article['published_date']]
        date_range = f"from {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}" if dates else "recently"
        
        return f"Found {len(related_articles)} related articles {date_range}. Key sources include: {', '.join(top_sources)}. Topics covered: {', '.join(keywords[:3])}."
    
    def _extract_entities_from_article(self, article_data: Dict[str, Any]) -> List[str]:
        """Extract entities from article data"""
        text = f"{article_data.get('title', '')} {article_data.get('content', '')}"
        
        # Look for capitalized words (simple approach)
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        # Remove common words and return unique entities
        common_words = {'The', 'This', 'That', 'These', 'Those', 'And', 'Or', 'But', 'In', 'On', 'At', 'To', 'For', 'Of', 'With', 'By'}
        entities = [entity for entity in entities if entity not in common_words]
        
        return list(set(entities))[:5]  # Return top 5 unique entities
    
    def _analyze_entities(self, entities: List[str], related_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze entities across related articles"""
        entity_mentions = {}
        
        for entity in entities:
            mentions = 0
            sources = set()
            
            for article in related_articles:
                text = f"{article.get('title', '')} {article.get('content', '')}"
                if entity.lower() in text.lower():
                    mentions += 1
                    sources.add(article.get('source', 'Unknown'))
            
            entity_mentions[entity] = {
                "mentions": mentions,
                "sources": list(sources),
                "relevance_score": mentions / len(related_articles) if related_articles else 0
            }
        
        return entity_mentions
    
    def _generate_timeline(self, related_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate a timeline of related events"""
        # Sort articles by date
        sorted_articles = sorted(
            [article for article in related_articles if article.get('published_date')],
            key=lambda x: x['published_date'],
            reverse=True
        )
        
        timeline = []
        for article in sorted_articles[:5]:  # Top 5 most recent
            timeline.append({
                "date": article['published_date'].isoformat(),
                "title": article['title'],
                "source": article['source'],
                "url": article['url']
            })
        
        return timeline
    
    def _store_enhancement(self, article_id: int, enhancement_data: Dict[str, Any]) -> bool:
        """Store enhancement data in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Update article with enhancement data
            cursor.execute("""
                UPDATE articles 
                SET ml_data = COALESCE(ml_data, '{}'::jsonb) || %s::jsonb,
                    rag_keep_longer = TRUE,
                    rag_context_needed = FALSE,
                    updated_at = NOW()
                WHERE id = %s
            """, (json.dumps({"rag_enhancement": enhancement_data}), article_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing enhancement: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _update_article_rag_status(self, article_id: int, status: str) -> bool:
        """Update article RAG processing status"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE articles 
                SET processing_status = %s,
                    rag_keep_longer = TRUE,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, article_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating article RAG status: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
