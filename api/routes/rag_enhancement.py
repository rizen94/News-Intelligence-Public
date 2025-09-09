"""
News Intelligence System v3.1.0 - RAG Enhancement API
RAG context enhancement for storylines
"""

from fastapi import APIRouter, HTTPException, Path, BackgroundTasks
from typing import Dict, Any, Optional
import logging
from services.rag_service import get_rag_service
from services.storyline_service import get_storyline_service
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/storylines/{storyline_id}/enhance")
async def enhance_storyline_with_rag(
    storyline_id: str = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None
):
    """Enhance storyline with RAG context from Wikipedia and GDELT"""
    try:
        logger.info(f"Enhancing storyline {storyline_id} with RAG context")
        
        # Get storyline service
        storyline_service = get_storyline_service()
        
        # Get storyline details
        storyline_data = await storyline_service.get_storyline_articles(storyline_id)
        if not storyline_data or 'storyline' not in storyline_data:
            raise HTTPException(status_code=404, detail="Storyline not found")
        
        storyline = storyline_data['storyline']
        articles = storyline_data.get('articles', [])
        
        if not articles:
            raise HTTPException(status_code=400, detail="No articles in storyline to enhance")
        
        # Get RAG service
        rag_service = get_rag_service()
        
        # Enhance storyline with RAG context
        rag_context = await rag_service.enhance_storyline_context(
            storyline_id=storyline_id,
            storyline_title=storyline.get('title', 'Untitled Storyline'),
            articles=articles
        )
        
        # Update storyline with RAG context summary
        await storyline_service.update_storyline_rag_context(
            storyline_id=storyline_id,
            rag_context=rag_context
        )
        
        return {
            "success": True,
            "message": "Storyline enhanced with RAG context",
            "data": {
                "storyline_id": storyline_id,
                "rag_context": rag_context,
                "enhanced_at": rag_context.get('enhanced_at')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enhancing storyline with RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enhance storyline: {str(e)}")

@router.get("/storylines/{storyline_id}/rag-context")
async def get_storyline_rag_context(
    storyline_id: str = Path(..., description="Storyline ID")
):
    """Get RAG context for a storyline"""
    try:
        rag_service = get_rag_service()
        rag_context = await rag_service.get_rag_context(storyline_id)
        
        if not rag_context:
            raise HTTPException(status_code=404, detail="No RAG context found for storyline")
        
        return {
            "success": True,
            "data": rag_context
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting RAG context: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get RAG context: {str(e)}")

@router.post("/storylines/{storyline_id}/regenerate-with-rag")
async def regenerate_storyline_summary_with_rag(
    storyline_id: str = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None
):
    """Regenerate storyline summary with RAG context"""
    try:
        logger.info(f"Regenerating storyline {storyline_id} summary with RAG context")
        
        # Get storyline service
        storyline_service = get_storyline_service()
        
        # Get RAG context
        rag_service = get_rag_service()
        rag_context = await rag_service.get_rag_context(storyline_id)
        
        if not rag_context:
            # First enhance with RAG context
            storyline_data = await storyline_service.get_storyline_articles(storyline_id)
            if not storyline_data or 'storyline' not in storyline_data:
                raise HTTPException(status_code=404, detail="Storyline not found")
            
            storyline = storyline_data['storyline']
            articles = storyline_data.get('articles', [])
            
            rag_context = await rag_service.enhance_storyline_context(
                storyline_id=storyline_id,
                storyline_title=storyline.get('title', 'Untitled Storyline'),
                articles=articles
            )
        
        # Generate enhanced summary with RAG context
        enhanced_summary = await storyline_service.generate_storyline_summary_with_rag(
            storyline_id=storyline_id,
            rag_context=rag_context
        )
        
        return {
            "success": True,
            "message": "Storyline summary regenerated with RAG context",
            "data": {
                "storyline_id": storyline_id,
                "enhanced_summary": enhanced_summary,
                "rag_context_used": rag_context is not None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating storyline summary with RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to regenerate summary: {str(e)}")

@router.get("/rag-status")
async def get_rag_status():
    """Get RAG system status"""
    try:
        rag_service = get_rag_service()
        
        # Test Wikipedia API
        wikipedia_status = "unknown"
        try:
            response = rag_service.session.get(
                f"{rag_service.wikipedia_api_url}/page/summary/Test",
                timeout=5
            )
            wikipedia_status = "online" if response.status_code == 200 else "offline"
        except:
            wikipedia_status = "offline"
        
        # Test GDELT API
        gdelt_status = "unknown"
        try:
            response = rag_service.session.get(
                f"{rag_service.gdelt_api_url}/doc/doc",
                params={"query": "test", "format": "json", "maxrecords": 1},
                timeout=10
            )
            gdelt_status = "online" if response.status_code == 200 else "offline"
        except:
            gdelt_status = "offline"
        
        return {
            "success": True,
            "data": {
                "wikipedia_api": wikipedia_status,
                "gdelt_api": gdelt_status,
                "rag_service": "online"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting RAG status: {e}")
        return {
            "success": False,
            "data": {
                "wikipedia_api": "error",
                "gdelt_api": "error",
                "rag_service": "error",
                "error": str(e)
            }
        }
