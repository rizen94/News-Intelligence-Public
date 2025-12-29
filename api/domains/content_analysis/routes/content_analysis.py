"""
Domain 2: Content Analysis Routes
Handles sentiment analysis, entity extraction, summarization, and bias detection
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Path, Query, Body
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta
import logging

from shared.services.llm_service import llm_service, TaskType
from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4",
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

@router.get("/{domain}/content_analysis/topics")
async def get_topics(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    """Get topic clusters with optional filtering for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Build query with filters (no is_active column in current schema)
                where_conditions = ["1=1"]
                params = []
                
                if search:
                    where_conditions.append("tc.cluster_name ILIKE %s")
                    params.append(f"%{search}%")
                
                # category filter not supported in current schema
 
                where_clause = "WHERE " + " AND ".join(where_conditions)
 
                # Get topics with article counts
                # FIXED: Use article_topic_clusters (not article_topic_assignments)
                # article_topic_assignments links to 'topics' table, not 'topic_clusters'
                # article_topic_clusters links to 'topic_clusters' table via topic_cluster_id
                query = f"""
                    SELECT tc.id, tc.cluster_name, tc.cluster_description, tc.cluster_type,
                           tc.created_at, tc.updated_at, tc.metadata,
                           COUNT(atc.article_id) as article_count,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
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
                        "name": row[1],  # cluster_name
                        "description": row[2],  # cluster_description
                        "type": row[3],  # cluster_type
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "metadata": row[6] if row[6] else {},
                        "article_count": row[7] or 0,
                        "avg_relevance": float(row[8]) if row[8] else 0.0
                    })
                
                # Get total count
                count_query = f"""
                    SELECT COUNT(DISTINCT tc.id)
                    FROM {schema}.topic_clusters tc
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

@router.post("/{domain}/content_analysis/topics/cluster")
async def cluster_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    request: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Cluster articles into topics using AI for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        limit = request.get("limit", 100)
        
        # Start background clustering task with domain
        background_tasks.add_task(process_article_clustering, limit, domain)
        
        return {
            "success": True,
            "message": "Article clustering started",
            "domain": domain,
            "limit": limit,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting article clustering: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/content_analysis/topics/{cluster_name}/articles")
async def get_topic_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    cluster_name: str = Path(...),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Get articles for a specific topic in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Get topic ID
                cur.execute(f"SELECT id FROM {schema}.topic_clusters WHERE cluster_name = %s", (cluster_name,))
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id = topic_result[0]
                
                # Get articles for this topic
                cur.execute(f"""
                    SELECT a.id, a.title, a.content, a.url, a.source_domain, a.published_at,
                           a.summary, a.quality_score, a.sentiment_score, a.sentiment_label,
                           atc.relevance_score
                    FROM {schema}.articles a
                    JOIN {schema}.article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY atc.relevance_score DESC, a.published_at DESC
                    LIMIT %s OFFSET %s
                """, (topic_id, limit, offset))
                
                articles = []
                for row in cur.fetchall():
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2][:500] + "..." if len(row[2]) > 500 else row[2] if row[2] else "",
                        "url": row[3],
                        "source_domain": row[4],
                        "published_at": row[5].isoformat() if row[5] else None,
                        "summary": row[6],
                        "quality_score": row[7],
                        "sentiment_score": row[8],
                        "sentiment_label": row[9],
                        "relevance_score": float(row[10]) if row[10] else 0.0
                    })
                
                # Get total count
                cur.execute(f"""
                    SELECT COUNT(*)
                    FROM {schema}.article_topic_clusters
                    WHERE topic_cluster_id = %s
                """, (topic_id,))
                total_count = cur.fetchone()[0]
                
                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "cluster_name": cluster_name,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit
                    },
                    "message": f"Retrieved {len(articles)} articles for topic '{cluster_name}'",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching topic articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{domain}/content_analysis/topics/{cluster_name}/summary")
async def get_topic_summary(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    cluster_name: str = Path(...)
):
    """Get AI-generated summary for a topic in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Get topic info
                cur.execute(f"""
                    SELECT id, cluster_name, NULL as cluster_description, NULL as metadata
                    FROM {schema}.topic_clusters 
                    WHERE cluster_name = %s
                """, (cluster_name,))
                
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id, cluster_name, description, metadata = topic_result
                
                # Get recent articles for summary
                cur.execute(f"""
                    SELECT a.title, a.summary, a.published_at, a.sentiment_score
                    FROM {schema}.articles a
                    JOIN {schema}.article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY a.published_at DESC
                    LIMIT 10
                """, (topic_id,))
                
                articles = cur.fetchall()
                
                if not articles:
                    return {
                        "success": True,
                        "data": {
                            "cluster_name": cluster_name,
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
                        "cluster_name": cluster_name,
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

@router.post("/{domain}/content_analysis/topics/{cluster_name}/convert_to_storyline")
async def convert_topic_to_storyline(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    cluster_name: str = Path(...),
    request: Dict[str, Any] = Body(...)
):
    """Convert a topic to a storyline, adding all topic articles for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        storyline_title = request.get("storyline_title", f"Storyline: {cluster_name}")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Get topic info
                cur.execute(f"""
                    SELECT id FROM {schema}.topic_clusters 
                    WHERE cluster_name = %s
                """, (cluster_name,))
                
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")
                
                topic_id = topic_result[0]
                
                # Create new storyline
                cur.execute(f"""
                    INSERT INTO {schema}.storylines (title, description, created_at, updated_at, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    storyline_title,
                    f"Auto-generated storyline from topic: {cluster_name}",
                    datetime.now(),
                    datetime.now(),
                    "active"
                ))
                
                storyline_id = cur.fetchone()[0]
                
                # Get all articles for this topic
                cur.execute(f"""
                    SELECT article_id, relevance_score
                    FROM {schema}.article_topic_clusters
                    WHERE topic_id = %s
                """, (topic_id,))
                
                topic_articles = cur.fetchall()
                
                # Add articles to storyline
                articles_added = 0
                for article_row in topic_articles:
                    article_id, relevance_score = article_row
                    try:
                        cur.execute(f"""
                            INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at, relevance_score)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (storyline_id, article_id) DO NOTHING
                        """, (
                            storyline_id,
                            article_id,
                            datetime.now(),
                            float(relevance_score) if relevance_score else 0.5
                        ))
                        articles_added += cur.rowcount
                    except Exception as e:
                        logger.warning(f"Error adding article {article_id} to storyline: {e}")
                        continue
                
                # Update article count
                cur.execute("""
                    UPDATE storylines 
                    SET article_count = (
                        SELECT COUNT(*) FROM storyline_articles 
                        WHERE storyline_id = %s
                    ),
                    updated_at = %s
                    WHERE id = %s
                """, (storyline_id, datetime.now(), storyline_id))
                
                conn.commit()
                
                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "storyline_title": storyline_title,
                        "articles_added": articles_added,
                        "total_topic_articles": len(topic_articles)
                    },
                    "message": f"Successfully converted topic '{cluster_name}' to storyline with {articles_added} articles",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting topic to storyline: {e}")
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
                # Current schema has no cluster_type; return empty categories list for now
                categories = []
 
                # (Optional) derive categories heuristically in future
 
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

@router.get("/{domain}/content_analysis/topics/word_cloud")
async def get_word_cloud_data(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    time_period_hours: int = Query(24, ge=1, le=720),
    min_frequency: int = Query(1, ge=1)
):
    """Get intelligent word cloud data with ML/LLM filtering for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        from ..services.topic_intelligence_service import TopicIntelligenceService
        
        # Initialize service with domain
        topic_intelligence_service = TopicIntelligenceService(domain=domain)
        result = topic_intelligence_service.get_intelligent_word_cloud(limit=30)
        
        if result['success']:
            # Convert to the format expected by frontend
            word_cloud_data = []
            for topic in result['data']['word_cloud']:
                word_cloud_data.append({
                    'text': topic['text'],
                    'size': min(100, max(20, topic['value'] * 2)),  # Scale size based on article count
                    'frequency': topic['value'],
                    'relevance': topic['confidence'],
                    'articles': topic['value'],
                    'quality_score': topic['quality_score'],
                    'category': topic['category']
                })
            
            return {
                'success': True,
                'data': {
                    'word_cloud': word_cloud_data,
                    'total_topics': result['data']['total_topics'],
                    'filtered_from': result['data']['filtered_from'],
                    'categories': result['data']['categories']
                },
                'timestamp': result['timestamp']
            }
        else:
            return result
        
    except Exception as e:
        logger.error(f"Error fetching intelligent word cloud: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/{domain}/content_analysis/topics/big_picture")
async def get_big_picture_analysis(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    time_period_hours: int = Query(24, ge=1, le=720)
):
    """Get big picture analysis of current topics and trends for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Get recent articles count
                cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                cur.execute(f"""
                    SELECT COUNT(*) FROM {schema}.articles WHERE created_at >= %s
                """, (cutoff_time,))
                recent_articles_count = cur.fetchone()[0]
                
                # Get topic distribution
                # FIXED: Use article_topic_clusters (not article_topic_assignments)
                cur.execute(f"""
                    SELECT tc.cluster_name, COUNT(atc.article_id) as article_count
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    LEFT JOIN {schema}.articles a ON atc.article_id = a.id
                    WHERE (a.created_at >= %s OR a.created_at IS NULL)
                    GROUP BY tc.cluster_name
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
                cur.execute(f"""
                    SELECT tc.cluster_name, COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM {schema}.topic_clusters tc
                    JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    JOIN {schema}.articles a ON atc.article_id = a.id
                    WHERE a.created_at >= %s
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
                cur.execute(f"""
                    SELECT source_domain, COUNT(*) as article_count
                    FROM {schema}.articles
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

@router.get("/{domain}/content_analysis/topics/trending")
async def get_trending_topics(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    time_period_hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100)
):
    """Get trending topics with trend analysis for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        
        schema = domain.replace('-', '_')
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")
                
                cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                
                # Get trending topics with trend analysis
                cur.execute(f"""
                    SELECT tc.cluster_name,
                           COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance,
                           AVG(a.sentiment_score) as avg_sentiment,
                           MAX(a.published_at) as latest_article_date,
                           COUNT(DISTINCT a.source_domain) as source_diversity
                    FROM {schema}.topic_clusters tc
                    JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    JOIN {schema}.articles a ON atc.article_id = a.id
                    WHERE a.created_at >= %s
                    GROUP BY tc.id, tc.cluster_name
                    ORDER BY recent_articles DESC, avg_relevance DESC
                    LIMIT %s
                """, (cutoff_time, limit))
                
                trending_topics = []
                for row in cur.fetchall():
                    # Calculate trend score
                    trend_score = row[1] * (float(row[2]) if row[2] else 0.0) * (row[5] or 1)
                    
                    trending_topics.append({
                        "name": row[0],
                        "description": None,
                        "category": 'semantic',
                        "recent_articles": row[1],
                        "avg_relevance": float(row[2]) if row[2] else 0.0,
                        "avg_sentiment": float(row[3]) if row[3] else 0.0,
                        "latest_article_date": row[4].isoformat() if row[4] else None,
                        "source_diversity": row[5] or 0,
                        "trend_score": round(trend_score, 2),
                        "trend_direction": "rising" if row[1] > 5 else "stable"
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
        # No fallback run here; keep a single clustering path to reduce complexity

@router.get("/articles/{article_id}")
async def get_individual_article(article_id: int):
    """Get a specific article by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, url, content, summary, source_domain,
                           published_at, word_count, processing_status,
                           created_at, updated_at
                    FROM articles 
                    WHERE id = %s
                """, (article_id,))
                
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Article not found")
                
                article = {
                    "id": row[0],
                    "title": row[1],
                    "url": row[2],
                    "content": row[3],
                    "summary": row[4],
                    "source_domain": row[5],
                    "published_at": row[6].isoformat() if row[6] else None,
                    "word_count": row[7],
                    "processing_status": row[8],
                    "created_at": row[9].isoformat() if row[9] else None,
                    "updated_at": row[10].isoformat() if row[10] else None
                }
                
                return {
                    "success": True,
                    "data": article,
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching article {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
