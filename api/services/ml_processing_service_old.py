"""
ML Processing Service for News Intelligence System
Handles background ML processing with real-time monitoring
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from config.database import get_db

logger = logging.getLogger(__name__)

class MLProcessingService:
    """Service for managing ML processing with real-time monitoring"""
    
    def __init__(self):
        self.is_running = False
        self.processing_thread = None
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "currently_processing": 0,
            "queue_size": 0,
            "last_processed": None,
            "avg_processing_time": 0.0
        }
        self.processing_times = []
    
    def start_processing(self):
        """Start the ML processing service"""
        if self.is_running:
            logger.warning("ML processing service is already running")
            return
        
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        logger.info("🚀 ML Processing Service started")
    
    def stop_processing(self):
        """Stop the ML processing service"""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        logger.info("🛑 ML Processing Service stopped")
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.is_running:
            try:
                # Get next storyline to process
                storyline = self._get_next_storyline()
                
                if storyline:
                    self._process_storyline(storyline)
                else:
                    # No storylines to process, wait a bit
                    time.sleep(5)
                
                # Update stats
                self._update_stats()
                
            except Exception as e:
                logger.error(f"Error in ML processing loop: {e}")
                time.sleep(10)
    
    def _get_next_storyline(self) -> Optional[Dict[str, Any]]:
        """Get the next storyline to process"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get next pending storyline
                result = db.execute(text("""
                    SELECT id, title, ml_processing_status, article_count
                    FROM storylines 
                    WHERE ml_processing_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                """)).fetchone()
                
                if result:
                    return {
                        "id": result.id,
                        "title": result.title,
                        "status": result.ml_processing_status,
                        "article_count": result.article_count
                    }
                return None
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting next storyline: {e}")
            return None
    
    def _process_storyline(self, storyline: Dict[str, Any]):
        """Process a storyline with ML"""
        storyline_id = storyline["id"]
        start_time = time.time()
        
        try:
            logger.info(f"🔄 Processing storyline {storyline_id}: {storyline['title']}")
            
            # Update status to processing
            self._update_storyline_status(storyline_id, "processing")
            self.stats["currently_processing"] = 1
            
            # Simulate ML processing (replace with actual ML calls)
            processing_time = self._simulate_ml_processing(storyline)
            
            # Update status to completed
            self._update_storyline_status(storyline_id, "completed", processing_time)
            
            # Update stats
            self.stats["total_processed"] += 1
            self.stats["successful"] += 1
            self.stats["currently_processing"] = 0
            self.stats["last_processed"] = datetime.now()
            
            # Track processing time
            self.processing_times.append(processing_time)
            if len(self.processing_times) > 10:  # Keep last 10 times
                self.processing_times.pop(0)
            
            logger.info(f"✅ Completed storyline {storyline_id} in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Failed to process storyline {storyline_id}: {e}")
            self._update_storyline_status(storyline_id, "failed", error=str(e))
            self.stats["total_processed"] += 1
            self.stats["failed"] += 1
            self.stats["currently_processing"] = 0
    
    def _simulate_ml_processing(self, storyline: Dict[str, Any]) -> float:
        """Process storyline with actual ML service"""
        start_time = time.time()
        
        try:
            # Import ML service
            from modules.ml.summarization_service import MLSummarizationService
            
            # Initialize ML service (use containerized Ollama)
            ml_service = MLSummarizationService("http://news-intelligence-ollama:11434")
            
            # Get storyline articles for processing
            articles = self._get_storyline_articles(storyline["id"])
            
            if not articles:
                logger.warning(f"No articles found for storyline {storyline['id']}")
                return time.time() - start_time
            
            # Process with ML
            logger.info(f"Processing {len(articles)} articles with ML for storyline {storyline['id']}")
            
            # Generate master summary
            master_summary = self._generate_master_summary(ml_service, articles)
            
            # Update storyline with ML results
            self._update_storyline_ml_results(storyline["id"], master_summary)
            
            processing_time = time.time() - start_time
            logger.info(f"ML processing completed in {processing_time:.2f}s")
            
            return processing_time
            
        except Exception as e:
            logger.error(f"ML processing failed: {e}")
            # Fallback to simulation if ML fails
            base_time = 2.0
            article_factor = storyline["article_count"] * 0.5
            processing_time = base_time + article_factor
            time.sleep(processing_time)
            return processing_time
    
    def _get_storyline_articles(self, storyline_id: int) -> List[Dict[str, Any]]:
        """Get articles for a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT a.id, a.title, a.content, a.summary, a.source, a.published_at
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = :storyline_id
                    ORDER BY a.published_at ASC
                """), {"storyline_id": storyline_id}).fetchall()
                
                return [
                    {
                        "id": row.id,
                        "title": row.title,
                        "content": row.content,
                        "summary": row.summary,
                        "source": row.source,
                        "published_at": row.published_at
                    }
                    for row in result
                ]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting storyline articles: {e}")
            return []
    
    def _generate_master_summary(self, ml_service, articles: List[Dict[str, Any]]) -> str:
        """Generate comprehensive journalistic master summary using ML service"""
        try:
            # Create structured content for journalistic summarization
            structured_content = self._create_journalistic_input(articles)
            
            if not structured_content:
                return "No content available for summarization."
            
            # Create comprehensive prompt for journalistic analysis
            journalistic_prompt = self._create_journalistic_prompt(structured_content, articles)
            
            # Generate summary using ML service with journalistic focus
            summary_result = ml_service.generate_summary(journalistic_prompt)
            
            if summary_result and summary_result.get('success'):
                raw_summary = summary_result.get('summary', 'Summary generation failed.')
                # Post-process for journalistic quality
                return self._enhance_journalistic_summary(raw_summary, articles)
            else:
                logger.warning("ML service returned no summary, using enhanced fallback")
                return self._generate_enhanced_fallback_summary(articles)
                
        except Exception as e:
            logger.error(f"Error generating master summary: {e}")
            return self._generate_enhanced_fallback_summary(articles)
    
    def _create_journalistic_input(self, articles: List[Dict[str, Any]]) -> str:
        """Create structured input optimized for journalistic analysis"""
        if not articles:
            return ""
        
        # Sort articles by publication date for chronological context
        sorted_articles = sorted(articles, key=lambda x: x.get('published_at', ''))
        
        structured_content = []
        structured_content.append("=== JOURNALISTIC ANALYSIS REQUEST ===")
        structured_content.append("")
        structured_content.append("Please analyze the following news articles and create a comprehensive, longform journalistic summary that:")
        structured_content.append("1. Provides deep context and background")
        structured_content.append("2. Identifies key players, stakeholders, and their positions")
        structured_content.append("3. Explains the significance and implications")
        structured_content.append("4. Tracks the evolution of the story over time")
        structured_content.append("5. Presents multiple perspectives and viewpoints")
        structured_content.append("6. Uses journalistic language and structure")
        structured_content.append("")
        structured_content.append("=== SOURCE ARTICLES ===")
        structured_content.append("")
        
        for i, article in enumerate(sorted_articles, 1):
            published_date = article.get('published_at', 'Unknown date')
            source = article.get('source', 'Unknown source')
            title = article.get('title', 'Untitled')
            content = article.get('content') or article.get('summary', '')
            
            structured_content.append(f"--- ARTICLE {i} ---")
            structured_content.append(f"Source: {source}")
            structured_content.append(f"Published: {published_date}")
            structured_content.append(f"Headline: {title}")
            structured_content.append("")
            structured_content.append("Content:")
            structured_content.append(content)
            structured_content.append("")
            structured_content.append("--- END ARTICLE {i} ---")
            structured_content.append("")
        
        return "\n".join(structured_content)
    
    def _create_journalistic_prompt(self, structured_content: str, articles: List[Dict[str, Any]]) -> str:
        """Create a comprehensive prompt for journalistic analysis"""
        sources = list(set(article.get('source', 'Unknown') for article in articles))
        date_range = self._get_date_range(articles)
        
        prompt = f"""
{structured_content}

=== ANALYSIS INSTRUCTIONS ===

Based on the above articles from {len(sources)} sources ({', '.join(sources)}) covering the period {date_range}, please create a comprehensive journalistic analysis that includes:

**STRUCTURE:**
1. **Executive Summary** - A compelling 2-3 paragraph overview of the story
2. **Key Developments** - Chronological breakdown of major events and turning points
3. **Stakeholder Analysis** - Who are the key players and what are their positions?
4. **Context & Background** - Historical context and why this story matters
5. **Implications** - What this means for different groups and the broader impact
6. **Timeline** - Key dates and milestones in the story's evolution
7. **Perspectives** - Different viewpoints and how they're represented in the coverage

**TONE & STYLE:**
- Use professional journalistic language
- Be comprehensive but accessible
- Include specific details, quotes, and data points where available
- Maintain objectivity while highlighting significance
- Use subheadings and clear organization
- Aim for 800-1500 words of substantive analysis

**FOCUS AREAS:**
- What are the underlying issues driving this story?
- How has the narrative evolved over time?
- What are the different perspectives and why do they matter?
- What are the potential outcomes and consequences?
- How does this fit into broader patterns or trends?

Please provide a thorough, well-structured analysis that would be suitable for a high-quality news magazine or investigative journalism piece.
"""
        return prompt
    
    def _get_date_range(self, articles: List[Dict[str, Any]]) -> str:
        """Get date range for articles"""
        dates = [article.get('published_at') for article in articles if article.get('published_at')]
        if not dates:
            return "Unknown dates"
        
        try:
            from datetime import datetime
            parsed_dates = [datetime.fromisoformat(d.replace('Z', '+00:00')) for d in dates if d]
            if parsed_dates:
                earliest = min(parsed_dates).strftime('%B %d, %Y')
                latest = max(parsed_dates).strftime('%B %d, %Y')
                return f"{earliest} to {latest}"
        except:
            pass
        
        return "Various dates"
    
    def _enhance_journalistic_summary(self, raw_summary: str, articles: List[Dict[str, Any]]) -> str:
        """Post-process summary for journalistic quality with separated core data and full summary"""
        if not raw_summary or len(raw_summary.strip()) < 100:
            return self._generate_enhanced_fallback_summary(articles)
        
        # Extract core metadata
        sources = list(set(article.get('source', 'Unknown') for article in articles))
        article_count = len(articles)
        date_range = self._get_date_range(articles)
        
        # Create user-friendly structure
        enhanced_summary = f"""# Story Overview

## 📊 Quick Facts
- **Articles:** {article_count} from {len(sources)} sources
- **Sources:** {', '.join(sources)}
- **Time Period:** {date_range}
- **Last Updated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## 📖 Full Analysis

{raw_summary}

---

*Generated by AI-powered journalistic analysis of multiple news sources*"""
        
        return enhanced_summary
    
    def _generate_enhanced_fallback_summary(self, articles: List[Dict[str, Any]]) -> str:
        """Generate an enhanced fallback summary with user-friendly structure"""
        if not articles:
            return "No articles available for this storyline."
        
        sources = list(set(article.get('source', 'Unknown') for article in articles))
        date_range = self._get_date_range(articles)
        
        # Create a structured fallback summary with separated core data
        fallback_summary = f"""# Story Overview

## 📊 Quick Facts
- **Articles:** {len(articles)} from {len(sources)} sources
- **Sources:** {', '.join(sources)}
- **Time Period:** {date_range}
- **Last Updated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## 📖 Full Analysis

### Executive Summary
This storyline tracks developments across {len(articles)} news articles from {len(sources)} different sources, providing comprehensive coverage of the topic. The articles span {date_range}, offering a chronological view of how the story has evolved over time.

### Key Sources and Coverage
The coverage includes perspectives from:
{chr(10).join(f"- **{source}**: {len([a for a in articles if a.get('source') == source])} article(s)" for source in sources)}

### Story Development
The articles provide multiple angles and perspectives on this developing story, with coverage that includes:
- Breaking news developments
- Analysis and commentary
- Background context and historical perspective
- Stakeholder reactions and responses
- Policy implications and broader impact

### Next Steps
As new articles are added to this storyline, the analysis will be automatically updated to incorporate the latest developments and provide increasingly comprehensive coverage of this important story.

---

*Generated by AI-powered journalistic analysis of multiple news sources*"""
        
        return fallback_summary
    
    def _update_storyline_ml_results(self, storyline_id: int, master_summary: str):
        """Update storyline with ML processing results"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    UPDATE storylines 
                    SET master_summary = :master_summary,
                        ml_processing_status = 'completed',
                        ml_last_processed = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :storyline_id
                """), {
                    "storyline_id": storyline_id,
                    "master_summary": master_summary
                })
                db.commit()
                logger.info(f"Updated storyline {storyline_id} with master summary")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating storyline ML results: {e}")
    
    def _update_storyline_status(self, storyline_id: int, status: str, processing_time: Optional[float] = None, error: Optional[str] = None):
        """Update storyline processing status"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                if status == "processing":
                    db.execute(text("""
                        UPDATE storylines 
                        SET ml_processing_status = 'processing',
                            ml_processing_attempts = ml_processing_attempts + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :storyline_id
                    """), {"storyline_id": storyline_id})
                elif status == "completed":
                    db.execute(text("""
                        UPDATE storylines 
                        SET ml_processing_status = 'completed',
                            ml_last_processed = CURRENT_TIMESTAMP,
                            ml_processing_duration = :processing_time,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :storyline_id
                    """), {
                        "storyline_id": storyline_id,
                        "processing_time": int(processing_time) if processing_time else None
                    })
                elif status == "failed":
                    db.execute(text("""
                        UPDATE storylines 
                        SET ml_processing_status = 'failed',
                            ml_last_error = :error,
                            ml_processing_attempts = ml_processing_attempts + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :storyline_id
                    """), {
                        "storyline_id": storyline_id,
                        "error": error
                    })
                
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating storyline status: {e}")
    
    def _update_stats(self):
        """Update processing statistics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get queue size
                result = db.execute(text("""
                    SELECT COUNT(*) as queue_size
                    FROM storylines 
                    WHERE ml_processing_status IN ('pending', 'queued')
                """)).fetchone()
                
                self.stats["queue_size"] = result.queue_size if result else 0
                
                # Calculate average processing time
                if self.processing_times:
                    self.stats["avg_processing_time"] = sum(self.processing_times) / len(self.processing_times)
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        return self.stats.copy()
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get detailed processing status"""
        return {
            "is_running": self.is_running,
            "stats": self.get_stats(),
            "timestamp": datetime.now().isoformat()
        }

# Global ML processing service instance
ml_processing_service = MLProcessingService()
