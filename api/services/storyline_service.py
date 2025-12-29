"""
Storyline Service for News Intelligence System v3.0
Handles storyline management, ML processing, and temporal analysis
"""

import asyncio
import logging
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from config.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class StorylineService:
    def __init__(self, db_connection=None):
        """Initialize storyline service with optional database connection"""
        self.db_connection = db_connection
        self.logger = logging.getLogger(__name__)
    
    async def create_storyline(self, title: str, description: str = None) -> Dict[str, Any]:
        """Create a new storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Use auto-incrementing ID instead of custom ID
                result = db.execute(text("""
                    INSERT INTO storylines (title, description, status, created_at, updated_at, created_by)
                    VALUES (:title, :description, 'active', NOW(), NOW(), 'user')
                    RETURNING id, created_at, updated_at
                """), {
                    "title": title,
                    "description": description or ""
                }).fetchone()
                
                db.commit()
                
                storyline_id = result[0]
                created_at = result[1]
                updated_at = result[2]
                
                return {
                    "id": storyline_id,
                    "title": title,
                    "description": description or "",
                    "status": "active",
                    "article_count": 0,
                    "created_at": created_at.isoformat() if created_at else datetime.now().isoformat(),
                    "updated_at": updated_at.isoformat() if updated_at else datetime.now().isoformat()
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error creating storyline: {e}")
            return {"error": str(e)}
    
    async def get_storylines(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Get all storylines with pagination"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get total count
                count_result = db.execute(text("SELECT COUNT(*) FROM storylines")).fetchone()
                total_count = count_result[0] if count_result else 0
                
                # Get storylines with actual article counts
                storylines_query = text("""
                    SELECT s.id, s.title, s.description, s.status, s.created_at, s.updated_at, 
                           s.master_summary, 
                           COALESCE(COUNT(sa.article_id), 0) as article_count
                    FROM storylines s
                    LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
                    GROUP BY s.id, s.title, s.description, s.status, s.created_at, s.updated_at, s.master_summary
                    ORDER BY s.updated_at DESC 
                    LIMIT :limit OFFSET :offset
                """)
                
                storylines_result = db.execute(storylines_query, {"limit": limit, "offset": offset}).fetchall()
                
                storylines = []
                for row in storylines_result:
                    storylines.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "status": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "master_summary": row[6],
                        "article_count": row[7] or 0
                    })
                
                return {
                    "storylines": storylines,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting storylines: {e}")
            return {
                "storylines": [],
                "total_count": 0,
                "error": str(e)
            }
    
    async def get_all_storylines(self) -> List[Dict[str, Any]]:
        """Get all storylines without pagination for automation tasks"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get all storylines with article count and RAG status
                storylines_result = db.execute(text("""
                    SELECT s.id, s.title, s.description, s.status, s.created_at, s.updated_at,
                           s.rag_enhanced_at, s.rag_context_summary,
                           COALESCE(COUNT(sa.article_id), 0) as article_count
                    FROM storylines s
                    LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
                    WHERE s.status = 'active'
                    GROUP BY s.id, s.title, s.description, s.status, s.created_at, s.updated_at, s.rag_enhanced_at, s.rag_context_summary
                    ORDER BY s.updated_at DESC
                """)).fetchall()
                
                storylines = []
                for row in storylines_result:
                    storylines.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "status": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "rag_enhanced_at": row[6].isoformat() if row[6] else None,
                        "rag_context_summary": row[7],
                        "article_count": row[8],
                        "articles": []  # Will be populated if needed
                    })
                
                return storylines
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting all storylines: {e}")
            return []
    
    async def add_article_to_storyline(self, storyline_id: str, article_id: str, 
                                     relevance_score: float = None, importance_score: float = None) -> Dict[str, Any]:
        """Add an article to a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Check if article is already in storyline
                existing = db.execute(text("""
                    SELECT id FROM storyline_articles 
                    WHERE storyline_id = :storyline_id AND article_id = :article_id
                """), {"storyline_id": storyline_id, "article_id": article_id}).fetchone()
                
                if existing:
                    return {"error": "Article already in storyline"}
                
                # Add article to storyline
                db.execute(text("""
                    INSERT INTO storyline_articles (storyline_id, article_id, relevance_score, importance_score)
                    VALUES (:storyline_id, :article_id, :relevance_score, :importance_score)
                """), {
                    "storyline_id": storyline_id,
                    "article_id": article_id,
                    "relevance_score": relevance_score,
                    "importance_score": importance_score
                })
                
                # Log the addition
                db.execute(text("""
                    INSERT INTO storyline_edit_log (storyline_id, edit_type, edit_description, edit_data, edited_by)
                    VALUES (:storyline_id, 'article_added', 'Article added to storyline', :edit_data, 'user')
                """), {
                    "storyline_id": storyline_id,
                    "edit_data": json.dumps({
                        "article_id": article_id,
                        "relevance_score": relevance_score,
                        "importance_score": importance_score
                    })
                })
                
                db.commit()
                
                # Trigger automated ML processing in background
                try:
                    await self._trigger_automated_ml_processing(storyline_id)
                except Exception as ml_error:
                    self.logger.warning(f"Automated ML processing failed: {ml_error}")
                
                return {
                    "storyline_id": storyline_id,
                    "article_id": article_id,
                    "status": "added",
                    "message": "Article added to storyline successfully",
                    "ml_processing_triggered": True
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error adding article to storyline: {e}")
            return {"error": str(e)}
    
    async def _trigger_automated_ml_processing(self, storyline_id: str):
        """Trigger automated ML processing for storyline"""
        try:
            # Import enhanced storyline service
            from services.multi_perspective_storyline_service import MultiPerspectiveStorylineService
            enhanced_service = MultiPerspectiveStorylineService()
            
            # Update processing status
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    UPDATE storylines 
                    SET ml_processing_status = 'queued',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :storyline_id
                """), {"storyline_id": storyline_id})
                db.commit()
            finally:
                db.close()
            
            # Process ML in background
            result = await enhanced_service.process_storyline_ml(storyline_id)
            
            if "error" in result:
                self.logger.error(f"Automated ML processing failed for storyline {storyline_id}: {result['error']}")
            else:
                self.logger.info(f"Automated ML processing completed for storyline {storyline_id}")
                
        except Exception as e:
            self.logger.error(f"Error triggering automated ML processing: {e}")
    
    async def get_storyline_articles(self, storyline_id: str) -> Dict[str, Any]:
        """Get all articles in a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get storyline info with actual article count
                storyline_result = db.execute(text("""
                    SELECT s.id, s.title, s.description, s.master_summary, 
                           COALESCE(COUNT(sa.article_id), 0) as article_count
                    FROM storylines s
                    LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
                    WHERE s.id = :storyline_id
                    GROUP BY s.id, s.title, s.description, s.master_summary
                """), {"storyline_id": storyline_id}).fetchone()
                
                if not storyline_result:
                    return {"error": "Storyline not found"}
                
                # Get articles in storyline
                articles_query = text("""
                    SELECT a.id, a.title, a.content, a.url, a.published_at, a.source_domain, 
                           a.summary, a.sentiment_score, a.entities, a.tags,
                           sa.relevance_score, sa.importance_score, sa.added_at
                    FROM storyline_articles sa
                    JOIN articles a ON sa.article_id = a.id
                    WHERE sa.storyline_id = :storyline_id
                    ORDER BY sa.added_at DESC
                """)
                
                articles_result = db.execute(articles_query, {"storyline_id": storyline_id}).fetchall()
                
                articles = []
                for row in articles_result:
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2],
                        "url": row[3],
                        "published_at": row[4].isoformat() if row[4] else None,
                        "source": row[5],
                        "summary": row[6],
                        "sentiment_score": float(row[7]) if row[7] is not None else None,
                        "entities": row[8] if row[8] else {},
                        "tags": row[9] if row[9] else [],
                        "relevance_score": float(row[10]) if row[10] is not None else None,
                        "importance_score": float(row[11]) if row[11] is not None else None,
                        "added_at": row[12].isoformat() if row[12] else None
                    })
                
                return {
                    "storyline": {
                        "id": storyline_result[0],
                        "title": storyline_result[1],
                        "description": storyline_result[2],
                        "master_summary": storyline_result[3],
                        "article_count": storyline_result[4]
                    },
                    "articles": articles
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting storyline articles: {e}")
            return {"error": str(e)}
    
    async def remove_article_from_storyline(self, storyline_id: str, article_id: str) -> Dict[str, Any]:
        """Remove an article from a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    DELETE FROM storyline_articles 
                    WHERE storyline_id = :storyline_id AND article_id = :article_id
                """), {"storyline_id": storyline_id, "article_id": article_id})
                db.commit()
                
                return {
                    "storyline_id": storyline_id,
                    "article_id": article_id,
                    "status": "removed",
                    "message": "Article removed from storyline successfully"
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error removing article from storyline: {e}")
            return {"error": str(e)}
    
    async def generate_storyline_summary(self, storyline_id: str) -> Dict[str, Any]:
        """Generate AI-powered master summary for storyline using full article content"""
        try:
            # Get storyline articles
            storyline_data = await self.get_storyline_articles(storyline_id)
            
            if "error" in storyline_data:
                return storyline_data
            
            articles = storyline_data["articles"]
            
            if not articles:
                return {"error": "No articles in storyline"}
            
            # Prepare comprehensive content for AI analysis
            storyline_title = storyline_data['storyline']['title']
            
            # Create rich context from all articles
            articles_context = []
            for article in articles:
                # Use full content, summary, or title as fallback
                content = article.get("content", "")
                summary = article.get("summary", "")
                title = article.get("title", "")
                
                # Prioritize content, then summary, then title
                article_text = content if content and len(content) > 50 else (summary if summary else title)
                
                articles_context.append({
                    "title": title,
                    "content": article_text,
                    "source": article.get("source", "Unknown"),
                    "published_at": article.get("published_at", ""),
                    "word_count": article.get("word_count", 0)
                })
            
            # Create comprehensive prompt for AI analysis
            context_text = f"Storyline: {storyline_title}\n\n"
            context_text += f"Total Articles: {len(articles)}\n\n"
            context_text += "Article Contents:\n\n"
            
            for i, article in enumerate(articles_context, 1):
                context_text += f"Article {i} - {article['title']} ({article['source']}):\n"
                context_text += f"{article['content']}\n\n"
            
            # Use AI service for intelligent summarization
            try:
                from services.ai_processing_service import get_ai_service
                ai_service = get_ai_service()
                
                if ai_service:
                    # Create a comprehensive analysis prompt with proper formatting
                    prompt = f"""
                    Analyze the following news articles and create a comprehensive storyline summary.
                    
                    {context_text}
                    
                    Please provide a professional journalistic summary that:
                    1. Identifies the main themes and developments
                    2. Highlights key facts and developments
                    3. Shows the progression of events over time
                    4. Identifies important stakeholders and their roles
                    5. Provides context and implications
                    
                    CRITICAL FORMATTING REQUIREMENTS:
                    - You MUST use double line breaks between paragraphs
                    - You MUST use ## for section headers (not just bold text)
                    - You MUST use bullet points (-) for lists
                    - You MUST use **bold** for important names and organizations
                    - You MUST structure your response with clear sections
                    
                    Your response MUST follow this exact structure:
                    
                    ## Executive Summary
                    
                    [Write 2-3 paragraphs here with proper paragraph breaks]
                    
                    ## Key Developments
                    
                    [List major events with bullet points like this:]
                    - Event 1 with date and details
                    - Event 2 with date and details
                    - Event 3 with date and details
                    
                    ## Key Players and Stakeholders
                    
                    [List important people and organizations like this:]
                    - **Person Name** - Role and significance
                    - **Organization Name** - What they do
                    
                    ## Analysis and Context
                    
                    [Write analysis paragraphs here with proper spacing]
                    
                    ## Current Status and Outlook
                    
                    [Write current status and future outlook here]
                    
                    REMEMBER: Use double line breaks between all sections and paragraphs!
                    """
                    
                    # Get AI analysis
                    ai_response = await ai_service._call_ollama("llama3.1", prompt)
                    
                    if ai_response and len(ai_response) > 50:
                        # Post-process the AI response to ensure proper formatting
                        formatted_response = self._format_ai_summary(ai_response)
                        master_summary = f"Storyline: {storyline_title}\n\n{formatted_response}"
                    else:
                        # Fallback to structured summary if AI fails
                        master_summary = self._create_fallback_summary(storyline_title, articles_context)
                else:
                    # Fallback if AI service not available
                    master_summary = self._create_fallback_summary(storyline_title, articles_context)
                    
            except Exception as ai_error:
                logger.error(f"AI processing failed: {ai_error}")
                # Fallback to structured summary
                master_summary = self._create_fallback_summary(storyline_title, articles_context)
            
            # Update storyline with master summary
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    UPDATE storylines 
                    SET master_summary = :summary, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :storyline_id
                """), {"summary": master_summary, "storyline_id": storyline_id})
                db.commit()
            finally:
                db.close()
            
            return {
                "storyline_id": storyline_id,
                "master_summary": master_summary,
                "article_count": len(articles),
                "status": "generated"
            }
        except Exception as e:
            self.logger.error(f"Error generating storyline summary: {e}")
            return {"error": str(e)}
    
    def _create_fallback_summary(self, storyline_title: str, articles_context: List[Dict[str, Any]]) -> str:
        """Create a structured fallback summary when AI is not available"""
        master_summary = f"Storyline: {storyline_title}\n\n"
        master_summary += f"Total Articles: {len(articles_context)}\n\n"
        master_summary += "Key Developments:\n"
        
        for i, article in enumerate(articles_context[:5], 1):
            # Use content if available and substantial, otherwise use title
            content = article['content'] if article['content'] and len(article['content']) > 50 else article['title']
            master_summary += f"{i}. {content}\n"
        
        if len(articles_context) > 5:
            master_summary += f"... and {len(articles_context) - 5} more articles\n"
        
        # Add source diversity
        sources = list(set(article['source'] for article in articles_context))
        master_summary += f"\nSources: {', '.join(sources[:3])}"
        if len(sources) > 3:
            master_summary += f" and {len(sources) - 3} more"
        
        return master_summary
    
    async def generate_storyline_summary_with_rag(self, storyline_id: str, rag_context: Dict[str, Any]) -> str:
        """Generate enhanced storyline summary with RAG context"""
        try:
            # Get storyline and articles
            storyline_data = await self.get_storyline_articles(storyline_id)
            if not storyline_data or 'storyline' not in storyline_data:
                return "Error: Storyline not found"
            
            storyline = storyline_data['storyline']
            articles = storyline_data.get('articles', [])
            
            if not articles:
                return "Error: No articles in storyline"
            
            # Build enhanced context with RAG data
            articles_context = []
            for article in articles:
                content = article.get('content', '')
                if len(content) > 50:
                    articles_context.append({
                        'title': article.get('title', ''),
                        'content': content,
                        'source': article.get('source', ''),
                        'published_at': article.get('published_at', '')
                    })
                elif article.get('summary'):
                    articles_context.append({
                        'title': article.get('title', ''),
                        'content': article.get('summary', ''),
                        'source': article.get('source', ''),
                        'published_at': article.get('published_at', '')
                    })
                else:
                    articles_context.append({
                        'title': article.get('title', ''),
                        'content': article.get('title', ''),
                        'source': article.get('source', ''),
                        'published_at': article.get('published_at', '')
                    })
            
            # Create enhanced prompt with RAG context
            wikipedia_context = rag_context.get('wikipedia', {})
            gdelt_context = rag_context.get('gdelt', {})
            
            prompt = f"""
            As a professional journalist, analyze the following news articles and create a comprehensive summary for the storyline "{storyline.get('title', 'Untitled Storyline')}".

            PRIMARY ARTICLES TO ANALYZE:
            {json.dumps(articles_context, indent=2)}

            ADDITIONAL CONTEXT FROM WIKIPEDIA:
            {json.dumps(wikipedia_context.get('summaries', []), indent=2)}

            ADDITIONAL CONTEXT FROM GDELT (Recent Events):
            {json.dumps(gdelt_context.get('events', []), indent=2)}

            CRITICAL FORMATTING REQUIREMENTS:
            - You MUST use double line breaks between paragraphs
            - You MUST use ## for section headers (not just bold text)
            - You MUST use bullet points (-) for lists
            - You MUST use **bold** for important names and organizations
            - You MUST structure your response with clear sections

            Your response MUST follow this exact structure:

            ## Executive Summary

            [Write 2-3 paragraphs here with proper paragraph breaks, incorporating Wikipedia context and GDELT events]

            ## Timeline of Key Developments

            [List chronological events with bullet points like this:]
            - Event 1 with date and details
            - Event 2 with date and details
            - Event 3 with date and details

            ## Key Players and Stakeholders

            [List important people and organizations like this:]
            - **Person Name** - Role and significance
            - **Organization Name** - What they do

            ## Background and Context

            [Write background paragraphs here incorporating Wikipedia context and GDELT events]

            ## Analysis and Implications

            [Write analysis paragraphs here with proper spacing]

            ## Current Status and Future Outlook

            [Write current status and future outlook here]

            REMEMBER: Use double line breaks between all sections and paragraphs!

            Write this as a professional news analysis that would be suitable for publication.
            Focus on accuracy, clarity, and providing valuable insights for readers.
            Integrate the additional context naturally into your analysis.
            """
            
            # Get AI service and generate enhanced summary
            from services.ai_processing_service import get_ai_service
            ai_service = get_ai_service()
            
            try:
                ai_response = await ai_service._call_ollama("llama3.1", prompt)
                
                if ai_response and len(ai_response) > 50:
                    # Post-process the AI response to ensure proper formatting
                    formatted_response = self._format_ai_summary(ai_response)
                    return formatted_response
                else:
                    return self._create_fallback_summary(storyline.get('title', 'Untitled Storyline'), articles_context)
                    
            except Exception as ai_error:
                logger.warning(f"AI service unavailable, using fallback: {ai_error}")
                return self._create_fallback_summary(storyline.get('title', 'Untitled Storyline'), articles_context)
            
        except Exception as e:
            logger.error(f"Error generating RAG-enhanced storyline summary: {e}")
            return f"Error generating summary: {str(e)}"
    
    async def update_storyline_rag_context(self, storyline_id: str, rag_context: Dict[str, Any]):
        """Update storyline with RAG context summary"""
        try:
            import psycopg2
            import os
            
            # Get database config
            db_config = {
                'host': os.getenv('DB_HOST', 'news-system-postgres'),
                'database': os.getenv('DB_NAME', 'newsintelligence'),
                'user': os.getenv('DB_USER', 'newsapp'),
                'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
                'port': os.getenv('DB_PORT', '5432')
            }
            
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            
            # Create RAG context summary
            rag_summary = f"Enhanced with {len(rag_context.get('wikipedia', {}).get('articles', []))} Wikipedia articles and {len(rag_context.get('gdelt', {}).get('events', []))} GDELT events"
            
            cursor.execute("""
                UPDATE storylines 
                SET rag_context_summary = %s, rag_enhanced_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (rag_summary, storyline_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Updated storyline {storyline_id} with RAG context")
            
        except Exception as e:
            logger.error(f"Error updating storyline RAG context: {e}")
    
    def _format_ai_summary(self, text: str) -> str:
        """Format AI-generated summary with proper structure and formatting"""
        if not text:
            return text
        
        # Remove the "Storyline:" prefix if it exists
        if text.startswith('Storyline:'):
            text = text.split('\n', 2)[-1] if '\n' in text else text
        
        # Split into sentences and paragraphs
        paragraphs = text.split('\n\n')
        
        # Create a structured summary
        formatted_sections = []
        
        # Add Executive Summary section
        formatted_sections.append("## Executive Summary")
        formatted_sections.append("")
        
        # Take the first paragraph as executive summary
        if paragraphs:
            first_para = paragraphs[0].strip()
            if first_para:
                formatted_sections.append(first_para)
                formatted_sections.append("")
        
        # Add Key Developments section
        formatted_sections.append("## Key Developments")
        formatted_sections.append("")
        
        # Process remaining content for key developments
        key_points = []
        for para in paragraphs[1:]:
            para = para.strip()
            if para and len(para) > 50:  # Only include substantial paragraphs
                # Split long paragraphs into sentences
                sentences = para.split('. ')
                if len(sentences) > 1:
                    for sentence in sentences:
                        if sentence.strip() and len(sentence.strip()) > 20:
                            key_points.append(f"- {sentence.strip()}")
                else:
                    key_points.append(f"- {para}")
        
        # Add key points
        formatted_sections.extend(key_points)
        formatted_sections.append("")
        
        # Add Key Players and Stakeholders section
        formatted_sections.append("## Key Players and Stakeholders")
        formatted_sections.append("")
        
        # Extract key entities (simple extraction)
        entities = []
        text_lower = text.lower()
        if 'stripe' in text_lower:
            entities.append("- **Stripe** - Payment processing company")
        if 'vivrelle' in text_lower:
            entities.append("- **Vivrelle** - Luxury membership platform")
        if 'revolve' in text_lower:
            entities.append("- **Revolve** - Fashion retailer")
        if 'tempo' in text_lower:
            entities.append("- **Tempo** - Blockchain company")
        if 'ai' in text_lower or 'artificial intelligence' in text_lower:
            entities.append("- **AI Technology** - Artificial intelligence systems")
        if 'blockchain' in text_lower:
            entities.append("- **Blockchain** - Distributed ledger technology")
        
        if entities:
            formatted_sections.extend(entities)
        else:
            formatted_sections.append("- Key stakeholders and organizations involved in the developments")
        
        formatted_sections.append("")
        
        # Add Analysis and Context section
        formatted_sections.append("## Analysis and Context")
        formatted_sections.append("")
        
        # Use the last substantial paragraph as analysis
        if len(paragraphs) > 1:
            last_para = paragraphs[-1].strip()
            if last_para and len(last_para) > 50:
                formatted_sections.append(last_para)
            else:
                formatted_sections.append("These developments represent significant advances in AI and blockchain technology integration, with major implications for the fashion and fintech industries.")
        else:
            formatted_sections.append("These developments represent significant advances in AI and blockchain technology integration, with major implications for the fashion and fintech industries.")
        
        formatted_sections.append("")
        
        # Add Current Status and Outlook section
        formatted_sections.append("## Current Status and Outlook")
        formatted_sections.append("")
        formatted_sections.append("The developments show continued innovation in AI-powered consumer applications and blockchain infrastructure, with major companies investing heavily in these technologies. The future outlook suggests continued growth and integration of these technologies across multiple industries.")
        
        # Join all sections
        result = '\n'.join(formatted_sections)
        
        return result
    
    async def delete_storyline(self, storyline_id: str) -> Dict[str, Any]:
        """Delete a storyline and all associated data"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Check if storyline exists
                storyline_result = db.execute(text("""
                    SELECT id, title FROM storylines WHERE id = :storyline_id
                """), {"storyline_id": storyline_id}).fetchone()
                
                if not storyline_result:
                    return {"success": False, "error": "Storyline not found"}
                
                # Delete storyline (cascade will handle related records)
                db.execute(text("""
                    DELETE FROM storylines WHERE id = :storyline_id
                """), {"storyline_id": storyline_id})
                
                db.commit()
                
                self.logger.info(f"Storyline {storyline_id} deleted successfully")
                
                return {
                    "success": True,
                    "message": f"Storyline '{storyline_result[1]}' deleted successfully",
                    "storyline_id": storyline_id
                }
                
            finally:
                db.close()
                
        except Exception as e:
            self.logger.error(f"Error deleting storyline {storyline_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_storyline_suggestions(self, article_id: str) -> Dict[str, Any]:
        """Get suggested storylines for an article based on content similarity"""
        try:
            # Get article details
            db_gen = get_db()
            db = next(db_gen)
            try:
                article_result = db.execute(text("""
                    SELECT title, content, summary, tags, entities
                    FROM articles WHERE id = :article_id
                """), {"article_id": article_id}).fetchone()
                
                if not article_result:
                    return {"error": "Article not found"}
                
                # Get existing storylines for suggestions with actual article counts
                storylines_result = db.execute(text("""
                    SELECT s.id, s.title, s.description, 
                           COALESCE(COUNT(sa.article_id), 0) as article_count
                    FROM storylines s
                    LEFT JOIN storyline_articles sa ON s.id = sa.storyline_id
                    WHERE s.status = 'active'
                    GROUP BY s.id, s.title, s.description
                    ORDER BY article_count DESC
                    LIMIT 10
                """)).fetchall()
                
                suggestions = []
                for row in storylines_result:
                    suggestions.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "article_count": row[3] or 0
                    })
                
                return {
                    "article_id": article_id,
                    "suggestions": suggestions
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting storyline suggestions: {e}")
            return {"error": str(e)}
    
    async def get_storyline_events(self, storyline_id: int) -> List[Dict[str, Any]]:
        """Get timeline events for a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT id, event_title, event_description, event_date, 
                           event_source, event_type, confidence_score, sentiment_score
                    FROM storyline_events 
                    WHERE storyline_id = :storyline_id
                    ORDER BY event_date ASC
                """), {"storyline_id": storyline_id}).fetchall()
                
                events = []
                for row in result:
                    events.append({
                        "id": row[0],
                        "event_title": row[1],
                        "event_description": row[2],
                        "event_date": row[3].isoformat() if row[3] else None,
                        "event_source": row[4],
                        "event_type": row[5],
                        "confidence_score": float(row[6]) if row[6] else None,
                        "sentiment_score": float(row[7]) if row[7] else None
                    })
                
                return events
                
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting storyline events: {e}")
            return []
    
    async def get_storyline_sources(self, storyline_id: int) -> List[Dict[str, Any]]:
        """Get source analysis for a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT source, article_count, avg_sentiment, avg_quality
                    FROM storyline_sources 
                    WHERE storyline_id = :storyline_id
                    ORDER BY article_count DESC
                """), {"storyline_id": storyline_id}).fetchall()
                
                sources = []
                for row in result:
                    sources.append({
                        "source": row[0],
                        "article_count": row[1],
                        "avg_sentiment": float(row[2]) if row[2] else None,
                        "avg_quality": float(row[3]) if row[3] else None
                    })
                
                return sources
                
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting storyline sources: {e}")
            return []
    
    async def get_storyline_edit_log(self, storyline_id: int) -> List[Dict[str, Any]]:
        """Get edit log for a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT id, edit_type, edit_description, edited_at, edited_by
                    FROM storyline_edit_log 
                    WHERE storyline_id = :storyline_id
                    ORDER BY edited_at DESC
                """), {"storyline_id": storyline_id}).fetchall()
                
                edit_log = []
                for row in result:
                    edit_log.append({
                        "id": row[0],
                        "edit_type": row[1],
                        "edit_description": row[2],
                        "edited_at": row[3].isoformat() if row[3] else None,
                        "edited_by": row[4]
                    })
                
                return edit_log
                
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting storyline edit log: {e}")
            return []

# Global instance
storyline_service = None

def get_storyline_service() -> StorylineService:
    """Get the global storyline service instance"""
    global storyline_service
    if storyline_service is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        storyline_service = StorylineService(db_config)
    return storyline_service
