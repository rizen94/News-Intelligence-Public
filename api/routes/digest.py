"""
News Intelligence System v3.1.0 - Digest API
Automated digest management and retrieval
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import json

from schemas.response_schemas import APIResponse
from services.digest_automation_service import get_digest_service

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'news-system-postgres'),
    'database': os.getenv('DB_NAME', 'newsintelligence'),
    'user': os.getenv('DB_USER', 'newsapp'),
    'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
    'port': os.getenv('DB_PORT', '5432')
}

# Pydantic models
class DigestSummary(BaseModel):
    id: int
    story_id: str
    title: str
    description: str
    generated_at: datetime
    articles_count: int
    storylines_count: int
    summary: dict
    metadata: dict

class DigestResponse(BaseModel):
    digest: DigestSummary
    articles: list
    storylines: list
    is_fresh: bool
    next_generation: Optional[datetime] = None

@router.get("/latest", response_model=APIResponse)
async def get_latest_digest():
    """Get the latest automated digest"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get the most recent digest
        cursor.execute("""
            SELECT id, headline, consolidated_summary, ai_analysis, sources, 
                   created_at, updated_at
            FROM story_consolidations 
            WHERE headline LIKE 'Daily News Digest%'
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        
        if not result:
            # No digest exists, trigger generation
            digest_service = get_digest_service()
            await digest_service.generate_digest_if_needed()
            
            # Try again
            cursor.execute("""
                SELECT id, headline, consolidated_summary, ai_analysis, sources, 
                       created_at, updated_at
                FROM story_consolidations 
                WHERE headline LIKE 'Daily News Digest%'
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
        
        if not result:
            return APIResponse(
                success=False,
                data=None,
                message="No digest available and unable to generate one"
            )
        
        # Parse consolidated data
        consolidated_data = json.loads(result['ai_analysis']) if result['ai_analysis'] else {}
        
        # Check if digest is fresh (less than 1 hour old)
        is_fresh = (datetime.now() - result['created_at']).total_seconds() < 3600
        
        # Create response
        digest_summary = DigestSummary(
            id=result['id'],
            story_id=f"digest_{result['id']}",  # Generate a story_id from the ID
            title=result['headline'],
            description=result['consolidated_summary'],
            generated_at=result['created_at'],
            articles_count=consolidated_data.get('articles_count', 0),
            storylines_count=consolidated_data.get('storylines_count', 0),
            summary=consolidated_data.get('summary', {}),
            metadata=consolidated_data.get('metadata', {})
        )
        
        response_data = DigestResponse(
            digest=digest_summary,
            articles=consolidated_data.get('articles', []),
            storylines=consolidated_data.get('storylines', []),
            is_fresh=is_fresh,
            next_generation=datetime.fromisoformat(consolidated_data.get('metadata', {}).get('next_generation', '')) if consolidated_data.get('metadata', {}).get('next_generation') else None
        )
        
        cursor.close()
        conn.close()
        
        return APIResponse(
            success=True,
            data=response_data,
            message=f"Latest digest retrieved successfully. Generated {digest_summary.generated_at.strftime('%Y-%m-%d %H:%M')}"
        )
        
    except Exception as e:
        logger.error(f"Error getting latest digest: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to retrieve digest: {str(e)}"
        )

@router.post("/generate", response_model=APIResponse)
async def force_generate_digest():
    """Force generation of a new digest (for testing)"""
    try:
        digest_service = get_digest_service()
        await digest_service.generate_digest_if_needed()
        
        return APIResponse(
            success=True,
            data=None,
            message="Digest generation triggered successfully"
        )
        
    except Exception as e:
        logger.error(f"Error forcing digest generation: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to generate digest: {str(e)}"
        )

@router.get("/status", response_model=APIResponse)
async def get_digest_status():
    """Get digest automation status"""
    try:
        digest_service = get_digest_service()
        
        # Get latest digest info
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT created_at, headline
            FROM story_consolidations 
            WHERE headline LIKE 'Daily News Digest%'
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        latest_digest = cursor.fetchone()
        cursor.close()
        conn.close()
        
        status_data = {
            "automation_running": digest_service.is_running,
            "last_digest": latest_digest['created_at'].isoformat() if latest_digest else None,
            "last_digest_title": latest_digest['headline'] if latest_digest else None,
            "interval_hours": digest_service.digest_interval / 3600,
            "next_check": (datetime.now() + timedelta(seconds=digest_service.digest_interval)).isoformat()
        }
        
        return APIResponse(
            success=True,
            data=status_data,
            message="Digest automation status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Error getting digest status: {e}")
        return APIResponse(
            success=False,
            data=None,
            message=f"Failed to get digest status: {str(e)}"
        )
