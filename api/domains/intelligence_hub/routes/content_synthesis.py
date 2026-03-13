"""
Deep Content Synthesis API Routes
Provides endpoints for creating comprehensive, Wikipedia-style synthesized content.
"""

from fastapi import APIRouter, HTTPException, Path, Query, Body, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import threading

from services.deep_content_synthesis import (
    get_synthesis_service,
    SynthesizedArticle
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Content Synthesis"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SynthesisRequest(BaseModel):
    """Request model for content synthesis"""
    depth: str = Field("comprehensive", description="Synthesis depth: brief, standard, comprehensive")
    include_terms: bool = Field(True, description="Include key term explanations")
    include_timeline: bool = Field(True, description="Include event timeline")
    format: str = Field("json", description="Output format: json, markdown")


class TopicSynthesisRequest(BaseModel):
    """Request for topic-based synthesis"""
    topic: str = Field(..., min_length=3, max_length=200)
    hours: int = Field(168, ge=24, le=720, description="Hours of content to analyze")
    depth: str = Field("comprehensive")
    format: str = Field("json")


class StorylineSynthesisResponse(BaseModel):
    """Response model for synthesized storyline"""
    success: bool
    title: str
    summary: str
    sections: List[Dict[str, Any]]
    word_count: int
    source_count: int
    quality_score: float
    key_entities: List[str]
    key_terms: Dict[str, str]
    timeline: List[Dict[str, Any]]
    created_at: str
    markdown: Optional[str] = None


# =============================================================================
# STORYLINE SYNTHESIS
# =============================================================================

@router.post("/{domain}/synthesis/storyline/{storyline_id}", response_model=Dict[str, Any])
async def synthesize_storyline(
    storyline_id: int = Path(..., gt=0),
    request: SynthesisRequest = Body(...),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """
    Create comprehensive, Wikipedia-style content for a storyline.
    
    This synthesizes all articles in the storyline into:
    - Background section with domain context
    - Current developments section
    - Key data and statistics
    - Reactions and perspectives
    - Analysis and implications
    - Glossary of key terms
    - Event timeline
    
    The output is suitable for publication as an informative article.
    """
    try:
        service = get_synthesis_service()
        
        synthesized = service.synthesize_storyline_content(
            domain=domain,
            storyline_id=storyline_id,
            depth=request.depth
        )
        
        response = {
            "success": True,
            "storyline_id": storyline_id,
            "domain": domain,
            **synthesized.to_dict()
        }
        
        if request.format == "markdown":
            response["markdown"] = synthesized.to_markdown()
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Storyline synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/synthesis/storyline/{storyline_id}/markdown")
async def get_storyline_markdown(
    storyline_id: int = Path(..., gt=0),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    depth: str = Query("comprehensive"),
    regenerate: bool = Query(False, description="Force regeneration even if cached")
):
    """
    Get storyline synthesis as markdown document.
    """
    try:
        service = get_synthesis_service()
        
        # Try to get cached version first
        if not regenerate:
            saved = service.get_saved_synthesis(domain, storyline_id)
            if saved and saved.get('synthesized_markdown'):
                return {
                    "success": True,
                    "storyline_id": storyline_id,
                    "title": saved.get('title', ''),
                    "markdown": saved['synthesized_markdown'],
                    "word_count": saved.get('synthesis_word_count', 0),
                    "cached": True,
                    "synthesized_at": str(saved.get('synthesized_at', ''))
                }
        
        # Generate fresh synthesis
        synthesized = service.synthesize_storyline_content(
            domain=domain,
            storyline_id=storyline_id,
            depth=depth,
            save_to_db=True
        )
        
        return {
            "success": True,
            "storyline_id": storyline_id,
            "title": synthesized.title,
            "markdown": synthesized.to_markdown(),
            "word_count": synthesized.word_count,
            "source_count": synthesized.total_sources,
            "cached": False
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Markdown synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/synthesis/storyline/{storyline_id}/cached", response_model=Dict[str, Any])
async def get_cached_synthesis(
    storyline_id: int = Path(..., gt=0),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """
    Get cached synthesized content if available.
    Returns the full saved content without regenerating.
    """
    try:
        service = get_synthesis_service()
        saved = service.get_saved_synthesis(domain, storyline_id)
        
        if not saved or not saved.get('synthesized_content'):
            return {
                "success": True,
                "has_synthesis": False,
                "storyline_id": storyline_id,
                "message": "No cached synthesis available. Use POST to generate."
            }
        
        return {
            "success": True,
            "has_synthesis": True,
            "storyline_id": storyline_id,
            "title": saved.get('title', ''),
            "content": saved['synthesized_content'],
            "markdown": saved.get('synthesized_markdown', ''),
            "word_count": saved.get('synthesis_word_count', 0),
            "quality_score": saved.get('synthesis_quality_score', 0),
            "synthesized_at": str(saved.get('synthesized_at', ''))
        }
        
    except Exception as e:
        logger.error(f"Get cached synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TOPIC SYNTHESIS
# =============================================================================

@router.post("/{domain}/synthesis/topic", response_model=Dict[str, Any])
async def synthesize_topic(
    request: TopicSynthesisRequest,
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """
    Create comprehensive, Wikipedia-style content about a topic.
    
    Searches for articles matching the topic and synthesizes them into
    a comprehensive, educational article with:
    - Full context and background
    - Key developments and facts
    - Multiple perspectives
    - Data and statistics
    - Expert analysis
    - Glossary and timeline
    """
    try:
        service = get_synthesis_service()
        
        synthesized = service.synthesize_topic_content(
            domain=domain,
            topic_name=request.topic,
            hours=request.hours,
            depth=request.depth
        )
        
        response = {
            "success": True,
            "topic": request.topic,
            "domain": domain,
            **synthesized.to_dict()
        }
        
        if request.format == "markdown":
            response["markdown"] = synthesized.to_markdown()
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Topic synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/synthesis/topic/{topic_name}")
async def get_topic_synthesis(
    topic_name: str = Path(..., min_length=3),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(168, ge=24, le=720),
    depth: str = Query("standard"),
    format: str = Query("json")
):
    """
    Quick topic synthesis via GET request.
    """
    try:
        service = get_synthesis_service()
        
        synthesized = service.synthesize_topic_content(
            domain=domain,
            topic_name=topic_name,
            hours=hours,
            depth=depth
        )
        
        response = {
            "success": True,
            "topic": topic_name,
            "domain": domain,
            **synthesized.to_dict()
        }
        
        if format == "markdown":
            response["markdown"] = synthesized.to_markdown()
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Topic synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# BREAKING NEWS SYNTHESIS
# =============================================================================

@router.get("/{domain}/synthesis/breaking", response_model=Dict[str, Any])
async def synthesize_breaking_news(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(24, ge=1, le=72),
    min_articles: int = Query(3, ge=2, le=10),
    format: str = Query("json")
):
    """
    Synthesize comprehensive articles for breaking/trending stories.
    
    Automatically identifies clusters of related articles and creates
    comprehensive synthesized content for each breaking story.
    """
    try:
        service = get_synthesis_service()
        
        synthesized_list = service.synthesize_breaking_news(
            domain=domain,
            hours=hours,
            min_articles=min_articles
        )
        
        results = []
        for article in synthesized_list:
            result = article.to_dict()
            if format == "markdown":
                result["markdown"] = article.to_markdown()
            results.append(result)
        
        return {
            "success": True,
            "domain": domain,
            "hours": hours,
            "breaking_stories": len(results),
            "stories": results
        }
        
    except Exception as e:
        logger.error(f"Breaking news synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# BULK SYNTHESIS (Background processing)
# =============================================================================

# Store for background synthesis tasks
synthesis_tasks: Dict[str, Dict[str, Any]] = {}


@router.post("/{domain}/synthesis/storylines/bulk", response_model=Dict[str, Any])
async def bulk_synthesize_storylines(
    storyline_ids: List[int] = Body(..., min_items=1, max_items=20),
    depth: str = Body("standard"),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    background_tasks: BackgroundTasks = None
):
    """
    Synthesize multiple storylines in background.
    
    Returns a task ID to check progress.
    """
    task_id = f"{domain}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    synthesis_tasks[task_id] = {
        "status": "running",
        "domain": domain,
        "total": len(storyline_ids),
        "completed": 0,
        "results": [],
        "errors": [],
        "started_at": datetime.now().isoformat()
    }
    
    def process_bulk():
        service = get_synthesis_service()
        
        for storyline_id in storyline_ids:
            try:
                synthesized = service.synthesize_storyline_content(
                    domain=domain,
                    storyline_id=storyline_id,
                    depth=depth
                )
                synthesis_tasks[task_id]["results"].append({
                    "storyline_id": storyline_id,
                    "title": synthesized.title,
                    "word_count": synthesized.word_count,
                    "quality_score": synthesized.quality_score
                })
            except Exception as e:
                synthesis_tasks[task_id]["errors"].append({
                    "storyline_id": storyline_id,
                    "error": str(e)
                })
            
            synthesis_tasks[task_id]["completed"] += 1
        
        synthesis_tasks[task_id]["status"] = "completed"
        synthesis_tasks[task_id]["completed_at"] = datetime.now().isoformat()
    
    # Run in background thread
    thread = threading.Thread(target=process_bulk, daemon=True)
    thread.start()
    
    return {
        "success": True,
        "task_id": task_id,
        "message": f"Synthesizing {len(storyline_ids)} storylines in background",
        "check_status": f"/api/{domain}/synthesis/tasks/{task_id}"
    }


@router.get("/{domain}/synthesis/tasks/{task_id}", response_model=Dict[str, Any])
async def get_synthesis_task_status(
    task_id: str = Path(...),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """
    Check status of a bulk synthesis task.
    """
    if task_id not in synthesis_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "success": True,
        "task_id": task_id,
        **synthesis_tasks[task_id]
    }


# =============================================================================
# SYNTHESIS QUALITY CHECK
# =============================================================================

@router.get("/{domain}/synthesis/quality/{storyline_id}", response_model=Dict[str, Any])
async def check_synthesis_quality(
    storyline_id: int = Path(..., gt=0),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$")
):
    """
    Analyze storyline and suggest improvements for synthesis quality.
    """
    try:
        service = get_synthesis_service()
        
        # Get basic info
        schema = domain.replace('-', '_')
        storyline, articles = service._fetch_storyline_with_articles(schema, storyline_id)
        
        if not storyline:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        # Calculate quality metrics
        article_count = len(articles)
        total_content = sum([len(a.get('content', '') or '') for a in articles])
        avg_content_length = total_content // max(article_count, 1)
        
        sources = set([a.get('source_name', a.get('source_domain', '')) for a in articles])
        
        quality_factors = {
            "article_count": article_count,
            "article_count_score": min(article_count / 10, 1.0),
            "source_diversity": len(sources),
            "source_diversity_score": min(len(sources) / 5, 1.0),
            "avg_content_length": avg_content_length,
            "content_score": min(avg_content_length / 2000, 1.0),
            "has_sufficient_content": total_content > 5000,
        }
        
        overall_score = (
            quality_factors["article_count_score"] * 0.3 +
            quality_factors["source_diversity_score"] * 0.3 +
            quality_factors["content_score"] * 0.4
        )
        
        recommendations = []
        if article_count < 5:
            recommendations.append("Add more articles for a more comprehensive synthesis")
        if len(sources) < 3:
            recommendations.append("Include sources from different outlets for balance")
        if avg_content_length < 500:
            recommendations.append("Articles have limited content - synthesis may be shallow")
        if total_content < 3000:
            recommendations.append("Total content is low - consider waiting for more coverage")
        
        return {
            "success": True,
            "storyline_id": storyline_id,
            "title": storyline.get('title', ''),
            "quality_factors": quality_factors,
            "overall_score": round(overall_score, 2),
            "ready_for_synthesis": overall_score > 0.5 and total_content > 3000,
            "recommendations": recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quality check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SUPER-STORYLINE (MEGA) SYNTHESIS
# =============================================================================

@router.post("/{domain}/synthesis/mega/{mega_storyline_id}", response_model=Dict[str, Any])
async def synthesize_mega_storyline(
    mega_storyline_id: int = Path(..., gt=0),
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    request: SynthesisRequest = Body(...)
):
    """
    Create comprehensive synthesis for a mega-storyline (super-storyline).
    
    Combines all child storylines into an overarching narrative with:
    - Executive summary of the entire topic
    - Individual storyline summaries
    - Cross-storyline analysis
    - Comprehensive timeline
    - All key terms and entities
    """
    try:
        service = get_synthesis_service()
        schema = domain.replace('-', '_')
        
        # Fetch mega-storyline and its children
        conn = service.get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET search_path TO {schema}, public")
            
            # Get mega-storyline
            cur.execute("""
                SELECT * FROM storylines 
                WHERE id = %s AND is_mega_storyline = TRUE
            """, (mega_storyline_id,))
            mega = cur.fetchone()
            
            if not mega:
                conn.close()
                raise HTTPException(status_code=404, detail="Mega-storyline not found")
            
            # Get child storylines
            cur.execute("""
                SELECT * FROM storylines 
                WHERE parent_storyline_id = %s
                ORDER BY created_at DESC
            """, (mega_storyline_id,))
            children = cur.fetchall()
            
            conn.close()
        
        if not children:
            raise HTTPException(status_code=400, detail="No child storylines found")
        
        # Synthesize each child storyline
        child_syntheses = []
        all_facts = []
        all_entities = set()
        all_terms = {}
        all_sources = []
        
        for child in children:
            try:
                child_synth = service.synthesize_storyline_content(
                    domain=domain,
                    storyline_id=child['id'],
                    depth="standard"  # Use standard for children
                )
                child_syntheses.append({
                    "id": child['id'],
                    "title": child_synth.title,
                    "summary": child_synth.summary,
                    "word_count": child_synth.word_count,
                    "source_count": child_synth.total_sources
                })
                
                all_entities.update(child_synth.key_entities)
                all_terms.update(child_synth.key_terms_explained)
                all_sources.extend(child_synth.source_articles)
                
            except Exception as e:
                logger.warning(f"Failed to synthesize child {child['id']}: {e}")
        
        # Create mega-synthesis combining children
        mega_title = mega.get('title', 'Comprehensive Topic Analysis')
        
        # Generate executive summary
        children_summaries = "\n".join([
            f"- {c['title']}: {c['summary'][:200]}..."
            for c in child_syntheses[:10]
        ])
        
        from services.deep_content_synthesis import LLM_MODEL, OLLAMA_BASE_URL, LLM_TIMEOUT
        import requests
        
        exec_prompt = f"""Write a comprehensive executive summary for the mega-storyline: "{mega_title}"

This encompasses these sub-stories:
{children_summaries}

Write 3-4 paragraphs that:
1. Provide the big-picture overview of this topic
2. Explain how the sub-stories connect
3. Identify the main themes and developments
4. Discuss the broader implications

Write in encyclopedic, authoritative style."""

        exec_summary = ""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": exec_prompt, "stream": False},
                timeout=LLM_TIMEOUT
            )
            if response.status_code == 200:
                exec_summary = response.json().get('response', '').strip()
        except:
            exec_summary = f"This mega-storyline encompasses {len(child_syntheses)} related storylines covering various aspects of {mega_title}."
        
        # Calculate stats
        total_words = sum([c['word_count'] for c in child_syntheses])
        total_sources = len(set([s.get('url', '') for s in all_sources]))
        
        response = {
            "success": True,
            "mega_storyline_id": mega_storyline_id,
            "title": mega_title,
            "executive_summary": exec_summary,
            "child_storylines": child_syntheses,
            "child_count": len(child_syntheses),
            "total_word_count": total_words,
            "total_sources": total_sources,
            "key_entities": list(all_entities)[:30],
            "key_terms": all_terms,
            "domain": domain,
            "created_at": datetime.now().isoformat()
        }
        
        if request.format == "markdown":
            # Generate markdown
            md_lines = [
                f"# {mega_title}",
                "",
                "## Executive Summary",
                "",
                exec_summary,
                "",
                "## Storylines",
                ""
            ]
            for child in child_syntheses:
                md_lines.extend([
                    f"### {child['title']}",
                    "",
                    child['summary'],
                    "",
                    f"*{child['source_count']} sources, {child['word_count']} words*",
                    ""
                ])
            
            if all_terms:
                md_lines.extend(["## Key Terms", ""])
                for term, defn in list(all_terms.items())[:15]:
                    md_lines.append(f"**{term}**: {defn}")
                    md_lines.append("")
            
            response["markdown"] = "\n".join(md_lines)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mega synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

