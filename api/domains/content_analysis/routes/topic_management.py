"""
Topic Clustering and Auto-Tagging Routes
Handles topic extraction, assignment, and iterative learning feedback
"""

import logging
from datetime import datetime

from domains.content_analysis.services.topic_clustering_service import TopicClusteringService
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path, Query
from pydantic import BaseModel
from shared.database.connection import get_db_config, get_db_connection
from shared.domain_registry import DOMAIN_PATH_PATTERN, resolve_domain_schema
from shared.services.domain_aware_service import (
    get_domain_data_schemas,
    parse_optional_domain_to_schema,
    validate_domain,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api", tags=["Topic Management"], responses={404: {"description": "Not found"}}
)

# Database configuration (should match your setup)
DB_CONFIG = {
    "host": "localhost",
    "database": "news_intelligence",
    "user": "newsapp",
    "password": "newsapp_password",
    "port": 5432,
}

from shared.topic_cluster_reads import cluster_row_to_topic_api, resolve_cluster_schema


# ============================================================================
# Pydantic Models
# ============================================================================


class TopicFeedback(BaseModel):
    """Feedback model for topic assignment"""

    is_correct: bool
    feedback_notes: str | None = None
    validated_by: str | None = None


class TopicCreate(BaseModel):
    """Model for creating a new topic (domain comes from URL path)."""

    name: str
    description: str | None = None
    category: str | None = None
    keywords: list[str] | None = None


class TopicUpdate(BaseModel):
    """Model for updating a topic"""

    description: str | None = None
    category: str | None = None
    keywords: list[str] | None = None
    status: str | None = None


class TopicMerge(BaseModel):
    """Model for merging topics"""

    topic_ids: list[int]
    keep_primary: bool = True  # If True, keep first topic; if False, create new merged topic
    domain: str = "politics"


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def health_check():
    """Health check for Topic Management domain"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        conn.close()

        return {
            "success": True,
            "domain": "topic_management",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "topic_management",
            "status": "unhealthy",
            "error": str(e),
        }


# ============================================================================
# Topic CRUD Operations
# ============================================================================


@router.get("/{domain}/topics/needing_review")
async def get_topics_needing_review(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    threshold: float = Query(0.6, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Topics that need review for a domain silo (accuracy below threshold).
    """
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    try:
        topic_service = TopicClusteringService(get_db_config(), domain=domain)
        topics = topic_service.get_topics_needing_review(threshold=threshold, limit=limit)

        return {
            "success": True,
            "data": {"topics": topics, "count": len(topics), "threshold": threshold, "domain": domain},
        }

    except Exception as e:
        logger.error(f"Error getting topics needing review: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/topics")
async def get_domain_topics(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(50, ge=1, le=100),  # Max 100 for performance
    offset: int = Query(0, ge=0),
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = Query(
        "accuracy_score", regex="^(name|accuracy_score|confidence_score|review_count|created_at)$"
    ),
):
    """
    Get list of topics for a specific domain with filtering and sorting

    Args:
        domain: Registry domain URL key
        limit: Maximum number of topics to return
        offset: Number of topics to skip
        category: Filter by category
        status: Filter by status (active, reviewed, archived)
        search: Search in topic names
        sort_by: Field to sort by
    """
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        # Get schema name
        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Build query with schema qualification
                query = f"""
                    SELECT
                        tc.id,
                        tc.cluster_name,
                        NULL::text AS description,
                        COALESCE(tc.relevance_score, 0.5) AS relevance_score,
                        COALESCE(tc.article_count, COUNT(DISTINCT atc.article_id)) AS article_count,
                        tc.created_at,
                        tc.updated_at
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    WHERE 1=1
                """
                params = []

                if category:
                    pass  # topic_clusters has no category column

                if status:
                    pass  # legacy status filter ignored for clusters

                if search:
                    query += " AND tc.cluster_name ILIKE %s"
                    params.append(f"%{search}%")

                query += " GROUP BY tc.id"

                valid_sort_fields = {
                    "name": "tc.cluster_name",
                    "accuracy_score": "tc.relevance_score",
                    "confidence_score": "tc.relevance_score",
                    "review_count": "tc.article_count",
                    "created_at": "tc.created_at",
                }
                sort_field = valid_sort_fields.get(sort_by, "tc.relevance_score")
                query += f" ORDER BY {sort_field} DESC"

                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)

                topics = [cluster_row_to_topic_api(row) for row in cur.fetchall()]

                count_query = f"SELECT COUNT(*) FROM {schema}.topic_clusters WHERE 1=1"
                count_params = []
                if search:
                    count_query += " AND cluster_name ILIKE %s"
                    count_params.append(f"%{search}%")

                cur.execute(count_query, count_params)
                total = cur.fetchone()[0]

                return {
                    "success": True,
                    "data": {
                        "topics": topics,
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "domain": domain,
                    },
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/topics/{topic_id}")
async def get_topic(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic_id: int = Path(..., ge=1),
):
    """Get a single topic by ID within a domain silo."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            try:
                sch = resolve_cluster_schema(conn, topic_id, domain)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if not sch:
                raise HTTPException(status_code=404, detail="Topic not found")

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        tc.id,
                        tc.cluster_name,
                        NULL::text,
                        COALESCE(tc.relevance_score, 0.5),
                        COALESCE(tc.article_count, COUNT(DISTINCT atc.article_id)),
                        tc.created_at,
                        tc.updated_at
                    FROM {sch}.topic_clusters tc
                    LEFT JOIN {sch}.article_topic_clusters atc ON tc.id = atc.topic_cluster_id
                    WHERE tc.id = %s
                    GROUP BY tc.id
                """,
                    (topic_id,),
                )

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Topic not found")

                data = cluster_row_to_topic_api(row)
                data["domain_schema"] = sch
                return {"success": True, "data": data}

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting topic {topic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/topics")
async def create_topic(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic: TopicCreate = Body(...),
):
    """Create a new topic manually in a domain silo."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        try:
            sch = parse_optional_domain_to_schema(domain)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {sch}.topic_clusters (cluster_name, relevance_score, article_count, created_at, updated_at)
                    VALUES (%s, %s, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id, cluster_name, created_at
                """,
                    (
                        topic.name,
                        0.8,
                    ),
                )

                result = cur.fetchone()
                conn.commit()

                return {
                    "success": True,
                    "data": {
                        "id": result[0],
                        "topic_uuid": None,
                        "name": result[1],
                        "created_at": result[2].isoformat(),
                        "domain_schema": sch,
                    },
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error creating topic: {e}")
        if "unique_topic_name" in str(e):
            raise HTTPException(status_code=409, detail="Topic with this name already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{domain}/topics/{topic_id}")
async def update_topic(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic_id: int = Path(..., ge=1),
    topic_update: TopicUpdate = Body(...),
):
    """Update a topic in a domain silo."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        try:
            sch = parse_optional_domain_to_schema(domain)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                updates = []
                params: list = []

                if topic_update.description is not None:
                    pass

                if topic_update.category is not None:
                    pass

                if topic_update.keywords is not None:
                    pass

                if topic_update.status is not None:
                    pass

                cur.execute(
                    f"SELECT id FROM {sch}.topic_clusters WHERE id = %s",
                    (topic_id,),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Topic not found")

                if updates:
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(topic_id)
                    query = f"UPDATE {sch}.topic_clusters SET {', '.join(updates)} WHERE id = %s RETURNING id"
                    cur.execute(query, params)
                    if not cur.fetchone():
                        raise HTTPException(status_code=404, detail="Topic not found")

                conn.commit()
                return {"success": True, "message": "Topic updated successfully"}

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating topic {topic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Article-Topic Operations
# ============================================================================


@router.get("/{domain}/articles/{article_id}/topics")
async def get_domain_article_topics(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_id: int = Path(..., description="Article ID"),
):
    """Get all topics assigned to an article in a specific domain"""
    try:
        # Validate domain
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")

        schema = resolve_domain_schema(domain)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        atc.id as assignment_id,
                        tc.id, tc.cluster_name, NULL::text AS category, NULL::text AS description,
                        atc.confidence_score, atc.relevance_score,
                        FALSE AS is_validated, NULL::boolean AS is_correct, NULL::text AS feedback_notes,
                        'cluster' AS assignment_method, NULL::timestamptz AS created_at
                    FROM {schema}.article_topic_clusters atc
                    JOIN {schema}.topic_clusters tc ON atc.topic_cluster_id = tc.id
                    WHERE atc.article_id = %s
                    ORDER BY atc.confidence_score DESC NULLS LAST
                """,
                    (article_id,),
                )

                topics = []
                for row in cur.fetchall():
                    topics.append(
                        {
                            "id": row[0],  # assignment_id
                            "topic_id": row[1],
                            "topic_name": row[2],
                            "category": row[3],
                            "description": row[4],
                            "confidence_score": float(row[5]) if row[5] else 0.5,
                            "relevance_score": float(row[6]) if row[6] else 0.5,
                            "is_validated": row[7],
                            "is_correct": row[8],
                            "feedback_notes": row[9],
                            "assignment_method": row[10],
                            "assigned_at": row[11].isoformat() if row[11] else None,
                        }
                    )

                return {
                    "success": True,
                    "data": {
                        "article_id": article_id,
                        "topics": topics,
                        "count": len(topics),
                        "domain": domain,
                    },
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting article topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/articles/{article_id}/process_topics")
async def process_article_topics(
    background_tasks: BackgroundTasks,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_id: int = Path(..., ge=1),
):
    """
    Process an article to extract and assign topics using LLM

    This will:
    1. Extract topics from the article using LLM
    2. Create new topics if needed
    3. Assign topics to the article
    """
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        topic_service = TopicClusteringService(get_db_config(), domain=domain)
        result = await topic_service.process_article(article_id)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))

        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing article topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/topics/{topic_id}/articles")
async def get_topic_articles(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic_id: int = Path(..., ge=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get all articles assigned to a topic in a domain silo."""
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            try:
                sch = _resolve_topic_row_schema(conn, topic_id, domain)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            if not sch:
                raise HTTPException(status_code=404, detail="Topic not found")

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        ata.id as assignment_id,
                        a.id, a.title, a.url, a.source_domain,
                        a.published_at, a.summary,
                        ata.confidence_score, ata.relevance_score,
                        ata.is_validated, ata.is_correct, ata.feedback_notes
                    FROM {sch}.article_topic_assignments ata
                    JOIN {sch}.articles a ON ata.article_id = a.id
                    WHERE ata.topic_id = %s
                    ORDER BY ata.confidence_score DESC, a.published_at DESC
                    LIMIT %s OFFSET %s
                """,
                    (topic_id, limit, offset),
                )

                articles = []
                for row in cur.fetchall():
                    articles.append(
                        {
                            "assignment_id": row[0],
                            "id": row[1],
                            "title": row[2],
                            "url": row[3],
                            "source_domain": row[4],
                            "published_at": row[5].isoformat() if row[5] else None,
                            "summary": row[6],
                            "confidence_score": float(row[7]) if row[7] else 0.5,
                            "relevance_score": float(row[8]) if row[8] else 0.5,
                            "is_validated": row[9],
                            "is_correct": row[10],
                            "feedback_notes": row[11],
                        }
                    )

                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {sch}.article_topic_assignments
                    WHERE topic_id = %s
                """,
                    (topic_id,),
                )
                total = cur.fetchone()[0]

                return {
                    "success": True,
                    "data": {
                        "topic_id": topic_id,
                        "articles": articles,
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "domain_schema": sch,
                    },
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting topic articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Iterative Learning / Feedback
# ============================================================================


@router.post("/{domain}/assignments/{assignment_id}/feedback")
async def submit_feedback(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    assignment_id: int = Path(..., ge=1),
    feedback: TopicFeedback = Body(...),
):
    """
    Submit feedback on a topic assignment for iterative learning

    This will:
    1. Record the feedback
    2. Update topic accuracy metrics
    3. Record learning history
    """
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        topic_service = TopicClusteringService(get_db_config(), domain=domain)
        result = topic_service.record_feedback(
            assignment_id=assignment_id,
            is_correct=feedback.is_correct,
            feedback_notes=feedback.feedback_notes,
            validated_by=feedback.validated_by,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500, detail=result.get("error", "Feedback recording failed")
            )

        return {
            "success": True,
            "data": result,
            "message": "Feedback recorded successfully. Topic accuracy has been updated.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Operations
# ============================================================================


@router.post("/{domain}/articles/batch_process_topics")
async def batch_process_articles(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    article_ids: list[int] = Body(...),
):
    """
    Process multiple articles for topic extraction and assignment

    This will process articles in the background and return immediately.
    """
    try:
        import asyncio

        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        topic_service = TopicClusteringService(get_db_config(), domain=domain)

        # Process articles concurrently (but limit concurrency)
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent processes

        async def process_with_limit(article_id):
            async with semaphore:
                return await topic_service.process_article(article_id)

        tasks = [process_with_limit(aid) for aid in article_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful

        return {
            "success": True,
            "data": {
                "total": len(article_ids),
                "successful": successful,
                "failed": failed,
                "results": [r if isinstance(r, dict) else {"error": str(r)} for r in results],
            },
        }

    except Exception as e:
        logger.error(f"Error batch processing articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Topic Merge Operations
# ============================================================================


@router.post("/{domain}/topics/merge")
async def merge_topics(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    merge_request: TopicMerge = Body(...),
):
    """Merge topic_clusters — primary is first ID; secondaries deleted after reassignment."""
    from shared.topic_cluster_store import sync_cluster_article_count

    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
        if len(merge_request.topic_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 topics required for merge")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            sch = parse_optional_domain_to_schema(merge_request.domain or domain)
            primary_id = merge_request.topic_ids[0]
            secondary_ids = merge_request.topic_ids[1:]

            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(merge_request.topic_ids))
                cur.execute(
                    f"""
                    SELECT id, cluster_name FROM {sch}.topic_clusters
                    WHERE id IN ({placeholders})
                    """,
                    merge_request.topic_ids,
                )
                existing = {int(r[0]): r[1] for r in cur.fetchall()}
                if len(existing) != len(merge_request.topic_ids):
                    missing = set(merge_request.topic_ids) - set(existing.keys())
                    raise HTTPException(status_code=404, detail=f"Topics not found: {missing}")

                primary_name = existing[primary_id]
                for sec_id in secondary_ids:
                    cur.execute(
                        f"""
                        INSERT INTO {sch}.article_topic_clusters (article_id, topic_cluster_id, relevance_score, confidence_score)
                        SELECT article_id, %s, relevance_score, confidence_score
                        FROM {sch}.article_topic_clusters
                        WHERE topic_cluster_id = %s
                        ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
                            relevance_score = GREATEST({sch}.article_topic_clusters.relevance_score, EXCLUDED.relevance_score),
                            confidence_score = GREATEST({sch}.article_topic_clusters.confidence_score, EXCLUDED.confidence_score)
                        """,
                        (primary_id, sec_id),
                    )
                    cur.execute(
                        f"DELETE FROM {sch}.article_topic_clusters WHERE topic_cluster_id = %s",
                        (sec_id,),
                    )
                    cur.execute(
                        f"DELETE FROM {sch}.topic_keywords WHERE topic_cluster_id = %s",
                        (sec_id,),
                    )
                    cur.execute(f"DELETE FROM {sch}.topic_clusters WHERE id = %s", (sec_id,))

                sync_cluster_article_count(cur, sch, primary_id)
                conn.commit()

                return {
                    "success": True,
                    "data": {
                        "primary_topic": {"id": primary_id, "name": primary_name},
                        "merged_topics": [
                            {"id": tid, "name": existing[tid]} for tid in secondary_ids
                        ],
                        "merged_count": len(secondary_ids),
                        "message": f"Merged {len(secondary_ids)} clusters into '{primary_name}'",
                    },
                }
        finally:
            conn.close()

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error merging topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error merging topics: {str(e)}")
