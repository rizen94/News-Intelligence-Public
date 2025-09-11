"""
News Intelligence System v3.0 - Intelligence API Routes
Provides intelligence data, insights, analysis, and ML processing status
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from config.database import get_db
from schemas.robust_schemas import APIResponse

logger = logging.getLogger(__name__)

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

@router.get("/morning-briefing", response_model=APIResponse)
async def get_morning_briefing(
    date: Optional[str] = Query(None, description="Date for briefing (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Get morning briefing with highlights and AI-generated summary"""
    try:
        from modules.ml.daily_briefing_service import DailyBriefingService
        from config.database import get_db_config
        
        # Get database config
        db_config = get_db_config()
        
        # Initialize briefing service
        briefing_service = DailyBriefingService(db_config)
        
        # Parse date if provided
        briefing_date = None
        if date:
            briefing_date = datetime.strptime(date, '%Y-%m-%d')
        
        # Generate briefing
        briefing = briefing_service.generate_daily_briefing(
            briefing_date=briefing_date,
            include_deduplication=True,
            include_storylines=True
        )
        
        return APIResponse(
            success=True,
            data=briefing,
            message="Morning briefing generated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error generating morning briefing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trending-topics", response_model=APIResponse)
async def get_trending_topics(
    time_period: str = Query("24h", description="Time period (1h, 24h, 7d, 30d)"),
    limit: int = Query(10, ge=1, le=50, description="Number of topics to return"),
    db: Session = Depends(get_db)
):
    """Get trending topics based on article analysis"""
    try:
        # Parse time period
        period_hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(time_period, 24)
        
        # Get trending topics from articles
        trending_query = text(f"""
            SELECT 
                category,
                COUNT(*) as article_count,
                AVG(quality_score) as avg_quality,
                AVG(sentiment_score) as avg_sentiment,
                COUNT(DISTINCT source) as source_diversity
            FROM articles 
            WHERE status = 'processed' 
            AND created_at > NOW() - INTERVAL '{period_hours} hours'
            AND category IS NOT NULL
            GROUP BY category
            ORDER BY article_count DESC, avg_quality DESC
            LIMIT :limit
        """)
        
        result = db.execute(trending_query, {"limit": limit}).fetchall()
        
        trending_topics = []
        for i, row in enumerate(result):
            topic = {
                "id": f"trend_{i+1}",
                "name": row[0],
                "article_count": row[1],
                "avg_quality": float(row[2]) if row[2] else 0.0,
                "avg_sentiment": float(row[3]) if row[3] else 0.0,
                "source_diversity": row[4],
                "trend_score": float(row[1]) * float(row[2]) if row[2] else 0.0,
                "time_period": time_period
            }
            trending_topics.append(topic)
        
        return APIResponse(
            success=True,
            data={
                "trending_topics": trending_topics,
                "time_period": time_period,
                "total_topics": len(trending_topics),
                "generated_at": datetime.now().isoformat()
            },
            message=f"Retrieved {len(trending_topics)} trending topics"
        )
        
    except Exception as e:
        logger.error(f"Error getting trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topic-clusters", response_model=APIResponse)
async def get_topic_clusters(
    min_articles: int = Query(3, ge=1, description="Minimum articles per cluster"),
    time_period: str = Query("7d", description="Time period (1d, 7d, 30d)"),
    db: Session = Depends(get_db)
):
    """Get topic clusters based on article similarity"""
    try:
        # Parse time period
        period_days = {"1d": 1, "7d": 7, "30d": 30}.get(time_period, 7)
        
        # Get articles for clustering
        articles_query = text(f"""
            SELECT 
                id, title, content, category, tags, entities, quality_score,
                created_at, source
            FROM articles 
            WHERE status = 'processed' 
            AND created_at > NOW() - INTERVAL '{period_days} days'
            AND quality_score > 0.5
            ORDER BY quality_score DESC
            LIMIT 1000
        """)
        
        articles = db.execute(articles_query).fetchall()
        
        # Simple clustering based on category and tags
        clusters = {}
        for article in articles:
            category = article[3] or "general"
            tags = article[4] or []
            
            # Create cluster key
            cluster_key = f"{category}_{len(tags)}"
            
            if cluster_key not in clusters:
                clusters[cluster_key] = {
                    "id": f"cluster_{len(clusters) + 1}",
                    "name": f"{category.title()} Cluster",
                    "category": category,
                    "articles": [],
                    "article_count": 0,
                    "avg_quality": 0.0,
                    "sources": set(),
                    "tags": set()
                }
            
            cluster = clusters[cluster_key]
            cluster["articles"].append({
                "id": article[0],
                "title": article[1],
                "quality_score": float(article[6]) if article[6] else 0.0
            })
            cluster["article_count"] += 1
            cluster["sources"].add(article[8])
            if tags:
                cluster["tags"].update(tags)
        
        # Filter clusters by minimum articles and calculate metrics
        filtered_clusters = []
        for cluster in clusters.values():
            if cluster["article_count"] >= min_articles:
                # Calculate average quality
                total_quality = sum(article["quality_score"] for article in cluster["articles"])
                cluster["avg_quality"] = total_quality / cluster["article_count"]
                
                # Convert sets to lists
                cluster["sources"] = list(cluster["sources"])
                cluster["tags"] = list(cluster["tags"])
                
                # Remove articles list for response (keep only count)
                del cluster["articles"]
                
                filtered_clusters.append(cluster)
        
        # Sort by article count and quality
        filtered_clusters.sort(key=lambda x: (x["article_count"], x["avg_quality"]), reverse=True)
        
        return APIResponse(
            success=True,
            data={
                "clusters": filtered_clusters,
                "total_clusters": len(filtered_clusters),
                "time_period": time_period,
                "min_articles": min_articles,
                "generated_at": datetime.now().isoformat()
            },
            message=f"Retrieved {len(filtered_clusters)} topic clusters"
        )
        
    except Exception as e:
        logger.error(f"Error getting topic clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/discovery", response_model=APIResponse)
async def discover_content(
    search_query: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    source: Optional[str] = Query(None, description="Filter by source"),
    min_quality: float = Query(0.5, ge=0.0, le=1.0, description="Minimum quality score"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    db: Session = Depends(get_db)
):
    """Discover articles with advanced search and filtering"""
    try:
        # Build search query
        where_conditions = ["status = 'processed'", "quality_score >= :min_quality"]
        params = {"min_quality": min_quality, "limit": limit}
        
        if search_query:
            where_conditions.append("(title ILIKE :search OR content ILIKE :search OR summary ILIKE :search)")
            params["search"] = f"%{search_query}%"
        
        if category:
            where_conditions.append("category = :category")
            params["category"] = category
            
        if source:
            where_conditions.append("source = :source")
            params["source"] = source
        
        where_clause = " AND ".join(where_conditions)
        
        # Execute search
        search_query_sql = text(f"""
            SELECT 
                id, title, content, summary, url, source, category, 
                quality_score, sentiment_score, tags, entities,
                created_at, published_at, word_count, reading_time
            FROM articles 
            WHERE {where_clause}
            ORDER BY quality_score DESC, created_at DESC
            LIMIT :limit
        """)
        
        results = db.execute(search_query_sql, params).fetchall()
        
        # Format results
        articles = []
        for row in results:
            article = {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "summary": row[3],
                "url": row[4],
                "source": row[5],
                "category": row[6],
                "quality_score": float(row[7]) if row[7] else 0.0,
                "sentiment_score": float(row[8]) if row[8] else 0.0,
                "tags": row[9] if row[9] else [],
                "entities": row[10] if row[10] else {},
                "created_at": row[11].isoformat() if row[11] else None,
                "published_at": row[12].isoformat() if row[12] else None,
                "word_count": row[13] if row[13] else 0,
                "reading_time": row[14] if row[14] else 0
            }
            articles.append(article)
        
        # Get discovery statistics
        stats_query = text(f"""
            SELECT 
                COUNT(*) as total_articles,
                COUNT(DISTINCT category) as category_count,
                COUNT(DISTINCT source) as source_count,
                AVG(quality_score) as avg_quality
            FROM articles 
            WHERE {where_clause}
        """)
        
        stats = db.execute(stats_query, params).fetchone()
        
        return APIResponse(
            success=True,
            data={
                "articles": articles,
                "total_results": len(articles),
                "search_query": search_query,
                "filters": {
                    "category": category,
                    "source": source,
                    "min_quality": min_quality
                },
                "statistics": {
                    "total_articles": stats[0] or 0,
                    "category_count": stats[1] or 0,
                    "source_count": stats[2] or 0,
                    "avg_quality": float(stats[3]) if stats[3] else 0.0
                },
                "generated_at": datetime.now().isoformat()
            },
            message=f"Found {len(articles)} articles matching criteria"
        )
        
    except Exception as e:
        logger.error(f"Error discovering content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/highlights", response_model=APIResponse)
async def get_highlights(
    highlight_type: str = Query("daily", description="Type of highlights (daily, weekly, breaking)"),
    limit: int = Query(5, ge=1, le=20, description="Number of highlights"),
    db: Session = Depends(get_db)
):
    """Get news highlights based on type"""
    try:
        if highlight_type == "breaking":
            # Get breaking news (high quality, recent)
            highlights_query = text("""
                SELECT 
                    id, title, content, summary, source, category,
                    quality_score, created_at, published_at
                FROM articles 
                WHERE status = 'processed' 
                AND quality_score > 0.8
                AND created_at > NOW() - INTERVAL '6 hours'
                ORDER BY quality_score DESC, created_at DESC
                LIMIT :limit
            """)
        elif highlight_type == "weekly":
            # Get weekly highlights (high quality, last 7 days)
            highlights_query = text("""
                SELECT 
                    id, title, content, summary, source, category,
                    quality_score, created_at, published_at
                FROM articles 
                WHERE status = 'processed' 
                AND quality_score > 0.7
                AND created_at > NOW() - INTERVAL '7 days'
                ORDER BY quality_score DESC, created_at DESC
                LIMIT :limit
            """)
        else:  # daily
            # Get daily highlights (high quality, last 24 hours)
            highlights_query = text("""
                SELECT 
                    id, title, content, summary, source, category,
                    quality_score, created_at, published_at
                FROM articles 
                WHERE status = 'processed' 
                AND quality_score > 0.6
                AND created_at > NOW() - INTERVAL '24 hours'
                ORDER BY quality_score DESC, created_at DESC
                LIMIT :limit
            """)
        
        results = db.execute(highlights_query, {"limit": limit}).fetchall()
        
        highlights = []
        for i, row in enumerate(results):
            highlight = {
                "id": f"highlight_{i+1}",
                "article_id": row[0],
                "title": row[1],
                "content": row[2],
                "summary": row[3],
                "source": row[4],
                "category": row[5],
                "quality_score": float(row[6]) if row[6] else 0.0,
                "created_at": row[7].isoformat() if row[7] else None,
                "published_at": row[8].isoformat() if row[8] else None,
                "highlight_type": highlight_type
            }
            highlights.append(highlight)
        
        return APIResponse(
            success=True,
            data={
                "highlights": highlights,
                "highlight_type": highlight_type,
                "total_highlights": len(highlights),
                "generated_at": datetime.now().isoformat()
            },
            message=f"Retrieved {len(highlights)} {highlight_type} highlights"
        )
        
    except Exception as e:
        logger.error(f"Error getting highlights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-endpoint", response_model=APIResponse)
async def test_endpoint():
    """Test endpoint to verify route registration"""
    return APIResponse(
        success=True,
        data={"message": "Test endpoint working"},
        message="Test endpoint is working"
    )

# Health check endpoint
@router.get("/health", response_model=APIResponse)
async def health_check():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        data={"status": "healthy", "timestamp": datetime.now().isoformat()},
        message="Intelligence service is healthy"
    )

