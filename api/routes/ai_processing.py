"""
News Intelligence System v3.1.0 - AI Processing API
Local AI processing endpoints using Ollama for story analysis and reporting
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
import asyncio

from services.ai_processing_service import get_ai_service
from schemas.response_schemas import APIResponse

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models
class AIAnalysisRequest(BaseModel):
    story_id: str
    analysis_type: str = Field(default="comprehensive", pattern="^(comprehensive|sentiment|technical|summary)$")
    articles: Optional[List[Dict[str, Any]]] = None

class SentimentAnalysisRequest(BaseModel):
    text: str
    context: Optional[str] = None

class EntityExtractionRequest(BaseModel):
    text: str
    context: Optional[str] = None

class ReadabilityAnalysisRequest(BaseModel):
    text: str
    context: Optional[str] = None

class JournalisticReportRequest(BaseModel):
    story_id: str
    timeline_events: List[Dict[str, Any]]
    articles: List[Dict[str, Any]]
    report_style: str = Field(default="news", pattern="^(news|analysis|opinion|breaking)$")

class AIAnalysisResponse(BaseModel):
    success: bool = True
    analysis: Dict[str, Any]
    processing_time_ms: Optional[int] = None
    model_used: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    models_available: int
    models: List[str]
    base_url: str
    error: Optional[str] = None

# API Endpoints

@router.get("/health", response_model=APIResponse)
async def ai_health_check():
    """Check AI processing service health and available models"""
    try:
        ai_service = get_ai_service()
        health_status = await ai_service.check_ollama_health()
        
        return APIResponse(
            success=health_status['status'] == 'healthy',
            data={
                "status": health_status['status'],
                "models_available": health_status.get('models_available', 0),
                "models": health_status.get('models', []),
                "base_url": health_status.get('base_url', ''),
                "error": health_status.get('error')
            },
            message=f"AI service is {health_status['status']}"
        )
        
    except Exception as e:
        logger.error(f"Error checking AI health: {e}")
        return APIResponse(
            success=False,
            data={
                "status": "unhealthy",
                "models_available": 0,
                "models": [],
                "base_url": "",
                "error": str(e)
            },
            message="AI service health check failed"
        )

@router.post("/analyze/story", response_model=AIAnalysisResponse)
async def analyze_story(request: AIAnalysisRequest):
    """Analyze a story using local AI processing"""
    try:
        ai_service = get_ai_service()
        
        # Get articles if not provided
        articles = request.articles
        if not articles:
            articles = await _get_story_articles(request.story_id)
        
        # Generate analysis
        start_time = datetime.now()
        analysis = await ai_service.generate_story_analysis(
            request.story_id, 
            articles, 
            request.analysis_type
        )
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AIAnalysisResponse(
            success=True,
            analysis=analysis,
            processing_time_ms=int(processing_time),
            model_used=analysis.get('model_used')
        )
        
    except Exception as e:
        logger.error(f"Error analyzing story: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/sentiment", response_model=AIAnalysisResponse)
async def analyze_sentiment(request: SentimentAnalysisRequest):
    """Analyze sentiment of text using local AI"""
    try:
        ai_service = get_ai_service()
        
        start_time = datetime.now()
        sentiment_analysis = await ai_service.analyze_sentiment(request.text)
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AIAnalysisResponse(
            success=True,
            analysis=sentiment_analysis,
            processing_time_ms=int(processing_time),
            model_used="llama3.1:70b-instruct-q4_K_M"
        )
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract/entities", response_model=AIAnalysisResponse)
async def extract_entities(request: EntityExtractionRequest):
    """Extract entities from text using local AI"""
    try:
        ai_service = get_ai_service()
        
        start_time = datetime.now()
        entities = await ai_service.extract_entities(request.text)
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AIAnalysisResponse(
            success=True,
            analysis=entities,
            processing_time_ms=int(processing_time),
            model_used="llama3.1:70b-instruct-q4_K_M"
        )
        
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/readability", response_model=AIAnalysisResponse)
async def analyze_readability(request: ReadabilityAnalysisRequest):
    """Analyze text readability using local AI"""
    try:
        ai_service = get_ai_service()
        
        start_time = datetime.now()
        readability = await ai_service.analyze_readability(request.text)
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AIAnalysisResponse(
            success=True,
            analysis=readability,
            processing_time_ms=int(processing_time),
            model_used="llama3.1:70b-instruct-q4_K_M"
        )
        
    except Exception as e:
        logger.error(f"Error analyzing readability: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/report", response_model=AIAnalysisResponse)
async def generate_journalistic_report(request: JournalisticReportRequest):
    """Generate professional journalistic report using local AI"""
    try:
        ai_service = get_ai_service()
        
        start_time = datetime.now()
        report = await ai_service.generate_consolidated_report(
            request.story_id,
            request.timeline_events,
            request.articles
        )
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AIAnalysisResponse(
            success=True,
            analysis=report,
            processing_time_ms=int(processing_time),
            model_used="llama3.1:70b-instruct-q4_K_M"
        )
        
    except Exception as e:
        logger.error(f"Error generating journalistic report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/batch", response_model=Dict[str, Any])
async def process_batch_analysis(
    story_ids: List[str] = Query(..., description="List of story IDs to process"),
    analysis_types: List[str] = Query(default=["comprehensive"], description="Types of analysis to perform"),
    background_tasks: BackgroundTasks = None
):
    """Process multiple stories for AI analysis in background"""
    try:
        ai_service = get_ai_service()
        
        # Start background processing
        background_tasks.add_task(
            _process_batch_analysis_background,
            story_ids,
            analysis_types
        )
        
        return {
            "success": True,
            "message": f"Started processing {len(story_ids)} stories with {len(analysis_types)} analysis types",
            "story_ids": story_ids,
            "analysis_types": analysis_types,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models", response_model=Dict[str, Any])
async def get_available_models():
    """Get available AI models and their capabilities"""
    try:
        ai_service = get_ai_service()
        
        return {
            "success": True,
            "models": ai_service.available_models,
            "total_models": len(ai_service.available_models)
        }
        
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis/{story_id}", response_model=Dict[str, Any])
async def get_story_analysis(
    story_id: str,
    analysis_type: Optional[str] = Query(None, description="Filter by analysis type")
):
    """Get AI analysis results for a specific story"""
    try:
        # This would query the database for stored analysis results
        # For now, return a placeholder
        return {
            "success": True,
            "story_id": story_id,
            "analysis_type": analysis_type,
            "message": "Analysis retrieval not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error getting story analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions

async def _get_story_articles(story_id: str) -> List[Dict[str, Any]]:
    """Get articles for a story from database"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get story timeline ID
        cursor.execute("SELECT id FROM story_timelines WHERE story_id = %s", (story_id,))
        timeline_row = cursor.fetchone()
        
        if timeline_row:
            timeline_id = timeline_row['id']
            
            # Get articles related to this story
            cursor.execute("""
                SELECT a.* FROM articles a
                JOIN story_sources ss ON a.id = ss.article_id
                WHERE ss.story_timeline_id = %s
                ORDER BY a.published_at DESC
                LIMIT 10
            """, (timeline_id,))
            
            articles = []
            for row in cursor.fetchall():
                articles.append(dict(row))
            
            cursor.close()
            conn.close()
            
            return articles
        
        cursor.close()
        conn.close()
        return []
        
    except Exception as e:
        logger.error(f"Error getting story articles: {e}")
        return []

async def _process_batch_analysis_background(story_ids: List[str], analysis_types: List[str]):
    """Background task for batch processing"""
    try:
        ai_service = get_ai_service()
        
        for story_id in story_ids:
            for analysis_type in analysis_types:
                try:
                    # Get articles for the story
                    articles = await _get_story_articles(story_id)
                    
                    # Process analysis
                    await ai_service.generate_story_analysis(story_id, articles, analysis_type)
                    
                    logger.info(f"Completed {analysis_type} analysis for story {story_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing story {story_id} with analysis {analysis_type}: {e}")
        
        logger.info(f"Completed batch processing for {len(story_ids)} stories")
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
