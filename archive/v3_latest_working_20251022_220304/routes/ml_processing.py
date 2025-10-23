"""
ML Processing Control API
Handles starting/stopping ML processing and monitoring
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
from services.ml_processing_service import ml_processing_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/start/")
async def start_ml_processing():
    """Start ML processing service"""
    try:
        ml_processing_service.start_processing()
        return {
            "success": True,
            "message": "ML processing service started",
            "data": ml_processing_service.get_processing_status()
        }
    except Exception as e:
        logger.error(f"Error starting ML processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop/")
async def stop_ml_processing():
    """Stop ML processing service"""
    try:
        ml_processing_service.stop_processing()
        return {
            "success": True,
            "message": "ML processing service stopped",
            "data": ml_processing_service.get_processing_status()
        }
    except Exception as e:
        logger.error(f"Error stopping ML processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/")
async def get_ml_processing_status():
    """Get ML processing status"""
    try:
        return {
            "success": True,
            "message": "ML processing status retrieved",
            "data": ml_processing_service.get_processing_status()
        }
    except Exception as e:
        logger.error(f"Error getting ML processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/")
async def get_ml_processing_stats():
    """Get ML processing statistics"""
    try:
        return {
            "success": True,
            "message": "ML processing stats retrieved",
            "data": ml_processing_service.get_stats()
        }
    except Exception as e:
        logger.error(f"Error getting ML processing stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/")
async def health_check():
    """Health check for ML processing API"""
    return {
        "status": "healthy",
        "service": "ml_processing",
        "message": "ML Processing API is running"
    }
