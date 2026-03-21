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
from shared.domain_registry import DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import (
    DOMAIN_DATA_SCHEMAS,
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

# Note: TopicClusteringService is now domain-aware and should be initialized per-domain
# For routes, we'll create service instances as needed


def _resolve_topic_row_schema(conn, topic_id: int, domain: str | None) -> str | None:
    """Schema containing topics.id = topic_id; if domain set, only that schema."""
    if domain is not None and str(domain).strip():
        schemas = [parse_optional_domain_to_schema(domain)]
    else:
        schemas = list(DOMAIN_DATA_SCHEMAS)
    with conn.cursor() as cur:
        for sch in schemas:
            cur.execute(f"SELECT 1 FROM {sch}.topics WHERE id = %s", (topic_id,))
            if cur.fetchone():
                return sch
    return None


# ============================================================================
# Pydantic Models
# ============================================================================


class TopicFeedback(BaseModel):
    """Feedback model for topic assignment"""

    is_correct: bool
    feedback_notes: str | None = None
    validated_by: str | None = None


class TopicCreate(BaseModel):
    """Model for creating a new topic"""

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
        domain: Domain key (politics, finance, science-tech)
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
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Build query with schema qualification
                query = f"""
                    SELECT
                        t.id, t.topic_uuid, t.name, t.description, t.category,
                        t.keywords, t.confidence_score, t.accuracy_score,
                        t.review_count, t.correct_assignments, t.incorrect_assignments,
                        t.status, t.is_auto_generated, t.created_at, t.updated_at,
                        COUNT(DISTINCT ata.article_id) as article_count
                    FROM {schema}.topics t
                    LEFT JOIN {schema}.article_topic_assignments ata ON t.id = ata.topic_id
                    WHERE 1=1
                """
                params = []

                if category:
                    query += " AND t.category = %s"
                    params.append(category)

                if status:
                    query += " AND t.status = %s"
                    params.append(status)

                if search:
                    query += " AND t.name ILIKE %s"
                    params.append(f"%{search}%")

                query += " GROUP BY t.id"

                # Sorting
                valid_sort_fields = {
                    "name": "t.name",
                    "accuracy_score": "t.accuracy_score",
                    "confidence_score": "t.confidence_score",
                    "review_count": "t.review_count",
                    "created_at": "t.created_at",
                }
                sort_field = valid_sort_fields.get(sort_by, "t.accuracy_score")
                query += f" ORDER BY {sort_field} DESC"

                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)

                topics = []
                for row in cur.fetchall():
                    topics.append(
                        {
                            "id": row[0],
                            "topic_uuid": str(row[1]) if row[1] else None,
                            "name": row[2],
                            "description": row[3],
                            "category": row[4],
                            "keywords": row[5] or [],
                            "confidence_score": float(row[6]) if row[6] else 0.5,
                            "accuracy_score": float(row[7]) if row[7] else 0.5,
                            "review_count": row[8] or 0,
                            "correct_assignments": row[9] or 0,
                            "incorrect_assignments": row[10] or 0,
                            "status": row[11],
                            "is_auto_generated": row[12],
                            "article_count": row[15] or 0,  # Fixed: COUNT is at index 15, not 16
                            "created_at": row[13].isoformat() if row[13] else None,
                            "updated_at": row[14].isoformat() if row[14] else None,
                        }
                    )

                # Get total count from domain schema
                count_query = f"SELECT COUNT(*) FROM {schema}.topics WHERE 1=1"
                count_params = []
                if category:
                    count_query += " AND category = %s"
                    count_params.append(category)
                if status:
                    count_query += " AND status = %s"
                    count_params.append(status)
                if search:
                    count_query += " AND name ILIKE %s"
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


@router.get("/topics/{topic_id}")
async def get_topic(
    topic_id: int,
    domain: str | None = Query(
        None,
        description="politics, finance, or science-tech; omit to search all domain schemas",
    ),
):
    """Get a single topic by ID"""
    try:
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
                        t.id, t.topic_uuid, t.name, t.description, t.category,
                        t.keywords, t.confidence_score, t.accuracy_score,
                        t.review_count, t.correct_assignments, t.incorrect_assignments,
                        t.status, t.is_auto_generated, t.created_at, t.updated_at,
                        t.learning_data, t.last_improved_at,
                        COUNT(DISTINCT ata.article_id) as article_count
                    FROM {sch}.topics t
                    LEFT JOIN {sch}.article_topic_assignments ata ON t.id = ata.topic_id
                    WHERE t.id = %s
                    GROUP BY t.id
                """,
                    (topic_id,),
                )

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Topic not found")

                return {
                    "success": True,
                    "data": {
                        "id": row[0],
                        "topic_uuid": str(row[1]),
                        "name": row[2],
                        "description": row[3],
                        "category": row[4],
                        "keywords": row[5] or [],
                        "confidence_score": float(row[6]) if row[6] else 0.5,
                        "accuracy_score": float(row[7]) if row[7] else 0.5,
                        "review_count": row[8] or 0,
                        "correct_assignments": row[9] or 0,
                        "incorrect_assignments": row[10] or 0,
                        "status": row[11],
                        "is_auto_generated": row[12],
                        "article_count": row[17] or 0,
                        "learning_data": row[15] or {},
                        "last_improved_at": row[16].isoformat() if row[16] else None,
                        "created_at": row[13].isoformat() if row[13] else None,
                        "updated_at": row[14].isoformat() if row[14] else None,
                        "domain_schema": sch,
                    },
                }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting topic {topic_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/topics")
async def create_topic(topic: TopicCreate):
    """Create a new topic manually"""
    try:
        try:
            sch = parse_optional_domain_to_schema(topic.domain or "politics")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {sch}.topics (
                        name, description, category, keywords,
                        is_auto_generated, status, confidence_score, accuracy_score
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, topic_uuid, created_at
                """,
                    (
                        topic.name,
                        topic.description,
                        topic.category,
                        topic.keywords or [],
                        False,  # Manual creation
                        "active",
                        0.8,  # High confidence for manual topics
                        0.8,  # High accuracy for manual topics
                    ),
                )

                result = cur.fetchone()
                conn.commit()

                return {
                    "success": True,
                    "data": {
                        "id": result[0],
                        "topic_uuid": str(result[1]),
                        "name": topic.name,
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


@router.put("/topics/{topic_id}")
async def update_topic(
    topic_id: int,
    topic_update: TopicUpdate,
    domain: str = Query(
        "politics",
        description="Domain schema for this topic: politics, finance, or science-tech",
    ),
):
    """Update a topic"""
    try:
        try:
            sch = parse_optional_domain_to_schema(domain)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Build update query dynamically
                updates = []
                params = []

                if topic_update.description is not None:
                    updates.append("description = %s")
                    params.append(topic_update.description)

                if topic_update.category is not None:
                    updates.append("category = %s")
                    params.append(topic_update.category)

                if topic_update.keywords is not None:
                    updates.append("keywords = %s")
                    params.append(topic_update.keywords)

                if topic_update.status is not None:
                    updates.append("status = %s")
                    params.append(topic_update.status)

                if not updates:
                    raise HTTPException(status_code=400, detail="No fields to update")

                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(topic_id)

                query = f"UPDATE {sch}.topics SET {', '.join(updates)} WHERE id = %s RETURNING id"
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

        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        ata.id as assignment_id,
                        t.id, t.name, t.category, t.description,
                        ata.confidence_score, ata.relevance_score,
                        ata.is_validated, ata.is_correct, ata.feedback_notes,
                        ata.assignment_method, ata.created_at
                    FROM {schema}.article_topic_assignments ata
                    JOIN {schema}.topics t ON ata.topic_id = t.id
                    WHERE ata.article_id = %s
                    ORDER BY ata.confidence_score DESC
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


@router.post("/articles/{article_id}/process_topics")
async def process_article_topics(article_id: int, background_tasks: BackgroundTasks):
    """
    Process an article to extract and assign topics using LLM

    This will:
    1. Extract topics from the article using LLM
    2. Create new topics if needed
    3. Assign topics to the article
    """
    try:
        topic_service = TopicClusteringService(get_db_config(), domain="politics")
        result = await topic_service.process_article(article_id)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))

        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing article topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topics/{topic_id}/articles")
async def get_topic_articles(
    topic_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    domain: str | None = Query(
        None,
        description="politics, finance, or science-tech; omit to search all schemas",
    ),
):
    """Get all articles assigned to a topic"""
    try:
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


@router.post("/assignments/{assignment_id}/feedback")
async def submit_feedback(assignment_id: int, feedback: TopicFeedback):
    """
    Submit feedback on a topic assignment for iterative learning

    This will:
    1. Record the feedback
    2. Update topic accuracy metrics
    3. Record learning history
    """
    try:
        topic_service = TopicClusteringService(get_db_config(), domain="politics")
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


@router.get("/topics/needing_review")
async def get_topics_needing_review(
    threshold: float = Query(0.6, ge=0.0, le=1.0), limit: int = Query(50, ge=1, le=200)
):
    """
    Get topics that need review based on accuracy threshold

    Topics with accuracy below the threshold and with review history
    are returned for human review and correction.
    """
    try:
        topic_service = TopicClusteringService(get_db_config(), domain="politics")
        topics = topic_service.get_topics_needing_review(threshold=threshold, limit=limit)

        return {
            "success": True,
            "data": {"topics": topics, "count": len(topics), "threshold": threshold},
        }

    except Exception as e:
        logger.error(f"Error getting topics needing review: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Operations
# ============================================================================


@router.post("/articles/batch_process_topics")
async def batch_process_articles(
    article_ids: list[int] = Body(...), background_tasks: BackgroundTasks = None
):
    """
    Process multiple articles for topic extraction and assignment

    This will process articles in the background and return immediately.
    """
    try:
        import asyncio

        topic_service = TopicClusteringService(get_db_config(), domain="politics")

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


@router.post("/topics/merge")
async def merge_topics(merge_request: TopicMerge):
    """
    Merge multiple topics into one

    This will:
    1. Keep the first topic as the primary (or create new merged topic)
    2. Transfer all article assignments from merged topics to primary
    3. Combine topic statistics (counts, scores)
    4. Merge keywords and descriptions
    5. Mark merged topics as 'merged' status
    6. Handle duplicate assignments (keep highest confidence)

    Args:
        merge_request: Contains list of topic IDs to merge
        keep_primary: If True, keep first topic; if False, create new merged topic
    """
    try:
        if len(merge_request.topic_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 topics required for merge")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            try:
                sch = parse_optional_domain_to_schema(merge_request.domain or "politics")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            with conn.cursor() as cur:
                # Validate all topics exist
                placeholders = ",".join(["%s"] * len(merge_request.topic_ids))
                cur.execute(
                    f"""
                    SELECT id, name, status FROM {sch}.topics
                    WHERE id IN ({placeholders})
                """,
                    merge_request.topic_ids,
                )

                existing_topics = {
                    row[0]: {"name": row[1], "status": row[2]} for row in cur.fetchall()
                }

                if len(existing_topics) != len(merge_request.topic_ids):
                    missing = set(merge_request.topic_ids) - set(existing_topics.keys())
                    raise HTTPException(status_code=404, detail=f"Topics not found: {missing}")

                # Check for already merged topics
                merged_topics = [
                    tid for tid, data in existing_topics.items() if data["status"] == "merged"
                ]
                if merged_topics:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot merge topics that are already merged: {merged_topics}",
                    )

                # Primary topic is the first one
                primary_topic_id = merge_request.topic_ids[0]
                topics_to_merge = merge_request.topic_ids[1:]

                # Get primary topic details
                cur.execute(
                    f"""
                    SELECT name, description, category, keywords, confidence_score, accuracy_score,
                           review_count, correct_assignments, incorrect_assignments, article_count
                    FROM {sch}.topics t
                    LEFT JOIN (
                        SELECT topic_id, COUNT(*) as article_count
                        FROM {sch}.article_topic_assignments
                        GROUP BY topic_id
                    ) ata ON t.id = ata.topic_id
                    WHERE t.id = %s
                """,
                    (primary_topic_id,),
                )

                primary_row = cur.fetchone()
                if not primary_row:
                    raise HTTPException(status_code=404, detail="Primary topic not found")

                primary_name = primary_row[0]
                primary_desc = primary_row[1]
                primary_row[2]
                primary_keywords = set(primary_row[3] or [])
                primary_confidence = float(primary_row[4] or 0.5)
                primary_accuracy = float(primary_row[5] or 0.5)
                primary_review_count = primary_row[6] or 0
                primary_correct = primary_row[7] or 0
                primary_incorrect = primary_row[8] or 0
                primary_article_count = primary_row[9] or 0

                # Collect data from topics to merge
                total_articles = primary_article_count
                total_reviews = primary_review_count
                total_correct = primary_correct
                total_incorrect = primary_incorrect
                all_keywords = primary_keywords.copy()
                all_descriptions = [primary_desc] if primary_desc else []

                # Get data from topics to merge
                for topic_id in topics_to_merge:
                    cur.execute(
                        """
                        SELECT name, description, category, keywords, confidence_score, accuracy_score,
                               review_count, correct_assignments, incorrect_assignments,
                               (SELECT COUNT(*) FROM article_topic_assignments WHERE topic_id = %s) as article_count
                        FROM topics
                        WHERE id = %s
                    """,
                        (topic_id, topic_id),
                    )

                    row = cur.fetchone()
                    if row:
                        if row[1]:  # description
                            all_descriptions.append(row[1])
                        if row[3]:  # keywords
                            all_keywords.update(row[3])

                        total_articles += row[9] or 0
                        total_reviews += row[6] or 0
                        total_correct += row[7] or 0
                        total_incorrect += row[8] or 0

                # Update primary topic with merged data
                merged_description = " | ".join([d for d in all_descriptions if d])
                if not merged_description:
                    merged_description = f"Merged topic combining: {', '.join([existing_topics[tid]['name'] for tid in merge_request.topic_ids])}"

                # Calculate weighted averages for scores
                # Get all assignments to calculate proper averages
                cur.execute(
                    f"""
                    SELECT
                        AVG(confidence_score) as avg_confidence,
                        AVG(relevance_score) as avg_relevance
                    FROM {sch}.article_topic_assignments
                    WHERE topic_id = ANY(%s)
                """,
                    (merge_request.topic_ids,),
                )

                score_row = cur.fetchone()
                new_confidence = (
                    float(score_row[0] or primary_confidence)
                    if score_row[0]
                    else primary_confidence
                )
                new_accuracy = primary_accuracy  # Keep primary accuracy, or could recalculate

                # Update primary topic
                cur.execute(
                    f"""
                    UPDATE {sch}.topics
                    SET
                        description = %s,
                        keywords = %s,
                        confidence_score = %s,
                        accuracy_score = %s,
                        review_count = %s,
                        correct_assignments = %s,
                        incorrect_assignments = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, name
                """,
                    (
                        merged_description,
                        list(all_keywords),
                        new_confidence,
                        new_accuracy,
                        total_reviews,
                        total_correct,
                        total_incorrect,
                        primary_topic_id,
                    ),
                )

                updated_primary = cur.fetchone()

                # Transfer article assignments from merged topics to primary
                # Handle duplicates by keeping the one with highest confidence
                # First, get all assignments from topics to merge
                cur.execute(
                    f"""
                    SELECT
                        article_id,
                        confidence_score,
                        relevance_score,
                        is_validated,
                        is_correct,
                        feedback_notes,
                        assignment_method
                    FROM {sch}.article_topic_assignments
                    WHERE topic_id = ANY(%s)
                    ORDER BY article_id, confidence_score DESC, relevance_score DESC
                """,
                    (topics_to_merge,),
                )

                assignments_to_transfer = cur.fetchall()

                # Group by article_id and keep only the best assignment per article
                assignments_by_article = {}
                for row in assignments_to_transfer:
                    article_id = row[0]
                    if article_id not in assignments_by_article:
                        assignments_by_article[article_id] = {
                            "article_id": row[0],
                            "confidence_score": float(row[1] or 0.5),
                            "relevance_score": float(row[2] or 0.5),
                            "is_validated": row[3],
                            "is_correct": row[4],
                            "feedback_notes": row[5],
                            "assignment_method": row[6],
                        }
                    else:
                        # Keep the one with higher confidence
                        if (
                            float(row[1] or 0.5)
                            > assignments_by_article[article_id]["confidence_score"]
                        ):
                            assignments_by_article[article_id] = {
                                "article_id": row[0],
                                "confidence_score": float(row[1] or 0.5),
                                "relevance_score": float(row[2] or 0.5),
                                "is_validated": row[3],
                                "is_correct": row[4],
                                "feedback_notes": row[5],
                                "assignment_method": row[6],
                            }

                # Insert or update assignments
                for assignment in assignments_by_article.values():
                    cur.execute(
                        f"""
                        INSERT INTO {sch}.article_topic_assignments AS ata (
                            article_id, topic_id, confidence_score, relevance_score,
                            is_validated, is_correct, feedback_notes, assignment_method
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (article_id, topic_id) DO UPDATE SET
                            confidence_score = GREATEST(
                                ata.confidence_score,
                                EXCLUDED.confidence_score
                            ),
                            relevance_score = GREATEST(
                                ata.relevance_score,
                                EXCLUDED.relevance_score
                            ),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (
                            assignment["article_id"],
                            primary_topic_id,
                            assignment["confidence_score"],
                            assignment["relevance_score"],
                            assignment["is_validated"],
                            assignment["is_correct"],
                            assignment["feedback_notes"],
                            assignment["assignment_method"],
                        ),
                    )

                # Delete assignments from merged topics (now that they're transferred)
                cur.execute(
                    f"""
                    DELETE FROM {sch}.article_topic_assignments
                    WHERE topic_id IN ({placeholders})
                """,
                    topics_to_merge,
                )

                # Mark merged topics as 'merged' status
                cur.execute(
                    f"""
                    UPDATE {sch}.topics
                    SET
                        status = 'merged',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                """,
                    topics_to_merge,
                )

                # Get names of merged topics for response
                cur.execute(
                    f"""
                    SELECT name FROM {sch}.topics
                    WHERE id IN ({placeholders})
                """,
                    topics_to_merge,
                )
                merged_names = [row[0] for row in cur.fetchall()]

                conn.commit()

                logger.info(
                    f"Merged {len(topics_to_merge)} topics into {primary_name}: {merged_names}"
                )

                return {
                    "success": True,
                    "data": {
                        "primary_topic": {"id": updated_primary[0], "name": updated_primary[1]},
                        "merged_topics": [
                            {"id": tid, "name": existing_topics[tid]["name"]}
                            for tid in topics_to_merge
                        ],
                        "merged_count": len(topics_to_merge),
                        "total_articles": total_articles,
                        "message": f"Successfully merged {len(topics_to_merge)} topics into '{updated_primary[1]}'",
                    },
                }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error merging topics: {str(e)}")
