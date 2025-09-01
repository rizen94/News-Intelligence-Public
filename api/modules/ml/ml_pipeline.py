"""
ML Pipeline for News Intelligence System
Integrates ML services with the existing data pipeline
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import psycopg2

from .summarization_service import MLSummarizationService
from .content_analyzer import ContentAnalyzer
from .quality_scorer import QualityScorer

logger = logging.getLogger(__name__)

class MLPipeline:
    """
    ML-enhanced pipeline for processing news articles
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize the ML Pipeline
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.ml_service = MLSummarizationService()
        self.content_analyzer = ContentAnalyzer()
        self.quality_scorer = QualityScorer()
        
        # Test ML service connection
        self._test_ml_service()
    
    def _test_ml_service(self) -> bool:
        """Test ML service connection"""
        try:
            status = self.ml_service.get_service_status()
            if status["status"] == "online" and status["model_available"]:
                logger.info("✅ ML service connection successful")
                return True
            else:
                logger.warning(f"⚠️ ML service not available: {status}")
                return False
        except Exception as e:
            logger.error(f"❌ ML service connection failed: {e}")
            return False
    
    def process_article(self, article_id: int) -> Dict[str, any]:
        """
        Process a single article through the ML pipeline
        
        Args:
            article_id: ID of the article to process
            
        Returns:
            Dictionary containing processing results
        """
        try:
            logger.info(f"🤖 Starting ML processing for article {article_id}")
            
            # Get article from database
            article = self._get_article(article_id)
            if not article:
                return {"status": "failed", "error": "Article not found"}
            
            # Step 1: Content Analysis
            logger.info(f"📊 Analyzing content for article {article_id}")
            content_analysis = self._analyze_content(article)
            
            # Step 2: Quality Scoring
            logger.info(f"⭐ Scoring quality for article {article_id}")
            quality_score = self._score_quality(article, content_analysis)
            
            # Step 3: ML Processing (if quality is sufficient)
            ml_results = {}
            if quality_score["overall_score"] >= 0.3:  # Minimum quality threshold
                logger.info(f"🤖 Running ML processing for article {article_id}")
                ml_results = self._run_ml_processing(article)
            else:
                logger.warning(f"⚠️ Skipping ML processing for article {article_id} - quality too low")
                ml_results = {"skipped": True, "reason": "low_quality"}
            
            # Step 4: Store Results
            logger.info(f"💾 Storing results for article {article_id}")
            storage_result = self._store_ml_results(article_id, content_analysis, quality_score, ml_results)
            
            return {
                "status": "success",
                "article_id": article_id,
                "content_analysis": content_analysis,
                "quality_score": quality_score,
                "ml_results": ml_results,
                "storage_result": storage_result,
                "processed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing article {article_id}: {e}")
            return {
                "status": "failed",
                "article_id": article_id,
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }
    
    def process_articles_batch(self, article_ids: List[int]) -> Dict[str, any]:
        """
        Process multiple articles through the ML pipeline
        
        Args:
            article_ids: List of article IDs to process
            
        Returns:
            Dictionary containing batch processing results
        """
        try:
            logger.info(f"🤖 Starting batch ML processing for {len(article_ids)} articles")
            
            results = {
                "total_articles": len(article_ids),
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "results": [],
                "started_at": datetime.now().isoformat()
            }
            
            for article_id in article_ids:
                try:
                    result = self.process_article(article_id)
                    results["results"].append(result)
                    
                    if result["status"] == "success":
                        results["processed"] += 1
                    elif result.get("ml_results", {}).get("skipped"):
                        results["skipped"] += 1
                    else:
                        results["failed"] += 1
                        
                except Exception as e:
                    logger.error(f"❌ Error processing article {article_id}: {e}")
                    results["results"].append({
                        "status": "failed",
                        "article_id": article_id,
                        "error": str(e)
                    })
                    results["failed"] += 1
            
            results["completed_at"] = datetime.now().isoformat()
            results["success_rate"] = results["processed"] / results["total_articles"] if results["total_articles"] > 0 else 0
            
            logger.info(f"✅ Batch processing completed: {results['processed']} processed, {results['failed']} failed, {results['skipped']} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in batch processing: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "total_articles": len(article_ids),
                "processed": 0,
                "failed": len(article_ids),
                "skipped": 0
            }
    
    def _get_article(self, article_id: int) -> Optional[Dict]:
        """Get article from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, content, url, source, published_date, category, language
                FROM articles 
                WHERE id = %s
            """, (article_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "url": row[3],
                    "source": row[4],
                    "published_date": row[5],
                    "category": row[6],
                    "language": row[7]
                }
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Error getting article {article_id}: {e}")
            return None
    
    def _analyze_content(self, article: Dict) -> Dict:
        """Analyze article content"""
        try:
            # Clean content
            cleaning_result = self.content_analyzer.clean_content(article["content"])
            
            # Extract metadata
            metadata = self.content_analyzer.extract_metadata(
                cleaning_result["cleaned_content"], 
                article["title"]
            )
            
            # Generate content hash
            content_hash = self.content_analyzer.generate_content_hash(
                cleaning_result["cleaned_content"]
            )
            
            return {
                "cleaning_result": cleaning_result,
                "metadata": metadata,
                "content_hash": content_hash,
                "analyzed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing content: {e}")
            return {"error": str(e)}
    
    def _score_quality(self, article: Dict, content_analysis: Dict) -> Dict:
        """Score article quality"""
        try:
            cleaned_content = content_analysis.get("cleaning_result", {}).get("cleaned_content", article["content"])
            
            quality_score = self.quality_scorer.score_content(
                cleaned_content, 
                article["title"], 
                content_analysis.get("metadata", {})
            )
            
            return quality_score
            
        except Exception as e:
            logger.error(f"Error scoring quality: {e}")
            return {"error": str(e), "overall_score": 0.0}
    
    def _run_ml_processing(self, article: Dict) -> Dict:
        """Run ML processing on article"""
        try:
            cleaned_content = article["content"]  # Use original content for now
            
            # Generate summary
            summary_result = self.ml_service.generate_summary(
                cleaned_content, 
                article["title"]
            )
            
            # Extract key points
            key_points_result = self.ml_service.extract_key_points(
                cleaned_content, 
                article["title"]
            )
            
            # Analyze sentiment
            sentiment_result = self.ml_service.analyze_sentiment(cleaned_content)
            
            # Analyze arguments and perspectives
            argument_result = self.ml_service.analyze_arguments(cleaned_content, article["title"])
            
            return {
                "summary": summary_result,
                "key_points": key_points_result,
                "sentiment": sentiment_result,
                "argument_analysis": argument_result,
                "processed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in ML processing: {e}")
            return {"error": str(e)}
    
    def _store_ml_results(self, article_id: int, content_analysis: Dict, quality_score: Dict, ml_results: Dict) -> Dict:
        """Store ML results in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Prepare ML data for storage
            ml_data = {
                "content_analysis": content_analysis,
                "quality_score": quality_score,
                "ml_processing": ml_results,
                "processed_at": datetime.now().isoformat()
            }
            
            # Update article with ML results
            update_fields = []
            update_values = []
            
            # Update summary if available
            if ml_results.get("summary", {}).get("status") == "success":
                update_fields.append("summary = %s")
                update_values.append(ml_results["summary"]["summary"])
            
            # Update quality score
            if quality_score.get("overall_score"):
                update_fields.append("quality_score = %s")
                update_values.append(quality_score["overall_score"])
            
            # Update ML data
            update_fields.append("ml_data = %s")
            update_values.append(json.dumps(ml_data))
            
            # Update processing status
            update_fields.append("processing_status = %s")
            update_values.append("ml_processed")
            
            # Update content hash if available
            if content_analysis.get("content_hash"):
                update_fields.append("content_hash = %s")
                update_values.append(content_analysis["content_hash"])
            
            # Update normalized content if available
            if content_analysis.get("cleaning_result", {}).get("cleaned_content"):
                update_fields.append("normalized_content = %s")
                update_values.append(content_analysis["cleaning_result"]["cleaned_content"])
            
            # Add article ID and timestamp
            update_values.append(article_id)
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            
            # Execute update
            query = f"""
                UPDATE articles 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """
            
            cursor.execute(query, update_values)
            conn.commit()
            
            conn.close()
            
            return {
                "status": "success",
                "updated_fields": len(update_fields) - 1,  # Exclude timestamp
                "stored_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error storing ML results: {e}")
            return {"status": "failed", "error": str(e)}
    
    def get_processing_status(self) -> Dict:
        """Get overall processing status"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get processing statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(CASE WHEN processing_status = 'ml_processed' THEN 1 END) as ml_processed,
                    COUNT(CASE WHEN summary IS NOT NULL THEN 1 END) as with_summaries,
                    COUNT(CASE WHEN ml_data IS NOT NULL THEN 1 END) as with_ml_data
                FROM articles
            """)
            
            stats = cursor.fetchone()
            
            # Get ML service status
            ml_status = self.ml_service.get_service_status()
            
            conn.close()
            
            return {
                "database_stats": {
                    "total_articles": stats[0],
                    "ml_processed": stats[1],
                    "with_summaries": stats[2],
                    "with_ml_data": stats[3]
                },
                "ml_service_status": ml_status,
                "checked_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return {"error": str(e)}
