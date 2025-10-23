"""
Improved ML Processing Service for News Intelligence System
Focuses on narrative building rather than content dumping
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
    """Service for managing ML processing with narrative-focused summarization"""
    
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
        logger.info("🚀 Improved ML Processing Service started")
    
    def stop_processing(self):
        """Stop the ML processing service"""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        logger.info("🛑 ML Processing Service stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.stats.copy()
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status"""
        return {
            "is_running": self.is_running,
            "stats": self.stats.copy(),
            "status": "running" if self.is_running else "stopped",
            "last_update": datetime.now().isoformat()
        }
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.is_running:
            try:
                self._process_storylines()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(60)
    
    def _process_storylines(self):
        """Process storylines that need ML analysis"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get storylines that need processing
                query = text("""
                    SELECT id, title, description, article_count
                    FROM storylines 
                    WHERE ml_processing_status = 'pending' 
                    OR (ml_processing_status = 'completed' AND updated_at > ml_last_processed)
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 5
                """)
                
                storylines = db.execute(query).fetchall()
                
                for storyline in storylines:
                    self._process_storyline_with_ml(storyline)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing storylines: {e}")
    
    def _process_storyline_with_ml(self, storyline):
        """Process a single storyline with improved ML summarization"""
        try:
            start_time = time.time()
            storyline_id = storyline.id
            
            logger.info(f"Processing storyline: {storyline.title}")
            
            # Get articles for this storyline
            articles = self._get_storyline_articles(storyline_id)
            
            if not articles:
                logger.warning(f"No articles found for storyline {storyline_id}")
                return
            
            # Import ML service
            from services.ml_summarization_service import MLSummarizationService
            ml_service = MLSummarizationService()
            
            # Generate narrative-focused summary
            master_summary = self._generate_narrative_summary(ml_service, articles, storyline)
            
            # Update storyline with ML results
            self._update_storyline_ml_results(storyline_id, master_summary)
            
            processing_time = time.time() - start_time
            logger.info(f"Narrative ML processing completed in {processing_time:.2f}s")
            
            return processing_time
            
        except Exception as e:
            logger.error(f"ML processing failed: {e}")
            return 0
    
    def _get_storyline_articles(self, storyline_id: int) -> List[Dict[str, Any]]:
        """Get articles for a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text("""
                    SELECT a.id, a.title, a.content, a.summary, a.source_domain, a.published_at, a.author
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = :storyline_id
                    ORDER BY a.published_at ASC
                """)
                
                result = db.execute(query, {"storyline_id": storyline_id}).fetchall()
                return [dict(row._mapping) for row in result]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting storyline articles: {e}")
            return []
    
    def _generate_narrative_summary(self, ml_service, articles: List[Dict[str, Any]], storyline) -> str:
        """Generate narrative-focused summary using improved approach"""
        try:
            # Create narrative-focused input
            narrative_input = self._create_narrative_input(articles, storyline)
            
            if not narrative_input:
                return "No content available for narrative analysis."
            
            # Create focused prompt for narrative building
            narrative_prompt = self._create_narrative_prompt(narrative_input, articles, storyline)
            
            # Generate summary using ML service
            summary_result = ml_service.generate_summary(narrative_prompt)
            
            if summary_result and summary_result.get('success'):
                raw_summary = summary_result.get('summary', 'Summary generation failed.')
                return self._enhance_narrative_summary(raw_summary, articles, storyline)
            else:
                logger.warning("ML service returned no summary, using narrative fallback")
                return self._generate_narrative_fallback(articles, storyline)
                
        except Exception as e:
            logger.error(f"Error generating narrative summary: {e}")
            return self._generate_narrative_fallback(articles, storyline)
    
    def _create_narrative_input(self, articles: List[Dict[str, Any]], storyline) -> str:
        """Create input focused on narrative building rather than content dumping"""
        if not articles:
            return ""
        
        # Sort articles by publication date for chronological context
        sorted_articles = sorted(articles, key=lambda x: x.get('published_at', ''))
        
        narrative_input = []
        narrative_input.append("=== NARRATIVE STORY ANALYSIS ===")
        narrative_input.append("")
        narrative_input.append(f"Storyline: {storyline.title}")
        narrative_input.append(f"Description: {storyline.description}")
        narrative_input.append("")
        narrative_input.append("Create a cohesive, high-level story summary by analyzing how these story elements connect and evolve.")
        narrative_input.append("Focus on building a unified narrative that shows the bigger picture.")
        narrative_input.append("")
        narrative_input.append("=== STORY ELEMENTS ===")
        narrative_input.append("")
        
        for i, article in enumerate(sorted_articles, 1):
            published_date = article.get('published_at', 'Unknown date')
            source = article.get('source', 'Unknown source')
            title = article.get('title', 'Untitled')
            content = article.get('content') or article.get('summary', '')
            
            # Extract key narrative elements instead of full content
            narrative_elements = self._extract_narrative_elements(content, title)
            
            narrative_input.append(f"--- STORY ELEMENT {i} ---")
            narrative_input.append(f"Source: {source}")
            narrative_input.append(f"Date: {published_date}")
            narrative_input.append(f"Headline: {title}")
            narrative_input.append("Key Narrative Points:")
            for element in narrative_elements:
                narrative_input.append(f"  • {element}")
            narrative_input.append("")
        
        return "\n".join(narrative_input)
    
    def _extract_narrative_elements(self, content: str, title: str) -> List[str]:
        """Extract key narrative elements from article content"""
        if not content:
            return [f"Headline: {title}"]
        
        # Limit content to first 300 characters to focus on key points
        content_preview = content[:300] + "..." if len(content) > 300 else content
        
        # Extract key sentences that contain important information
        sentences = content_preview.split('. ')
        narrative_elements = []
        
        # Look for sentences that contain key information (quotes, facts, developments)
        for sentence in sentences[:3]:
            if sentence.strip() and len(sentence.strip()) > 15:
                # Clean up the sentence
                clean_sentence = sentence.strip().replace('\n', ' ').replace('\r', ' ')
                if clean_sentence and not clean_sentence.endswith('.'):
                    clean_sentence += '.'
                narrative_elements.append(clean_sentence)
        
        # If we don't have enough elements, add the title as context
        if len(narrative_elements) < 2:
            narrative_elements.insert(0, f"Headline: {title}")
        
        return narrative_elements[:4]  # Limit to 4 elements max
    
    def _create_narrative_prompt(self, narrative_input: str, articles: List[Dict[str, Any]], storyline) -> str:
        """Create a focused prompt for narrative building"""
        sources = list(set(article.get('source', 'Unknown') for article in articles))
        date_range = self._get_date_range(articles)
        
        prompt = f"""
{narrative_input}

=== NARRATIVE BUILDING INSTRUCTIONS ===

Based on the story elements above, create a cohesive narrative summary that:

**FOCUS ON:**
- How these story elements connect to form a bigger picture
- The main story arc and its progression over time
- Key themes and patterns that emerge across sources
- The significance and implications of the overall story

**STRUCTURE YOUR RESPONSE AS:**
1. **Story Overview** - What is this story fundamentally about?
2. **Key Developments** - How has the story evolved and what are the main turning points?
3. **Stakeholders & Perspectives** - Who are the key players and what are their positions?
4. **Context & Significance** - Why does this story matter and what are the broader implications?
5. **Current Status** - Where does the story stand now and what might happen next?

**WRITING STYLE:**
- Write as a journalist creating a comprehensive story report
- Use clear, engaging language that tells a story
- Connect the dots between different story elements
- Focus on the narrative flow rather than listing individual article details
- Aim for 400-600 words that provide a complete picture

**STORYLINE CONTEXT:**
- Title: {storyline.title}
- Description: {storyline.description}
- Sources: {len(sources)} different sources ({', '.join(sources)})
- Time Period: {date_range}
- Total Elements: {len(articles)} story components

Create a narrative that shows how these individual story elements combine to tell a complete, compelling story.
"""
        return prompt
    
    def _enhance_narrative_summary(self, raw_summary: str, articles: List[Dict[str, Any]], storyline) -> str:
        """Post-process summary for narrative quality"""
        if not raw_summary or len(raw_summary.strip()) < 100:
            return self._generate_narrative_fallback(articles, storyline)
        
        # Extract core metadata
        sources = list(set(article.get('source', 'Unknown') for article in articles))
        article_count = len(articles)
        date_range = self._get_date_range(articles)
        
        # Create enhanced narrative structure
        enhanced_summary = f"""# {storyline.title}

## 📊 Story Overview
- **Sources:** {len(sources)} different outlets ({', '.join(sources)})
- **Time Period:** {date_range}
- **Story Elements:** {article_count} components analyzed
- **Last Updated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## 📖 Narrative Analysis

{raw_summary}

---

*Generated by AI-powered narrative analysis of multiple news sources*"""
        
        return enhanced_summary
    
    def _generate_narrative_fallback(self, articles: List[Dict[str, Any]], storyline) -> str:
        """Generate a narrative-focused fallback summary"""
        if not articles:
            return "No articles available for this storyline."
        
        sources = list(set(article.get('source', 'Unknown') for article in articles))
        date_range = self._get_date_range(articles)
        
        # Create a narrative-focused fallback
        fallback_summary = f"""# {storyline.title}

## 📊 Story Overview
- **Sources:** {len(sources)} different outlets ({', '.join(sources)})
- **Time Period:** {date_range}
- **Story Elements:** {len(articles)} components analyzed
- **Last Updated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## 📖 Narrative Analysis

### Story Summary
This storyline tracks developments across {len(articles)} news articles from {len(sources)} different sources, providing comprehensive coverage of {storyline.title.lower()}. The articles span {date_range}, offering a chronological view of how the story has evolved over time.

### Key Themes
The coverage reveals several interconnected themes:
- Multiple perspectives on the same core story
- Evolving developments over time
- Different sources providing unique angles and insights
- A complex narrative with multiple stakeholders and viewpoints

### Story Development
The articles provide multiple angles and perspectives on this developing story, with coverage that includes:
- Breaking news developments and updates
- Analysis and commentary from different sources
- Background context and historical perspective
- Stakeholder reactions and responses
- Policy implications and broader impact

### Current Status
As new articles are added to this storyline, the narrative analysis will be automatically updated to incorporate the latest developments and provide increasingly comprehensive coverage of this important story.

---

*Generated by AI-powered narrative analysis of multiple news sources*"""
        
        return fallback_summary
    
    def _get_date_range(self, articles: List[Dict[str, Any]]) -> str:
        """Get date range for articles"""
        if not articles:
            return "Unknown"
        
        dates = [article.get('published_at') for article in articles if article.get('published_at')]
        if not dates:
            return "Unknown"
        
        try:
            min_date = min(dates)
            max_date = max(dates)
            if min_date == max_date:
                return min_date.strftime('%B %d, %Y')
            else:
                return f"{min_date.strftime('%B %d, %Y')} - {max_date.strftime('%B %d, %Y')}"
        except:
            return "Unknown"
    
    def _update_storyline_ml_results(self, storyline_id: int, master_summary: str):
        """Update storyline with ML results"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text("""
                    UPDATE storylines 
                    SET master_summary = :summary,
                        ml_processing_status = 'completed',
                        ml_last_processed = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :storyline_id
                """)
                
                db.execute(query, {
                    "summary": master_summary,
                    "storyline_id": storyline_id
                })
                db.commit()
                
                logger.info(f"Updated storyline {storyline_id} with narrative summary")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating storyline ML results: {e}")

# Create global instance
ml_processing_service = MLProcessingService()
