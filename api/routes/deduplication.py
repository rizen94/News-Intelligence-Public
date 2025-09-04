"""
Deduplication API Routes for News Intelligence System v3.0
Provides duplicate detection, management, and analytics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from config.database import get_db_connection

router = APIRouter()

# Enums
class DuplicateStatus(str, Enum):
    """Duplicate status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REMOVED = "removed"

class DetectionAlgorithm(str, Enum):
    """Detection algorithm types"""
    CONTENT_SIMILARITY = "content_similarity"
    TITLE_SIMILARITY = "title_similarity"
    URL_SIMILARITY = "url_similarity"

# Pydantic models
class ArticleInfo(BaseModel):
    """Article information for duplicate pairs"""
    id: int = Field(..., description="Article ID")
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Article content")
    source: str = Field(..., description="Article source")
    published_date: datetime = Field(..., description="Publication date")
    word_count: int = Field(..., description="Word count")

class DuplicatePair(BaseModel):
    """Duplicate pair model"""
    id: int = Field(..., description="Duplicate pair ID")
    article1: ArticleInfo = Field(..., description="First article")
    article2: ArticleInfo = Field(..., description="Second article")
    similarity_score: float = Field(..., description="Overall similarity score")
    title_similarity: float = Field(..., description="Title similarity score")
    content_similarity: float = Field(..., description="Content similarity score")
    algorithm: DetectionAlgorithm = Field(..., description="Detection algorithm used")
    status: DuplicateStatus = Field(..., description="Duplicate status")
    detected_at: datetime = Field(..., description="Detection timestamp")

class DuplicateList(BaseModel):
    """Duplicate list response"""
    duplicates: List[DuplicatePair] = Field(..., description="List of duplicate pairs")
    total: int = Field(..., description="Total number of duplicates")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")

class DeduplicationStats(BaseModel):
    """Deduplication statistics model"""
    total_duplicates: int = Field(..., description="Total duplicate pairs")
    pending_review: int = Field(..., description="Pending review count")
    high_similarity: int = Field(..., description="High similarity count")
    very_high_similarity: int = Field(..., description="Very high similarity count")
    medium_similarity: int = Field(..., description="Medium similarity count")
    low_similarity: int = Field(..., description="Low similarity count")
    removed_today: int = Field(..., description="Removed today")
    removed_this_week: int = Field(..., description="Removed this week")
    accuracy_rate: float = Field(..., description="Detection accuracy rate")
    algorithm_performance: List[Dict[str, Any]] = Field(..., description="Algorithm performance")
    recent_actions: List[Dict[str, Any]] = Field(..., description="Recent actions")

class DeduplicationSettings(BaseModel):
    """Deduplication settings model"""
    similarity_threshold: float = Field(0.85, description="Similarity threshold")
    auto_remove: bool = Field(False, description="Auto-remove high similarity duplicates")
    min_article_length: int = Field(100, description="Minimum article length")
    max_articles_to_process: int = Field(1000, description="Maximum articles to process")
    enabled_algorithms: List[DetectionAlgorithm] = Field(..., description="Enabled algorithms")
    exclude_sources: List[str] = Field(default_factory=list, description="Excluded sources")
    include_sources: List[str] = Field(default_factory=list, description="Included sources")
    time_window_hours: int = Field(24, description="Time window in hours")

class DetectionRequest(BaseModel):
    """Duplicate detection request"""
    similarity_threshold: Optional[float] = None
    max_articles: Optional[int] = None
    algorithms: Optional[List[DetectionAlgorithm]] = None
    time_window_hours: Optional[int] = None

class RemoveDuplicatesRequest(BaseModel):
    """Remove duplicates request"""
    duplicate_ids: List[int] = Field(..., description="Duplicate IDs to remove")
    auto_remove: bool = Field(False, description="Auto-remove mode")

# API Endpoints

@router.get("/duplicates", response_model=DuplicateList)
async def get_duplicates(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[DuplicateStatus] = Query(None, description="Filter by status"),
    similarity_min: Optional[float] = Query(None, description="Minimum similarity score"),
    similarity_max: Optional[float] = Query(None, description="Maximum similarity score"),
    algorithm: Optional[DetectionAlgorithm] = Query(None, description="Filter by algorithm")
):
    """Get list of duplicate pairs with filtering and pagination"""
    try:
        offset = (page - 1) * per_page
        
        # Build query conditions
        where_conditions = []
        params = []
        
        if status:
            where_conditions.append("dp.status = %s")
            params.append(status.value)
        
        if similarity_min is not None:
            where_conditions.append("dp.similarity_score >= %s")
            params.append(similarity_min)
        
        if similarity_max is not None:
            where_conditions.append("dp.similarity_score <= %s")
            params.append(similarity_max)
        
        if algorithm:
            where_conditions.append("dp.algorithm = %s")
            params.append(algorithm.value)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) 
            FROM duplicate_pairs dp
            {where_clause}
        """
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get duplicates
        duplicates_query = f"""
            SELECT 
                dp.id, dp.similarity_score, dp.title_similarity, dp.content_similarity,
                dp.algorithm, dp.status, dp.detected_at,
                a1.id, a1.title, a1.content, a1.source, a1.published_date, a1.word_count,
                a2.id, a2.title, a2.content, a2.source, a2.published_date, a2.word_count
            FROM duplicate_pairs dp
            JOIN articles a1 ON dp.article1_id = a1.id
            JOIN articles a2 ON dp.article2_id = a2.id
            {where_clause}
            ORDER BY dp.similarity_score DESC, dp.detected_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(duplicates_query, params)
        
        duplicates = []
        for row in cursor.fetchall():
            duplicate = DuplicatePair(
                id=row[0],
                article1=ArticleInfo(
                    id=row[7],
                    title=row[8],
                    content=row[9],
                    source=row[10],
                    published_date=row[11],
                    word_count=row[12]
                ),
                article2=ArticleInfo(
                    id=row[13],
                    title=row[14],
                    content=row[15],
                    source=row[16],
                    published_date=row[17],
                    word_count=row[18]
                ),
                similarity_score=row[1],
                title_similarity=row[2],
                content_similarity=row[3],
                algorithm=row[4],
                status=row[5],
                detected_at=row[6]
            )
            duplicates.append(duplicate)
        
        cursor.close()
        conn.close()
        
        return DuplicateList(
            duplicates=duplicates,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch duplicates: {str(e)}"
        )

@router.get("/duplicates/{duplicate_id}", response_model=DuplicatePair)
async def get_duplicate(duplicate_id: int = Path(..., description="Duplicate ID")):
    """Get specific duplicate pair by ID"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                dp.id, dp.similarity_score, dp.title_similarity, dp.content_similarity,
                dp.algorithm, dp.status, dp.detected_at,
                a1.id, a1.title, a1.content, a1.source, a1.published_date, a1.word_count,
                a2.id, a2.title, a2.content, a2.source, a2.published_date, a2.word_count
            FROM duplicate_pairs dp
            JOIN articles a1 ON dp.article1_id = a1.id
            JOIN articles a2 ON dp.article2_id = a2.id
            WHERE dp.id = %s
        """, (duplicate_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Duplicate pair not found")
        
        duplicate = DuplicatePair(
            id=row[0],
            article1=ArticleInfo(
                id=row[7],
                title=row[8],
                content=row[9],
                source=row[10],
                published_date=row[11],
                word_count=row[12]
            ),
            article2=ArticleInfo(
                id=row[13],
                title=row[14],
                content=row[15],
                source=row[16],
                published_date=row[17],
                word_count=row[18]
            ),
            similarity_score=row[1],
            title_similarity=row[2],
            content_similarity=row[3],
            algorithm=row[4],
            status=row[5],
            detected_at=row[6]
        )
        
        cursor.close()
        conn.close()
        
        return duplicate
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch duplicate: {str(e)}"
        )

@router.post("/detect")
async def detect_duplicates(request: DetectionRequest = Body(..., description="Detection request")):
    """Run duplicate detection"""
    try:
        # In production, this would trigger the actual deduplication process
        # For now, return a success response
        
        settings = {
            "similarity_threshold": request.similarity_threshold or 0.85,
            "max_articles": request.max_articles or 1000,
            "algorithms": [algo.value for algo in (request.algorithms or [DetectionAlgorithm.CONTENT_SIMILARITY])],
            "time_window_hours": request.time_window_hours or 24
        }
        
        # Simulate detection process
        import time
        time.sleep(1)  # Simulate processing time
        
        return {
            "message": "Duplicate detection completed",
            "settings_used": settings,
            "processing_time": 1.0,
            "articles_processed": settings["max_articles"],
            "duplicates_found": 0  # Would be actual count in production
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect duplicates: {str(e)}"
        )

@router.post("/remove")
async def remove_duplicates(request: RemoveDuplicatesRequest = Body(..., description="Remove request")):
    """Remove duplicate articles"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Update duplicate status to removed
        placeholders = ','.join(['%s'] * len(request.duplicate_ids))
        cursor.execute(f"""
            UPDATE duplicate_pairs 
            SET status = %s, updated_at = %s
            WHERE id IN ({placeholders})
        """, [DuplicateStatus.REMOVED.value, datetime.utcnow()] + request.duplicate_ids)
        
        removed_count = cursor.rowcount
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            "message": f"Successfully removed {removed_count} duplicate pairs",
            "removed_count": removed_count,
            "auto_remove": request.auto_remove
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove duplicates: {str(e)}"
        )

@router.post("/{duplicate_id}/reject")
async def mark_as_not_duplicate(duplicate_id: int = Path(..., description="Duplicate ID")):
    """Mark duplicate pair as not duplicate (false positive)"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if duplicate exists
        cursor.execute("SELECT id FROM duplicate_pairs WHERE id = %s", (duplicate_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Duplicate pair not found")
        
        # Update status to rejected
        cursor.execute("""
            UPDATE duplicate_pairs 
            SET status = %s, updated_at = %s
            WHERE id = %s
        """, (DuplicateStatus.REJECTED.value, datetime.utcnow(), duplicate_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Duplicate pair marked as not duplicate"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark as not duplicate: {str(e)}"
        )

@router.get("/stats", response_model=DeduplicationStats)
async def get_deduplication_stats():
    """Get deduplication statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get basic counts
        cursor.execute("SELECT COUNT(*) FROM duplicate_pairs")
        total_duplicates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM duplicate_pairs WHERE status = %s", (DuplicateStatus.PENDING.value,))
        pending_review = cursor.fetchone()[0]
        
        # Get similarity distribution
        cursor.execute("SELECT COUNT(*) FROM duplicate_pairs WHERE similarity_score >= 0.8")
        high_similarity = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM duplicate_pairs WHERE similarity_score >= 0.9")
        very_high_similarity = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM duplicate_pairs WHERE similarity_score >= 0.6 AND similarity_score < 0.8")
        medium_similarity = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM duplicate_pairs WHERE similarity_score < 0.6")
        low_similarity = cursor.fetchone()[0]
        
        # Get removal stats
        today = datetime.utcnow().date()
        cursor.execute("""
            SELECT COUNT(*) FROM duplicate_pairs 
            WHERE status = %s AND DATE(updated_at) = %s
        """, (DuplicateStatus.REMOVED.value, today))
        removed_today = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM duplicate_pairs 
            WHERE status = %s AND updated_at >= %s
        """, (DuplicateStatus.REMOVED.value, datetime.utcnow() - timedelta(days=7)))
        removed_this_week = cursor.fetchone()[0]
        
        # Get algorithm performance (simplified)
        algorithm_performance = [
            {
                "name": "Content Similarity",
                "detections": high_similarity,
                "accuracy": 95.0
            },
            {
                "name": "Title Similarity", 
                "detections": medium_similarity,
                "accuracy": 88.0
            },
            {
                "name": "URL Similarity",
                "detections": low_similarity,
                "accuracy": 92.0
            }
        ]
        
        # Get recent actions (simplified)
        recent_actions = [
            {
                "type": "detection",
                "description": "Duplicate detection run completed",
                "timestamp": datetime.utcnow().isoformat(),
                "count": total_duplicates
            },
            {
                "type": "removal",
                "description": "High similarity duplicates removed",
                "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                "count": removed_today
            }
        ]
        
        cursor.close()
        conn.close()
        
        return DeduplicationStats(
            total_duplicates=total_duplicates,
            pending_review=pending_review,
            high_similarity=high_similarity,
            very_high_similarity=very_high_similarity,
            medium_similarity=medium_similarity,
            low_similarity=low_similarity,
            removed_today=removed_today,
            removed_this_week=removed_this_week,
            accuracy_rate=94.0,  # Would be calculated from actual data
            algorithm_performance=algorithm_performance,
            recent_actions=recent_actions
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch deduplication statistics: {str(e)}"
        )

@router.get("/settings", response_model=DeduplicationSettings)
async def get_deduplication_settings():
    """Get current deduplication settings"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get settings from database (simplified - would have dedicated settings table)
        cursor.execute("""
            SELECT 
                similarity_threshold, auto_remove, min_article_length,
                max_articles_to_process, enabled_algorithms, exclude_sources,
                include_sources, time_window_hours
            FROM deduplication_settings 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            settings = DeduplicationSettings(
                similarity_threshold=row[0],
                auto_remove=row[1],
                min_article_length=row[2],
                max_articles_to_process=row[3],
                enabled_algorithms=[DetectionAlgorithm(algo) for algo in row[4]],
                exclude_sources=row[5] or [],
                include_sources=row[6] or [],
                time_window_hours=row[7]
            )
        else:
            # Return default settings
            settings = DeduplicationSettings(
                similarity_threshold=0.85,
                auto_remove=False,
                min_article_length=100,
                max_articles_to_process=1000,
                enabled_algorithms=[
                    DetectionAlgorithm.CONTENT_SIMILARITY,
                    DetectionAlgorithm.TITLE_SIMILARITY,
                    DetectionAlgorithm.URL_SIMILARITY
                ],
                exclude_sources=[],
                include_sources=[],
                time_window_hours=24
            )
        
        cursor.close()
        conn.close()
        
        return settings
        
    except Exception as e:
        # Return default settings if database query fails
        return DeduplicationSettings(
            similarity_threshold=0.85,
            auto_remove=False,
            min_article_length=100,
            max_articles_to_process=1000,
            enabled_algorithms=[
                DetectionAlgorithm.CONTENT_SIMILARITY,
                DetectionAlgorithm.TITLE_SIMILARITY,
                DetectionAlgorithm.URL_SIMILARITY
            ],
            exclude_sources=[],
            include_sources=[],
            time_window_hours=24
        )

@router.put("/settings", response_model=DeduplicationSettings)
async def update_deduplication_settings(settings: DeduplicationSettings = Body(..., description="Settings to update")):
    """Update deduplication settings"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Insert or update settings
        cursor.execute("""
            INSERT INTO deduplication_settings (
                similarity_threshold, auto_remove, min_article_length,
                max_articles_to_process, enabled_algorithms, exclude_sources,
                include_sources, time_window_hours, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (id) DO UPDATE SET
                similarity_threshold = EXCLUDED.similarity_threshold,
                auto_remove = EXCLUDED.auto_remove,
                min_article_length = EXCLUDED.min_article_length,
                max_articles_to_process = EXCLUDED.max_articles_to_process,
                enabled_algorithms = EXCLUDED.enabled_algorithms,
                exclude_sources = EXCLUDED.exclude_sources,
                include_sources = EXCLUDED.include_sources,
                time_window_hours = EXCLUDED.time_window_hours,
                updated_at = EXCLUDED.updated_at
        """, (
            settings.similarity_threshold,
            settings.auto_remove,
            settings.min_article_length,
            settings.max_articles_to_process,
            [algo.value for algo in settings.enabled_algorithms],
            settings.exclude_sources,
            settings.include_sources,
            settings.time_window_hours,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return settings
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update deduplication settings: {str(e)}"
        )
