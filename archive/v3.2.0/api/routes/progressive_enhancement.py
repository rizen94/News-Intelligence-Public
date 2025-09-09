"""
Progressive Enhancement API Routes
Handles automatic summary generation and progressive RAG enhancement
"""

from fastapi import APIRouter, HTTPException, Path, BackgroundTasks
from typing import Dict, Any, Optional
import logging
from services.progressive_enhancement_service import get_progressive_service
from services.api_usage_monitor import get_usage_monitor
from services.api_cache_service import get_cache_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/storylines/create-with-auto-summary")
async def create_storyline_with_auto_summary(
    storyline_data: Dict[str, Any],
    background_tasks: BackgroundTasks = None
):
    """Create storyline and automatically generate basic summary"""
    try:
        progressive_service = get_progressive_service()
        
        result = await progressive_service.create_storyline_with_auto_summary(storyline_data)
        
        if result.get('success'):
            return {
                "success": True,
                "data": result,
                "message": "Storyline created with automatic basic summary"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to create storyline'))
            
    except Exception as e:
        logger.error(f"Error creating storyline with auto summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storylines/{storyline_id}/generate-basic-summary")
async def generate_basic_summary(
    storyline_id: str = Path(..., description="Storyline ID"),
    background_tasks: BackgroundTasks = None
):
    """Generate basic summary for storyline"""
    try:
        progressive_service = get_progressive_service()
        
        result = await progressive_service.generate_basic_summary(storyline_id)
        
        if result.get('success'):
            return {
                "success": True,
                "data": result,
                "message": "Basic summary generated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to generate basic summary'))
            
    except Exception as e:
        logger.error(f"Error generating basic summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storylines/{storyline_id}/enhance-with-rag")
async def enhance_with_rag(
    storyline_id: str = Path(..., description="Storyline ID"),
    force: bool = False,
    background_tasks: BackgroundTasks = None
):
    """Enhance storyline summary with RAG context"""
    try:
        progressive_service = get_progressive_service()
        
        result = await progressive_service.enhance_with_rag(storyline_id, force)
        
        if result.get('success'):
            return {
                "success": True,
                "data": result,
                "message": "RAG enhancement completed successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to enhance with RAG'))
            
    except Exception as e:
        logger.error(f"Error enhancing with RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storylines/{storyline_id}/summary-history")
async def get_summary_history(
    storyline_id: str = Path(..., description="Storyline ID")
):
    """Get summary version history for storyline"""
    try:
        progressive_service = get_progressive_service()
        
        history = await progressive_service.get_summary_history(storyline_id)
        
        return {
            "success": True,
            "data": {
                "storyline_id": storyline_id,
                "summary_history": history,
                "total_versions": len(history)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting summary history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api-usage/stats")
async def get_api_usage_stats(
    service: Optional[str] = None,
    days: int = 7
):
    """Get API usage statistics"""
    try:
        usage_monitor = get_usage_monitor()
        
        stats = await usage_monitor.get_usage_stats(service, days)
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting API usage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api-usage/service/{service_name}/status")
async def get_service_status(
    service_name: str = Path(..., description="Service name")
):
    """Get current status of a specific service"""
    try:
        usage_monitor = get_usage_monitor()
        
        status = await usage_monitor.get_service_status(service_name)
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    try:
        cache_service = get_cache_service()
        
        stats = await cache_service.get_cache_stats()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/cleanup")
async def cleanup_cache():
    """Clean up expired cache entries"""
    try:
        cache_service = get_cache_service()
        
        cleared_count = await cache_service.clear_expired_cache()
        
        return {
            "success": True,
            "data": {
                "cleared_entries": cleared_count,
                "message": f"Cleared {cleared_count} expired cache entries"
            }
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


