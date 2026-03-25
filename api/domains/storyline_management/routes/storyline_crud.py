#!/usr/bin/env python3
"""
Storyline CRUD Routes
Core create, read, update, delete operations for storylines
"""

import logging
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from shared.database.connection import get_db_connection
from shared.domain_registry import DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import validate_domain

from ..schemas.storyline_schemas import (
    ArticleSummary,
    PaginationInfo,
    StorylineCreateRequest,
    StorylineDetailResponse,
    StorylineEntitySummary,
    StorylineListItem,
    StorylineListResponse,
    StorylineResponse,
    StorylineSourceCoverageRow,
    StorylineUpdateRequest,
)
from ..services.storyline_service import StorylineService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storyline CRUD"], responses={404: {"description": "Not found"}})


# ============================================================================
# Dependencies
# ============================================================================


async def validate_domain_dependency(domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN)):
    """Dependency to validate domain"""
    if not validate_domain(domain):
        raise HTTPException(status_code=400, detail=f"Invalid or inactive domain: {domain}")
    return domain


# ============================================================================
# List Endpoints (with pagination)
# ============================================================================


@router.get("/{domain}/storylines", response_model=StorylineListResponse)
async def get_domain_storylines(
    domain: str = Depends(validate_domain_dependency),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(
        None, description="Filter by status (e.g. active, archived, draft, completed, paused)"
    ),
):
    """Get paginated list of storylines for a specific domain"""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Build query with optional status filter
                base_query = f"FROM {schema}.storylines"
                where_clause = ""
                params = []

                if status:
                    where_clause = "WHERE status = %s"
                    params.append(status)

                # Get total count
                count_query = f"SELECT COUNT(*) {base_query} {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()[0]

                # Calculate pagination
                offset = (page - 1) * page_size
                pages = math.ceil(total / page_size) if total > 0 else 0

                # Get paginated results
                query = f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, article_count, quality_score
                    {base_query}
                    {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(query, params + [page_size, offset])
                list_rows = cur.fetchall()
                storyline_ids = [r[0] for r in list_rows]

                # Top 3 entities per storyline (by mention count) for list view
                top_entities_by_storyline = {sid: [] for sid in storyline_ids}
                if storyline_ids:
                    cur.execute(
                        f"""
                        WITH article_entities_agg AS (
                            SELECT sa.storyline_id, ae.canonical_entity_id, COUNT(*) AS cnt
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                            WHERE sa.storyline_id = ANY(%s)
                            GROUP BY sa.storyline_id, ae.canonical_entity_id
                        ),
                        ranked AS (
                            SELECT storyline_id, canonical_entity_id,
                                   ROW_NUMBER() OVER (PARTITION BY storyline_id ORDER BY cnt DESC) AS rn
                            FROM article_entities_agg
                        )
                        SELECT r.storyline_id, ec.canonical_name, ec.entity_type, ec.description
                        FROM ranked r
                        JOIN {schema}.entity_canonical ec ON ec.id = r.canonical_entity_id
                        WHERE r.rn <= 3
                    """,
                        (storyline_ids,),
                    )
                    for r in cur.fetchall():
                        desc = r[3]
                        top_entities_by_storyline.setdefault(r[0], []).append(
                            {
                                "name": r[1] or "",
                                "type": r[2] or "subject",
                                "description_short": (desc[:100] + "…")
                                if desc and len(desc) > 100
                                else (desc or ""),
                            }
                        )

                storylines = []
                for row in list_rows:
                    storylines.append(
                        StorylineListItem(
                            id=row[0],
                            title=row[1],
                            description=row[2],
                            article_count=row[6] or 0,
                            quality_score=row[7],
                            status=row[5],
                            created_at=row[3],
                            updated_at=row[4],
                            top_entities=top_entities_by_storyline.get(row[0], []),
                        )
                    )

                pagination = PaginationInfo(
                    page=page,
                    page_size=page_size,
                    total=total,
                    pages=pages,
                    has_next=page < pages,
                    has_prev=page > 1,
                )

                return StorylineListResponse(data=storylines, pagination=pagination, domain=domain)

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Create Endpoint
# ============================================================================


@router.post("/{domain}/storylines", response_model=StorylineResponse)
async def create_domain_storyline(
    domain: str = Depends(validate_domain_dependency), request: StorylineCreateRequest = None
):
    """Create a new storyline in a specific domain"""
    try:
        storyline_service = StorylineService(domain=domain)

        result = await storyline_service.create_storyline_from_articles(
            title=request.title if request else "",
            description=request.description if request else None,
            article_ids=request.article_ids if request else None,
        )

        if result.get("success"):
            data = result.get("data", {})
            # Fetch created storyline for response
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    schema = domain.replace("-", "_")
                    cur.execute(
                        f"""
                        SELECT id, title, description, status, article_count,
                               quality_score, analysis_summary, created_at, updated_at,
                               last_evolution_at, evolution_count
                        FROM {schema}.storylines
                        WHERE id = %s
                    """,
                        (data.get("id"),),
                    )
                    row = cur.fetchone()
                    if row:
                        return StorylineResponse(
                            id=row[0],
                            title=row[1],
                            description=row[2],
                            status=row[3],
                            article_count=row[4] or 0,
                            quality_score=row[5],
                            analysis_summary=row[6],
                            created_at=row[7],
                            updated_at=row[8],
                            last_evolution_at=row[9],
                            evolution_count=row[10],
                        )
            finally:
                conn.close()

            raise HTTPException(status_code=500, detail="Failed to retrieve created storyline")
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Creation failed"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Get Single Endpoint
# ============================================================================


@router.get("/{domain}/storylines/{storyline_id}", response_model=StorylineDetailResponse)
async def get_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
):
    """Get a single storyline with all its articles from a specific domain"""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Get storyline details (include key_entities, ml_processing_status)
                cur.execute(
                    f"""
                    SELECT id, title, description, created_at, updated_at,
                           status, analysis_summary, master_summary, quality_score, article_count,
                           last_evolution_at, evolution_count, background_information,
                           context_last_updated,
                           COALESCE(ml_processing_status, 'completed') as ml_processing_status,
                           editorial_document, document_version, document_status, last_refinement,
                           key_entities,
                           canonical_narrative, narrative_finisher_model, narrative_finisher_at,
                           narrative_finisher_meta,
                           timeline_narrative_chronological, timeline_narrative_briefing,
                           timeline_narrative_chronological_at, timeline_narrative_briefing_at
                    FROM {schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                storyline = cur.fetchone()
                if not storyline:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Get articles in storyline
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at DESC
                """,
                    (storyline_id,),
                )

                article_rows = cur.fetchall()
                articles = []
                article_ids = []
                for row in article_rows:
                    article_ids.append(row[0])
                    articles.append(
                        ArticleSummary(
                            id=row[0],
                            title=row[1],
                            url=row[2],
                            source_domain=row[3],
                            published_at=row[4],
                            summary=row[5],
                        )
                    )

                cur.execute(
                    f"""
                    SELECT COALESCE(NULLIF(TRIM(a.source_domain), ''), '(unknown)') AS src,
                           COUNT(*)::int
                    FROM {schema}.articles a
                    JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC, src ASC
                """,
                    (storyline_id,),
                )
                source_coverage = [
                    StorylineSourceCoverageRow(source_domain=r[0], article_count=r[1])
                    for r in cur.fetchall()
                ]

                # Entities: article_entities + entity_canonical for this storyline's articles
                entity_list = []
                if article_ids:
                    domain_key = domain  # politics | finance | science-tech
                    cur.execute(
                        f"""
                        SELECT ec.id, ec.canonical_name, ec.entity_type, ec.description,
                               COUNT(ae.article_id) AS mention_count
                        FROM {schema}.article_entities ae
                        JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                        WHERE ae.article_id = ANY(%s)
                        GROUP BY ec.id, ec.canonical_name, ec.entity_type, ec.description
                        ORDER BY mention_count DESC
                    """,
                        (article_ids,),
                    )
                    entity_rows = cur.fetchall()
                    canonical_ids = [r[0] for r in entity_rows]
                    profile_map = {}
                    dossier_set = set()
                    if canonical_ids:
                        cur.execute(
                            """
                            SELECT canonical_entity_id, id FROM intelligence.entity_profiles
                            WHERE domain_key = %s AND canonical_entity_id = ANY(%s)
                        """,
                            (domain_key, canonical_ids),
                        )
                        for r in cur.fetchall():
                            profile_map[r[0]] = r[1]
                        cur.execute(
                            """
                            SELECT entity_id FROM intelligence.entity_dossiers
                            WHERE domain_key = %s AND entity_id = ANY(%s)
                        """,
                            (domain_key, canonical_ids),
                        )
                        dossier_set = {r[0] for r in cur.fetchall()}
                    for r in entity_rows:
                        entity_list.append(
                            StorylineEntitySummary(
                                canonical_entity_id=r[0],
                                name=r[1] or "",
                                type=r[2] or "subject",
                                description=r[3],
                                mention_count=r[4] or 0,
                                has_profile=(r[0] in profile_map),
                                has_dossier=(r[0] in dossier_set),
                                profile_id=profile_map.get(r[0]),
                            )
                        )

                # Parse background_information and key_entities if present
                import json

                background_info = None
                if storyline[12]:
                    try:
                        background_info = (
                            json.loads(storyline[12])
                            if isinstance(storyline[12], str)
                            else storyline[12]
                        )
                    except Exception:
                        pass
                key_entities_raw = storyline[19] if len(storyline) > 19 else None
                key_entities = None
                if key_entities_raw is not None:
                    try:
                        key_entities = (
                            key_entities_raw
                            if isinstance(key_entities_raw, (dict, list))
                            else json.loads(key_entities_raw)
                        )
                    except Exception:
                        pass

                nf_meta = storyline[23] if len(storyline) > 23 else None
                if nf_meta is not None and isinstance(nf_meta, str):
                    try:
                        nf_meta = json.loads(nf_meta)
                    except Exception:
                        pass

                from services.content_refinement_queue_service import list_pending_job_types

                refinement_pending = list_pending_job_types(domain, storyline_id)

                return StorylineDetailResponse(
                    id=storyline[0],
                    title=storyline[1],
                    description=storyline[2],
                    status=storyline[5],
                    article_count=storyline[9] or 0,
                    quality_score=storyline[8],
                    analysis_summary=storyline[6],
                    master_summary=storyline[7] if len(storyline) > 7 else None,
                    created_at=storyline[3],
                    updated_at=storyline[4],
                    last_evolution_at=storyline[10],
                    evolution_count=storyline[11],
                    source_coverage=source_coverage,
                    articles=articles,
                    background_information=background_info,
                    context_last_updated=storyline[13],
                    ml_processing_status=storyline[14] if len(storyline) > 14 else "completed",
                    editorial_document=storyline[15] if len(storyline) > 15 else None,
                    document_version=storyline[16] if len(storyline) > 16 else None,
                    document_status=storyline[17] if len(storyline) > 17 else None,
                    last_refinement=storyline[18] if len(storyline) > 18 else None,
                    key_entities=key_entities,
                    entities=entity_list,
                    canonical_narrative=storyline[20] if len(storyline) > 20 else None,
                    narrative_finisher_model=storyline[21] if len(storyline) > 21 else None,
                    narrative_finisher_at=storyline[22] if len(storyline) > 22 else None,
                    narrative_finisher_meta=nf_meta if isinstance(nf_meta, dict) else None,
                    timeline_narrative_chronological=storyline[24] if len(storyline) > 24 else None,
                    timeline_narrative_briefing=storyline[25] if len(storyline) > 25 else None,
                    timeline_narrative_chronological_at=storyline[26]
                    if len(storyline) > 26
                    else None,
                    timeline_narrative_briefing_at=storyline[27] if len(storyline) > 27 else None,
                    refinement_jobs_pending=refinement_pending,
                )

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Update Endpoint
# ============================================================================


@router.put("/{domain}/storylines/{storyline_id}", response_model=StorylineResponse)
async def update_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    request: StorylineUpdateRequest = None,
):
    """Update an existing storyline in a specific domain"""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # Check if storyline exists
                cur.execute(f"SELECT id FROM {schema}.storylines WHERE id = %s", (storyline_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Storyline not found")

                # Build update query dynamically
                updates = []
                params = []

                if request and request.title is not None:
                    updates.append("title = %s")
                    params.append(request.title)

                if request and request.description is not None:
                    updates.append("description = %s")
                    params.append(request.description)

                if request and request.status is not None:
                    updates.append("status = %s")
                    params.append(request.status)

                if updates:
                    updates.append("updated_at = %s")
                    params.append(datetime.now())
                    params.append(storyline_id)

                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET {", ".join(updates)}
                        WHERE id = %s
                    """,
                        params,
                    )

                    conn.commit()

                # Fetch updated storyline
                cur.execute(
                    f"""
                    SELECT id, title, description, status, article_count,
                           quality_score, analysis_summary, created_at, updated_at,
                           last_evolution_at, evolution_count
                    FROM {schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                row = cur.fetchone()
                if row:
                    return StorylineResponse(
                        id=row[0],
                        title=row[1],
                        description=row[2],
                        status=row[3],
                        article_count=row[4] or 0,
                        quality_score=row[5],
                        analysis_summary=row[6],
                        created_at=row[7],
                        updated_at=row[8],
                        last_evolution_at=row[9],
                        evolution_count=row[10],
                    )

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Cross-domain related storylines (shared entities)
# ============================================================================


def _entity_profile_domain_keys_for_path(path_domain: str) -> list[str]:
    if path_domain == "science-tech":
        return ["science-tech", "science_tech"]
    return [path_domain]


@router.get("/{domain}/storylines/{storyline_id}/related_cross_domain")
async def get_storyline_related_cross_domain(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
    limit: int = Query(8, ge=1, le=20),
):
    """Storylines in other domains that share canonical entities with this storyline."""
    schema = domain.replace("-", "_")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    out: list[dict] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id
                FROM {schema}.storyline_articles sa
                JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                WHERE sa.storyline_id = %s
                """,
                (storyline_id,),
            )
            canon = list({int(r[0]) for r in cur.fetchall() if r and r[0] is not None})[:50]
        if not canon:
            conn.close()
            return {"success": True, "data": {"storylines": []}, "message": None}

        prof_domains = _entity_profile_domain_keys_for_path(domain)
        for other_schema, origin in (
            ("politics", "politics"),
            ("finance", "finance"),
            ("science_tech", "science-tech"),
        ):
            if other_schema == schema or len(out) >= limit:
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT DISTINCT s.id, s.title, s.updated_at
                        FROM {other_schema}.storylines s
                        JOIN {other_schema}.storyline_articles sa ON sa.storyline_id = s.id
                        JOIN {other_schema}.article_entities ae ON ae.article_id = sa.article_id
                        WHERE ae.canonical_entity_id = ANY(%s)
                          AND s.id IS NOT NULL
                          AND s.title IS NOT NULL AND TRIM(s.title) != ''
                        ORDER BY s.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (canon, limit),
                    )
                    for r in cur.fetchall() or []:
                        if len(out) >= limit:
                            break
                        out.append(
                            {
                                "id": r[0],
                                "title": r[1] or "",
                                "updated_at": r[2].isoformat()
                                if hasattr(r[2], "isoformat")
                                else str(r[2]),
                                "origin_domain": origin,
                                "link_reason": "shared_entity",
                            }
                        )
            except Exception as e:
                logger.debug("related_cross_domain %s: %s", other_schema, e)
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("get_storyline_related_cross_domain: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"success": True, "data": {"storylines": out}, "message": None}


# ============================================================================
# Delete Endpoint
# ============================================================================


@router.delete("/{domain}/storylines/{storyline_id}")
async def delete_domain_storyline(
    domain: str = Depends(validate_domain_dependency),
    storyline_id: int = Path(..., description="Storyline ID", ge=1),
):
    """Delete a storyline and its junction rows in a specific domain."""
    try:
        schema = domain.replace("-", "_")

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")

        try:
            with conn.cursor() as cur:
                # No FK from intelligence queue to domain storylines — clear jobs first
                cur.execute(
                    """
                    DELETE FROM intelligence.content_refinement_queue
                    WHERE domain_key = %s AND storyline_id = %s
                    """,
                    (domain, storyline_id),
                )

                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                """,
                    (storyline_id,),
                )

                cur.execute(
                    f"""
                    DELETE FROM {schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                conn.commit()

                return {
                    "success": True,
                    "message": "Storyline deleted successfully",
                    "timestamp": datetime.now().isoformat(),
                }

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting storyline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
