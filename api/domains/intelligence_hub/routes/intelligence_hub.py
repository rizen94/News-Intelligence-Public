"""
Domain 4: Intelligence Hub Routes
Handles predictive analytics, trend analysis, and strategic insights
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/intelligence-hub",
    tags=["Intelligence Hub"],
    responses={404: {"description": "Not found"}}
)

@router.get("/health")
async def health_check():
    """Health check for Intelligence Hub domain"""
    try:
        # Check LLM service
        llm_status = await llm_service.get_model_status()
        
        return {
            "success": True,
            "domain": "intelligence_hub",
            "status": "healthy",
            "llm_service": llm_status,
            "primary_model": "llama3.1:8b",
            "secondary_model": "mistral:7b",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "intelligence_hub",
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/insights")
async def get_intelligence_insights(
    insight_type: Optional[str] = None,
    limit: int = 20,
    active_only: bool = True
):
    """Get intelligence insights"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Build query with filters
            where_conditions = []
            params = []
            
            if insight_type:
                where_conditions.append("insight_type = %s")
                params.append(insight_type)
            
            if active_only:
                where_conditions.append("is_active = true")
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, insight_type, insight_title, insight_description,
                           insight_data, confidence_score, relevance_score,
                           created_at, updated_at, expires_at
                    FROM intelligence_insights 
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, params + [limit])
                
                insights = []
                for row in cur.fetchall():
                    insights.append({
                        "id": row[0],
                        "insight_type": row[1],
                        "title": row[2],
                        "description": row[3],
                        "data": row[4],
                        "confidence_score": row[5],
                        "relevance_score": row[6],
                        "created_at": row[7].isoformat() if row[7] else None,
                        "updated_at": row[8].isoformat() if row[8] else None,
                        "expires_at": row[9].isoformat() if row[9] else None
                    })
                
                return {
                    "success": True,
                    "data": {"insights": insights},
                    "count": len(insights),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/insights/generate")
async def generate_intelligence_insights(background_tasks: BackgroundTasks):
    """Generate new intelligence insights using LLM"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get recent articles for analysis
                cur.execute("""
                    SELECT id, title, content, source, published_at, summary
                    FROM articles 
                    WHERE created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (datetime.now() - timedelta(days=7),))
                
                recent_articles = cur.fetchall()
                
                if not recent_articles:
                    return {
                        "success": True,
                        "message": "No recent articles found for analysis",
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Start background insight generation
                background_tasks.add_task(process_intelligence_analysis, recent_articles)
                
                return {
                    "success": True,
                    "message": "Intelligence analysis started",
                    "articles_analyzed": len(recent_articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting insight generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends")
async def get_trend_predictions(
    prediction_type: Optional[str] = None,
    limit: int = 20,
    active_only: bool = True
):
    """Get trend predictions"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            # Build query with filters
            where_conditions = []
            params = []
            
            if prediction_type:
                where_conditions.append("prediction_type = %s")
                params.append(prediction_type)
            
            if active_only:
                where_conditions.append("is_active = true")
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, prediction_type, prediction_title, prediction_description,
                           prediction_data, confidence_score, predicted_date,
                           created_at, updated_at
                    FROM trend_predictions 
                    {where_clause}
                    ORDER BY predicted_date ASC
                    LIMIT %s
                """, params + [limit])
                
                predictions = []
                for row in cur.fetchall():
                    predictions.append({
                        "id": row[0],
                        "prediction_type": row[1],
                        "title": row[2],
                        "description": row[3],
                        "data": row[4],
                        "confidence_score": row[5],
                        "predicted_date": row[6].isoformat() if row[6] else None,
                        "created_at": row[7].isoformat() if row[7] else None,
                        "updated_at": row[8].isoformat() if row[8] else None
                    })
                
                return {
                    "success": True,
                    "data": {"predictions": predictions},
                    "count": len(predictions),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trends/predict")
async def predict_trends(request: Dict[str, Any], background_tasks: BackgroundTasks):
    """Generate trend predictions using LLM"""
    try:
        timeframe = request.get("timeframe", "7 days")
        category = request.get("category", "general")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get relevant articles for trend analysis
                cur.execute("""
                    SELECT id, title, content, source, published_at, summary
                    FROM articles 
                    WHERE created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (datetime.now() - timedelta(days=30),))
                
                articles = cur.fetchall()
                
                if not articles:
                    return {
                        "success": True,
                        "message": "No articles found for trend analysis",
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Start background trend prediction
                background_tasks.add_task(process_trend_prediction, articles, timeframe, category)
                
                return {
                    "success": True,
                    "message": "Trend prediction started",
                    "articles_analyzed": len(articles),
                    "timeframe": timeframe,
                    "category": category,
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting trend prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Get comprehensive analytics summary"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get various analytics metrics
                analytics = {}
                
                # Article analytics
                cur.execute("SELECT COUNT(*) FROM articles")
                analytics["total_articles"] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM articles WHERE created_at >= %s", 
                           (datetime.now() - timedelta(days=7),))
                analytics["articles_last_week"] = cur.fetchone()[0]
                
                # Storyline analytics
                cur.execute("SELECT COUNT(*) FROM storylines")
                analytics["total_storylines"] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storyline_articles")
                analytics["total_storyline_articles"] = cur.fetchone()[0]
                
                # Intelligence analytics
                cur.execute("SELECT COUNT(*) FROM intelligence_insights WHERE is_active = true")
                analytics["active_insights"] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM trend_predictions WHERE is_active = true")
                analytics["active_predictions"] = cur.fetchone()[0]
                
                # Quality metrics
                cur.execute("SELECT AVG(quality_score) FROM articles WHERE quality_score IS NOT NULL")
                analytics["avg_article_quality"] = round(cur.fetchone()[0] or 0, 2)
                
                cur.execute("SELECT AVG(quality_score) FROM storylines WHERE quality_score IS NOT NULL")
                analytics["avg_storyline_quality"] = round(cur.fetchone()[0] or 0, 2)
                
                return {
                    "success": True,
                    "data": analytics,
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def process_intelligence_analysis(articles: List[tuple]):
    """Background task for intelligence analysis"""
    try:
        # Build context from articles
        context_parts = ["Recent News Analysis for Intelligence Insights:"]
        
        for article in articles[:20]:  # Limit to 20 most recent
            article_id, title, content, source, published_at, summary = article
            context_parts.append(f"\n- {title} ({source}, {published_at})")
            if summary:
                context_parts.append(f"  Summary: {summary}")
            else:
                context_parts.append(f"  Content: {content[:200]}...")
        
        analysis_context = "\n".join(context_parts)
        
        # Generate insights using LLM
        insights_result = await llm_service.generate_summary(
            analysis_context, 
            TaskType.COMPREHENSIVE_ANALYSIS
        )
        
        if insights_result["success"]:
            # Store insights in database
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO intelligence_insights 
                            (insight_type, insight_title, insight_description, insight_data, 
                             confidence_score, relevance_score, created_at, updated_at, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            "news_analysis",
                            "Weekly News Intelligence Report",
                            insights_result["summary"],
                            {"articles_analyzed": len(articles), "model_used": insights_result["model_used"]},
                            85,  # High confidence
                            90,  # High relevance
                            datetime.now(),
                            datetime.now(),
                            True
                        ))
                        conn.commit()
                        logger.info(f"Generated intelligence insights from {len(articles)} articles")
                finally:
                    conn.close()
        
    except Exception as e:
        logger.error(f"Error in intelligence analysis: {e}")

async def process_trend_prediction(articles: List[tuple], timeframe: str, category: str):
    """Background task for trend prediction"""
    try:
        # Build context for trend analysis
        context_parts = [f"Trend Analysis for {category} over {timeframe}:"]
        
        for article in articles[:30]:  # Limit to 30 most recent
            article_id, title, content, source, published_at, summary = article
            context_parts.append(f"\n- {title} ({source}, {published_at})")
            if summary:
                context_parts.append(f"  Summary: {summary}")
        
        trend_context = "\n".join(context_parts)
        
        # Generate trend prediction using LLM
        prediction_result = await llm_service.generate_summary(
            trend_context, 
            TaskType.COMPREHENSIVE_ANALYSIS
        )
        
        if prediction_result["success"]:
            # Store prediction in database
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO trend_predictions 
                            (prediction_type, prediction_title, prediction_description, prediction_data,
                             confidence_score, predicted_date, created_at, updated_at, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            category,
                            f"{category.title()} Trend Prediction - {timeframe}",
                            prediction_result["summary"],
                            {"articles_analyzed": len(articles), "model_used": prediction_result["model_used"]},
                            80,  # Good confidence
                            datetime.now() + timedelta(days=7),  # Predict 1 week ahead
                            datetime.now(),
                            datetime.now(),
                            True
                        ))
                        conn.commit()
                        logger.info(f"Generated trend prediction for {category} from {len(articles)} articles")
                finally:
                    conn.close()
        
    except Exception as e:
        logger.error(f"Error in trend prediction: {e}")

@router.get("/topic-clusters")
async def get_topic_clusters(
    time_period: str = "7d",
    min_articles: int = 3,
    limit: int = 20
):
    """Get topic clusters for intelligence analysis"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Calculate time filter
                if time_period == "24h":
                    time_filter = datetime.now() - timedelta(hours=24)
                elif time_period == "7d":
                    time_filter = datetime.now() - timedelta(days=7)
                elif time_period == "30d":
                    time_filter = datetime.now() - timedelta(days=30)
                else:
                    time_filter = datetime.now() - timedelta(days=7)
                
                # Get topic clusters with recent activity
                cur.execute("""
                    SELECT tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           tc.created_at, tc.updated_at, tc.metadata,
                           COUNT(atc.article_id) as total_articles,
                           COUNT(CASE WHEN a.created_at >= %s THEN atc.article_id END) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance,
                           MAX(a.published_at) as latest_article_date
                    FROM topic_clusters tc
                    LEFT JOIN article_topics atc ON tc.id = atc.topic_id
                    LEFT JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                             tc.created_at, tc.updated_at, tc.metadata
                    HAVING COUNT(atc.article_id) >= %s
                    ORDER BY recent_articles DESC, total_articles DESC
                    LIMIT %s
                """, (time_filter, min_articles, limit))
                
                clusters = []
                for row in cur.fetchall():
                    clusters.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "type": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "metadata": row[6],
                        "total_articles": row[7] or 0,
                        "recent_articles": row[8] or 0,
                        "avg_relevance": float(row[9]) if row[9] else 0.0,
                        "latest_article_date": row[10].isoformat() if row[10] else None
                    })
                
                return {
                    "success": True,
                    "data": {
                        "clusters": clusters,
                        "time_period": time_period,
                        "min_articles": min_articles,
                        "total_clusters": len(clusters)
                    },
                    "message": f"Retrieved {len(clusters)} topic clusters",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topic clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trending-topics")
async def get_trending_topics(
    time_period: str = "24h",
    limit: int = 10
):
    """Get trending topics based on recent article activity"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Calculate time filter
                if time_period == "24h":
                    time_filter = datetime.now() - timedelta(hours=24)
                elif time_period == "7d":
                    time_filter = datetime.now() - timedelta(days=7)
                elif time_period == "30d":
                    time_filter = datetime.now() - timedelta(days=30)
                else:
                    time_filter = datetime.now() - timedelta(hours=24)
                
                # Get trending topics based on recent article activity
                cur.execute("""
                    SELECT tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance,
                           AVG(a.sentiment_score) as avg_sentiment,
                           MAX(a.published_at) as latest_article_date
                    FROM topic_clusters tc
                    JOIN article_topics atc ON tc.id = atc.topic_id
                    JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    AND a.created_at >= %s
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type
                    ORDER BY recent_articles DESC, avg_relevance DESC
                    LIMIT %s
                """, (time_filter, limit))
                
                trending_topics = []
                for row in cur.fetchall():
                    trending_topics.append({
                        "name": row[0],
                        "description": row[1],
                        "type": row[2],
                        "recent_articles": row[3],
                        "avg_relevance": float(row[4]) if row[4] else 0.0,
                        "avg_sentiment": float(row[5]) if row[5] else 0.0,
                        "latest_article_date": row[6].isoformat() if row[6] else None,
                        "trend_score": row[3] * (float(row[4]) if row[4] else 0.0)  # Simple trend calculation
                    })
                
                return {
                    "success": True,
                    "data": {
                        "trending_topics": trending_topics,
                        "time_period": time_period,
                        "total_topics": len(trending_topics)
                    },
                    "message": f"Retrieved {len(trending_topics)} trending topics",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
