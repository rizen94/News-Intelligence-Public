"""
Enhanced Timeline API Routes
Provides endpoints for chronological event extraction and timeline reconstruction
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from config.database import get_db
from services.enhanced_timeline_service import enhanced_timeline_service
from services.temporal_nlp_service import temporal_nlp_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/timeline/{storyline_id}/extract-events/")
async def extract_chronological_events(
    storyline_id: str,
    db: Session = Depends(get_db)
):
    """Extract chronological events from storyline articles"""
    try:
        events = enhanced_timeline_service.extract_chronological_events_from_storyline(storyline_id)
        
        return {
            "success": True,
            "message": f"Extracted {len(events)} chronological events",
            "data": {
                "storyline_id": storyline_id,
                "events_count": len(events),
                "events": [
                    {
                        "title": event.title,
                        "description": event.description,
                        "actual_event_date": event.actual_event_date.isoformat() if event.actual_event_date else None,
                        "relative_expression": event.relative_expression,
                        "event_type": event.event_type,
                        "importance_score": event.importance_score,
                        "confidence": event.confidence,
                        "entities": event.entities,
                        "historical_context": event.historical_context
                    } for event in events
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error extracting chronological events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeline/{storyline_id}/events/")
async def get_chronological_events(
    storyline_id: str,
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Event type filter"),
    min_importance: float = Query(0.0, description="Minimum importance score"),
    db: Session = Depends(get_db)
):
    """Get chronological events for a storyline with filters"""
    try:
        from sqlalchemy import text
        
        # Build query with filters
        where_conditions = ["storyline_id = :storyline_id"]
        params = {"storyline_id": storyline_id}
        
        if start_date:
            where_conditions.append("actual_event_date >= :start_date")
            params["start_date"] = start_date
        
        if end_date:
            where_conditions.append("actual_event_date <= :end_date")
            params["end_date"] = end_date
        
        if event_type:
            where_conditions.append("event_type = :event_type")
            params["event_type"] = event_type
        
        if min_importance > 0:
            where_conditions.append("importance_score >= :min_importance")
            params["min_importance"] = min_importance
        
        where_clause = " AND ".join(where_conditions)
        
        query = text(f"""
            SELECT id, event_id, title, description, actual_event_date, actual_event_time,
                   event_type, importance_score, entities, temporal_confidence, verified,
                   source_article_id, relative_temporal_expression, historical_context
            FROM chronological_events
            WHERE {where_clause}
            ORDER BY actual_event_date, actual_event_time, importance_score DESC
        """)
        
        result = db.execute(query, params).fetchall()
        
        events = []
        for row in result:
            events.append({
                "id": row.id,
                "event_id": row.event_id,
                "title": row.title,
                "description": row.description,
                "actual_event_date": row.actual_event_date.isoformat() if row.actual_event_date else None,
                "actual_event_time": str(row.actual_event_time) if row.actual_event_time else None,
                "event_type": row.event_type,
                "importance_score": float(row.importance_score),
                "entities": row.entities,
                "temporal_confidence": float(row.temporal_confidence),
                "verified": row.verified,
                "source_article_id": row.source_article_id,
                "relative_expression": row.relative_temporal_expression,
                "historical_context": row.historical_context
            })
        
        return {
            "success": True,
            "message": f"Retrieved {len(events)} chronological events",
            "data": {
                "storyline_id": storyline_id,
                "events": events,
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "event_type": event_type,
                    "min_importance": min_importance
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting chronological events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeline/{storyline_id}/reconstruct/")
async def reconstruct_timeline_narrative(
    storyline_id: str,
    reconstruction_type: str = Query("chronological", description="Type of reconstruction"),
    db: Session = Depends(get_db)
):
    """Reconstruct timeline narrative from chronological events"""
    try:
        reconstruction = enhanced_timeline_service.reconstruct_timeline_narrative(storyline_id)
        
        return {
            "success": True,
            "message": "Timeline narrative reconstructed successfully",
            "data": {
                "reconstruction_id": reconstruction.reconstruction_id,
                "storyline_id": reconstruction.storyline_id,
                "narrative_text": reconstruction.narrative_text,
                "event_sequence": reconstruction.event_sequence,
                "quality_scores": {
                    "coherence": reconstruction.coherence_score,
                    "completeness": reconstruction.completeness_score,
                    "accuracy": reconstruction.accuracy_score
                },
                "reconstruction_type": reconstruction.reconstruction_type,
                "events_count": len(reconstruction.event_sequence)
            }
        }
    except Exception as e:
        logger.error(f"Error reconstructing timeline narrative: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeline/{storyline_id}/relationships/")
async def get_event_relationships(
    storyline_id: str,
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    min_strength: float = Query(0.0, description="Minimum relationship strength"),
    db: Session = Depends(get_db)
):
    """Get relationships between chronological events"""
    try:
        from sqlalchemy import text
        
        where_conditions = [
            "ce1.storyline_id = :storyline_id",
            "ce2.storyline_id = :storyline_id"
        ]
        params = {"storyline_id": storyline_id}
        
        if relationship_type:
            where_conditions.append("er.relationship_type = :relationship_type")
            params["relationship_type"] = relationship_type
        
        if min_strength > 0:
            where_conditions.append("er.relationship_strength >= :min_strength")
            params["min_strength"] = min_strength
        
        where_clause = " AND ".join(where_conditions)
        
        query = text(f"""
            SELECT 
                er.id, er.relationship_id, er.relationship_type, er.relationship_strength,
                er.temporal_relationship, er.time_gap_days, er.confidence_score,
                ce1.title as source_event_title, ce1.actual_event_date as source_event_date,
                ce2.title as target_event_title, ce2.actual_event_date as target_event_date
            FROM event_relationships er
            JOIN chronological_events ce1 ON er.source_event_id = ce1.id
            JOIN chronological_events ce2 ON er.target_event_id = ce2.id
            WHERE {where_clause}
            ORDER BY er.relationship_strength DESC
        """)
        
        result = db.execute(query, params).fetchall()
        
        relationships = []
        for row in result:
            relationships.append({
                "id": row.id,
                "relationship_id": row.relationship_id,
                "relationship_type": row.relationship_type,
                "relationship_strength": float(row.relationship_strength),
                "temporal_relationship": row.temporal_relationship,
                "time_gap_days": row.time_gap_days,
                "confidence_score": float(row.confidence_score),
                "source_event": {
                    "title": row.source_event_title,
                    "date": row.source_event_date.isoformat() if row.source_event_date else None
                },
                "target_event": {
                    "title": row.target_event_title,
                    "date": row.target_event_date.isoformat() if row.target_event_date else None
                }
            })
        
        return {
            "success": True,
            "message": f"Retrieved {len(relationships)} event relationships",
            "data": {
                "storyline_id": storyline_id,
                "relationships": relationships,
                "filters": {
                    "relationship_type": relationship_type,
                    "min_strength": min_strength
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting event relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/timeline/{storyline_id}/analyze-temporal/")
async def analyze_temporal_expressions(
    storyline_id: str,
    text: str,
    db: Session = Depends(get_db)
):
    """Analyze temporal expressions in provided text"""
    try:
        # Extract temporal expressions
        expressions = temporal_nlp_service.extract_temporal_expressions(text)
        
        # Extract chronological events
        events = temporal_nlp_service.extract_chronological_events(text)
        
        return {
            "success": True,
            "message": f"Analyzed temporal expressions in text",
            "data": {
                "storyline_id": storyline_id,
                "temporal_expressions": [
                    {
                        "raw_expression": expr.raw_expression,
                        "normalized_date": expr.normalized_date.isoformat() if expr.normalized_date else None,
                        "expression_type": expr.expression_type,
                        "confidence": expr.confidence,
                        "context_sentence": expr.context_sentence,
                        "parsed_components": expr.parsed_components
                    } for expr in expressions
                ],
                "chronological_events": [
                    {
                        "title": event.title,
                        "description": event.description,
                        "actual_event_date": event.actual_event_date.isoformat() if event.actual_event_date else None,
                        "relative_expression": event.relative_expression,
                        "event_type": event.event_type,
                        "importance_score": event.importance_score,
                        "confidence": event.confidence,
                        "entities": event.entities,
                        "historical_context": event.historical_context
                    } for event in events
                ],
                "summary": {
                    "expressions_found": len(expressions),
                    "events_found": len(events),
                    "high_confidence_expressions": len([e for e in expressions if e.confidence > 0.8]),
                    "high_importance_events": len([e for e in events if e.importance_score > 0.7])
                }
            }
        }
    except Exception as e:
        logger.error(f"Error analyzing temporal expressions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeline/{storyline_id}/statistics/")
async def get_timeline_statistics(
    storyline_id: str,
    db: Session = Depends(get_db)
):
    """Get timeline statistics and analysis"""
    try:
        from sqlalchemy import text
        
        # Get basic statistics
        stats_query = text("""
            SELECT 
                COUNT(*) as total_events,
                COUNT(CASE WHEN actual_event_date IS NOT NULL THEN 1 END) as events_with_dates,
                COUNT(CASE WHEN verified = true THEN 1 END) as verified_events,
                AVG(importance_score) as avg_importance,
                AVG(temporal_confidence) as avg_confidence,
                MIN(actual_event_date) as earliest_date,
                MAX(actual_event_date) as latest_date
            FROM chronological_events
            WHERE storyline_id = :storyline_id
        """)
        
        stats_result = db.execute(stats_query, {"storyline_id": storyline_id}).fetchone()
        
        # Get event type distribution
        type_query = text("""
            SELECT event_type, COUNT(*) as count
            FROM chronological_events
            WHERE storyline_id = :storyline_id
            GROUP BY event_type
            ORDER BY count DESC
        """)
        
        type_result = db.execute(type_query, {"storyline_id": storyline_id}).fetchall()
        
        # Get relationship statistics
        rel_query = text("""
            SELECT 
                COUNT(*) as total_relationships,
                AVG(relationship_strength) as avg_strength,
                relationship_type,
                COUNT(*) as count
            FROM event_relationships er
            JOIN chronological_events ce1 ON er.source_event_id = ce1.id
            WHERE ce1.storyline_id = :storyline_id
            GROUP BY relationship_type
        """)
        
        rel_result = db.execute(rel_query, {"storyline_id": storyline_id}).fetchall()
        
        return {
            "success": True,
            "message": "Timeline statistics retrieved successfully",
            "data": {
                "storyline_id": storyline_id,
                "basic_statistics": {
                    "total_events": stats_result.total_events,
                    "events_with_dates": stats_result.events_with_dates,
                    "verified_events": stats_result.verified_events,
                    "avg_importance": float(stats_result.avg_importance) if stats_result.avg_importance else 0.0,
                    "avg_confidence": float(stats_result.avg_confidence) if stats_result.avg_confidence else 0.0,
                    "earliest_date": stats_result.earliest_date.isoformat() if stats_result.earliest_date else None,
                    "latest_date": stats_result.latest_date.isoformat() if stats_result.latest_date else None
                },
                "event_type_distribution": [
                    {"event_type": row.event_type, "count": row.count}
                    for row in type_result
                ],
                "relationship_statistics": [
                    {
                        "relationship_type": row.relationship_type,
                        "count": row.count,
                        "avg_strength": float(row.avg_strength) if row.avg_strength else 0.0
                    }
                    for row in rel_result
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error getting timeline statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/timeline/{storyline_id}/verify-event/")
async def verify_event(
    storyline_id: str,
    event_id: str,
    verification_source: str,
    verification_notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Verify a chronological event"""
    try:
        from sqlalchemy import text
        
        update_query = text("""
            UPDATE chronological_events
            SET verified = true, verification_source = :verification_source,
                verification_notes = :verification_notes, updated_at = CURRENT_TIMESTAMP
            WHERE event_id = :event_id AND storyline_id = :storyline_id
            RETURNING id, title
        """)
        
        result = db.execute(update_query, {
            "event_id": event_id,
            "storyline_id": storyline_id,
            "verification_source": verification_source,
            "verification_notes": verification_notes
        }).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Event not found")
        
        db.commit()
        
        return {
            "success": True,
            "message": "Event verified successfully",
            "data": {
                "event_id": event_id,
                "title": result.title,
                "verification_source": verification_source,
                "verification_notes": verification_notes,
                "verified_at": datetime.now().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying event: {e}")
        raise HTTPException(status_code=500, detail=str(e))
