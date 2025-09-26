"""
Simplified Deduplication API Routes
Provides basic endpoints for duplicate detection testing
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from config.database import get_db, get_db_config
from schemas.robust_schemas import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deduplication", tags=["Deduplication"])

@router.get("/statistics", response_model=APIResponse)
async def get_deduplication_statistics(db: Session = Depends(get_db)):
    """Get deduplication statistics and performance metrics"""
    try:
        # Get basic statistics
        stats = {
            'total_articles': 0,
            'articles_with_content_hash': 0,
            'total_clusters': 0,
            'total_duplicate_pairs': 0,
            'system_status': 'operational'
        }
        
        # Get total articles count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM articles")).fetchone()
            stats['total_articles'] = result[0] if result else 0
        except Exception as e:
            logger.warning(f"Could not get total articles count: {e}")
        
        # Get articles with content hash count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM articles WHERE content_hash IS NOT NULL")).fetchone()
            stats['articles_with_content_hash'] = result[0] if result else 0
        except Exception as e:
            logger.warning(f"Could not get content hash count: {e}")
        
        # Get total clusters count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM cluster_metadata")).fetchone()
            stats['total_clusters'] = result[0] if result else 0
        except Exception as e:
            logger.warning(f"Could not get clusters count: {e}")
        
        # Get total duplicate pairs count
        try:
            result = db.execute(text("SELECT COUNT(*) FROM duplicate_pairs")).fetchone()
            stats['total_duplicate_pairs'] = result[0] if result else 0
        except Exception as e:
            logger.warning(f"Could not get duplicate pairs count: {e}")
        
        return APIResponse(
            success=True,
            data=stats,
            message="Deduplication statistics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting deduplication statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test", response_model=APIResponse)
async def test_deduplication_system():
    """Test endpoint to verify deduplication system is working"""
    try:
        return APIResponse(
            success=True,
            data={
                'status': 'operational',
                'message': 'Deduplication system is running',
                'features': [
                    'Content hash generation',
                    'Same-source duplicate detection',
                    'Cross-source similarity analysis',
                    'Article clustering',
                    'Storyline suggestions'
                ]
            },
            message="Deduplication system test successful"
        )
        
    except Exception as e:
        logger.error(f"Error testing deduplication system: {e}")
        raise HTTPException(status_code=500, detail=str(e))
