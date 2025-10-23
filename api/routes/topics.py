"""
News Intelligence System v3.0 - Simplified Topic Management API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from config.database import get_db
from schemas.robust_schemas import APIResponse

router = APIRouter()

@router.get("/", response_model=APIResponse)
async def get_topics(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    search: Optional[str] = None
):
    """Get all topics with optional filtering"""
    try:
        # For now, return a simple response to test the endpoint
        return APIResponse(
            success=True,
            data={"topics": [], "message": "Topics endpoint is working"},
            message="Topics endpoint is functional",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cluster", response_model=APIResponse)
async def cluster_articles(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100)
):
    """Manually trigger topic clustering for recent articles"""
    try:
        # For now, return a simple response to test the endpoint
        return APIResponse(
            success=True,
            data={"message": "Clustering endpoint is working", "articles_processed": 0},
            message="Clustering endpoint is functional",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
