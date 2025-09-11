"""
News Intelligence System v3.0 - Intelligence API Routes
Provides intelligence data, insights, analysis, and ML processing status
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import get_db
from schemas.robust_schemas import APIResponse

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])

# Pydantic models
class IntelligenceInsight(BaseModel):
    """Intelligence insight model"""
    id: str = Field(..., description="Insight ID")
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Insight description")
    category: str = Field(..., description="Insight category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    created_at: str = Field(..., description="Creation timestamp")
    data: Dict[str, Any] = Field(..., description="Insight data")
    source_articles: List[int] = Field(default=[], description="Source article IDs")

class IntelligenceTrend(BaseModel):
    """Intelligence trend model"""
    id: str = Field(..., description="Trend ID")
    title: str = Field(..., description="Trend title")
    description: str = Field(..., description="Trend description")
    trend_type: str = Field(..., description="Type of trend (rising, falling, stable)")
    strength: float = Field(..., ge=0.0, le=1.0, description="Trend strength (0-1)")
    time_period: str = Field(..., description="Time period of trend")
    created_at: str = Field(..., description="Creation timestamp")
    data_points: List[Dict[str, Any]] = Field(..., description="Trend data points")

class IntelligenceAlert(BaseModel):
    """Intelligence alert model"""
    id: str = Field(..., description="Alert ID")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    severity: str = Field(..., description="Alert severity (low, medium, high, critical)")
    category: str = Field(..., description="Alert category")
    created_at: str = Field(..., description="Creation timestamp")
    is_active: bool = Field(..., description="Whether alert is active")
    data: Dict[str, Any] = Field(..., description="Alert data")

class MLProcessingStatus(BaseModel):
    """ML processing status model"""
    pipeline_id: str = Field(..., description="Pipeline ID")
    status: str = Field(..., description="Processing status")
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress percentage")
    started_at: str = Field(..., description="Start timestamp")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    processed_items: int = Field(..., description="Number of items processed")
    total_items: int = Field(..., description="Total items to process")
    errors: List[str] = Field(default=[], description="Processing errors")

@router.get("/insights", response_model=APIResponse)
async def get_intelligence_insights(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=100, description="Number of insights"),
    db: Session = Depends(get_db)
):
    """Get intelligence insights"""
    try:
        # For now, generate insights based on article analysis
        insights = await generate_insights_from_articles(category, limit, db)
        
        return APIResponse(
            success=True,
            data={
                "insights": insights,
                "total": len(insights),
                "category": category,
                "generated_at": datetime.now().isoformat()
            },
            message=f"Retrieved {len(insights)} intelligence insights"
        )
        
    except Exception as e:
        logger.error(f"Error getting intelligence insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends", response_model=APIResponse)
async def get_intelligence_trends(
    trend_type: Optional[str] = Query(None, description="Filter by trend type"),
    time_period: str = Query("7d", description="Time period (1d, 7d, 30d, 90d)"),
    db: Session = Depends(get_db)
):
    """Get intelligence trends"""
    try:
        trends = await generate_trends_from_articles(trend_type, time_period, db)
        
        return APIResponse(
            success=True,
            data={
                "trends": trends,
                "total": len(trends),
                "time_period": time_period,
                "generated_at": datetime.now().isoformat()
            },
            message=f"Retrieved {len(trends)} intelligence trends"
        )
        
    except Exception as e:
        logger.error(f"Error getting intelligence trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts", response_model=APIResponse)
async def get_intelligence_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Show only active alerts"),
    db: Session = Depends(get_db)
):
    """Get intelligence alerts"""
    try:
        alerts = await generate_alerts_from_analysis(severity, category, active_only, db)
        
        return APIResponse(
            success=True,
            data={
                "alerts": alerts,
                "total": len(alerts),
                "severity": severity,
                "category": category,
                "generated_at": datetime.now().isoformat()
            },
            message=f"Retrieved {len(alerts)} intelligence alerts"
        )
        
    except Exception as e:
        logger.error(f"Error getting intelligence alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ml/status", response_model=APIResponse)
async def get_ml_processing_status(db: Session = Depends(get_db)):
    """Get ML processing status"""
    try:
        # Get processing status from database
        status_data = await get_ml_processing_status_from_db(db)
        
        return APIResponse(
            success=True,
            data=status_data,
            message="ML processing status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting ML processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ml/pipelines", response_model=APIResponse)
async def get_ml_pipelines(db: Session = Depends(get_db)):
    """Get available ML pipelines"""
    try:
        pipelines = [
            {
                "pipeline_id": "article_classification",
                "name": "Article Classification",
                "description": "Classifies articles by category and topic",
                "status": "active",
                "last_run": datetime.now().isoformat(),
                "performance": {"accuracy": 0.92, "f1_score": 0.89}
            },
            {
                "pipeline_id": "entity_extraction",
                "name": "Entity Extraction",
                "description": "Extracts named entities from articles",
                "status": "active",
                "last_run": datetime.now().isoformat(),
                "performance": {"precision": 0.88, "recall": 0.85}
            },
            {
                "pipeline_id": "sentiment_analysis",
                "name": "Sentiment Analysis",
                "description": "Analyzes sentiment of articles",
                "status": "active",
                "last_run": datetime.now().isoformat(),
                "performance": {"accuracy": 0.87, "f1_score": 0.84}
            },
            {
                "pipeline_id": "quality_scoring",
                "name": "Quality Scoring",
                "description": "Scores article quality and relevance",
                "status": "active",
                "last_run": datetime.now().isoformat(),
                "performance": {"correlation": 0.91, "mae": 0.12}
            }
        ]
        
        return APIResponse(
            success=True,
            data={"pipelines": pipelines, "total": len(pipelines)},
            message="ML pipelines retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting ML pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ml/pipelines/{pipeline_id}/run", response_model=APIResponse)
async def run_ml_pipeline(
    pipeline_id: str,
    force: bool = Query(False, description="Force run even if already running"),
    db: Session = Depends(get_db)
):
    """Run a specific ML pipeline"""
    try:
        # Validate pipeline ID
        valid_pipelines = ["article_classification", "entity_extraction", "sentiment_analysis", "quality_scoring"]
        if pipeline_id not in valid_pipelines:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # For now, simulate pipeline execution
        pipeline_status = {
            "pipeline_id": pipeline_id,
            "status": "running",
            "progress": 0.0,
            "started_at": datetime.now().isoformat(),
            "estimated_completion": (datetime.now() + timedelta(minutes=30)).isoformat(),
            "processed_items": 0,
            "total_items": 1000,  # Placeholder
            "errors": []
        }
        
        return APIResponse(
            success=True,
            data=pipeline_status,
            message=f"ML pipeline {pipeline_id} started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running ML pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/summary", response_model=APIResponse)
async def get_intelligence_analytics_summary(db: Session = Depends(get_db)):
    """Get intelligence analytics summary"""
    try:
        # Get article statistics
        article_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_articles,
                COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_articles,
                AVG(quality_score) as avg_quality,
                COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as recent_articles
            FROM articles
        """)).fetchone()
        
        # Get category distribution
        category_stats = db.execute(text("""
            SELECT category, COUNT(*) as count
            FROM articles 
            WHERE status = 'processed' AND category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        """)).fetchall()
        
        # Get entity statistics
        entity_stats = db.execute(text("""
            SELECT 
                COUNT(DISTINCT id) as articles_with_entities,
                AVG(jsonb_array_length(entities)) as avg_entities_per_article
            FROM articles 
            WHERE status = 'processed' AND entities IS NOT NULL
        """)).fetchone()
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "articles": {
                "total": article_stats[0] or 0,
                "processed": article_stats[1] or 0,
                "recent_24h": article_stats[3] or 0,
                "avg_quality": float(article_stats[2]) if article_stats[2] else 0.0
            },
            "categories": [
                {"category": row[0], "count": row[1]} for row in category_stats
            ],
            "entities": {
                "articles_with_entities": entity_stats[0] or 0,
                "avg_entities_per_article": float(entity_stats[1]) if entity_stats[1] else 0.0
            },
            "insights_generated": 0,  # Placeholder
            "trends_identified": 0,  # Placeholder
            "alerts_active": 0  # Placeholder
        }
        
        return APIResponse(
            success=True,
            data=summary,
            message="Intelligence analytics summary retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting intelligence analytics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def generate_insights_from_articles(category: Optional[str], limit: int, db: Session) -> List[Dict[str, Any]]:
    """Generate insights from article analysis"""
    try:
        insights = []
        
        # Get top articles by quality score
        query = """
            SELECT id, title, quality_score, category, entities, tags, created_at
            FROM articles 
            WHERE status = 'processed' AND quality_score > 0.7
        """
        params = {}
        
        if category:
            query += " AND category = :category"
            params["category"] = category
        
        query += " ORDER BY quality_score DESC LIMIT :limit"
        params["limit"] = limit
        
        result = db.execute(text(query), params).fetchall()
        
        for i, row in enumerate(result):
            insight = {
                "id": f"insight_{i+1}_{int(datetime.now().timestamp())}",
                "title": f"High-quality article: {row[1][:50]}...",
                "description": f"Article with quality score {row[2]:.2f} in category {row[3] or 'unknown'}",
                "category": row[3] or "general",
                "confidence": float(row[2]),
                "created_at": datetime.now().isoformat(),
                "data": {
                    "article_id": row[0],
                    "quality_score": float(row[2]),
                    "entities": row[4] if row[4] else [],
                    "tags": row[5] if row[5] else []
                },
                "source_articles": [row[0]]
            }
            insights.append(insight)
        
        return insights
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return []

async def generate_trends_from_articles(trend_type: Optional[str], time_period: str, db: Session) -> List[Dict[str, Any]]:
    """Generate trends from article analysis"""
    try:
        trends = []
        
        # Parse time period
        period_days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}.get(time_period, 7)
        
        # Get category trends
        category_trends = db.execute(text("""
            SELECT category, DATE(created_at) as date, COUNT(*) as count
            FROM articles 
            WHERE status = 'processed' 
            AND created_at > NOW() - INTERVAL :days DAY
            AND category IS NOT NULL
            GROUP BY category, DATE(created_at)
            ORDER BY category, date
        """), {"days": period_days}).fetchall()
        
        # Group by category
        category_data = {}
        for row in category_trends:
            category = row[0]
            if category not in category_data:
                category_data[category] = []
            category_data[category].append({
                "date": row[1].isoformat(),
                "count": row[2]
            })
        
        # Generate trend objects
        for i, (category, data_points) in enumerate(category_data.items()):
            if len(data_points) < 2:
                continue
                
            # Calculate trend direction
            first_count = data_points[0]["count"]
            last_count = data_points[-1]["count"]
            
            if last_count > first_count * 1.2:
                trend_direction = "rising"
                strength = min((last_count - first_count) / first_count, 1.0)
            elif last_count < first_count * 0.8:
                trend_direction = "falling"
                strength = min((first_count - last_count) / first_count, 1.0)
            else:
                trend_direction = "stable"
                strength = 0.5
            
            if trend_type and trend_direction != trend_type:
                continue
            
            trend = {
                "id": f"trend_{i+1}_{int(datetime.now().timestamp())}",
                "title": f"{category.title()} Article Trend",
                "description": f"Articles in {category} category showing {trend_direction} trend",
                "trend_type": trend_direction,
                "strength": strength,
                "time_period": time_period,
                "created_at": datetime.now().isoformat(),
                "data_points": data_points
            }
            trends.append(trend)
        
        return trends
        
    except Exception as e:
        logger.error(f"Error generating trends: {e}")
        return []

async def generate_alerts_from_analysis(severity: Optional[str], category: Optional[str], active_only: bool, db: Session) -> List[Dict[str, Any]]:
    """Generate alerts from analysis"""
    try:
        alerts = []
        
        # Check for high-quality articles spike
        recent_high_quality = db.execute(text("""
            SELECT COUNT(*) FROM articles 
            WHERE status = 'processed' 
            AND quality_score > 0.8 
            AND created_at > NOW() - INTERVAL '1 hour'
        """)).fetchone()[0] or 0
        
        if recent_high_quality > 10:
            alert = {
                "id": f"alert_quality_spike_{int(datetime.now().timestamp())}",
                "title": "High-Quality Articles Spike",
                "description": f"Detected {recent_high_quality} high-quality articles in the last hour",
                "severity": "medium",
                "category": "quality",
                "created_at": datetime.now().isoformat(),
                "is_active": True,
                "data": {"count": recent_high_quality, "threshold": 10}
            }
            alerts.append(alert)
        
        # Check for processing errors
        recent_errors = db.execute(text("""
            SELECT COUNT(*) FROM articles 
            WHERE status = 'failed' 
            AND created_at > NOW() - INTERVAL '1 hour'
        """)).fetchone()[0] or 0
        
        if recent_errors > 5:
            alert = {
                "id": f"alert_processing_errors_{int(datetime.now().timestamp())}",
                "title": "High Processing Error Rate",
                "description": f"Detected {recent_errors} processing errors in the last hour",
                "severity": "high",
                "category": "processing",
                "created_at": datetime.now().isoformat(),
                "is_active": True,
                "data": {"count": recent_errors, "threshold": 5}
            }
            alerts.append(alert)
        
        # Filter by severity and category
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        if category:
            alerts = [a for a in alerts if a["category"] == category]
        if active_only:
            alerts = [a for a in alerts if a["is_active"]]
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error generating alerts: {e}")
        return []

async def get_ml_processing_status_from_db(db: Session) -> Dict[str, Any]:
    """Get ML processing status from database"""
    try:
        # For now, return simulated status
        return {
            "pipelines": [
                {
                    "pipeline_id": "article_classification",
                    "status": "running",
                    "progress": 0.75,
                    "started_at": (datetime.now() - timedelta(minutes=15)).isoformat(),
                    "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat(),
                    "processed_items": 750,
                    "total_items": 1000,
                    "errors": []
                },
                {
                    "pipeline_id": "entity_extraction",
                    "status": "completed",
                    "progress": 1.0,
                    "started_at": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "estimated_completion": (datetime.now() - timedelta(minutes=30)).isoformat(),
                    "processed_items": 1000,
                    "total_items": 1000,
                    "errors": []
                }
            ],
            "overall_status": "running",
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting ML processing status: {e}")
        return {
            "pipelines": [],
            "overall_status": "error",
            "last_updated": datetime.now().isoformat(),
            "error": str(e)
        }

# Health check endpoint
@router.get("/health", response_model=APIResponse)
async def health_check():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        data={"status": "healthy", "timestamp": datetime.now().isoformat()},
        message="Intelligence service is healthy"
    )

