"""
RAG System API Routes for News Intelligence System v3.0
Provides RAG dossier management, iterations, and research capabilities
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from api.config.database import get_db_connection

router = APIRouter()

# Enums
class RAGPhase(str, Enum):
    """RAG phases"""
    TIMELINE = "timeline"
    CONTEXT = "context"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"

class RAGStatus(str, Enum):
    """RAG status"""
    ACTIVE = "active"
    COMPLETE = "complete"
    PLATEAU = "plateau"
    ERROR = "error"

# Pydantic models
class RAGDossierBase(BaseModel):
    """Base RAG dossier model"""
    article_id: int = Field(..., description="Source article ID")

class RAGDossierCreate(RAGDossierBase):
    """RAG dossier creation model"""
    pass

class RAGDossierUpdate(BaseModel):
    """RAG dossier update model"""
    current_phase: Optional[RAGPhase] = None
    is_complete: Optional[bool] = None
    plateau_reached: Optional[bool] = None

class RAGIteration(BaseModel):
    """RAG iteration model"""
    id: int = Field(..., description="Iteration ID")
    dossier_id: str = Field(..., description="Dossier ID")
    iteration_number: int = Field(..., description="Iteration number")
    phase: RAGPhase = Field(..., description="Iteration phase")
    input_tags: List[str] = Field(default_factory=list, description="Input tags")
    output_tags: List[str] = Field(default_factory=list, description="Output tags")
    new_articles_found: int = Field(0, description="New articles found")
    new_entities_found: int = Field(0, description="New entities found")
    new_insights: List[Dict[str, Any]] = Field(default_factory=list, description="New insights")
    processing_time: float = Field(0.0, description="Processing time")
    plateau_score: float = Field(0.0, description="Plateau score")
    success: bool = Field(True, description="Success status")
    error_message: Optional[str] = Field(None, description="Error message")
    timestamp: datetime = Field(..., description="Iteration timestamp")

class RAGDossier(RAGDossierBase):
    """Complete RAG dossier model"""
    id: int = Field(..., description="Dossier ID")
    dossier_id: str = Field(..., description="Unique dossier identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_updated: datetime = Field(..., description="Last update timestamp")
    total_iterations: int = Field(0, description="Total iterations")
    current_phase: RAGPhase = Field(..., description="Current phase")
    is_complete: bool = Field(False, description="Completion status")
    plateau_reached: bool = Field(False, description="Plateau status")
    total_articles_analyzed: int = Field(0, description="Total articles analyzed")
    total_entities_found: int = Field(0, description="Total entities found")
    historical_depth_years: int = Field(0, description="Historical depth")
    final_timeline: Dict[str, Any] = Field(default_factory=dict, description="Final timeline")
    final_context: Dict[str, Any] = Field(default_factory=dict, description="Final context")
    final_analysis: Dict[str, Any] = Field(default_factory=dict, description="Final analysis")
    final_synthesis: Dict[str, Any] = Field(default_factory=dict, description="Final synthesis")
    iterations: List[RAGIteration] = Field(default_factory=list, description="Dossier iterations")

class RAGDossierList(BaseModel):
    """RAG dossier list response"""
    dossiers: List[RAGDossier] = Field(..., description="List of dossiers")
    total: int = Field(..., description="Total number of dossiers")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")

class RAGStats(BaseModel):
    """RAG statistics model"""
    total_dossiers: int = Field(..., description="Total dossiers")
    active_dossiers: int = Field(..., description="Active dossiers")
    completed_dossiers: int = Field(..., description="Completed dossiers")
    plateau_dossiers: int = Field(..., description="Plateau dossiers")
    avg_iterations_per_dossier: float = Field(..., description="Average iterations")
    avg_processing_time: float = Field(..., description="Average processing time")
    success_rate: float = Field(..., description="Success rate")
    recent_dossiers: List[Dict[str, Any]] = Field(..., description="Recent dossiers")

class ResearchRequest(BaseModel):
    """Research request model"""
    topic_name: str = Field(..., description="Research topic name")
    topic_description: Optional[str] = Field(None, description="Topic description")
    keywords: List[str] = Field(default_factory=list, description="Research keywords")
    research_depth: int = Field(3, ge=1, le=5, description="Research depth (1-5)")
    historical_scope_years: int = Field(5, ge=1, le=20, description="Historical scope in years")

# API Endpoints

@router.get("/dossiers", response_model=RAGDossierList)
async def get_rag_dossiers(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[RAGStatus] = Query(None, description="Filter by status"),
    phase: Optional[RAGPhase] = Query(None, description="Filter by phase"),
    is_complete: Optional[bool] = Query(None, description="Filter by completion status"),
    search: Optional[str] = Query(None, description="Search query")
):
    """Get list of RAG dossiers with filtering and pagination"""
    try:
        offset = (page - 1) * per_page
        
        # Build query conditions
        where_conditions = []
        params = []
        
        if status:
            if status == RAGStatus.ACTIVE:
                where_conditions.append("is_complete = false AND plateau_reached = false")
            elif status == RAGStatus.COMPLETE:
                where_conditions.append("is_complete = true")
            elif status == RAGStatus.PLATEAU:
                where_conditions.append("plateau_reached = true")
        
        if phase:
            where_conditions.append("current_phase = %s")
            params.append(phase.value)
        
        if is_complete is not None:
            where_conditions.append("is_complete = %s")
            params.append(is_complete)
        
        if search:
            where_conditions.append("dossier_id ILIKE %s")
            params.append(f"%{search}%")
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM rag_dossiers {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get dossiers
        dossiers_query = f"""
            SELECT 
                id, dossier_id, article_id, created_at, last_updated, total_iterations,
                current_phase, is_complete, plateau_reached, total_articles_analyzed,
                total_entities_found, historical_depth_years, final_timeline, final_context,
                final_analysis, final_synthesis
            FROM rag_dossiers 
            {where_clause}
            ORDER BY last_updated DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(dossiers_query, params)
        
        dossiers = []
        for row in cursor.fetchall():
            # Get iterations for this dossier
            cursor.execute("""
                SELECT 
                    id, iteration_number, phase, input_tags, output_tags,
                    new_articles_found, new_entities_found, new_insights,
                    processing_time, plateau_score, success, error_message, timestamp
                FROM rag_iterations 
                WHERE dossier_id = %s
                ORDER BY iteration_number
            """, (row[1],))
            
            iterations = []
            for iter_row in cursor.fetchall():
                iteration = RAGIteration(
                    id=iter_row[0],
                    dossier_id=row[1],
                    iteration_number=iter_row[1],
                    phase=iter_row[2],
                    input_tags=iter_row[3] or [],
                    output_tags=iter_row[4] or [],
                    new_articles_found=iter_row[5],
                    new_entities_found=iter_row[6],
                    new_insights=iter_row[7] or [],
                    processing_time=iter_row[8],
                    plateau_score=iter_row[9],
                    success=iter_row[10],
                    error_message=iter_row[11],
                    timestamp=iter_row[12]
                )
                iterations.append(iteration)
            
            dossier = RAGDossier(
                id=row[0],
                dossier_id=row[1],
                article_id=row[2],
                created_at=row[3],
                last_updated=row[4],
                total_iterations=row[5],
                current_phase=row[6],
                is_complete=row[7],
                plateau_reached=row[8],
                total_articles_analyzed=row[9],
                total_entities_found=row[10],
                historical_depth_years=row[11],
                final_timeline=row[12] or {},
                final_context=row[13] or {},
                final_analysis=row[14] or {},
                final_synthesis=row[15] or {},
                iterations=iterations
            )
            dossiers.append(dossier)
        
        cursor.close()
        conn.close()
        
        return RAGDossierList(
            dossiers=dossiers,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch RAG dossiers: {str(e)}"
        )

@router.get("/dossiers/{dossier_id}", response_model=RAGDossier)
async def get_rag_dossier(dossier_id: str = Path(..., description="Dossier ID")):
    """Get specific RAG dossier by ID"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get dossier details
        cursor.execute("""
            SELECT 
                id, dossier_id, article_id, created_at, last_updated, total_iterations,
                current_phase, is_complete, plateau_reached, total_articles_analyzed,
                total_entities_found, historical_depth_years, final_timeline, final_context,
                final_analysis, final_synthesis
            FROM rag_dossiers 
            WHERE dossier_id = %s
        """, (dossier_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="RAG dossier not found")
        
        # Get iterations
        cursor.execute("""
            SELECT 
                id, iteration_number, phase, input_tags, output_tags,
                new_articles_found, new_entities_found, new_insights,
                processing_time, plateau_score, success, error_message, timestamp
            FROM rag_iterations 
            WHERE dossier_id = %s
            ORDER BY iteration_number
        """, (dossier_id,))
        
        iterations = []
        for iter_row in cursor.fetchall():
            iteration = RAGIteration(
                id=iter_row[0],
                dossier_id=dossier_id,
                iteration_number=iter_row[1],
                phase=iter_row[2],
                input_tags=iter_row[3] or [],
                output_tags=iter_row[4] or [],
                new_articles_found=iter_row[5],
                new_entities_found=iter_row[6],
                new_insights=iter_row[7] or [],
                processing_time=iter_row[8],
                plateau_score=iter_row[9],
                success=iter_row[10],
                error_message=iter_row[11],
                timestamp=iter_row[12]
            )
            iterations.append(iteration)
        
        dossier = RAGDossier(
            id=row[0],
            dossier_id=row[1],
            article_id=row[2],
            created_at=row[3],
            last_updated=row[4],
            total_iterations=row[5],
            current_phase=row[6],
            is_complete=row[7],
            plateau_reached=row[8],
            total_articles_analyzed=row[9],
            total_entities_found=row[10],
            historical_depth_years=row[11],
            final_timeline=row[12] or {},
            final_context=row[13] or {},
            final_analysis=row[14] or {},
            final_synthesis=row[15] or {},
            iterations=iterations
        )
        
        cursor.close()
        conn.close()
        
        return dossier
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch RAG dossier: {str(e)}"
        )

@router.post("/dossiers", response_model=RAGDossier)
async def create_rag_dossier(dossier_data: RAGDossierCreate):
    """Create new RAG dossier"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE id = %s", (dossier_data.article_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail="Source article not found")
        
        # Generate unique dossier ID
        import uuid
        dossier_id = str(uuid.uuid4())[:16]
        
        # Insert new dossier
        cursor.execute("""
            INSERT INTO rag_dossiers (
                dossier_id, article_id, created_at, last_updated, current_phase
            ) VALUES (
                %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            dossier_id,
            dossier_data.article_id,
            datetime.utcnow(),
            datetime.utcnow(),
            RAGPhase.TIMELINE.value
        ))
        
        dossier_db_id = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return created dossier
        return await get_rag_dossier(dossier_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create RAG dossier: {str(e)}"
        )

@router.put("/dossiers/{dossier_id}", response_model=RAGDossier)
async def update_rag_dossier(
    dossier_id: str = Path(..., description="Dossier ID"),
    dossier_data: RAGDossierUpdate = Body(..., description="Dossier update data")
):
    """Update RAG dossier"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if dossier exists
        cursor.execute("SELECT id FROM rag_dossiers WHERE dossier_id = %s", (dossier_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RAG dossier not found")
        
        # Build update query dynamically
        update_fields = []
        params = []
        
        if dossier_data.current_phase is not None:
            update_fields.append("current_phase = %s")
            params.append(dossier_data.current_phase.value)
        
        if dossier_data.is_complete is not None:
            update_fields.append("is_complete = %s")
            params.append(dossier_data.is_complete)
        
        if dossier_data.plateau_reached is not None:
            update_fields.append("plateau_reached = %s")
            params.append(dossier_data.plateau_reached)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("last_updated = %s")
        params.append(datetime.utcnow())
        params.append(dossier_id)
        
        update_query = f"""
            UPDATE rag_dossiers 
            SET {', '.join(update_fields)}
            WHERE dossier_id = %s
        """
        
        cursor.execute(update_query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated dossier
        return await get_rag_dossier(dossier_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update RAG dossier: {str(e)}"
        )

@router.delete("/dossiers/{dossier_id}")
async def delete_rag_dossier(dossier_id: str = Path(..., description="Dossier ID")):
    """Delete RAG dossier"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if dossier exists
        cursor.execute("SELECT id FROM rag_dossiers WHERE dossier_id = %s", (dossier_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RAG dossier not found")
        
        # Delete dossier (cascade will handle iterations)
        cursor.execute("DELETE FROM rag_dossiers WHERE dossier_id = %s", (dossier_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "RAG dossier deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete RAG dossier: {str(e)}"
        )

@router.get("/dossiers/{dossier_id}/iterations", response_model=List[RAGIteration])
async def get_dossier_iterations(dossier_id: str = Path(..., description="Dossier ID")):
    """Get all iterations for a specific dossier"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if dossier exists
        cursor.execute("SELECT id FROM rag_dossiers WHERE dossier_id = %s", (dossier_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="RAG dossier not found")
        
        # Get iterations
        cursor.execute("""
            SELECT 
                id, iteration_number, phase, input_tags, output_tags,
                new_articles_found, new_entities_found, new_insights,
                processing_time, plateau_score, success, error_message, timestamp
            FROM rag_iterations 
            WHERE dossier_id = %s
            ORDER BY iteration_number
        """, (dossier_id,))
        
        iterations = []
        for row in cursor.fetchall():
            iteration = RAGIteration(
                id=row[0],
                dossier_id=dossier_id,
                iteration_number=row[1],
                phase=row[2],
                input_tags=row[3] or [],
                output_tags=row[4] or [],
                new_articles_found=row[5],
                new_entities_found=row[6],
                new_insights=row[7] or [],
                processing_time=row[8],
                plateau_score=row[9],
                success=row[10],
                error_message=row[11],
                timestamp=row[12]
            )
            iterations.append(iteration)
        
        cursor.close()
        conn.close()
        
        return iterations
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dossier iterations: {str(e)}"
        )

@router.post("/research")
async def trigger_research(research_request: ResearchRequest):
    """Trigger research topic analysis"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Insert research topic
        cursor.execute("""
            INSERT INTO rag_research_topics (
                topic_name, topic_description, keywords, research_depth,
                historical_scope_years, created_at, last_researched
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            research_request.topic_name,
            research_request.topic_description,
            research_request.keywords,
            research_request.research_depth,
            research_request.historical_scope_years,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        topic_id = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # In production, this would trigger the actual research process
        return {
            "message": "Research topic created successfully",
            "topic_id": topic_id,
            "status": "queued"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger research: {str(e)}"
        )

@router.get("/stats", response_model=RAGStats)
async def get_rag_stats():
    """Get RAG system statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get basic counts
        cursor.execute("SELECT COUNT(*) FROM rag_dossiers")
        total_dossiers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM rag_dossiers WHERE is_complete = false AND plateau_reached = false")
        active_dossiers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM rag_dossiers WHERE is_complete = true")
        completed_dossiers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM rag_dossiers WHERE plateau_reached = true")
        plateau_dossiers = cursor.fetchone()[0]
        
        # Get average iterations per dossier
        cursor.execute("SELECT AVG(total_iterations) FROM rag_dossiers")
        avg_iterations = float(cursor.fetchone()[0] or 0)
        
        # Get average processing time
        cursor.execute("SELECT AVG(processing_time) FROM rag_iterations")
        avg_processing_time = float(cursor.fetchone()[0] or 0)
        
        # Get success rate
        cursor.execute("SELECT AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) FROM rag_iterations")
        success_rate = float(cursor.fetchone()[0] or 0) * 100
        
        # Get recent dossiers
        cursor.execute("""
            SELECT dossier_id, current_phase, total_iterations, last_updated
            FROM rag_dossiers 
            ORDER BY last_updated DESC 
            LIMIT 10
        """)
        recent_dossiers = [
            {
                "dossier_id": row[0],
                "current_phase": row[1],
                "total_iterations": row[2],
                "last_updated": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return RAGStats(
            total_dossiers=total_dossiers,
            active_dossiers=active_dossiers,
            completed_dossiers=completed_dossiers,
            plateau_dossiers=plateau_dossiers,
            avg_iterations_per_dossier=avg_iterations,
            avg_processing_time=avg_processing_time,
            success_rate=success_rate,
            recent_dossiers=recent_dossiers
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch RAG statistics: {str(e)}"
        )
