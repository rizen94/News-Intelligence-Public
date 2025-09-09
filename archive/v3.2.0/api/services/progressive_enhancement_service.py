"""
Progressive Enhancement Service for News Intelligence System
Implements automatic summary generation and progressive RAG enhancement
"""

import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

from .api_cache_service import get_cache_service
from .api_usage_monitor import get_usage_monitor
from .storyline_service import get_storyline_service
from .rag_service import get_rag_service

logger = logging.getLogger(__name__)

class ProgressiveEnhancementService:
    """Service for progressive enhancement of storyline summaries"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.cache_service = get_cache_service()
        self.usage_monitor = get_usage_monitor()
        self.storyline_service = get_storyline_service()
        self.rag_service = get_rag_service()
        
    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    async def create_storyline_with_auto_summary(self, storyline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create storyline and automatically generate basic summary"""
        try:
            # Create storyline first
            storyline_id = storyline_data.get('id')
            if not storyline_id:
                # Generate storyline ID if not provided
                storyline_id = f"storyline_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(storyline_data)) % 10000}"
                storyline_data['id'] = storyline_id
            
            # Save storyline to database
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO storylines (id, title, description, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
            """, (
                storyline_id,
                storyline_data.get('title', 'Untitled Storyline'),
                storyline_data.get('description', ''),
                storyline_data.get('status', 'active'),
                datetime.now(),
                datetime.now()
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Generate basic summary immediately
            await self.generate_basic_summary(storyline_id)
            
            return {
                'success': True,
                'storyline_id': storyline_id,
                'message': 'Storyline created with automatic basic summary'
            }
            
        except Exception as e:
            logger.error(f"Error creating storyline with auto summary: {e}")
            return {'success': False, 'error': str(e)}
    
    async def generate_basic_summary(self, storyline_id: str) -> Dict[str, Any]:
        """Generate basic summary using local AI only"""
        try:
            logger.info(f"Generating basic summary for storyline {storyline_id}")
            
            # Get storyline articles
            storyline_data = await self.storyline_service.get_storyline_articles(storyline_id)
            if not storyline_data or 'storyline' not in storyline_data:
                return {'success': False, 'error': 'Storyline not found'}
            
            articles = storyline_data.get('articles', [])
            if not articles:
                return {'success': False, 'error': 'No articles in storyline'}
            
            # Generate basic summary using existing service
            summary_result = await self.storyline_service.generate_storyline_summary(storyline_id)
            
            if summary_result.get('success'):
                # Save as version 1
                await self._save_summary_version(
                    storyline_id, 
                    1, 
                    'basic', 
                    summary_result['data']['master_summary']
                )
                
                # Update storyline with basic summary info
                await self._update_storyline_summary_info(storyline_id, 'basic')
                
                return {
                    'success': True,
                    'summary_type': 'basic',
                    'version': 1,
                    'message': 'Basic summary generated successfully'
                }
            else:
                return {'success': False, 'error': summary_result.get('error', 'Failed to generate summary')}
                
        except Exception as e:
            logger.error(f"Error generating basic summary: {e}")
            return {'success': False, 'error': str(e)}
    
    async def enhance_with_rag(self, storyline_id: str, force: bool = False) -> Dict[str, Any]:
        """Enhance storyline summary with RAG context"""
        try:
            logger.info(f"Enhancing storyline {storyline_id} with RAG")
            
            # Check if enhancement is needed
            if not force:
                enhancement_needed = await self._should_enhance_storyline(storyline_id)
                if not enhancement_needed:
                    return {
                        'success': True,
                        'message': 'Enhancement not needed at this time',
                        'skipped': True
                    }
            
            # Get current storyline data
            storyline_data = await self.storyline_service.get_storyline_articles(storyline_id)
            if not storyline_data or 'storyline' not in storyline_data:
                return {'success': False, 'error': 'Storyline not found'}
            
            storyline = storyline_data['storyline']
            articles = storyline_data.get('articles', [])
            
            if not articles:
                return {'success': False, 'error': 'No articles in storyline'}
            
            # Get current summary version
            current_version = await self._get_current_summary_version(storyline_id)
            next_version = current_version + 1
            
            # Generate RAG context with caching and usage monitoring
            rag_context = await self._get_rag_context_with_monitoring(
                storyline_id, 
                storyline.get('title', 'Untitled Storyline'), 
                articles
            )
            
            if not rag_context:
                return {'success': False, 'error': 'Failed to get RAG context'}
            
            # Generate enhanced summary
            enhanced_summary = await self.storyline_service.generate_storyline_summary_with_rag(
                storyline_id, 
                rag_context
            )
            
            if enhanced_summary and len(enhanced_summary) > 50:
                # Save as new version
                await self._save_summary_version(
                    storyline_id, 
                    next_version, 
                    'rag_enhanced', 
                    enhanced_summary,
                    rag_context
                )
                
                # Update storyline with enhanced summary
                await self._update_storyline_summary_info(storyline_id, 'rag_enhanced')
                
                return {
                    'success': True,
                    'summary_type': 'rag_enhanced',
                    'version': next_version,
                    'message': 'RAG enhancement completed successfully'
                }
            else:
                return {'success': False, 'error': 'Failed to generate enhanced summary'}
                
        except Exception as e:
            logger.error(f"Error enhancing with RAG: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _should_enhance_storyline(self, storyline_id: str) -> bool:
        """Check if storyline should be enhanced"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    last_basic_summary_at,
                    last_rag_enhancement_at,
                    enhancement_count,
                    article_count
                FROM storylines 
                WHERE id = %s
            """, (storyline_id,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result:
                return False
            
            # Enhancement criteria
            last_rag = result['last_rag_enhancement_at']
            article_count = result['article_count'] or 0
            enhancement_count = result['enhancement_count'] or 0
            
            # Always enhance if never enhanced
            if not last_rag:
                return True
            
            # Enhance if new articles added (article count increased)
            if article_count > 0 and enhancement_count < article_count:
                return True
            
            # Enhance if last enhancement was more than 24 hours ago
            if last_rag:
                hours_since_enhancement = (datetime.now() - last_rag).total_seconds() / 3600
                if hours_since_enhancement > 24:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking enhancement criteria: {e}")
            return False
    
    async def _get_rag_context_with_monitoring(self, storyline_id: str, title: str, articles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get RAG context with usage monitoring and caching"""
        try:
            # Check if we can make API calls
            wikipedia_status = await self.usage_monitor.get_service_status('wikipedia')
            gdelt_status = await self.usage_monitor.get_service_status('gdelt')
            
            if not wikipedia_status.get('daily_limit_ok', True):
                logger.warning("Wikipedia daily limit reached, skipping RAG enhancement")
                return None
            
            if not gdelt_status.get('daily_limit_ok', True):
                logger.warning("GDELT daily limit reached, skipping RAG enhancement")
                return None
            
            # Extract topics and entities for RAG
            topics = []
            entities = []
            
            for article in articles:
                # Extract topics from title and content
                article_text = f"{article.get('title', '')} {article.get('content', '')}"
                article_topics = self._extract_simple_topics(article_text)
                topics.extend(article_topics)
                
                # Extract entities (simple extraction)
                article_entities = self._extract_simple_entities(article_text)
                entities.extend(article_entities)
            
            # Remove duplicates and limit
            topics = list(set(topics))[:10]
            entities = list(set(entities))[:10]
            
            # Get Wikipedia context with caching
            wikipedia_context = await self._get_wikipedia_context_cached(topics + entities)
            
            # Get GDELT context with caching
            gdelt_context = await self._get_gdelt_context_cached(topics + entities)
            
            return {
                'wikipedia': wikipedia_context,
                'gdelt': gdelt_context,
                'topics': topics,
                'entities': entities,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting RAG context: {e}")
            return None
    
    async def _get_wikipedia_context_cached(self, search_terms: List[str]) -> Dict[str, Any]:
        """Get Wikipedia context with caching"""
        try:
            wikipedia_context = {"articles": [], "summaries": [], "error": None}
            
            for term in search_terms[:5]:  # Limit to 5 searches
                # Check cache first
                cache_key = f"wikipedia:{term}"
                cached_result = await self.cache_service.get_cached_response('wikipedia', term)
                
                if cached_result:
                    wikipedia_context["articles"].extend(cached_result.get("articles", []))
                    wikipedia_context["summaries"].extend(cached_result.get("summaries", []))
                else:
                    # Make API call with monitoring
                    start_time = time.time()
                    
                    try:
                        # Check rate limit
                        if not await self.usage_monitor.check_rate_limit('wikipedia'):
                            await asyncio.sleep(1)
                            continue
                        
                        # Make Wikipedia API call
                        response = await self._call_wikipedia_api(term)
                        
                        if response:
                            wikipedia_context["articles"].append(response)
                            wikipedia_context["summaries"].append({
                                "term": term,
                                "summary": response.get('extract', '')[:500]
                            })
                            
                            # Cache the result
                            await self.cache_service.cache_response('wikipedia', term, {
                                "articles": [response],
                                "summaries": [{"term": term, "summary": response.get('extract', '')[:500]}]
                            })
                        
                        # Record API call
                        processing_time = int((time.time() - start_time) * 1000)
                        await self.usage_monitor.record_api_call(
                            'wikipedia', 
                            f'/page/summary/{term}',
                            len(str(response)) if response else 0,
                            processing_time,
                            True
                        )
                        
                    except Exception as e:
                        logger.warning(f"Wikipedia API error for {term}: {e}")
                        await self.usage_monitor.record_api_call(
                            'wikipedia', 
                            f'/page/summary/{term}',
                            0, 0, False, str(e)
                        )
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            return wikipedia_context
            
        except Exception as e:
            logger.error(f"Error getting Wikipedia context: {e}")
            return {"articles": [], "summaries": [], "error": str(e)}
    
    async def _get_gdelt_context_cached(self, search_terms: List[str]) -> Dict[str, Any]:
        """Get GDELT context with caching"""
        try:
            gdelt_context = {"events": [], "error": None}
            
            # For now, return empty GDELT context
            # GDELT API can be complex and may not be needed for basic functionality
            return gdelt_context
            
        except Exception as e:
            logger.error(f"Error getting GDELT context: {e}")
            return {"events": [], "error": str(e)}
    
    async def _call_wikipedia_api(self, term: str) -> Optional[Dict[str, Any]]:
        """Call Wikipedia API"""
        try:
            import requests
            from urllib.parse import quote
            
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(term)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get('title', term),
                    "extract": data.get('extract', ''),
                    "url": data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                    "search_term": term
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Wikipedia API call failed: {e}")
            return None
    
    def _extract_simple_topics(self, text: str) -> List[str]:
        """Extract simple topics from text"""
        # Simple keyword extraction
        words = text.lower().split()
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        # Filter out common words and short words
        topics = [word for word in words if len(word) > 3 and word not in common_words]
        
        # Return top 5 unique topics
        return list(set(topics))[:5]
    
    def _extract_simple_entities(self, text: str) -> List[str]:
        """Extract simple entities from text"""
        # Simple entity extraction (capitalized words)
        words = text.split()
        entities = [word for word in words if word[0].isupper() and len(word) > 2]
        
        # Return top 5 unique entities
        return list(set(entities))[:5]
    
    async def _save_summary_version(self, storyline_id: str, version: int, summary_type: str, 
                                  content: str, rag_context: Dict[str, Any] = None) -> None:
        """Save summary version to database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO storyline_summary_versions 
                (storyline_id, version_number, summary_type, summary_content, rag_context)
                VALUES (%s, %s, %s, %s, %s)
            """, (storyline_id, version, summary_type, content, 
                  json.dumps(rag_context) if rag_context else None))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving summary version: {e}")
    
    async def _get_current_summary_version(self, storyline_id: str) -> int:
        """Get current summary version number"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT MAX(version_number) as max_version
                FROM storyline_summary_versions 
                WHERE storyline_id = %s
            """, (storyline_id,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result['max_version'] if result and result['max_version'] else 0
            
        except Exception as e:
            logger.error(f"Error getting current summary version: {e}")
            return 0
    
    async def _update_storyline_summary_info(self, storyline_id: str, summary_type: str) -> None:
        """Update storyline with summary information"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            if summary_type == 'basic':
                cursor.execute("""
                    UPDATE storylines 
                    SET last_basic_summary_at = %s, updated_at = %s
                    WHERE id = %s
                """, (datetime.now(), datetime.now(), storyline_id))
            elif summary_type == 'rag_enhanced':
                cursor.execute("""
                    UPDATE storylines 
                    SET last_rag_enhancement_at = %s, 
                        enhancement_count = enhancement_count + 1,
                        updated_at = %s
                    WHERE id = %s
                """, (datetime.now(), datetime.now(), storyline_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating storyline summary info: {e}")
    
    async def get_summary_history(self, storyline_id: str) -> List[Dict[str, Any]]:
        """Get summary version history for a storyline"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    version_number,
                    summary_type,
                    summary_content,
                    rag_context,
                    created_at
                FROM storyline_summary_versions 
                WHERE storyline_id = %s
                ORDER BY version_number DESC
            """, (storyline_id,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error getting summary history: {e}")
            return []

# Global instance
_progressive_service = None

def get_progressive_service() -> ProgressiveEnhancementService:
    """Get global progressive enhancement service instance"""
    global _progressive_service
    if _progressive_service is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        _progressive_service = ProgressiveEnhancementService(db_config)
    return _progressive_service
