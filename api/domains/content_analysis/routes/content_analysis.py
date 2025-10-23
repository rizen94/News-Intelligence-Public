"""
Domain 2: Content Analysis Routes
Handles sentiment analysis, entity extraction, summarization, and bias detection
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/content-analysis",
    tags=["Content Analysis"],
    responses={404: {"description": "Not found"}}
)

@router.get("/health")
async def health_check():
    """Health check for Content Analysis domain"""
    try:
        # Check LLM service
        llm_status = await llm_service.get_model_status()
        
        return {
            "success": True,
            "domain": "content_analysis",
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
            "domain": "content_analysis",
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/articles")
async def get_articles(limit: int = 20, offset: int = 0, status: Optional[str] = None):
    """Get articles with optional filtering"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query with optional status filter
                query = """
                    SELECT id, title, content, url, source_domain, published_at,
                           summary, quality_score, sentiment_score, sentiment_label,
                           processing_status, created_at
                    FROM articles 
                """
                params = []
                
                if status:
                    query += " WHERE processing_status = %s"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2][:500] + "..." if len(row[2]) > 500 else row[2],  # Truncate for list view
                        "url": row[3],
                        "source_domain": row[4],
                        "published_at": row[5].isoformat() if row[5] else None,
                        "summary": row[6],
                        "quality_score": row[7],
                        "sentiment_score": row[8],
                        "sentiment_label": row[9],
                        "processing_status": row[10],
                        "created_at": row[11].isoformat() if row[11] else None
                    })
                
                # Get total count
                count_query = "SELECT COUNT(*) FROM articles"
                count_params = []
                if status:
                    count_query += " WHERE processing_status = %s"
                    count_params.append(status)
                
                cur.execute(count_query, count_params)
                total_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit
                    },
                    "message": f"Retrieved {len(articles)} articles",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/articles/{article_id}/analyze")
async def analyze_article(article_id: int, background_tasks: BackgroundTasks):
    """Comprehensive article analysis using LLM"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, content, url, source_domain
                    FROM articles 
                    WHERE id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")
                
                # Start comprehensive analysis
                background_tasks.add_task(process_comprehensive_analysis, article)
                
                return {
                    "success": True,
                    "message": "Comprehensive analysis started",
                    "article_id": article_id,
                    "analysis_types": ["sentiment", "entities", "summary", "bias"],
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sentiment/analyze")
async def analyze_sentiment(request: Dict[str, Any]):
    """Analyze sentiment of provided content"""
    try:
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        # Use LLM for sentiment analysis
        sentiment_result = await llm_service.analyze_sentiment(content)
        
        return {
            "success": True,
            "data": sentiment_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/entities/extract")
async def extract_entities(request: Dict[str, Any]):
    """Extract named entities from provided content"""
    try:
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        # Use LLM for entity extraction
        entities_result = await llm_service.extract_entities(content)
        
        return {
            "success": True,
            "data": entities_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/summarize")
async def summarize_content(request: Dict[str, Any]):
    """Generate summary of provided content"""
    try:
        content = request.get("content", "")
        task_type = request.get("task_type", "quick_summary")
        
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        # Map task type
        task_enum = TaskType.QUICK_SUMMARY
        if task_type == "comprehensive":
            task_enum = TaskType.COMPREHENSIVE_ANALYSIS
        elif task_type == "batch":
            task_enum = TaskType.BATCH_PROCESSING
        
        # Use LLM for summarization
        summary_result = await llm_service.generate_summary(content, task_enum)
        
        return {
            "success": True,
            "data": summary_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles/{article_id}/analysis")
async def get_article_analysis(article_id: int):
    """Get analysis results for an article"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, summary, sentiment_score, sentiment_label,
                           entities, bias_score, bias_indicators, quality_score,
                           analysis_updated_at
                    FROM articles 
                    WHERE id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")
                
                return {
                    "success": True,
                    "data": {
                        "article_id": article[0],
                        "title": article[1],
                        "summary": article[2],
                        "sentiment": {
                            "score": article[3],
                            "label": article[4]
                        },
                        "entities": article[5],
                        "bias": {
                            "score": article[6],
                            "indicators": article[7]
                        },
                        "quality_score": article[8],
                        "analysis_updated_at": article[9].isoformat() if article[9] else None
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batch/status")
async def get_batch_processing_status():
    """Get status of batch processing operations"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Count articles pending analysis
                cur.execute("""
                    SELECT COUNT(*) FROM articles 
                    WHERE analysis_updated_at IS NULL 
                    OR analysis_updated_at < created_at
                """)
                pending_count = cur.fetchone()[0]
                
                # Count articles analyzed in last hour
                from datetime import timedelta
                last_hour = datetime.now() - timedelta(hours=1)
                cur.execute("""
                    SELECT COUNT(*) FROM articles 
                    WHERE analysis_updated_at >= %s
                """, (last_hour,))
                recent_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "pending_analysis": pending_count,
                        "analyzed_last_hour": recent_count,
                        "batch_processing_active": pending_count > 0
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/process")
async def start_batch_processing(background_tasks: BackgroundTasks):
    """Start batch processing of pending articles"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, content FROM articles 
                    WHERE analysis_updated_at IS NULL 
                    OR analysis_updated_at < created_at
                    ORDER BY created_at ASC
                    LIMIT 10
                """)
                
                articles = cur.fetchall()
                
                if not articles:
                    return {
                        "success": True,
                        "message": "No articles pending analysis",
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Start batch processing
                background_tasks.add_task(process_batch_analysis, articles)
                
                return {
                    "success": True,
                    "message": f"Started batch analysis for {len(articles)} articles",
                    "articles_count": len(articles),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def process_comprehensive_analysis(article: tuple):
    """Background task for comprehensive article analysis"""
    try:
        article_id, title, content, url, source = article
        
        # Run all analysis types in parallel
        sentiment_task = llm_service.analyze_sentiment(content)
        entities_task = llm_service.extract_entities(content)
        summary_task = llm_service.generate_summary(content, TaskType.COMPREHENSIVE_ANALYSIS)
        
        # Wait for all tasks to complete
        sentiment_result, entities_result, summary_result = await asyncio.gather(
            sentiment_task, entities_task, summary_task
        )
        
        # Update article with results
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Convert entities dict to JSON string for JSONB column
                    import json
                    entities_json = json.dumps(entities_result.get("entities", {}))
                    
                    cur.execute("""
                        UPDATE articles 
                        SET summary = %s,
                            sentiment_score = %s,
                            sentiment_label = %s,
                            entities = %s,
                            analysis_updated_at = %s
                        WHERE id = %s
                    """, (
                        summary_result.get("summary", ""),
                        sentiment_result.get("sentiment", {}).get("confidence", 0),
                        sentiment_result.get("sentiment", {}).get("overall_sentiment", "neutral"),
                        entities_json,
                        datetime.now(),
                        article_id
                    ))
                    conn.commit()
                    logger.info(f"Updated comprehensive analysis for article {article_id}")
            finally:
                conn.close()
        
    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}")

async def process_batch_analysis(articles: List[tuple]):
    """Background task for batch analysis processing"""
    logger.info(f"Starting batch analysis for {len(articles)} articles")
    
    for article in articles:
        try:
            await process_comprehensive_analysis(article)
            # Small delay to prevent overwhelming the LLM service
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error processing article {article[0]}: {e}")
    
    logger.info("Batch analysis completed")

# ============================================================================
# TOPIC CLUSTERING ENDPOINTS
# ============================================================================

@router.get("/topics")
async def get_topics(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    category: Optional[str] = None
):
    """Get topic clusters with optional filtering"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Build query with filters
                where_conditions = ["tc.is_active = true"]
                params = []
                
                if search:
                    where_conditions.append("tc.cluster_name ILIKE %s")
                    params.append(f"%{search}%")
                
                if category:
                    where_conditions.append("tc.cluster_type = %s")
                    params.append(category)
                
                where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # Get topics with article counts
                query = f"""
                    SELECT tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           tc.created_at, tc.updated_at, tc.metadata,
                           COUNT(atc.article_id) as article_count,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    {where_clause}
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                             tc.created_at, tc.updated_at, tc.metadata
                    ORDER BY article_count DESC, tc.created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cur.execute(query, params + [limit, offset])
                
                topics = []
                for row in cur.fetchall():
                    topics.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "type": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "metadata": row[6],
                        "article_count": row[7] or 0,
                        "avg_relevance": float(row[8]) if row[8] else 0.0
                    })
                
                # Get total count
                count_query = f"""
                    SELECT COUNT(DISTINCT tc.id)
                    FROM topic_clusters tc
                    {where_clause}
                """
                cur.execute(count_query, params)
                total_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "topics": topics,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit
                    },
                    "message": f"Retrieved {len(topics)} topics",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/topics/cluster")
async def cluster_articles(request: Dict[str, Any], background_tasks: BackgroundTasks):
    """Cluster articles into topics using AI"""
    try:
        limit = request.get("limit", 100)
        
        # Start background clustering task
        background_tasks.add_task(process_article_clustering, limit)
        
        return {
            "success": True,
            "message": "Article clustering started",
            "limit": limit,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting article clustering: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/{topic_name}/articles")
async def get_topic_articles(
    topic_name: str,
    limit: int = 20,
    offset: int = 0
):
    """Get articles for a specific topic"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get topic ID
                cur.execute("SELECT id FROM topic_clusters WHERE cluster_name = %s", (topic_name,))
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id = topic_result[0]
                
                # Get articles for this topic
                cur.execute("""
                    SELECT a.id, a.title, a.content, a.url, a.source_domain, a.published_at,
                           a.summary, a.quality_score, a.sentiment_score, a.sentiment_label,
                           atc.relevance_score, atc.assigned_at
                    FROM articles a
                    JOIN article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY atc.relevance_score DESC, a.published_at DESC
                    LIMIT %s OFFSET %s
                """, (topic_id, limit, offset))
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2][:500] + "..." if len(row[2]) > 500 else row[2],
                        "url": row[3],
                        "source_domain": row[4],
                        "published_at": row[5].isoformat() if row[5] else None,
                        "summary": row[6],
                        "quality_score": row[7],
                        "sentiment_score": row[8],
                        "sentiment_label": row[9],
                        "relevance_score": float(row[10]) if row[10] else 0.0,
                        "assigned_at": row[11].isoformat() if row[11] else None
                    })
                
                # Get total count
                cur.execute("""
                    SELECT COUNT(*)
                    FROM article_topic_clusters
                    WHERE topic_cluster_id = %s
                """, (topic_id,))
                total_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "topic_name": topic_name,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit
                    },
                    "message": f"Retrieved {len(articles)} articles for topic '{topic_name}'",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topic articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/{topic_name}/summary")
async def get_topic_summary(topic_name: str):
    """Get AI-generated summary for a topic"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get topic info
                cur.execute("""
                    SELECT id, cluster_name, cluster_description, metadata
                    FROM topic_clusters 
                    WHERE cluster_name = %s
                """, (topic_name,))
                
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id, cluster_name, description, metadata = topic_result
                
                # Get recent articles for summary
                cur.execute("""
                    SELECT a.title, a.summary, a.published_at, a.sentiment_score
                    FROM articles a
                    JOIN article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY a.published_at DESC
                    LIMIT 10
                """, (topic_id,))
                
                articles = cur.fetchall()
                
                if not articles:
                    return {
                        "success": True,
                        "data": {
                            "topic_name": cluster_name,
                            "summary": "No articles available for this topic yet.",
                            "article_count": 0,
                            "last_updated": None
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Generate summary using LLM
                article_texts = [f"Title: {article[0]}\nSummary: {article[1] or 'No summary available'}" 
                               for article in articles]
                combined_text = "\n\n".join(article_texts)
                
                # Use LLM to generate topic summary
                summary_result = await llm_service.generate_summary(
                    combined_text, 
                    TaskType.COMPREHENSIVE_ANALYSIS
                )
                
                return {
                    "success": True,
                    "data": {
                        "topic_name": cluster_name,
                        "summary": summary_result.get("summary", "Summary generation failed"),
                        "article_count": len(articles),
                        "last_updated": datetime.now().isoformat(),
                        "metadata": metadata
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error generating topic summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/categories/stats")
async def get_category_stats():
    """Get statistics for topic categories"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get category statistics
                cur.execute("""
                    SELECT tc.cluster_type,
                           COUNT(tc.id) as topic_count,
                           COUNT(atc.article_id) as total_articles,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    WHERE tc.is_active = true
                    GROUP BY tc.cluster_type
                    ORDER BY total_articles DESC
                """)
                
                categories = []
                for row in cur.fetchall():
                    categories.append({
                        "category": row[0],
                        "topic_count": row[1],
                        "total_articles": row[2] or 0,
                        "avg_relevance": float(row[3]) if row[3] else 0.0
                    })
                
                return {
                    "success": True,
                    "data": {
                        "categories": categories,
                        "total_categories": len(categories)
                    },
                    "message": f"Retrieved statistics for {len(categories)} categories",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching category stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/word-cloud")
async def get_word_cloud_data(
    time_period_hours: int = 24,
    min_frequency: int = 2
):
    """Get word cloud data for visualization"""
    try:
        from ..services.advanced_topic_extractor import AdvancedTopicExtractor
        
        # Initialize advanced topic extractor
        extractor = AdvancedTopicExtractor(get_db_connection)
        
        # Extract topics from recent articles
        topics = extractor.extract_topics_from_articles(time_period_hours=time_period_hours)
        
        # Filter by minimum frequency
        filtered_topics = [t for t in topics if t.frequency >= min_frequency]
        
        # Generate word cloud data
        word_cloud_data = extractor.generate_word_cloud_data(filtered_topics)
        
        return {
            "success": True,
            "data": word_cloud_data,
            "message": f"Generated word cloud with {len(word_cloud_data['words'])} topics",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating word cloud data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/big-picture")
async def get_big_picture_analysis(
    time_period_hours: int = 24
):
    """Get big picture analysis of current topics and trends"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Get recent articles count
                cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                cur.execute("""
                    SELECT COUNT(*) FROM articles WHERE created_at >= %s
                """, (cutoff_time,))
                recent_articles_count = cur.fetchone()[0]
                
                # Get topic distribution
                cur.execute("""
                    SELECT tc.cluster_type, COUNT(atc.article_id) as article_count
                    FROM topic_clusters tc
                    LEFT JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    LEFT JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    AND (a.created_at >= %s OR a.created_at IS NULL)
                    GROUP BY tc.cluster_type
                    ORDER BY article_count DESC
                """, (cutoff_time,))
                
                topic_distribution = []
                for row in cur.fetchall():
                    topic_distribution.append({
                        "category": row[0],
                        "article_count": row[1] or 0,
                        "percentage": round((row[1] or 0) / max(recent_articles_count, 1) * 100, 1)
                    })
                
                # Get trending topics (most active in recent period)
                cur.execute("""
                    SELECT tc.cluster_name, COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM topic_clusters tc
                    JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    AND a.created_at >= %s
                    GROUP BY tc.id, tc.cluster_name
                    ORDER BY recent_articles DESC, avg_relevance DESC
                    LIMIT 10
                """, (cutoff_time,))
                
                trending_topics = []
                for row in cur.fetchall():
                    trending_topics.append({
                        "name": row[0],
                        "recent_articles": row[1],
                        "avg_relevance": float(row[2]) if row[2] else 0.0,
                        "trend_score": row[1] * (float(row[2]) if row[2] else 0.0)
                    })
                
                # Get source diversity
                cur.execute("""
                    SELECT source_domain, COUNT(*) as article_count
                    FROM articles
                    WHERE created_at >= %s
                    GROUP BY source_domain
                    ORDER BY article_count DESC
                    LIMIT 10
                """, (cutoff_time,))
                
                source_diversity = []
                for row in cur.fetchall():
                    source_diversity.append({
                        "source": row[0],
                        "article_count": row[1],
                        "percentage": round(row[1] / max(recent_articles_count, 1) * 100, 1)
                    })
                
                # Calculate insights
                insights = {
                    "total_articles": recent_articles_count,
                    "active_topics": len(topic_distribution),
                    "top_category": topic_distribution[0]["category"] if topic_distribution else "None",
                    "source_diversity": len(source_diversity),
                    "avg_articles_per_topic": round(recent_articles_count / max(len(topic_distribution), 1), 1),
                    "time_period_hours": time_period_hours
                }
                
                return {
                    "success": True,
                    "data": {
                        "insights": insights,
                        "topic_distribution": topic_distribution,
                        "trending_topics": trending_topics,
                        "source_diversity": source_diversity,
                        "summary": {
                            "period": f"Last {time_period_hours} hours",
                            "articles_analyzed": recent_articles_count,
                            "topics_active": len(topic_distribution),
                            "sources": len(source_diversity)
                        }
                    },
                    "message": f"Big picture analysis for last {time_period_hours} hours",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error generating big picture analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topics/trending")
async def get_trending_topics(
    time_period_hours: int = 24,
    limit: int = 20
):
    """Get trending topics with trend analysis"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                
                # Get trending topics with trend analysis
                cur.execute("""
                    SELECT tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance,
                           AVG(a.sentiment_score) as avg_sentiment,
                           MAX(a.published_at) as latest_article_date,
                           COUNT(DISTINCT a.source_domain) as source_diversity
                    FROM topic_clusters tc
                    JOIN article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    JOIN articles a ON atc.article_id = a.id
                    WHERE tc.is_active = true
                    AND a.created_at >= %s
                    GROUP BY tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type
                    ORDER BY recent_articles DESC, avg_relevance DESC
                    LIMIT %s
                """, (cutoff_time, limit))
                
                trending_topics = []
                for row in cur.fetchall():
                    # Calculate trend score
                    trend_score = row[3] * (float(row[4]) if row[4] else 0.0) * row[7]  # articles * relevance * diversity
                    
                    trending_topics.append({
                        "name": row[0],
                        "description": row[1],
                        "category": row[2],
                        "recent_articles": row[3],
                        "avg_relevance": float(row[4]) if row[4] else 0.0,
                        "avg_sentiment": float(row[5]) if row[5] else 0.0,
                        "latest_article_date": row[6].isoformat() if row[6] else None,
                        "source_diversity": row[7],
                        "trend_score": round(trend_score, 2),
                        "trend_direction": "rising" if row[3] > 5 else "stable"  # Simple trend logic
                    })
                
                return {
                    "success": True,
                    "data": {
                        "trending_topics": trending_topics,
                        "time_period_hours": time_period_hours,
                        "total_trending": len(trending_topics)
                    },
                    "message": f"Retrieved {len(trending_topics)} trending topics",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task for article clustering
async def process_article_clustering(limit: int):
    """Background task for clustering articles into topics using advanced extraction"""
    try:
        from ..services.advanced_topic_extractor import AdvancedTopicExtractor
        
        # Initialize advanced topic extractor
        extractor = AdvancedTopicExtractor(get_db_connection)
        
        # Extract topics from recent articles (last 24 hours)
        topics = extractor.extract_topics_from_articles(time_period_hours=24)
        
        if topics:
            # Generate word cloud data
            word_cloud_data = extractor.generate_word_cloud_data(topics)
            
            # Save topics to database
            success = extractor.save_topics_to_database(topics)
            
            if success:
                logger.info(f"Advanced topic extraction completed: {len(topics)} topics extracted")
                logger.info(f"Word cloud data generated: {len(word_cloud_data['words'])} words")
            else:
                logger.error("Failed to save topics to database")
        else:
            logger.info("No topics extracted from recent articles")
            
    except Exception as e:
        logger.error(f"Error in advanced article clustering: {e}")
        # Fallback to simple clustering
        await process_simple_clustering(limit)

async def process_simple_clustering(limit: int):
    """Fallback simple clustering method"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                # Get unclustered articles
                cur.execute("""
                    SELECT a.id, a.title, a.content, a.summary
                    FROM articles a
                    LEFT JOIN article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.article_id IS NULL
                    AND a.content IS NOT NULL
                    AND LENGTH(a.content) > 100
                    ORDER BY a.created_at DESC
                    LIMIT %s
                """, (limit,))
                
                articles = cur.fetchall()
                
                if not articles:
                    logger.info("No articles available for clustering")
                    return
                
                # Simple topic clustering based on keywords
                topic_clusters = {}
                
                for article_id, title, content, summary in articles:
                    # Extract keywords from title and content
                    text = f"{title} {summary or ''}".lower()
                    
                    # Simple keyword-based clustering
                    topic = "General News"
                    if any(word in text for word in ['election', 'vote', 'president', 'campaign']):
                        topic = "Politics"
                    elif any(word in text for word in ['climate', 'environment', 'global warming', 'carbon']):
                        topic = "Environment"
                    elif any(word in text for word in ['tech', 'ai', 'software', 'technology', 'digital']):
                        topic = "Technology"
                    elif any(word in text for word in ['economy', 'market', 'inflation', 'economic', 'financial']):
                        topic = "Economy"
                    elif any(word in text for word in ['health', 'medical', 'covid', 'pandemic', 'vaccine']):
                        topic = "Health"
                    elif any(word in text for word in ['war', 'conflict', 'military', 'defense', 'security']):
                        topic = "International"
                    
                    if topic not in topic_clusters:
                        topic_clusters[topic] = []
                    topic_clusters[topic].append((article_id, 0.8))  # Default relevance score
                
                # Create or update topic clusters
                for topic_name, articles_list in topic_clusters.items():
                    # Check if topic exists
                    cur.execute("SELECT id FROM topic_clusters WHERE cluster_name = %s", (topic_name,))
                    topic_result = cur.fetchone()
                    
                    if topic_result:
                        topic_id = topic_result[0]
                    else:
                        # Create new topic cluster
                        cur.execute("""
                            INSERT INTO topic_clusters (cluster_name, cluster_description, cluster_type, is_active)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                        """, (topic_name, f"AI-generated cluster for {topic_name}", "semantic", True))
                        topic_id = cur.fetchone()[0]
                    
                    # Assign articles to topic
                    for article_id, relevance_score in articles_list:
                        cur.execute("""
                            INSERT INTO article_topic_clusters (article_id, topic_cluster_id, relevance_score)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
                                relevance_score = EXCLUDED.relevance_score,
                                assigned_at = CURRENT_TIMESTAMP
                        """, (article_id, topic_id, relevance_score))
                
                conn.commit()
                logger.info(f"Simple clustering completed: {len(articles)} articles into {len(topic_clusters)} topics")
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error in simple article clustering: {e}")
