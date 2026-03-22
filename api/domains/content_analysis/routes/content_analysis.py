"""
Domain 2: Content Analysis Routes
Handles sentiment analysis, entity extraction, summarization, and bias detection
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from domains.content_analysis.services.topic_filter_rules import (
    filter_topic_list,
    filter_word_cloud_entries,
)
from domains.content_analysis.services.topic_merge_suggestions import get_merge_suggestions
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path, Query
from shared.database.connection import get_db_connection
from shared.domain_registry import DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import (
    get_domain_data_schemas,
    parse_optional_domain_to_schema,
    resolve_article_id_to_schema,
    validate_domain,
)
from shared.services.llm_service import TaskType, llm_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api", tags=["Content Analysis"], responses={404: {"description": "Not found"}}
)


@router.get("/health")
async def health_check():
    """Health check for Content Analysis domain"""
    try:
        # Check LLM service (1s timeout — don't block health when Ollama is busy)
        llm_status = await llm_service.get_model_status(timeout_seconds=1.0)

        return {
            "success": True,
            "domain": "content_analysis",
            "status": "healthy",
            "llm_service": llm_status,
            "primary_model": "llama3.1:8b",
            "secondary_model": "mistral:7b",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "content_analysis",
            "status": "unhealthy",
            "error": str(e),
        }


@router.get("/articles")
async def get_articles(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    domain: str | None = Query(
        None,
        description="Optional: politics, finance, or science-tech. Omit to aggregate all domains.",
    ),
):
    """Get articles with optional filtering (domain-scoped or all domains)."""
    try:
        try:
            schema = parse_optional_domain_to_schema(domain)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                if schema:
                    wh = " WHERE processing_status = %s" if status else ""
                    q = f"""
                        SELECT id, title, content, url, source_domain, published_at,
                               summary, quality_score, sentiment_score, sentiment_label,
                               processing_status, created_at
                        FROM {schema}.articles
                        {wh}
                        ORDER BY created_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                    """
                    params = []
                    if status:
                        params.append(status)
                    params.extend([limit, offset])
                    cur.execute(q, params)
                else:
                    branches = []
                    params = []
                    for sch in get_domain_data_schemas():
                        wh = " WHERE processing_status = %s" if status else ""
                        branches.append(f"""
                            SELECT id, title, content, url, source_domain, published_at,
                                   summary, quality_score, sentiment_score, sentiment_label,
                                   processing_status, created_at
                            FROM {sch}.articles
                            {wh}
                        """)
                        if status:
                            params.append(status)
                    union = " UNION ALL ".join(branches)
                    params.extend([limit, offset])
                    cur.execute(
                        f"""
                        SELECT * FROM (
                            {union}
                        ) all_articles
                        ORDER BY created_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                    """,
                        params,
                    )

                articles = []
                for row in cur.fetchall():
                    pub_at = row[5].isoformat() if row[5] else None
                    src_domain = row[4]
                    articles.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "content": row[2][:800] + "..."
                            if row[2] and len(row[2]) > 800
                            else (row[2] or ""),
                            "url": row[3],
                            "source_domain": src_domain,
                            "source": src_domain,
                            "published_at": pub_at,
                            "published_date": pub_at,
                            "summary": row[6],
                            "quality_score": row[7],
                            "sentiment_score": row[8],
                            "sentiment_label": row[9],
                            "processing_status": row[10],
                            "created_at": row[11].isoformat() if row[11] else None,
                        }
                    )

                if schema:
                    count_query = f"SELECT COUNT(*) FROM {schema}.articles"
                    count_params = []
                    if status:
                        count_query += " WHERE processing_status = %s"
                        count_params.append(status)
                    cur.execute(count_query, count_params)
                    total_count = cur.fetchone()[0]
                else:
                    total_count = 0
                    for sch in get_domain_data_schemas():
                        cq = f"SELECT COUNT(*) FROM {sch}.articles"
                        cp = []
                        if status:
                            cq += " WHERE processing_status = %s"
                            cp.append(status)
                        cur.execute(cq, cp)
                        total_count += cur.fetchone()[0] or 0

                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit,
                    },
                    "message": f"Retrieved {len(articles)} articles",
                    "timestamp": datetime.now().isoformat(),
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
        schema = resolve_article_id_to_schema(article_id)
        if not schema:
            raise HTTPException(status_code=404, detail="Article not found")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, content, url, source_domain
                    FROM {schema}.articles
                    WHERE id = %s
                """,
                    (article_id,),
                )

                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")

                # Start comprehensive analysis
                background_tasks.add_task(process_comprehensive_analysis, article + (schema,))

                return {
                    "success": True,
                    "message": "Comprehensive analysis started",
                    "article_id": article_id,
                    "analysis_types": ["sentiment", "entities", "summary", "bias"],
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/analyze")
async def analyze_sentiment(request: dict[str, Any]):
    """Analyze sentiment of provided content"""
    try:
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        # Use LLM for sentiment analysis
        sentiment_result = await llm_service.analyze_sentiment(content)

        return {"success": True, "data": sentiment_result, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities/extract")
async def extract_entities(request: dict[str, Any]):
    """Extract named entities from provided content"""
    try:
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        # Use LLM for entity extraction
        entities_result = await llm_service.extract_entities(content)

        return {"success": True, "data": entities_result, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize")
async def summarize_content(request: dict[str, Any]):
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

        return {"success": True, "data": summary_result, "timestamp": datetime.now().isoformat()}

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
            sch = resolve_article_id_to_schema(article_id)
            if not sch:
                raise HTTPException(status_code=404, detail="Article not found")
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, summary, sentiment_score, sentiment_label,
                           entities, bias_score, bias_indicators, quality_score,
                           analysis_updated_at
                    FROM {sch}.articles
                    WHERE id = %s
                """,
                    (article_id,),
                )

                article = cur.fetchone()
                if not article:
                    raise HTTPException(status_code=404, detail="Article not found")

                # Build narrative explanation of analysis scores
                sentiment_score = article[3]
                sentiment_label = article[4] or ""
                bias_score = article[6]
                quality_score = article[8]
                narrative_parts = []
                if sentiment_label:
                    narrative_parts.append(f"Sentiment is {sentiment_label.lower()}")
                    if sentiment_score is not None:
                        narrative_parts[-1] += f" ({sentiment_score:.2f})"
                if quality_score is not None:
                    level = (
                        "high"
                        if quality_score >= 0.7
                        else "moderate"
                        if quality_score >= 0.4
                        else "low"
                    )
                    narrative_parts.append(f"{level} quality ({quality_score:.2f})")
                if bias_score is not None:
                    bias_level = (
                        "low" if bias_score < 0.3 else "moderate" if bias_score < 0.6 else "notable"
                    )
                    narrative_parts.append(f"{bias_level} bias ({bias_score:.2f})")
                narrative = ". ".join(narrative_parts) + "." if narrative_parts else ""

                return {
                    "success": True,
                    "data": {
                        "article_id": article[0],
                        "title": article[1],
                        "summary": article[2],
                        "narrative": narrative,
                        "sentiment": {
                            "score": sentiment_score,
                            "label": sentiment_label,
                        },
                        "entities": article[5],
                        "bias": {"score": bias_score, "indicators": article[7]},
                        "quality_score": quality_score,
                        "analysis_updated_at": article[9].isoformat() if article[9] else None,
                    },
                    "timestamp": datetime.now().isoformat(),
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
                pending_count = 0
                recent_count = 0
                from datetime import timedelta

                last_hour = datetime.now() - timedelta(hours=1)
                for sch in get_domain_data_schemas():
                    cur.execute(f"""
                        SELECT COUNT(*) FROM {sch}.articles
                        WHERE analysis_updated_at IS NULL
                           OR analysis_updated_at < created_at
                    """)
                    pending_count += cur.fetchone()[0] or 0
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {sch}.articles
                        WHERE analysis_updated_at >= %s
                    """,
                        (last_hour,),
                    )
                    recent_count += cur.fetchone()[0] or 0

                return {
                    "success": True,
                    "data": {
                        "pending_analysis": pending_count,
                        "analyzed_last_hour": recent_count,
                        "batch_processing_active": pending_count > 0,
                    },
                    "timestamp": datetime.now().isoformat(),
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
                branches = []
                params = []
                for sch in get_domain_data_schemas():
                    branches.append(f"""
                        SELECT id, title, content, %s::text AS _schema, created_at
                        FROM {sch}.articles
                        WHERE analysis_updated_at IS NULL
                           OR analysis_updated_at < created_at
                    """)
                    params.append(sch)
                union_sql = " UNION ALL ".join(branches)
                cur.execute(
                    f"""
                    SELECT id, title, content, _schema FROM (
                        {union_sql}
                    ) pending
                    ORDER BY created_at ASC NULLS LAST
                    LIMIT 10
                """,
                    params,
                )

                articles = cur.fetchall()

                if not articles:
                    return {
                        "success": True,
                        "message": "No articles pending analysis",
                        "timestamp": datetime.now().isoformat(),
                    }

                # Start batch processing
                background_tasks.add_task(process_batch_analysis, articles)

                return {
                    "success": True,
                    "message": f"Started batch analysis for {len(articles)} articles",
                    "articles_count": len(articles),
                    "timestamp": datetime.now().isoformat(),
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
        if len(article) >= 6:
            article_id, title, content, url, source, schema = article[:6]
        else:
            article_id, title, content, url, source = article[:5]
            schema = resolve_article_id_to_schema(article_id)
        if not schema:
            logger.error("process_comprehensive_analysis: no schema for article %s", article_id)
            return

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

                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET summary = %s,
                            sentiment_score = %s,
                            sentiment_label = %s,
                            entities = %s,
                            analysis_updated_at = %s
                        WHERE id = %s
                    """,
                        (
                            summary_result.get("summary", ""),
                            sentiment_result.get("sentiment", {}).get("confidence", 0),
                            sentiment_result.get("sentiment", {}).get(
                                "overall_sentiment", "neutral"
                            ),
                            entities_json,
                            datetime.now(),
                            article_id,
                        ),
                    )
                    conn.commit()
                    logger.info(f"Updated comprehensive analysis for article {article_id}")
            finally:
                conn.close()

    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}")


async def process_batch_analysis(articles: list[tuple]):
    """Background task for batch analysis processing"""
    logger.info(f"Starting batch analysis for {len(articles)} articles")

    for article in articles:
        try:
            # (id, title, content, _schema) from batch query
            if len(article) >= 4:
                aid, title, content, schema = article[0], article[1], article[2], article[3]
                row = (aid, title, content, None, None, schema)
            else:
                row = article
            await process_comprehensive_analysis(row)
            # Small delay to prevent overwhelming the LLM service
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error processing article {article[0] if article else '?'}: {e}")

    logger.info("Batch analysis completed")


# ============================================================================
# TOPIC CLUSTERING ENDPOINTS
# ============================================================================


@router.get("/{domain}/content_analysis/topics")
async def get_topics(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(50, ge=1, le=100),  # Max 100 for performance
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    category: str | None = Query(None),
):
    """Get topic clusters with optional filtering for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
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

                # Get topics with article counts and article IDs (minimal columns for schema compatibility)
                cur.execute(
                    f"""
                    SELECT tc.id, tc.cluster_name,
                           NULL::text as cluster_description, NULL::text as cluster_type,
                           tc.created_at, tc.updated_at, '{{}}'::jsonb as metadata,
                           COUNT(atc.article_id) as article_count,
                           AVG(atc.relevance_score) as avg_relevance,
                           ARRAY_AGG(atc.article_id) FILTER (WHERE atc.article_id IS NOT NULL) as article_ids
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    {where_clause}
                    GROUP BY tc.id, tc.cluster_name, tc.created_at, tc.updated_at
                    ORDER BY article_count DESC, tc.created_at DESC
                    LIMIT %s OFFSET %s
                """,
                    params + [limit, offset],
                )

                topics = []
                for row in cur.fetchall():
                    # Handle article_ids (column 10, index 9)
                    article_ids = []
                    if len(row) > 9:
                        article_ids_raw = row[9]
                        if article_ids_raw:
                            # Remove duplicates and None values
                            article_ids = list(
                                set([aid for aid in article_ids_raw if aid is not None])
                            )

                    cluster_name = row[1] or ""
                    article_count = row[7] or 0
                    description = (
                        row[2]
                        or f"Topic cluster covering {cluster_name} with {article_count} articles"
                    )
                    topics.append(
                        {
                            "id": row[0],
                            "name": cluster_name,
                            "description": description,
                            "type": row[3] or "semantic",
                            "created_at": row[4].isoformat() if row[4] else None,
                            "updated_at": row[5].isoformat() if row[5] else None,
                            "metadata": row[6] if row[6] else {},
                            "article_count": article_count,
                            "avg_relevance": float(row[8]) if row[8] else 0.0,
                            "article_ids": article_ids,
                        }
                    )

                # Apply date/country filter rules and banned topics - exclude from display
                banned = _get_banned_topics(cur, schema)
                topics = filter_topic_list(topics, name_key="name", banned_topics=banned)
                topics = _attach_topic_trend_signals(cur, schema, topics)

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
                        "limit": limit,
                    },
                    "message": f"Retrieved {len(topics)} topics",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/topics/merge_suggestions")
async def get_topic_merge_suggestions(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    min_score: float = Query(0.35, ge=0.1, le=1.0),
    limit: int = Query(50, ge=1, le=100),
):
    """Second-layer clustering: analyze all topics and suggest which could be merged."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                # Fetch ALL topic clusters (up to 500) for comparison — no filter
                cur.execute(f"""
                    SELECT tc.id, tc.cluster_name, COUNT(atc.article_id) as article_count
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    GROUP BY tc.id, tc.cluster_name
                    HAVING COUNT(atc.article_id) >= 1
                    ORDER BY article_count DESC
                    LIMIT 500
                """)
                rows = cur.fetchall()
                topics = []
                for row in rows:
                    topics.append(
                        {
                            "id": row[0],
                            "name": row[1],
                            "cluster_name": row[1],
                            "article_count": row[2] if len(row) > 2 else 0,
                            "keywords": [],
                        }
                    )
                suggestions = get_merge_suggestions(
                    topics, min_score=min_score, max_suggestions=limit, name_key="name"
                )
                return {
                    "success": True,
                    "data": {"suggestions": suggestions, "topics_analyzed": len(topics)},
                    "timestamp": datetime.now().isoformat(),
                }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating merge suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/content_analysis/topics/merge_clusters")
async def merge_topic_clusters(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN), body: dict[str, Any] = Body(...)
):
    """Merge a topic cluster into another (secondary -> primary). Keeps primary, moves all articles."""
    primary_name = body.get("primary_cluster") or body.get("primary")
    secondary_name = body.get("secondary_cluster") or body.get("secondary")
    if not primary_name or not secondary_name:
        raise HTTPException(
            status_code=400, detail="primary_cluster and secondary_cluster required"
        )
    if str(primary_name).strip().lower() == str(secondary_name).strip().lower():
        raise HTTPException(status_code=400, detail="Primary and secondary must be different")
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(
                    f"SELECT id FROM {schema}.topic_clusters WHERE cluster_name = %s",
                    (primary_name.strip(),),
                )
                primary_row = cur.fetchone()
                cur.execute(
                    f"SELECT id FROM {schema}.topic_clusters WHERE cluster_name = %s",
                    (secondary_name.strip(),),
                )
                secondary_row = cur.fetchone()
                if not primary_row:
                    raise HTTPException(
                        status_code=404, detail=f"Primary cluster '{primary_name}' not found"
                    )
                if not secondary_row:
                    raise HTTPException(
                        status_code=404, detail=f"Secondary cluster '{secondary_name}' not found"
                    )
                primary_id, secondary_id = primary_row[0], secondary_row[0]
                if primary_id == secondary_id:
                    raise HTTPException(
                        status_code=400, detail="Primary and secondary are the same cluster"
                    )
                # Move article assignments: insert into primary, keep max relevance on conflict
                cur.execute(
                    f"""
                    INSERT INTO {schema}.article_topic_clusters (article_id, topic_cluster_id, relevance_score, confidence_score)
                    SELECT article_id, %s, relevance_score, confidence_score
                    FROM {schema}.article_topic_clusters
                    WHERE topic_cluster_id = %s
                    ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
                        relevance_score = GREATEST(article_topic_clusters.relevance_score, EXCLUDED.relevance_score),
                        confidence_score = GREATEST(article_topic_clusters.confidence_score, EXCLUDED.confidence_score)
                """,
                    (primary_id, secondary_id),
                )
                # Delete secondary's assignments
                cur.execute(
                    f"DELETE FROM {schema}.article_topic_clusters WHERE topic_cluster_id = %s",
                    (secondary_id,),
                )
                # Delete secondary cluster
                cur.execute(f"DELETE FROM {schema}.topic_clusters WHERE id = %s", (secondary_id,))
                # Update primary's article_count if column exists
                try:
                    cur.execute(
                        f"""
                        UPDATE {schema}.topic_clusters
                        SET article_count = (SELECT COUNT(*) FROM {schema}.article_topic_clusters WHERE topic_cluster_id = %s),
                            updated_at = NOW()
                        WHERE id = %s
                    """,
                        (primary_id, primary_id),
                    )
                except Exception:
                    pass
                conn.commit()
                return {
                    "success": True,
                    "message": f"Merged '{secondary_name}' into '{primary_name}'",
                    "primary_cluster": primary_name,
                    "secondary_cluster": secondary_name,
                    "timestamp": datetime.now().isoformat(),
                }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging topic clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/content_analysis/topics/cluster")
async def cluster_articles(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    request: dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Cluster articles into topics using AI for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        limit = request.get("limit", 100)
        time_period_hours = request.get("time_period_hours", 24)

        # Validate time period
        if (
            not isinstance(time_period_hours, int)
            or time_period_hours < 1
            or time_period_hours > 720
        ):
            time_period_hours = 24
            logger.warning("Invalid time_period_hours, defaulting to 24 hours")

        logger.info(
            f"📊 Clustering request received: domain={domain}, limit={limit}, time_period={time_period_hours}h"
        )

        # Start background clustering task with domain and configurable time period
        background_tasks.add_task(process_article_clustering, limit, domain, time_period_hours)

        logger.info(f"✅ Background clustering task queued for domain '{domain}'")

        return {
            "success": True,
            "message": "Article clustering started",
            "domain": domain,
            "limit": limit,
            "time_period_hours": time_period_hours,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting article clustering: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Failed to start clustering: {str(e)}")


@router.get("/{domain}/content_analysis/topics/cluster/status")
async def get_clustering_status(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)):
    """Get the status of topic clustering - returns recent topic count and queue status"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")

                # Get count of topics created in last hour (indicates recent clustering)
                cur.execute(f"""
                    SELECT COUNT(*) as recent_count
                    FROM {schema}.topic_clusters
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """)
                recent_count = cur.fetchone()[0] or 0

                # Get total topic count
                cur.execute(f"SELECT COUNT(*) FROM {schema}.topic_clusters")
                total_count = cur.fetchone()[0] or 0

                # Get most recent clustering time
                cur.execute(f"""
                    SELECT MAX(created_at) as last_clustering
                    FROM {schema}.topic_clusters
                """)
                last_clustering = cur.fetchone()[0]

                # Get queue statistics
                queue_stats = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
                try:
                    cur.execute(f"""
                        SELECT
                            COUNT(*) FILTER (WHERE status = 'pending') as pending,
                            COUNT(*) FILTER (WHERE status = 'processing') as processing,
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed
                        FROM {schema}.topic_extraction_queue
                    """)
                    row = cur.fetchone()
                    if row:
                        queue_stats = {
                            "pending": row[0] or 0,
                            "processing": row[1] or 0,
                            "completed": row[2] or 0,
                            "failed": row[3] or 0,
                        }
                except Exception:
                    # Table might not exist yet (migration not applied)
                    pass

                return {
                    "success": True,
                    "domain": domain,
                    "total_topics": total_count,
                    "recent_topics": recent_count,
                    "last_clustering": last_clustering.isoformat() if last_clustering else None,
                    "status": "active" if recent_count > 0 else "idle",
                    "queue": queue_stats,
                }
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting clustering status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/topics/{cluster_name}/articles")
async def get_topic_articles(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    cluster_name: str = Path(...),
    limit: int = Query(20, ge=1, le=100),  # Max 100 for performance
    offset: int = Query(0, ge=0),
):
    """Get articles for a specific topic in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")

                # Get topic ID
                cur.execute(
                    f"SELECT id FROM {schema}.topic_clusters WHERE cluster_name = %s",
                    (cluster_name,),
                )
                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")

                topic_id = topic_result[0]

                # Get articles for this topic
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.content, a.url, a.source_domain, a.published_at,
                           a.summary, a.quality_score, a.sentiment_score, a.sentiment_label,
                           atc.relevance_score
                    FROM {schema}.articles a
                    JOIN {schema}.article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY atc.relevance_score DESC, a.published_at DESC
                    LIMIT %s OFFSET %s
                """,
                    (topic_id, limit, offset),
                )

                articles = []
                for row in cur.fetchall():
                    articles.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "content": row[2][:800] + "..."
                            if row[2] and len(row[2]) > 800
                            else (row[2] or ""),
                            "url": row[3],
                            "source_domain": row[4],
                            "published_at": row[5].isoformat() if row[5] else None,
                            "summary": row[6],
                            "quality_score": row[7],
                            "sentiment_score": row[8],
                            "sentiment_label": row[9],
                            "relevance_score": float(row[10]) if row[10] else 0.0,
                        }
                    )

                # Get total count
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {schema}.article_topic_clusters
                    WHERE topic_cluster_id = %s
                """,
                    (topic_id,),
                )
                total_count = cur.fetchone()[0]

                return {
                    "success": True,
                    "data": {
                        "articles": articles,
                        "cluster_name": cluster_name,
                        "total": total_count,
                        "page": (offset // limit) + 1,
                        "limit": limit,
                    },
                    "message": f"Retrieved {len(articles)} articles for topic '{cluster_name}'",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching topic articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/topics/{cluster_name}/summary")
async def get_topic_summary(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN), cluster_name: str = Path(...)
):
    """Get AI-generated summary for a topic in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")

                # Get topic info
                cur.execute(
                    f"""
                    SELECT id, cluster_name, NULL as cluster_description, NULL as metadata
                    FROM {schema}.topic_clusters
                    WHERE cluster_name = %s
                """,
                    (cluster_name,),
                )

                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")

                topic_id, cluster_name, description, metadata = topic_result

                # Get recent articles for summary (include content for richer LLM input)
                cur.execute(
                    f"""
                    SELECT a.title, a.summary, a.published_at, a.sentiment_score,
                           LEFT(a.content, 800) as content_excerpt
                    FROM {schema}.articles a
                    JOIN {schema}.article_topic_clusters atc ON a.id = atc.article_id
                    WHERE atc.topic_cluster_id = %s
                    ORDER BY a.published_at DESC
                    LIMIT 10
                """,
                    (topic_id,),
                )

                articles = cur.fetchall()

                if not articles:
                    return {
                        "success": True,
                        "data": {
                            "cluster_name": cluster_name,
                            "summary": "No articles available for this topic yet.",
                            "article_count": 0,
                            "last_updated": None,
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

                # Generate summary using LLM — use content when summary is missing
                article_texts = []
                for article in articles:
                    text_parts = [f"Title: {article[0]}"]
                    if article[1]:
                        text_parts.append(f"Summary: {article[1]}")
                    elif len(article) > 4 and article[4]:
                        text_parts.append(f"Content: {article[4]}")
                    article_texts.append("\n".join(text_parts))
                combined_text = "\n\n".join(article_texts)

                # Use LLM to generate topic summary
                summary_result = await llm_service.generate_summary(
                    combined_text, TaskType.COMPREHENSIVE_ANALYSIS
                )

                return {
                    "success": True,
                    "data": {
                        "cluster_name": cluster_name,
                        "summary": summary_result.get("summary", "Summary generation failed"),
                        "article_count": len(articles),
                        "last_updated": datetime.now().isoformat(),
                        "metadata": metadata,
                    },
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error generating topic summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/content_analysis/topics/{cluster_name}/convert_to_storyline")
async def convert_topic_to_storyline(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    cluster_name: str = Path(...),
    request: dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = None,
):
    """Convert a topic to a storyline, adding all topic articles for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        storyline_title = request.get("storyline_title", f"Storyline: {cluster_name}")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")

                # Get topic info
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.topic_clusters
                    WHERE cluster_name = %s
                """,
                    (cluster_name,),
                )

                topic_result = cur.fetchone()
                if not topic_result:
                    raise HTTPException(status_code=404, detail="Topic not found")

                topic_id = topic_result[0]

                # Create new storyline with HIGH priority for LLM processing
                cur.execute(
                    f"""
                    INSERT INTO {schema}.storylines (title, description, created_at, updated_at, status, priority, ml_processing_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        storyline_title,
                        f"Auto-generated storyline from topic: {cluster_name}",
                        datetime.now(),
                        datetime.now(),
                        "active",
                        10,  # HIGH priority (1-10 scale, 10 = highest)
                        "pending",  # Queue for LLM processing
                    ),
                )

                storyline_id = cur.fetchone()[0]

                # Get all articles for this topic
                cur.execute(
                    f"""
                    SELECT article_id, relevance_score
                    FROM {schema}.article_topic_clusters
                    WHERE topic_cluster_id = %s
                """,
                    (topic_id,),
                )

                topic_articles = cur.fetchall()

                # Add articles to storyline
                articles_added = 0
                for article_row in topic_articles:
                    article_id, relevance_score = article_row
                    try:
                        cur.execute(
                            f"""
                            INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at, relevance_score)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (storyline_id, article_id) DO NOTHING
                        """,
                            (
                                storyline_id,
                                article_id,
                                datetime.now(),
                                float(relevance_score) if relevance_score else 0.5,
                            ),
                        )
                        articles_added += cur.rowcount
                    except Exception as e:
                        logger.warning(f"Error adding article {article_id} to storyline: {e}")
                        continue

                # Update article count and ensure priority/processing status are set
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    priority = 10,
                    ml_processing_status = 'pending',
                    updated_at = %s
                    WHERE id = %s
                """,
                    (storyline_id, datetime.now(), storyline_id),
                )

                conn.commit()

                # Trigger comprehensive LLM processing in background
                # This will generate summary, timeline, and full breakdown
                if background_tasks:
                    background_tasks.add_task(
                        process_new_storyline_comprehensive, domain, storyline_id, schema
                    )
                    logger.info(
                        f"Queued storyline {storyline_id} for comprehensive LLM processing (priority: HIGH)"
                    )
                else:
                    logger.warning(
                        f"BackgroundTasks not available - storyline {storyline_id} will be processed by ML service"
                    )

                return {
                    "success": True,
                    "data": {
                        "storyline_id": storyline_id,
                        "storyline_title": storyline_title,
                        "articles_added": articles_added,
                        "total_topic_articles": len(topic_articles),
                    },
                    "message": f"Successfully converted topic '{cluster_name}' to storyline with {articles_added} articles",
                    "timestamp": datetime.now().isoformat(),
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
            with conn.cursor():
                # Current schema has no cluster_type; return empty categories list for now
                categories = []

                # (Optional) derive categories heuristically in future

                return {
                    "success": True,
                    "data": {"categories": categories, "total_categories": len(categories)},
                    "message": f"Retrieved statistics for {len(categories)} categories",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching category stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/topics/word_cloud")
async def get_word_cloud_data(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    time_period_hours: int = Query(24, ge=1, le=720),
    min_frequency: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Get word cloud data from stored topic_keywords table (incremental, gets better over time)"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")

                # Check which topic tables exist
                cur.execute(
                    """
                    SELECT
                        EXISTS (SELECT FROM information_schema.tables WHERE table_schema = %s AND table_name = 'topic_keywords') as has_keywords,
                        EXISTS (SELECT FROM information_schema.tables WHERE table_schema = %s AND table_name = 'topic_clusters') as has_clusters,
                        EXISTS (SELECT FROM information_schema.tables WHERE table_schema = %s AND table_name = 'topics') as has_topics
                """,
                    (schema, schema, schema),
                )
                table_check = cur.fetchone()
                has_topic_keywords = table_check[0]
                has_topic_clusters = table_check[1]
                has_topics = table_check[2]

                word_cloud_data = []
                categories = {}

                # Priority 1: Use topic_keywords if available (best - incremental data)
                if has_topic_keywords:
                    # Use topic_keywords table (preferred - incremental data)
                    cur.execute(
                        f"""
                        SELECT
                            tk.keyword,
                            tk.keyword_type,
                            tk.frequency_count,
                            tk.importance_score,
                            tk.tf_idf_score,
                            tc.cluster_name,
                            tc.article_count,
                            tc.relevance_score as topic_relevance
                        FROM {schema}.topic_keywords tk
                        JOIN {schema}.topic_clusters tc ON tk.topic_cluster_id = tc.id
                        WHERE tk.frequency_count >= %s
                        ORDER BY tk.importance_score DESC, tk.frequency_count DESC
                        LIMIT %s
                    """,
                        (min_frequency, limit),
                    )

                    for row in cur.fetchall():
                        (
                            keyword,
                            keyword_type,
                            freq_count,
                            importance,
                            tf_idf,
                            cluster_name,
                            article_count,
                            topic_relevance,
                        ) = row
                        word_cloud_data.append(
                            {
                                "text": keyword,
                                "size": min(100, max(20, int(freq_count * 2))),
                                "frequency": freq_count,
                                "relevance": float(importance) if importance else 0.0,
                                "articles": article_count or 0,
                                "quality_score": float(topic_relevance) if topic_relevance else 0.0,
                                "category": keyword_type or "general",
                                "topic": cluster_name,
                                "tf_idf": float(tf_idf) if tf_idf else 0.0,
                            }
                        )

                    # Get category stats
                    cur.execute(
                        f"""
                        SELECT
                            tk.keyword_type,
                            COUNT(*) as count,
                            SUM(tk.frequency_count) as total_frequency
                        FROM {schema}.topic_keywords tk
                        WHERE tk.frequency_count >= %s
                        GROUP BY tk.keyword_type
                    """,
                        (min_frequency,),
                    )

                    for row in cur.fetchall():
                        cat_type, count, total_freq = row
                        categories[cat_type or "general"] = {
                            "count": count,
                            "total_frequency": total_freq or 0,
                        }
                else:
                    # Fallback: Use topic_clusters directly - use cluster_name as the word cloud word
                    # This is simpler and more direct - each topic cluster becomes a word in the cloud
                    cur.execute(
                        f"""
                        SELECT
                            tc.cluster_name,
                            tc.cluster_keywords,
                            tc.article_count,
                            tc.relevance_score,
                            tc.cluster_type,
                            COUNT(atc.article_id) as actual_article_count
                        FROM {schema}.topic_clusters tc
                        LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                        GROUP BY tc.id, tc.cluster_name, tc.cluster_keywords, tc.article_count, tc.relevance_score, tc.cluster_type
                        HAVING COUNT(atc.article_id) >= %s
                        ORDER BY COUNT(atc.article_id) DESC, tc.relevance_score DESC
                        LIMIT %s
                    """,
                        (min_frequency, limit),
                    )

                    for row in cur.fetchall():
                        (
                            cluster_name,
                            cluster_keywords,
                            article_count,
                            relevance_score,
                            cluster_type,
                            actual_count,
                        ) = row

                        if not cluster_name:
                            continue

                        # Use cluster_name as the primary word (it's the topic name)
                        # This makes the word cloud show actual topic names, not individual keywords
                        word_cloud_data.append(
                            {
                                "text": cluster_name,
                                "size": min(
                                    100, max(20, int((actual_count or article_count or 1) * 3))
                                ),  # Scale based on article count
                                "frequency": actual_count or article_count or 1,
                                "relevance": float(relevance_score) if relevance_score else 0.5,
                                "articles": actual_count or article_count or 0,
                                "quality_score": float(relevance_score) if relevance_score else 0.5,
                                "category": cluster_type or "general",
                                "topic": cluster_name,  # Same as text for topic-based word cloud
                            }
                        )

                        # Also extract individual keywords from cluster_keywords if available
                        if cluster_keywords:
                            keywords_to_add = []
                            if isinstance(cluster_keywords, list):
                                keywords_to_add.extend(cluster_keywords)
                            elif isinstance(cluster_keywords, dict):
                                keywords_to_add.extend(cluster_keywords.get("keywords", []))

                            # Add keywords as additional words (smaller size)
                            for keyword in set(keywords_to_add):
                                if (
                                    keyword
                                    and len(keyword) > 2
                                    and keyword.lower() != cluster_name.lower()
                                ):
                                    word_cloud_data.append(
                                        {
                                            "text": keyword,
                                            "size": min(
                                                80,
                                                max(
                                                    15,
                                                    int((actual_count or article_count or 1) * 2),
                                                ),
                                            ),
                                            "frequency": max(
                                                1, (actual_count or article_count or 1) // 2
                                            ),
                                            "relevance": float(relevance_score)
                                            if relevance_score
                                            else 0.4,
                                            "articles": max(
                                                1, (actual_count or article_count or 1) // 2
                                            ),
                                            "quality_score": float(relevance_score)
                                            if relevance_score
                                            else 0.4,
                                            "category": cluster_type or "general",
                                            "topic": cluster_name,
                                        }
                                    )

                    # Group by category
                    for word in word_cloud_data:
                        cat = word.get("category", "general")
                        if cat not in categories:
                            categories[cat] = {"count": 0, "total_frequency": 0}
                        categories[cat]["count"] += 1
                        categories[cat]["total_frequency"] += word.get("frequency", 0)

                # Priority 2: Fallback to 'topics' table (what management tab uses)
                if len(word_cloud_data) == 0 and has_topics:
                    # Show all active topics, even if they have 0 articles
                    # This matches what the management tab shows
                    cur.execute(
                        f"""
                        SELECT
                            t.name,
                            t.category,
                            t.keywords,
                            COUNT(DISTINCT ata.article_id) as article_count,
                            t.confidence_score
                        FROM {schema}.topics t
                        LEFT JOIN {schema}.article_topic_assignments ata ON t.id = ata.topic_id
                        WHERE t.status = 'active'
                        GROUP BY t.id, t.name, t.category, t.keywords, t.confidence_score
                        ORDER BY COUNT(DISTINCT ata.article_id) DESC, t.confidence_score DESC
                        LIMIT %s
                    """,
                        (limit,),
                    )

                    for row in cur.fetchall():
                        topic_name, category, keywords, article_count, confidence = row

                        if not topic_name:
                            continue

                        # Use topic name as the word
                        # Even if article_count is 0, show the topic (but with smaller size)
                        actual_count = article_count or 0
                        word_cloud_data.append(
                            {
                                "text": topic_name,
                                "size": min(
                                    100, max(20, int((actual_count + 1) * 3))
                                ),  # +1 to ensure minimum size
                                "frequency": actual_count or 1,  # Show as 1 if 0 for visibility
                                "relevance": float(confidence) if confidence else 0.5,
                                "articles": actual_count,
                                "quality_score": float(confidence) if confidence else 0.5,
                                "category": category or "general",
                                "topic": topic_name,
                            }
                        )

                        # Also add keywords from the topic if available
                        if keywords:
                            keyword_list = keywords if isinstance(keywords, list) else []
                            for keyword in keyword_list[:5]:  # Limit to 5 keywords per topic
                                if (
                                    keyword
                                    and len(keyword) > 2
                                    and keyword.lower() != topic_name.lower()
                                ):
                                    word_cloud_data.append(
                                        {
                                            "text": keyword,
                                            "size": min(80, max(15, int((article_count or 1) * 2))),
                                            "frequency": max(1, (article_count or 1) // 2),
                                            "relevance": float(confidence) if confidence else 0.4,
                                            "articles": max(1, (article_count or 1) // 2),
                                            "quality_score": float(confidence)
                                            if confidence
                                            else 0.4,
                                            "category": category or "general",
                                            "topic": topic_name,
                                        }
                                    )

                    # Update categories
                    for word in word_cloud_data:
                        cat = word.get("category", "general")
                        if cat not in categories:
                            categories[cat] = {"count": 0, "total_frequency": 0}
                        categories[cat]["count"] += 1
                        categories[cat]["total_frequency"] += word.get("frequency", 0)

                # If still no data found, check if any topics exist at all
                if len(word_cloud_data) == 0:
                    topic_count = 0
                    if has_topics:
                        cur.execute(f"SELECT COUNT(*) FROM {schema}.topics WHERE status = 'active'")
                        topic_count = cur.fetchone()[0] or 0
                    if has_topic_clusters and topic_count == 0:
                        cur.execute(f"SELECT COUNT(*) FROM {schema}.topic_clusters")
                        topic_count = cur.fetchone()[0] or 0

                    if topic_count == 0:
                        logger.info(
                            f"No topics found in {schema} schema - clustering may be needed"
                        )
                        return {
                            "success": True,
                            "data": {
                                "word_cloud": [],
                                "total_keywords": 0,
                                "categories": {},
                                "source": "none",
                                "incremental": False,
                                "message": "No topics found. Run topic clustering to create topics.",
                            },
                            "timestamp": datetime.now().isoformat(),
                        }

                # Exclude dates, days, months, country identifiers, and banned topics from topic cloud
                banned = _get_banned_topics(cur, schema)
                word_cloud_data = filter_word_cloud_entries(
                    word_cloud_data, text_key="text", banned_topics=banned
                )
                word_cloud_data = _augment_word_cloud_with_entity_signals(
                    cur, schema, word_cloud_data, time_period_hours, limit
                )
                # Rebuild category stats after filtering
                categories = {}
                for word in word_cloud_data:
                    cat = word.get("category", "general")
                    if cat not in categories:
                        categories[cat] = {"count": 0, "total_frequency": 0}
                    categories[cat]["count"] += 1
                    categories[cat]["total_frequency"] += word.get("frequency", 0)

                return {
                    "success": True,
                    "data": {
                        "word_cloud": word_cloud_data,
                        "total_keywords": len(word_cloud_data),
                        "categories": categories,
                        "source": "hybrid_entity_context_topic",
                        "incremental": has_topic_keywords,  # Only incremental if using topic_keywords
                    },
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching word cloud data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_banned_topics(cur, schema: str) -> set:
    """Fetch banned topic names for a domain (lowercased for case-insensitive matching)."""
    try:
        cur.execute(f"SELECT topic_name FROM {schema}.banned_topics")
        return {row[0].lower().strip() for row in cur.fetchall() if row[0]}
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return set()


def _attach_topic_trend_signals(
    cur, schema: str, topics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Enrich topics with context/entity-backed trend signals so topics represent
    bigger-picture themes across multiple participants and perspectives.
    """
    if not topics:
        return topics
    topic_ids = [t.get("id") for t in topics if t.get("id") is not None]
    if not topic_ids:
        return topics

    domain_key = schema  # intelligence domain_key uses science_tech format
    counts_by_topic: dict[int, dict[str, int]] = {}
    top_entities_by_topic: dict[int, list[str]] = {}

    try:
        cur.execute(
            f"""
            SELECT
                atc.topic_cluster_id,
                COUNT(DISTINCT atc.article_id) AS article_count,
                COUNT(DISTINCT a2c.context_id) AS context_count,
                COUNT(DISTINCT cem.entity_profile_id) AS entity_count
            FROM {schema}.article_topic_clusters atc
            LEFT JOIN intelligence.article_to_context a2c
              ON a2c.article_id = atc.article_id
             AND a2c.domain_key = %s
            LEFT JOIN intelligence.context_entity_mentions cem
              ON cem.context_id = a2c.context_id
            WHERE atc.topic_cluster_id = ANY(%s)
            GROUP BY atc.topic_cluster_id
        """,
            (domain_key, topic_ids),
        )
        for row in cur.fetchall():
            counts_by_topic[row[0]] = {
                "articles": row[1] or 0,
                "contexts": row[2] or 0,
                "entities": row[3] or 0,
            }
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass

    try:
        cur.execute(
            f"""
            SELECT topic_cluster_id, entity_name, mentions
            FROM (
                SELECT
                    atc.topic_cluster_id,
                    COALESCE(
                        ep.metadata->>'canonical_name',
                        ep.metadata->>'name'
                    ) AS entity_name,
                    COUNT(*) AS mentions,
                    ROW_NUMBER() OVER (
                        PARTITION BY atc.topic_cluster_id
                        ORDER BY COUNT(*) DESC
                    ) AS rn
                FROM {schema}.article_topic_clusters atc
                JOIN intelligence.article_to_context a2c
                  ON a2c.article_id = atc.article_id
                 AND a2c.domain_key = %s
                JOIN intelligence.context_entity_mentions cem
                  ON cem.context_id = a2c.context_id
                JOIN intelligence.entity_profiles ep
                  ON ep.id = cem.entity_profile_id
                WHERE atc.topic_cluster_id = ANY(%s)
                GROUP BY atc.topic_cluster_id, entity_name
            ) ranked
            WHERE rn <= 4
              AND entity_name IS NOT NULL
              AND BTRIM(entity_name) <> ''
            ORDER BY topic_cluster_id, mentions DESC
        """,
            (domain_key, topic_ids),
        )
        for topic_id, entity_name, _mentions in cur.fetchall():
            top_entities_by_topic.setdefault(topic_id, []).append(entity_name)
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass

    for topic in topics:
        topic_id = topic.get("id")
        counts = counts_by_topic.get(topic_id, {"articles": 0, "contexts": 0, "entities": 0})
        top_entities = top_entities_by_topic.get(topic_id, [])
        topic["trend_signals"] = {
            "backed_by": "entity_context",
            "articles": counts["articles"],
            "contexts": counts["contexts"],
            "entities": counts["entities"],
            "top_entities": top_entities,
        }
        topic["theme_strength"] = (
            counts["articles"] * 1.0 + counts["contexts"] * 1.25 + counts["entities"] * 1.5
        )
    return topics


def _augment_word_cloud_with_entity_signals(
    cur,
    schema: str,
    word_cloud_data: list[dict[str, Any]],
    time_period_hours: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Add entity-backed trend items from contexts to the topic word cloud."""
    if limit <= 0:
        return word_cloud_data

    domain_key = schema
    existing = {str(w.get("text", "")).strip().lower() for w in word_cloud_data if w.get("text")}
    room = max(0, min(20, limit) - min(len(word_cloud_data), min(20, limit)))
    if room <= 0:
        room = 8

    try:
        cur.execute(
            """
            SELECT
                COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name') AS entity_name,
                COUNT(*) AS mentions
            FROM intelligence.contexts c
            JOIN intelligence.context_entity_mentions cem
              ON cem.context_id = c.id
            JOIN intelligence.entity_profiles ep
              ON ep.id = cem.entity_profile_id
            WHERE c.domain_key = %s
              AND c.created_at >= NOW() - (%s * INTERVAL '1 hour')
            GROUP BY entity_name
            HAVING COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name') IS NOT NULL
            ORDER BY mentions DESC
            LIMIT %s
        """,
            (domain_key, max(1, time_period_hours), room),
        )
        for entity_name, mentions in cur.fetchall():
            if not entity_name:
                continue
            key = entity_name.strip().lower()
            if not key or key in existing:
                continue
            freq = int(mentions or 0)
            word_cloud_data.append(
                {
                    "text": entity_name,
                    "size": min(100, max(18, int(freq * 3))),
                    "frequency": freq,
                    "relevance": min(1.0, 0.35 + (freq / 30.0)),
                    "articles": 0,
                    "quality_score": min(1.0, 0.35 + (freq / 30.0)),
                    "category": "entity_signal",
                    "topic": "entity_context_trends",
                }
            )
            existing.add(key)
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
    return word_cloud_data


@router.get("/{domain}/content_analysis/topics/banned")
async def get_banned_topics(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)):
    """List all banned topics for a domain."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(
                    f"SELECT id, topic_name, created_at, reason FROM {schema}.banned_topics ORDER BY topic_name"
                )
                rows = cur.fetchall()
                banned = [
                    {
                        "id": r[0],
                        "topic_name": r[1],
                        "created_at": r[2].isoformat() if r[2] else None,
                        "reason": r[3],
                    }
                    for r in rows
                ]
                return {"success": True, "data": banned}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching banned topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/content_analysis/topics/banned")
async def ban_topic(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN), body: dict[str, Any] = Body(...)
):
    """Add a topic to the banned list."""
    topic_name = body.get("topic_name") or body.get("topic")
    if not topic_name or not isinstance(topic_name, str):
        raise HTTPException(status_code=400, detail="topic_name is required")
    topic_name = topic_name.strip()
    if not topic_name:
        raise HTTPException(status_code=400, detail="topic_name cannot be empty")
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(
                    f"INSERT INTO {schema}.banned_topics (topic_name, reason) VALUES (%s, %s) ON CONFLICT (topic_name) DO NOTHING RETURNING id",
                    (topic_name, body.get("reason")),
                )
                row = cur.fetchone()
                conn.commit()
                if row:
                    return {
                        "success": True,
                        "message": f"Topic '{topic_name}' banned",
                        "id": row[0],
                    }
                return {"success": True, "message": f"Topic '{topic_name}' was already banned"}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error banning topic: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{domain}/content_analysis/topics/banned/{topic_name:path}")
async def unban_topic(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN), topic_name: str = Path(...)
):
    """Remove a topic from the banned list."""
    if not topic_name:
        raise HTTPException(status_code=400, detail="topic_name is required")
    topic_name = topic_name.strip()
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(
                    f"DELETE FROM {schema}.banned_topics WHERE LOWER(topic_name) = LOWER(%s)",
                    (topic_name,),
                )
                deleted = cur.rowcount
                conn.commit()
                return {
                    "success": True,
                    "message": "Topic unbanned" if deleted else "Topic was not banned",
                    "deleted": deleted > 0,
                }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unbanning topic: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/topics/big_picture")
async def get_big_picture_analysis(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    time_period_hours: int = Query(24, ge=1, le=720),
):
    """Get big picture analysis of current topics and trends for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")

                # Get recent articles count
                cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles WHERE created_at >= %s
                """,
                    (cutoff_time,),
                )
                recent_articles_count = cur.fetchone()[0]

                # Get topic distribution
                # FIXED: Use article_topic_clusters (not article_topic_assignments)
                cur.execute(
                    f"""
                    SELECT tc.cluster_name, COUNT(atc.article_id) as article_count
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    LEFT JOIN {schema}.articles a ON atc.article_id = a.id
                    WHERE (a.created_at >= %s OR a.created_at IS NULL)
                    GROUP BY tc.cluster_name
                    ORDER BY article_count DESC
                """,
                    (cutoff_time,),
                )

                topic_distribution = []
                for row in cur.fetchall():
                    topic_distribution.append(
                        {
                            "category": row[0],
                            "article_count": row[1] or 0,
                            "percentage": round(
                                (row[1] or 0) / max(recent_articles_count, 1) * 100, 1
                            ),
                        }
                    )
                banned = _get_banned_topics(cur, schema)
                topic_distribution = filter_topic_list(
                    topic_distribution, name_key="category", banned_topics=banned
                )

                # Get trending topics (most active in recent period)
                cur.execute(
                    f"""
                    SELECT tc.cluster_name, COUNT(atc.article_id) as recent_articles,
                           AVG(atc.relevance_score) as avg_relevance
                    FROM {schema}.topic_clusters tc
                    JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    JOIN {schema}.articles a ON atc.article_id = a.id
                    WHERE a.created_at >= %s
                    GROUP BY tc.id, tc.cluster_name
                    ORDER BY recent_articles DESC, avg_relevance DESC
                    LIMIT 10
                """,
                    (cutoff_time,),
                )

                trending_topics = []
                for row in cur.fetchall():
                    trending_topics.append(
                        {
                            "name": row[0],
                            "recent_articles": row[1],
                            "avg_relevance": float(row[2]) if row[2] else 0.0,
                            "trend_score": row[1] * (float(row[2]) if row[2] else 0.0),
                        }
                    )
                trending_topics = filter_topic_list(
                    trending_topics, name_key="name", banned_topics=banned
                )

                # Get source diversity
                cur.execute(
                    f"""
                    SELECT source_domain, COUNT(*) as article_count
                    FROM {schema}.articles
                    WHERE created_at >= %s
                    GROUP BY source_domain
                    ORDER BY article_count DESC
                    LIMIT 10
                """,
                    (cutoff_time,),
                )

                source_diversity = []
                for row in cur.fetchall():
                    source_diversity.append(
                        {
                            "source": row[0],
                            "article_count": row[1],
                            "percentage": round(row[1] / max(recent_articles_count, 1) * 100, 1),
                        }
                    )

                # Calculate insights
                insights = {
                    "total_articles": recent_articles_count,
                    "active_topics": len(topic_distribution),
                    "top_category": topic_distribution[0]["category"]
                    if topic_distribution
                    else "None",
                    "source_diversity": len(source_diversity),
                    "avg_articles_per_topic": round(
                        recent_articles_count / max(len(topic_distribution), 1), 1
                    ),
                    "time_period_hours": time_period_hours,
                }

                # Build narrative summary from available data
                top_cat = topic_distribution[0]["category"] if topic_distribution else "general"
                top_cat_count = topic_distribution[0]["count"] if topic_distribution else 0
                trending_names = [
                    t.get("name", "") for t in (trending_topics or [])[:3] if t.get("name")
                ]
                narrative_parts = []
                narrative_parts.append(
                    f"Over the last {time_period_hours} hours, {recent_articles_count} articles were analyzed "
                    f"across {len(topic_distribution)} categories from {len(source_diversity)} sources."
                )
                if top_cat and top_cat_count:
                    narrative_parts.append(
                        f"Coverage is led by {top_cat} ({top_cat_count} articles)."
                    )
                if trending_names:
                    narrative_parts.append(f"Trending topics include {', '.join(trending_names)}.")

                return {
                    "success": True,
                    "data": {
                        "insights": insights,
                        "topic_distribution": topic_distribution,
                        "trending_topics": trending_topics,
                        "source_diversity": source_diversity,
                        "narrative": " ".join(narrative_parts),
                        "summary": {
                            "period": f"Last {time_period_hours} hours",
                            "articles_analyzed": recent_articles_count,
                            "topics_active": len(topic_distribution),
                            "sources": len(source_diversity),
                        },
                    },
                    "message": f"Big picture analysis for last {time_period_hours} hours",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error generating big picture analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/content_analysis/topics/trending")
async def get_trending_topics(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    time_period_hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
):
    """Get trending topics with trend analysis for a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        schema = domain.replace("-", "_")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Set search path to domain schema
                cur.execute(f"SET search_path TO {schema}, public")

                cutoff_time = datetime.now() - timedelta(hours=time_period_hours)

                # Get trending topics with trend analysis
                cur.execute(
                    f"""
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
                """,
                    (cutoff_time, limit),
                )

                trending_topics = []
                for row in cur.fetchall():
                    trend_score = row[1] * (float(row[2]) if row[2] else 0.0) * (row[5] or 1)
                    topic_name = row[0] or ""
                    article_count = row[1] or 0
                    source_count = row[5] or 0
                    direction = "rising" if article_count > 5 else "stable"
                    description = (
                        f"{article_count} articles from {source_count} sources, {direction} trend"
                    )

                    trending_topics.append(
                        {
                            "name": topic_name,
                            "description": description,
                            "category": "semantic",
                            "recent_articles": article_count,
                            "avg_relevance": float(row[2]) if row[2] else 0.0,
                            "avg_sentiment": float(row[3]) if row[3] else 0.0,
                            "latest_article_date": row[4].isoformat() if row[4] else None,
                            "source_diversity": source_count,
                            "trend_score": round(trend_score, 2),
                            "trend_direction": direction,
                        }
                    )
                banned = _get_banned_topics(cur, schema)
                trending_topics = filter_topic_list(
                    trending_topics, name_key="name", banned_topics=banned
                )

                return {
                    "success": True,
                    "data": {
                        "trending_topics": trending_topics,
                        "time_period_hours": time_period_hours,
                        "total_trending": len(trending_topics),
                    },
                    "message": f"Retrieved {len(trending_topics)} trending topics",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task for article clustering
async def process_article_clustering(
    limit: int, domain: str = "politics", time_period_hours: int = 24
):
    """Background task for clustering articles into topics using LLM (with fallback)"""
    start_time = datetime.now()
    logger.info(
        f"🚀 Starting article clustering for domain '{domain}' (limit={limit}, time_period={time_period_hours}h)"
    )

    try:
        # Try LLM-based extraction first, fallback to rule-based if unavailable
        try:
            from ..services.llm_topic_extractor import LLMTopicExtractor

            schema = domain.replace("-", "_")
            logger.debug(f"Using schema: {schema}")

            extractor = LLMTopicExtractor(get_db_connection, schema=schema)
            logger.info("✅ Using LLM-based topic extraction (with resource management)")

            # Extract topics from recent articles using LLM
            logger.info(
                f"Extracting topics from articles in last {time_period_hours} hours using LLM..."
            )
            topics = await extractor.extract_topics_from_articles(
                time_period_hours=time_period_hours
            )

        except Exception as llm_error:
            logger.warning(f"⚠️ LLM extraction failed: {llm_error}")
            logger.info("Articles will be queued for LLM processing when available")

            # Queue articles for LLM processing (no fallback - ensures eventual consistency)
            schema = domain.replace("-", "_")
            extractor = LLMTopicExtractor(get_db_connection, schema=schema)

            # Get articles and queue them
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cutoff_time = datetime.now() - timedelta(hours=time_period_hours)
                        cur.execute(
                            f"""
                            SELECT id FROM {schema}.articles
                            WHERE created_at >= %s
                            AND content IS NOT NULL
                            AND LENGTH(content) > 100
                        """,
                            (cutoff_time,),
                        )
                        article_ids = [row[0] for row in cur.fetchall()]

                        for article_id in article_ids:
                            extractor._queue_article_for_llm_extraction(
                                article_id,
                                priority=2,
                                error_message=f"LLM unavailable during initial clustering: {llm_error}",
                            )

                        logger.info(
                            f"✅ Queued {len(article_ids)} articles for LLM topic extraction"
                        )
                finally:
                    conn.close()

            # Return empty topics - will be processed by queue worker
            topics = []
            logger.info(
                "Articles queued for LLM processing. Queue worker will process them when LLM is available."
            )

        logger.info(f"Topic extraction completed: {len(topics)} topics found")

        if topics:
            # Apply date/country filter - exclude before saving to DB
            topics = filter_topic_list(topics, name_key="name")
            if not topics:
                logger.info("All extracted topics filtered out (dates/countries) - nothing to save")
        if topics:
            # Generate word cloud data
            logger.debug("Generating word cloud data...")
            word_cloud_data = extractor.generate_word_cloud_data(topics)
            logger.debug(f"Word cloud generated: {len(word_cloud_data.get('words', []))} words")

            # Save topics to database
            logger.info(f"Saving {len(topics)} topics to database...")
            success = extractor.save_topics_to_database(topics)

            if success:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info("✅ Advanced topic extraction completed successfully:")
                logger.info(f"   - Topics extracted: {len(topics)}")
                logger.info(f"   - Word cloud words: {len(word_cloud_data.get('words', []))}")
                logger.info(f"   - Processing time: {elapsed:.2f}s")
                logger.info(f"   - Domain: {domain}")
            else:
                logger.error("❌ Failed to save topics to database")
        else:
            elapsed = (datetime.now() - start_time).total_seconds()
            # Check if articles were queued
            schema = domain.replace("-", "_")
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"SET search_path TO {schema}, public")
                        cur.execute(f"""
                            SELECT COUNT(*) FROM {schema}.topic_extraction_queue
                            WHERE status = 'pending'
                        """)
                        queued_count = cur.fetchone()[0] or 0
                        if queued_count > 0:
                            logger.info(
                                f"📋 {queued_count} articles queued for LLM topic extraction"
                            )
                            logger.info("   - Queue worker will process them when LLM is available")
                except:
                    pass
                finally:
                    conn.close()

            logger.warning(
                f"⚠️  No topics extracted from recent articles (last {time_period_hours}h)"
            )
            logger.info(f"   - Processing time: {elapsed:.2f}s")
            logger.info(f"   - Domain: {domain}")
            logger.info(
                "   - This may be normal if no articles exist in the time window or articles are queued"
            )

    except ImportError as e:
        logger.error(f"❌ Import error in article clustering: {e}")
        logger.exception("Full traceback:")
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Error in advanced article clustering (after {elapsed:.2f}s):")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Error message: {str(e)}")
        logger.exception("Full traceback:")
        # Re-raise to ensure error is visible in logs
        raise


@router.get("/articles/{article_id}")
async def get_individual_article(article_id: int):
    """Get a specific article by ID"""
    try:
        schema = resolve_article_id_to_schema(article_id)
        if not schema:
            raise HTTPException(status_code=404, detail="Article not found")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, url, content, summary, source_domain,
                           published_at, word_count, processing_status,
                           created_at, updated_at
                    FROM {schema}.articles
                    WHERE id = %s
                """,
                    (article_id,),
                )

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
                    "updated_at": row[10].isoformat() if row[10] else None,
                }

                return {"success": True, "data": article, "timestamp": datetime.now().isoformat()}

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching article {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task for comprehensive storyline processing
async def process_new_storyline_comprehensive(domain: str, storyline_id: int, schema: str):
    """
    Process a newly created storyline with comprehensive LLM analysis.
    Generates summary, timeline, and full breakdown.
    """
    try:
        from domains.storyline_management.routes.storyline_management import (
            process_storyline_rag_analysis,
        )
        from domains.storyline_management.services.storyline_service import StorylineService
        from shared.database.connection import get_db_connection

        logger.info(
            f"Starting comprehensive processing for storyline {storyline_id} (domain: {domain})"
        )

        storyline_service = StorylineService(domain=domain)

        # Step 1: Generate comprehensive summary with breakdown
        logger.info(f"Generating comprehensive summary for storyline {storyline_id}")
        summary_result = await storyline_service.generate_storyline_summary(storyline_id)

        if summary_result.get("success"):
            logger.info(f"✅ Generated comprehensive summary for storyline {storyline_id}")
        else:
            logger.warning(
                f"Summary generation returned: {summary_result.get('error', 'Unknown error')}"
            )

        # Step 2: Extract timeline events from articles
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {schema}, public")

                    # Get storyline and articles
                    cur.execute(
                        f"""
                        SELECT s.title, s.description, s.analysis_summary
                        FROM {schema}.storylines s
                        WHERE s.id = %s
                    """,
                        (storyline_id,),
                    )

                    storyline = cur.fetchone()
                    if storyline:
                        cur.execute(
                            f"""
                            SELECT a.id, a.title, a.content, a.summary, a.published_at, a.source_domain, a.url
                            FROM {schema}.articles a
                            JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                            WHERE sa.storyline_id = %s
                            ORDER BY a.published_at ASC
                        """,
                            (storyline_id,),
                        )

                        articles = cur.fetchall()

                        if articles:
                            # Trigger RAG analysis which includes timeline extraction
                            await process_storyline_rag_analysis(
                                domain, storyline_id, storyline, articles
                            )
                            logger.info(
                                f"✅ Triggered RAG analysis and timeline extraction for storyline {storyline_id}"
                            )
            finally:
                conn.close()

        # Step 3: Update processing status
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET search_path TO {schema}, public")
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET ml_processing_status = 'completed',
                            updated_at = %s
                        WHERE id = %s
                    """,
                        (datetime.now(), storyline_id),
                    )
                    conn.commit()
                    logger.info(
                        f"✅ Completed comprehensive processing for storyline {storyline_id}"
                    )
            finally:
                conn.close()

    except Exception as e:
        logger.error(f"Error in comprehensive storyline processing for {storyline_id}: {e}")
        logger.exception("Full traceback:")

        # Update status to indicate error (but don't mark as failed - let it retry)
        try:
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"SET search_path TO {schema}, public")
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET ml_processing_status = 'pending',
                                updated_at = %s
                            WHERE id = %s
                        """,
                            (datetime.now(), storyline_id),
                        )
                        conn.commit()
                finally:
                    conn.close()
        except Exception as update_error:
            logger.error(f"Error updating storyline status after processing error: {update_error}")
