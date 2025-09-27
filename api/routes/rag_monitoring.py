"""
RAG Monitoring and Tracking Routes
Provides comprehensive monitoring and validation for RAG system activities
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import logging
from config.database import get_db
from sqlalchemy import text
import json

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/rag-activity")
async def get_rag_activity(
    hours: int = Query(24, description="Hours to look back for activity"),
    storyline_id: Optional[str] = Query(None, description="Filter by specific storyline")
):
    """Get RAG activity summary for the specified time period"""
    try:        try:
            # Calculate time threshold
            time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            # Base query for RAG context updates
            base_query = """
                SELECT 
                    src.storyline_id,
                    s.title as storyline_title,
                    src.created_at,
                    src.updated_at,
                    LENGTH(src.rag_data::text) as rag_data_size,
                    src.rag_data->'wikipedia'->'articles' as wikipedia_articles,
                    src.rag_data->'gdelt'->'events' as gdelt_events,
                    src.rag_data->'extracted_entities' as extracted_entities,
                    src.rag_data->'extracted_topics' as extracted_topics
                FROM storyline_rag_context src
                JOIN storylines s ON src.storyline_id = s.id
                WHERE src.updated_at >= :time_threshold
            """
            
            params = {"time_threshold": time_threshold}
            
            if storyline_id:
                base_query += " AND src.storyline_id = :storyline_id"
                params["storyline_id"] = storyline_id
            
            base_query += " ORDER BY src.updated_at DESC"
            
            result = db.execute(text(base_query), params).fetchall()
            
            activities = []
            total_wikipedia_articles = 0
            total_gdelt_events = 0
            total_entities = 0
            total_topics = 0
            
            for row in result:
                # Handle JSON data properly
                wikipedia_articles = row[5] if isinstance(row[5], list) else (json.loads(row[5]) if row[5] else [])
                gdelt_events = row[6] if isinstance(row[6], list) else (json.loads(row[6]) if row[6] else [])
                entities = row[7] if isinstance(row[7], list) else (json.loads(row[7]) if row[7] else [])
                topics = row[8] if isinstance(row[8], list) else (json.loads(row[8]) if row[8] else [])
                
                activities.append({
                    "storyline_id": row[0],
                    "storyline_title": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None,
                    "rag_data_size": row[4],
                    "wikipedia_articles_count": len(wikipedia_articles),
                    "gdelt_events_count": len(gdelt_events),
                    "entities_count": len(entities),
                    "topics_count": len(topics),
                    "wikipedia_articles": wikipedia_articles[:5],  # Show first 5
                    "entities": entities[:10],  # Show first 10
                    "topics": topics
                })
                
                total_wikipedia_articles += len(wikipedia_articles)
                total_gdelt_events += len(gdelt_events)
                total_entities += len(entities)
                total_topics += len(topics)
            
            return {
                "success": True,
                "data": {
                    "time_period_hours": hours,
                    "total_activities": len(activities),
                    "summary": {
                        "total_wikipedia_articles": total_wikipedia_articles,
                        "total_gdelt_events": total_gdelt_events,
                        "total_entities": total_entities,
                        "total_topics": total_topics,
                        "avg_rag_data_size": sum(a["rag_data_size"] for a in activities) / len(activities) if activities else 0
                    },
                    "activities": activities
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting RAG activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get RAG activity: {str(e)}")

@router.get("/rag-performance")
async def get_rag_performance(
    days: int = Query(7, description="Days to look back for performance metrics")
):
    """Get RAG system performance metrics"""
    try:        try:
            time_threshold = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Get RAG enhancement statistics
            stats_query = text("""
                SELECT 
                    COUNT(*) as total_enhancements,
                    COUNT(CASE WHEN updated_at >= :time_threshold THEN 1 END) as recent_enhancements,
                    AVG(LENGTH(rag_data::text)) as avg_data_size,
                    MAX(updated_at) as last_enhancement,
                    MIN(updated_at) as first_enhancement
                FROM storyline_rag_context
            """)
            
            stats_result = db.execute(stats_query, {"time_threshold": time_threshold}).fetchone()
            
            # Get storyline RAG status
            storyline_query = text("""
                SELECT 
                    s.id,
                    s.title,
                    s.rag_enhanced_at,
                    s.rag_context_summary,
                    CASE 
                        WHEN s.rag_enhanced_at IS NULL THEN 'never_enhanced'
                        WHEN s.rag_enhanced_at < :time_threshold THEN 'needs_refresh'
                        ELSE 'recently_enhanced'
                    END as rag_status
                FROM storylines s
                WHERE s.status = 'active'
                ORDER BY s.rag_enhanced_at DESC NULLS LAST
            """)
            
            storyline_result = db.execute(storyline_query, {"time_threshold": time_threshold}).fetchall()
            
            storylines = []
            never_enhanced = 0
            needs_refresh = 0
            recently_enhanced = 0
            
            for row in storyline_result:
                storylines.append({
                    "id": row[0],
                    "title": row[1],
                    "rag_enhanced_at": row[2].isoformat() if row[2] else None,
                    "rag_context_summary": row[3],
                    "rag_status": row[4]
                })
                
                if row[4] == 'never_enhanced':
                    never_enhanced += 1
                elif row[4] == 'needs_refresh':
                    needs_refresh += 1
                else:
                    recently_enhanced += 1
            
            return {
                "success": True,
                "data": {
                    "time_period_days": days,
                    "performance_metrics": {
                        "total_enhancements": stats_result[0] or 0,
                        "recent_enhancements": stats_result[1] or 0,
                        "avg_data_size": float(stats_result[2]) if stats_result[2] else 0,
                        "last_enhancement": stats_result[3].isoformat() if stats_result[3] else None,
                        "first_enhancement": stats_result[4].isoformat() if stats_result[4] else None
                    },
                    "storyline_status": {
                        "total_storylines": len(storylines),
                        "never_enhanced": never_enhanced,
                        "needs_refresh": needs_refresh,
                        "recently_enhanced": recently_enhanced
                    },
                    "storylines": storylines
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting RAG performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get RAG performance: {str(e)}")

@router.get("/rag-validation/{storyline_id}")
async def validate_rag_enhancement(storyline_id: str, db: Session = Depends(get_db)):
    """Validate RAG enhancement quality for a specific storyline"""
    try:
            # Get RAG context for storyline
            rag_query = text("""
                SELECT 
                    src.rag_data,
                    src.created_at,
                    src.updated_at,
                    s.title as storyline_title
                FROM storyline_rag_context src
                JOIN storylines s ON src.storyline_id = s.id
                WHERE src.storyline_id = :storyline_id
            """)
            
            rag_result = db.execute(rag_query, {"storyline_id": storyline_id}).fetchone()
            
            if not rag_result:
                return {
                    "success": False,
                    "message": "No RAG context found for this storyline"
                }
            
            rag_data = json.loads(rag_result[0]) if isinstance(rag_result[0], str) else rag_result[0]
            
            # Validate RAG data quality
            validation_results = {
                "storyline_id": storyline_id,
                "storyline_title": rag_result[3],
                "created_at": rag_result[1].isoformat() if rag_result[1] else None,
                "updated_at": rag_result[2].isoformat() if rag_result[2] else None,
                "validation_scores": {},
                "issues": [],
                "recommendations": []
            }
            
            # Check Wikipedia articles
            wikipedia = rag_data.get('wikipedia', {})
            wikipedia_articles = wikipedia.get('articles', [])
            wikipedia_error = wikipedia.get('error')
            
            if wikipedia_error:
                validation_results["issues"].append(f"Wikipedia API error: {wikipedia_error}")
                validation_results["validation_scores"]["wikipedia"] = 0
            else:
                validation_results["validation_scores"]["wikipedia"] = min(100, len(wikipedia_articles) * 10)
                if len(wikipedia_articles) < 3:
                    validation_results["issues"].append("Few Wikipedia articles found")
                    validation_results["recommendations"].append("Consider expanding topic keywords")
            
            # Check GDELT events
            gdelt = rag_data.get('gdelt', {})
            gdelt_events = gdelt.get('events', [])
            gdelt_error = gdelt.get('error')
            
            if gdelt_error:
                validation_results["issues"].append(f"GDELT API error: {gdelt_error}")
                validation_results["validation_scores"]["gdelt"] = 0
            else:
                validation_results["validation_scores"]["gdelt"] = min(100, len(gdelt_events) * 20)
                if len(gdelt_events) == 0:
                    validation_results["issues"].append("No GDELT events found")
                    validation_results["recommendations"].append("Consider using more specific entity names")
            
            # Check entities
            entities = rag_data.get('extracted_entities', [])
            validation_results["validation_scores"]["entities"] = min(100, len(entities) * 5)
            if len(entities) < 5:
                validation_results["issues"].append("Few entities extracted")
                validation_results["recommendations"].append("Review entity extraction settings")
            
            # Check topics
            topics = rag_data.get('extracted_topics', [])
            validation_results["validation_scores"]["topics"] = min(100, len(topics) * 12)
            if len(topics) < 3:
                validation_results["issues"].append("Few topics extracted")
                validation_results["recommendations"].append("Review topic extraction keywords")
            
            # Calculate overall score
            scores = validation_results["validation_scores"]
            overall_score = sum(scores.values()) / len(scores) if scores else 0
            validation_results["overall_score"] = round(overall_score, 1)
            
            # Add quality assessment
            if overall_score >= 80:
                validation_results["quality"] = "excellent"
            elif overall_score >= 60:
                validation_results["quality"] = "good"
            elif overall_score >= 40:
                validation_results["quality"] = "fair"
            else:
                validation_results["quality"] = "poor"
            
            return {
                "success": True,
                "data": validation_results
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error validating RAG enhancement: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate RAG enhancement: {str(e)}")

@router.get("/rag-logs")
async def get_rag_logs(
    limit: int = Query(50, description="Number of log entries to return"),
    level: str = Query("INFO", description="Log level filter")
):
    """Get RAG-related log entries"""
    try:
        # This would typically query a log database or file
        # For now, we'll return a placeholder structure
        return {
            "success": True,
            "data": {
                "message": "RAG logs endpoint - implementation needed",
                "note": "This would typically query application logs for RAG-related entries",
                "suggested_implementation": "Query log files or log database for entries containing 'rag' or 'RAG'"
            }
        }
    except Exception as e:
        logger.error(f"Error getting RAG logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get RAG logs: {str(e)}")
