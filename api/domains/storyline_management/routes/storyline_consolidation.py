"""
Storyline Consolidation Routes

API endpoints for managing the background storyline consolidation service.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Query
from shared.domain_registry import DOMAIN_PATH_PATTERN

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storyline Consolidation"])


def get_consolidation_service():
    """Lazy load the consolidation service"""
    from services.storyline_consolidation_service import get_consolidation_service

    return get_consolidation_service()


@router.get("/storylines/consolidation/status")
async def get_consolidation_status():
    """
    Get the current status and statistics of the consolidation service.

    Returns configuration and run history.
    """
    try:
        service = get_consolidation_service()
        return {"success": True, "status": "active", "stats": service.get_stats()}
    except Exception as e:
        logger.error(f"Error getting consolidation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/storylines/consolidation/run")
async def run_consolidation_all_domains(background_tasks: BackgroundTasks):
    """
    Trigger consolidation for all domains immediately.

    Runs in the background and returns immediately.
    """
    try:
        from services.storyline_consolidation_service import consolidation_task

        # Run in background
        background_tasks.add_task(consolidation_task)

        return {
            "success": True,
            "message": "Consolidation started for all domains",
            "started_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error starting consolidation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/consolidation/run")
async def run_consolidation_domain(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    background: bool = Query(False, description="Run in background"),
):
    """
    Trigger consolidation for a specific domain.

    Args:
        domain: The domain to consolidate
        background: If true, run in background and return immediately
    """
    try:
        service = get_consolidation_service()

        if background:
            from concurrent.futures import ThreadPoolExecutor

            executor = ThreadPoolExecutor(max_workers=1)
            executor.submit(service.run_consolidation, domain)

            return {
                "success": True,
                "message": f"Consolidation started for {domain}",
                "started_at": datetime.now().isoformat(),
            }
        else:
            result = service.run_consolidation(domain)
            return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Error running consolidation for {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/hierarchy")
async def get_storyline_hierarchy(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    include_merged: bool = Query(False, description="Include merged storylines"),
    mega_only: bool = Query(False, description="Only show mega-storylines"),
):
    """
    Get the storyline hierarchy for a domain.

    Shows parent-child relationships between storylines.
    """
    schema = domain.replace("-", "_")

    try:
        service = get_consolidation_service()
        conn = service.get_db_connection()

        try:
            with conn.cursor() as cur:
                # Build WHERE clause
                conditions = []
                if not include_merged:
                    conditions.append("merged_into_id IS NULL")
                if mega_only:
                    conditions.append("is_mega_storyline = TRUE")

                where_clause = " AND ".join(conditions) if conditions else "TRUE"

                cur.execute(f"""
                    SELECT
                        id, title, description, article_count,
                        parent_storyline_id, is_mega_storyline, merge_count,
                        merged_into_id, status, created_at, updated_at
                    FROM {schema}.storylines
                    WHERE {where_clause}
                    ORDER BY is_mega_storyline DESC, article_count DESC
                    LIMIT 100
                """)

                rows = cur.fetchall()

                # Build tree structure
                storylines = {}
                roots = []

                for row in rows:
                    storyline = {
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "article_count": row[3],
                        "parent_id": row[4],
                        "is_mega": row[5],
                        "merge_count": row[6],
                        "merged_into": row[7],
                        "status": row[8],
                        "created_at": row[9].isoformat() if row[9] else None,
                        "children": [],
                    }
                    storylines[row[0]] = storyline

                # Build hierarchy
                for sid, storyline in storylines.items():
                    parent_id = storyline["parent_id"]
                    if parent_id and parent_id in storylines:
                        storylines[parent_id]["children"].append(storyline)
                    else:
                        roots.append(storyline)

                return {
                    "success": True,
                    "domain": domain,
                    "total_storylines": len(storylines),
                    "root_storylines": len(roots),
                    "hierarchy": roots,
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting storyline hierarchy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/mega")
async def get_mega_storylines(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN), limit: int = Query(20, ge=1, le=100)
):
    """
    Get all mega-storylines (parent storylines that aggregate related stories).
    """
    schema = domain.replace("-", "_")

    try:
        service = get_consolidation_service()
        conn = service.get_db_connection()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        s.id, s.title, s.description, s.article_count,
                        s.consolidation_score, s.merge_count, s.created_at,
                        (SELECT COUNT(*) FROM {schema}.storylines child
                         WHERE child.parent_storyline_id = s.id) as child_count
                    FROM {schema}.storylines s
                    WHERE s.is_mega_storyline = TRUE
                    AND s.merged_into_id IS NULL
                    ORDER BY s.article_count DESC
                    LIMIT %s
                """,
                    (limit,),
                )

                rows = cur.fetchall()

                mega_storylines = []
                for row in rows:
                    # Get child storylines
                    cur.execute(
                        f"""
                        SELECT id, title, article_count
                        FROM {schema}.storylines
                        WHERE parent_storyline_id = %s
                        ORDER BY article_count DESC
                    """,
                        (row[0],),
                    )

                    children = [
                        {"id": c[0], "title": c[1], "article_count": c[2]} for c in cur.fetchall()
                    ]

                    mega_storylines.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "description": row[2],
                            "article_count": row[3],
                            "consolidation_score": row[4],
                            "merge_count": row[5],
                            "created_at": row[6].isoformat() if row[6] else None,
                            "child_count": row[7],
                            "children": children,
                        }
                    )

                return {
                    "success": True,
                    "domain": domain,
                    "mega_storylines": mega_storylines,
                    "count": len(mega_storylines),
                }

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting mega-storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/merge/{primary_id}/{secondary_id}")
async def manual_merge_storylines(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    primary_id: int = Path(..., description="ID of the primary storyline to keep"),
    secondary_id: int = Path(..., description="ID of the storyline to merge into primary"),
):
    """
    Manually merge two storylines.

    The secondary storyline will be merged into the primary one.
    """
    try:
        from services.storyline_consolidation_service import StorylineInfo

        service = get_consolidation_service()

        # Fetch both storylines
        schema = domain.replace("-", "_")
        conn = service.get_db_connection()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, description, article_count, created_at, updated_at
                    FROM {schema}.storylines
                    WHERE id IN (%s, %s)
                """,
                    (primary_id, secondary_id),
                )

                rows = cur.fetchall()
                if len(rows) != 2:
                    raise HTTPException(status_code=404, detail="One or both storylines not found")

                storylines = {}
                for row in rows:
                    storylines[row[0]] = StorylineInfo(
                        id=row[0],
                        title=row[1] or "",
                        description=row[2] or "",
                        article_count=row[3] or 0,
                        created_at=row[4],
                        updated_at=row[5],
                    )

                primary = storylines[primary_id]
                secondary = storylines[secondary_id]

        finally:
            conn.close()

        # Calculate similarity (for logging)
        similarity = {"overall": 1.0, "semantic": 0.0, "entity": 0.0, "article": 0.0}

        # Perform merge
        result = service.merge_storylines(domain, primary, secondary, similarity)

        if result:
            return {
                "success": True,
                "message": f"Merged storyline {secondary_id} into {primary_id}",
                "primary_id": primary_id,
                "merged_id": secondary_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Merge failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error manually merging storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/related")
async def get_related_storylines(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    storyline_id: int = Path(..., description="Storyline ID"),
    min_similarity: float = Query(0.3, ge=0.1, le=0.99),
):
    """
    Get storylines related to a specific storyline.

    Returns siblings (same parent) and similar storylines.
    """
    schema = domain.replace("-", "_")

    try:
        service = get_consolidation_service()
        conn = service.get_db_connection()

        try:
            with conn.cursor() as cur:
                # Get the storyline info
                cur.execute(
                    f"""
                    SELECT id, title, parent_storyline_id, merged_into_id
                    FROM {schema}.storylines
                    WHERE id = %s
                """,
                    (storyline_id,),
                )

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Storyline not found")

                parent_id = row[2]
                merged_into = row[3]

                related = {"siblings": [], "parent": None, "children": [], "merged_into": None}

                # Get siblings (same parent)
                if parent_id:
                    cur.execute(
                        f"""
                        SELECT id, title, article_count
                        FROM {schema}.storylines
                        WHERE parent_storyline_id = %s AND id != %s
                        ORDER BY article_count DESC
                    """,
                        (parent_id, storyline_id),
                    )

                    related["siblings"] = [
                        {"id": r[0], "title": r[1], "article_count": r[2]} for r in cur.fetchall()
                    ]

                    # Get parent info
                    cur.execute(
                        f"""
                        SELECT id, title, article_count, is_mega_storyline
                        FROM {schema}.storylines
                        WHERE id = %s
                    """,
                        (parent_id,),
                    )
                    p = cur.fetchone()
                    if p:
                        related["parent"] = {
                            "id": p[0],
                            "title": p[1],
                            "article_count": p[2],
                            "is_mega": p[3],
                        }

                # Get children
                cur.execute(
                    f"""
                    SELECT id, title, article_count
                    FROM {schema}.storylines
                    WHERE parent_storyline_id = %s
                    ORDER BY article_count DESC
                """,
                    (storyline_id,),
                )

                related["children"] = [
                    {"id": r[0], "title": r[1], "article_count": r[2]} for r in cur.fetchall()
                ]

                # Get what this was merged into
                if merged_into:
                    cur.execute(
                        f"""
                        SELECT id, title, article_count
                        FROM {schema}.storylines
                        WHERE id = %s
                    """,
                        (merged_into,),
                    )
                    m = cur.fetchone()
                    if m:
                        related["merged_into"] = {"id": m[0], "title": m[1], "article_count": m[2]}

                return {"success": True, "storyline_id": storyline_id, "related": related}

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting related storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))
