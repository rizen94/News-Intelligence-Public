#!/usr/bin/env python3
"""
Storyline CRUD Routes
Core create, read, update, delete operations for storylines
"""

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from typing import List, Optional
from datetime import datetime
import logging
import math

from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain
from ..services.storyline_service import StorylineService
from ..schemas.storyline_schemas import (
    StorylineCreateRequest,
    StorylineUpdateRequest,
    StorylineResponse,
    StorylineDetailResponse,
    StorylineListResponse,
    StorylineListItem,
    PaginationInfo,
    ArticleSummary
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Storyline CRUD"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Dependencies
# ============================================================================

async def validate_domain_dependency(domain: str = Path(..., pattern="^(politics|finance|science-tech)$")):
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    return domain


# ============================================================================
# List Endpoints (with pagination)
# ============================================================================

@router.get("/{domain}/storylines", response_model=StorylineListResponse)
async def get_domain_storylines(
    domain: str = Depends(validate_domain_dependency),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, pattern="^(active|archived|draft)$", description="Filter by status")
):
    """Get paginated list of storylines for a specific domain"""
    try:
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query with optional status filter
                base_query = f"FROM {schema}.storylines"
                where_clause = ""
                params = []
                
                if status:
                    where_clause = "WHERE status = %s"
                    params.append(status)
                
                # Get total count
                count_query = f"SELECT COUNT(*) {base_query} {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()[0]
                
                # Calculate pagination
                offset = (page - 1) * page_size
                pages = math.ceil(total / page_size) if total > 0 else 0
                
                # Get paginated results
                query = f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, article_count, quality_score
                    {base_query}
                    {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(query, params + [page_size, offset])
                
                storylines = []
                for row in cur.fetchall():
                    storylines.append(StorylineListItem(
                        id=row[0],
                        title=row[1],
                        description=row[2],
                        article_count=row[6] or 0,
                        quality_score=row[7],
                        status=row[5],
                        created_at=row[3],
                        updated_at=row[4]
                    ))
                
                pagination = PaginationInfo(
                    page=page,
                    page_size=page_size,
                    total=total,
                    pages=pages,
                    has_next=page < pages,
                    has_prev=page > 1
                )
                
                return StorylineListResponse(
                    data=storylines,
                    pagination=pagination,
                    domain=domain
                )
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Create Endpoint
# ============================================================================

@router.post("/{domain}/storylines", response_model=StorylineResponse)
async def create_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    request: StorylineCreateRequest = None
):
    """Create a new storyline in a specific domain"""
    try:
        storyline_service = StorylineService(domain=domain)
        
        result = await storyline_service.create_storyline_from_articles(
            title=request.title if request else "",
            description=request.description if request else None,
            article_ids=request.article_ids if request else None
        )
        
        if result.get("success"):
            data = result.get("data", {})
            # Fetch created storyline for response
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    schema = domain.replace('-', '_')
                    cur.execute(f"""
                        SELECT id, title, description, status, article_count,
                               quality_score, analysis_summary, created_at, updated_at,
                               last_evolution_at, evolution_count
                        FROM {schema}.storylines
                        WHERE id = %s
                    """, (data.get("id"),))
                    row = cur.fetchone()
                    if row:
                        return StorylineResponse(
                            id=row[0],
                            title=row[1],
                            description=row[2],
                            status=row[3],
                            article_count=row[4] or 0,
                            quality_score=row[5],
                            analysis_summary=row[6],
                            created_at=row[7],
                            updated_at=row[8],
                            last_evolution_at=row[9],
                            evolution_count=row[10]
                        )
            finally:
                conn.close()
            
            raise HTTPException(status_code=500, detail="Failed to retrieve created storyline")
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Creation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Get Single Endpoint
# ============================================================================

@router.get("/{domain}/storylines/{storyline_id}", response_model=StorylineDetailResponse)
async def get_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1)
):
    """Get a single storyline with all its articles from a specific domain"""
    try:
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get storyline details (include ml_processing_status for frontend processing state)
                cur.execute(f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, analysis_summary, quality_score, article_count,
                           last_evolution_at, evolution_count, background_information,
                           context_last_updated,
                           COALESCE(ml_processing_status, 'completed') as ml_processing_status
                    FROM {schema}.storylines 
                    WHERE id = %s
                """, (storyline_id,))
                
                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Get articles in storyline
                cur.execute(f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC
                """, (storyline_id,))
                
                articles = []
                for row in cur.fetchall():
                    articles.append(ArticleSummary(
                        id=row[0],
                        title=row[1],
                        url=row[2],
                        source_domain=row[3],
                        published_at=row[4],
                        summary=row[5]
                    ))
                
                # Parse background_information if present
                background_info = None
                if storyline[11]:
                    import json
                    try:
                        background_info = json.loads(storyline[11]) if isinstance(storyline[11], str) else storyline[11]
                    except:
                        pass
                
                # storyline row: [0]id [1]title [2]description [3]created_at [4]updated_at [5]status [6]analysis_summary [7]quality_score [8]article_count [9]last_evolution_at [10]evolution_count [11]background_information [12]context_last_updated [13]ml_processing_status
                return StorylineDetailResponse(
                    id=storyline[0],
                    title=storyline[1],
                    description=storyline[2],
                    status=storyline[5],
                    article_count=storyline[8] or 0,
                    quality_score=storyline[7],
                    analysis_summary=storyline[6],
                    created_at=storyline[3],
                    updated_at=storyline[4],
                    last_evolution_at=storyline[9],
                    evolution_count=storyline[10],
                    articles=articles,
                    background_information=background_info,
                    context_last_updated=storyline[12],
                    ml_processing_status=storyline[13] if len(storyline) > 13 else 'completed'
                )
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Update Endpoint
# ============================================================================

@router.put("/{domain}/storylines/{storyline_id}", response_model=StorylineResponse)
async def update_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    request: StorylineUpdateRequest = None
):
    """Update an existing storyline in a specific domain"""
    try:
        schema = domain.replace('-', '_')
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")
                
                # Build update query dynamically
                updates = []
                params = []
                
                if request and request.title is not None:
                    updates.append("title = %s")
                    params.append(request.title)
                
                if request and request.description is not None:
                    updates.append("description = %s")
                    params.append(request.description)
                
                if request and request.status is not None:
                    updates.append("status = %s")
                    params.append(request.status)
                
                if updates:
                    updates.append("updated_at = %s")
                    params.append(datetime.now())
                    params.append(storyline_id)
                    
                    cur.execute(f"""
                        UPDATE {schema}.storylines 
                        SET {', '.join(updates)}
                        WHERE id = %s
                    """, params)
                    
                    conn.commit()
                
                # Fetch updated storyline
                cur.execute(f"""
                    SELECT id, title, description, status, article_count,
                           quality_score, analysis_summary, created_at, updated_at,
                           last_evolution_at, evolution_count
                    FROM {schema}.storylines
                    WHERE id = %s
                """, (storyline_id,))
                
                row = cur.fetchone()
                if row:
                    return StorylineResponse(
                        id=row[0],
                        title=row[1],
                        description=row[2],
                        status=row[3],
                        article_count=row[4] or 0,
                        quality_score=row[5],
                        analysis_summary=row[6],
                        created_at=row[7],
                        updated_at=row[8],
                        last_evolution_at=row[9],
                        evolution_count=row[10]
                    )
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

