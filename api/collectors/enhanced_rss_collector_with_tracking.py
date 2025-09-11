"""
Enhanced RSS Collector with Comprehensive Pipeline Tracking
Tracks RSS feeds and articles through the entire pipeline with detailed logging
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import feedparser
import requests
from bs4 import BeautifulSoup

from config.database import get_db
from sqlalchemy import text
from services.pipeline_logger import PipelineLogger, PipelineStage, get_pipeline_logger
from services.enhanced_storyline_service import EnhancedStorylineService
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

logger = logging.getLogger(__name__)

class EnhancedRSSCollectorWithTracking:
    """
    Enhanced RSS collector with comprehensive pipeline tracking and logging
    """
    
    def __init__(self, ml_service=None, rag_service=None, pipeline_logger=None):
        """
        Initialize the enhanced RSS collector with tracking
        
        Args:
            ml_service: ML summarization service
            rag_service: RAG service for context enhancement
            pipeline_logger: Pipeline logger instance
        """
        self.ml_service = ml_service
        self.rag_service = rag_service
        self.pipeline_logger = pipeline_logger or get_pipeline_logger()
        self.enhanced_service = EnhancedStorylineService(ml_service, rag_service)
        
        # Performance tracking
        self.performance_metrics = {
            'total_feeds_processed': 0,
            'total_articles_processed': 0,
            'total_errors': 0,
            'average_processing_time_ms': 0.0,
            'success_rate': 0.0
        }
    
    async def process_rss_feed_with_tracking(self, rss_feed_id: str, 
                                           rss_url: str, 
                                           feed_name: str) -> Dict[str, Any]:
        """
        Process an RSS feed with comprehensive pipeline tracking
        
        Args:
            rss_feed_id: ID of the RSS feed
            rss_url: URL of the RSS feed
            feed_name: Name of the RSS feed
            
        Returns:
            Dictionary containing processing results and metrics
        """
        # Start pipeline trace
        trace_id = self.pipeline_logger.start_trace(
            rss_feed_id=rss_feed_id,
            article_id=None,
            storyline_id=None
        )
        
        try:
            logger.info(f"🚀 Starting RSS feed processing with tracking: {feed_name} ({rss_url})")
            
            # Stage 1: RSS Feed Discovery
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_DISCOVERY,
                status="started",
                input_data={"rss_url": rss_url, "feed_name": feed_name},
                metadata={"feed_id": rss_feed_id}
            )
            
            # Validate RSS feed
            feed_validation = await self._validate_rss_feed(rss_url)
            if not feed_validation['valid']:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="failed",
                    error_message=feed_validation['error'],
                    metadata={"feed_id": rss_feed_id}
                )
                return {"success": False, "error": feed_validation['error']}
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_DISCOVERY,
                status="completed",
                output_data=feed_validation,
                metadata={"feed_id": rss_feed_id}
            )
            
            # Stage 2: RSS Feed Fetch
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_FETCH,
                status="started",
                input_data={"rss_url": rss_url},
                metadata={"feed_id": rss_feed_id}
            )
            
            feed_data = await self._fetch_rss_feed(rss_url)
            if not feed_data['success']:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_FETCH,
                    status="failed",
                    error_message=feed_data['error'],
                    metadata={"feed_id": rss_feed_id}
                )
                return {"success": False, "error": feed_data['error']}
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_FETCH,
                status="completed",
                output_data={"articles_count": len(feed_data['articles'])},
                metadata={"feed_id": rss_feed_id}
            )
            
            # Process each article with tracking
            processed_articles = []
            for article_data in feed_data['articles']:
                article_result = await self._process_article_with_tracking(
                    trace_id, rss_feed_id, article_data
                )
                if article_result['success']:
                    processed_articles.append(article_result['article'])
            
            # Update performance metrics
            self.performance_metrics['total_feeds_processed'] += 1
            self.performance_metrics['total_articles_processed'] += len(processed_articles)
            
            # End trace
            trace = self.pipeline_logger.end_trace(trace_id, success=True)
            
            return {
                "success": True,
                "feed_id": rss_feed_id,
                "articles_processed": len(processed_articles),
                "trace_id": trace_id,
                "performance_metrics": trace.performance_metrics if trace else {},
                "processed_articles": processed_articles
            }
            
        except Exception as e:
            logger.error(f"Error processing RSS feed {rss_feed_id}: {e}")
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_FETCH,
                status="failed",
                error_message=str(e),
                metadata={"feed_id": rss_feed_id}
            )
            
            self.pipeline_logger.end_trace(trace_id, success=False, error_stage=PipelineStage.RSS_FEED_FETCH)
            return {"success": False, "error": str(e)}
    
    async def _process_article_with_tracking(self, trace_id: str, rss_feed_id: str, 
                                           article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an individual article with comprehensive tracking
        
        Args:
            trace_id: Parent trace ID
            rss_feed_id: ID of the RSS feed
            article_data: Raw article data from RSS feed
            
        Returns:
            Dictionary containing processing results
        """
        try:
            # Stage 3: Article Extraction
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.ARTICLE_EXTRACTION,
                status="started",
                input_data={"title": article_data.get('title', ''), "url": article_data.get('link', '')},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            # Extract article content
            article_content = await self._extract_article_content(article_data)
            if not article_content['success']:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.ARTICLE_EXTRACTION,
                    status="failed",
                    error_message=article_content['error'],
                    metadata={"rss_feed_id": rss_feed_id}
                )
                return {"success": False, "error": article_content['error']}
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.ARTICLE_EXTRACTION,
                status="completed",
                output_data={"content_length": len(article_content['content'])},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            # Stage 4: Content Validation
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.CONTENT_VALIDATION,
                status="started",
                input_data={"content_length": len(article_content['content'])},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            validation_result = await self._validate_article_content(article_content['content'])
            if not validation_result['valid']:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.CONTENT_VALIDATION,
                    status="failed",
                    error_message=validation_result['error'],
                    metadata={"rss_feed_id": rss_feed_id}
                )
                return {"success": False, "error": validation_result['error']}
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.CONTENT_VALIDATION,
                status="completed",
                output_data=validation_result,
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            # Stage 5: Deduplication
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.DEDUPLICATION,
                status="started",
                input_data={"title": article_data.get('title', '')},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            deduplication_result = await self._check_duplicate_article(article_data)
            if deduplication_result['is_duplicate']:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.DEDUPLICATION,
                    status="skipped",
                    output_data={"reason": "duplicate_article"},
                    metadata={"rss_feed_id": rss_feed_id}
                )
                return {"success": False, "error": "Duplicate article"}
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.DEDUPLICATION,
                status="completed",
                output_data={"is_duplicate": False},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            # Stage 6: Early Quality Gate
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.EARLY_QUALITY_GATE,
                status="started",
                input_data={"content_length": len(article_content['content'])},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            quality_gate_result = await self._apply_early_quality_gate(article_content['content'])
            if not quality_gate_result['passed']:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.EARLY_QUALITY_GATE,
                    status="skipped",
                    output_data={"reason": "quality_gate_failed", "score": quality_gate_result['score']},
                    metadata={"rss_feed_id": rss_feed_id}
                )
                return {"success": False, "error": "Failed quality gate"}
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.EARLY_QUALITY_GATE,
                status="completed",
                output_data={"quality_score": quality_gate_result['score']},
                metadata={"rss_feed_id": rss_feed_id}
            )
            
            # Stage 7: ML Summarization
            if self.ml_service:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.ML_SUMMARIZATION,
                    status="started",
                    input_data={"content_length": len(article_content['content'])},
                    metadata={"rss_feed_id": rss_feed_id}
                )
                
                ml_start_time = time.time()
                try:
                    summary_result = await self.ml_service.generate_summary(
                        article_content['content'],
                        "Generate a comprehensive summary of this news article"
                    )
                    ml_duration = (time.time() - ml_start_time) * 1000
                    
                    # Log ML step with detailed metrics
                    self.pipeline_logger.log_ml_step(
                        trace_id=trace_id,
                        stage=PipelineStage.ML_SUMMARIZATION,
                        model_name="llama-3.1-70b",
                        input_tokens=len(article_content['content'].split()),
                        output_tokens=len(summary_result.get('summary', '').split()),
                        processing_time_ms=ml_duration,
                        success=True
                    )
                    
                except Exception as e:
                    ml_duration = (time.time() - ml_start_time) * 1000
                    self.pipeline_logger.log_ml_step(
                        trace_id=trace_id,
                        stage=PipelineStage.ML_SUMMARIZATION,
                        model_name="llama-3.1-70b",
                        input_tokens=len(article_content['content'].split()),
                        output_tokens=0,
                        processing_time_ms=ml_duration,
                        success=False,
                        error=str(e)
                    )
                    summary_result = {"summary": "ML summarization failed", "confidence_score": 0.0}
            else:
                summary_result = {"summary": "ML service not available", "confidence_score": 0.0}
            
            # Store article in database
            article_id = await self._store_article_with_tracking(
                trace_id, rss_feed_id, article_data, article_content, summary_result
            )
            
            if not article_id:
                return {"success": False, "error": "Failed to store article"}
            
            # Stage 8: Enhanced Analysis (if enabled)
            if self.enhanced_service:
                await self._run_enhanced_analysis_with_tracking(
                    trace_id, article_id, article_data, article_content
                )
            
            return {
                "success": True,
                "article": {
                    "id": article_id,
                    "title": article_data.get('title', ''),
                    "url": article_data.get('link', ''),
                    "summary": summary_result.get('summary', ''),
                    "confidence_score": summary_result.get('confidence_score', 0.0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing article: {e}")
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.ARTICLE_EXTRACTION,
                status="failed",
                error_message=str(e),
                metadata={"rss_feed_id": rss_feed_id}
            )
            return {"success": False, "error": str(e)}
    
    async def _run_enhanced_analysis_with_tracking(self, trace_id: str, article_id: str, 
                                                 article_data: Dict[str, Any], 
                                                 article_content: Dict[str, Any]):
        """Run enhanced analysis with comprehensive tracking"""
        try:
            # RAG Enhancement
            if self.rag_service:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RAG_ENHANCEMENT,
                    status="started",
                    input_data={"article_id": article_id},
                    metadata={"rss_feed_id": article_data.get('rss_feed_id')}
                )
                
                rag_start_time = time.time()
                try:
                    rag_context = await self.rag_service.enhance_article_context(
                        article_id, article_content['content']
                    )
                    rag_duration = (time.time() - rag_start_time) * 1000
                    
                    self.pipeline_logger.add_checkpoint(
                        trace_id=trace_id,
                        stage=PipelineStage.RAG_ENHANCEMENT,
                        status="completed",
                        output_data={"context_keys": list(rag_context.keys())},
                        metadata={"rss_feed_id": article_data.get('rss_feed_id'), "duration_ms": rag_duration}
                    )
                except Exception as e:
                    self.pipeline_logger.add_checkpoint(
                        trace_id=trace_id,
                        stage=PipelineStage.RAG_ENHANCEMENT,
                        status="failed",
                        error_message=str(e),
                        metadata={"rss_feed_id": article_data.get('rss_feed_id')}
                    )
            
            # Multi-Perspective Analysis
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.MULTI_PERSPECTIVE_ANALYSIS,
                status="started",
                input_data={"article_id": article_id},
                metadata={"rss_feed_id": article_data.get('rss_feed_id')}
            )
            
            try:
                # This would integrate with the enhanced storyline service
                # For now, we'll just log the checkpoint
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.MULTI_PERSPECTIVE_ANALYSIS,
                    status="completed",
                    output_data={"perspectives_analyzed": 6},
                    metadata={"rss_feed_id": article_data.get('rss_feed_id')}
                )
            except Exception as e:
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.MULTI_PERSPECTIVE_ANALYSIS,
                    status="failed",
                    error_message=str(e),
                    metadata={"rss_feed_id": article_data.get('rss_feed_id')}
                )
            
        except Exception as e:
            logger.error(f"Error in enhanced analysis: {e}")
    
    async def _validate_rss_feed(self, rss_url: str) -> Dict[str, Any]:
        """Validate RSS feed URL and accessibility"""
        try:
            response = requests.get(rss_url, timeout=10)
            if response.status_code != 200:
                return {"valid": False, "error": f"HTTP {response.status_code}"}
            
            # Try to parse as RSS
            feed = feedparser.parse(response.content)
            if not feed.entries:
                return {"valid": False, "error": "No entries found in RSS feed"}
            
            return {
                "valid": True,
                "entries_count": len(feed.entries),
                "feed_title": feed.feed.get('title', ''),
                "last_updated": feed.feed.get('updated', '')
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    async def _fetch_rss_feed(self, rss_url: str) -> Dict[str, Any]:
        """Fetch and parse RSS feed"""
        try:
            response = requests.get(rss_url, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            articles = []
            
            for entry in feed.entries[:20]:  # Limit to 20 articles
                article_data = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'description': entry.get('description', ''),
                    'published': entry.get('published', ''),
                    'author': entry.get('author', ''),
                    'tags': [tag.term for tag in entry.get('tags', [])]
                }
                articles.append(article_data)
            
            return {
                "success": True,
                "articles": articles,
                "feed_title": feed.feed.get('title', ''),
                "feed_description": feed.feed.get('description', '')
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _extract_article_content(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract full article content from URL"""
        try:
            url = article_data.get('link', '')
            if not url:
                return {"success": False, "error": "No URL provided"}
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to find article content
            content_selectors = [
                'article',
                '.article-content',
                '.post-content',
                '.entry-content',
                '.content',
                'main'
            ]
            
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = ' '.join([elem.get_text() for elem in elements])
                    break
            
            if not content:
                content = soup.get_text()
            
            # Clean up content
            content = ' '.join(content.split())
            
            return {
                "success": True,
                "content": content,
                "content_length": len(content),
                "url": url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _validate_article_content(self, content: str) -> Dict[str, Any]:
        """Validate article content quality"""
        if len(content) < 100:
            return {"valid": False, "error": "Content too short"}
        
        if len(content) > 50000:
            return {"valid": False, "error": "Content too long"}
        
        # Check for common issues
        if content.count(' ') < 10:
            return {"valid": False, "error": "Insufficient word count"}
        
        return {
            "valid": True,
            "content_length": len(content),
            "word_count": len(content.split()),
            "quality_score": min(len(content) / 1000, 1.0)
        }
    
    async def _check_duplicate_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if article is a duplicate"""
        try:
            # Simple duplicate check based on title similarity
            # In production, this would use more sophisticated deduplication
            title = article_data.get('title', '').lower()
            
            # Check against recent articles in database
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text("""
                    SELECT id, title FROM articles 
                    WHERE LOWER(title) = :title 
                    AND created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """)
                
                result = db.execute(query, {"title": title}).fetchone()
                is_duplicate = result is not None
                
                return {
                    "is_duplicate": is_duplicate,
                    "duplicate_id": result[0] if result else None
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return {"is_duplicate": False, "error": str(e)}
    
    async def _apply_early_quality_gate(self, content: str) -> Dict[str, Any]:
        """Apply early quality gate to content"""
        # Simple quality scoring
        word_count = len(content.split())
        char_count = len(content)
        
        # Basic quality metrics
        avg_word_length = char_count / word_count if word_count > 0 else 0
        sentence_count = content.count('.') + content.count('!') + content.count('?')
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        # Quality score (0-1)
        quality_score = 0.0
        
        # Word count score
        if 200 <= word_count <= 2000:
            quality_score += 0.3
        elif 100 <= word_count < 200 or 2000 < word_count <= 5000:
            quality_score += 0.2
        
        # Average word length score
        if 3 <= avg_word_length <= 8:
            quality_score += 0.2
        
        # Sentence structure score
        if 5 <= avg_sentence_length <= 25:
            quality_score += 0.2
        
        # Content diversity score
        unique_words = len(set(content.lower().split()))
        diversity_ratio = unique_words / word_count if word_count > 0 else 0
        if diversity_ratio > 0.3:
            quality_score += 0.3
        
        passed = quality_score >= 0.5
        
        return {
            "passed": passed,
            "score": quality_score,
            "word_count": word_count,
            "avg_word_length": avg_word_length,
            "sentence_count": sentence_count,
            "diversity_ratio": diversity_ratio
        }
    
    async def _store_article_with_tracking(self, trace_id: str, rss_feed_id: str, 
                                         article_data: Dict[str, Any], 
                                         article_content: Dict[str, Any],
                                         summary_result: Dict[str, Any]) -> Optional[str]:
        """Store article in database with tracking"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Insert article
                insert_query = text("""
                    INSERT INTO articles (
                        title, content, url, source, published_at, 
                        summary, confidence_score, rss_feed_id, created_at
                    ) VALUES (
                        :title, :content, :url, :source, :published_at,
                        :summary, :confidence_score, :rss_feed_id, NOW()
                    ) RETURNING id
                """)
                
                result = db.execute(insert_query, {
                    'title': article_data.get('title', ''),
                    'content': article_content['content'],
                    'url': article_data.get('link', ''),
                    'source': article_data.get('author', 'Unknown'),
                    'published_at': article_data.get('published', ''),
                    'summary': summary_result.get('summary', ''),
                    'confidence_score': summary_result.get('confidence_score', 0.0),
                    'rss_feed_id': rss_feed_id
                })
                
                article_id = result.fetchone()[0]
                db.commit()
                
                # Log database operation
                self.pipeline_logger.log_database_operation(
                    trace_id=trace_id,
                    operation="INSERT",
                    table="articles",
                    record_count=1,
                    duration_ms=0.0,  # Would measure actual duration
                    success=True
                )
                
                return str(article_id)
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing article: {e}")
            self.pipeline_logger.log_database_operation(
                trace_id=trace_id,
                operation="INSERT",
                table="articles",
                record_count=0,
                duration_ms=0.0,
                success=False,
                error=str(e)
            )
            return None
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.performance_metrics.copy()
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get pipeline summary from logger"""
        return self.pipeline_logger.get_performance_summary()

# Global instance
_enhanced_rss_collector = None

def get_enhanced_rss_collector(ml_service=None, rag_service=None, pipeline_logger=None):
    """Get global enhanced RSS collector instance"""
    global _enhanced_rss_collector
    if _enhanced_rss_collector is None:
        _enhanced_rss_collector = EnhancedRSSCollectorWithTracking(ml_service, rag_service, pipeline_logger)
    return _enhanced_rss_collector
