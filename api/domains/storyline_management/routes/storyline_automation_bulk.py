"""Bulk review-queue and domain discovery routes (included by storyline_automation router)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Body, HTTPException, Path, Query
from pydantic import BaseModel, Field

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema
from shared.services.domain_aware_service import validate_domain
from services.storyline_automation_service import StorylineAutomationService

logger = logging.getLogger(__name__)


class BulkSuggestionBody(BaseModel):
    suggestion_ids: list[int] = Field(default_factory=list)
    all: bool = False
    storyline_id: Optional[int] = None
    reason_code: Optional[str] = None
    review_notes: Optional[str] = None


def _approve_suggestion_row(
    cur,
    *,
    domain: str,
    schema: str,
    storyline_id: int,
    suggestion_id: int,
) -> tuple[bool, str | None]:
    cur.execute(
        """
        SELECT article_id, combined_score FROM public.storyline_article_suggestions
        WHERE id = %s AND domain_key = %s AND storyline_id = %s AND status = 'pending'
        """,
        (suggestion_id, domain, storyline_id),
    )
    result = cur.fetchone()
    if not result:
        return False, "not_found"
    article_id, relevance_score = result[0], float(result[1] or 0.7)
    cur.execute(
        f"""
        INSERT INTO {schema}.storyline_articles (storyline_id, article_id, added_at, relevance_score)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (storyline_id, article_id) DO NOTHING
        """,
        (storyline_id, article_id, datetime.now(), relevance_score),
    )
    if cur.rowcount == 0:
        return False, "already_linked"
    try:
        svc = StorylineAutomationService(domain=domain)
        svc._merge_article_entities_to_storyline(cur, storyline_id, article_id)
    except Exception as merge_err:
        logger.debug("Entity merge on bulk approve: %s", merge_err)
    cur.execute(
        """
        UPDATE public.storyline_article_suggestions
        SET status = 'approved', reviewed_at = %s
        WHERE id = %s AND domain_key = %s
        """,
        (datetime.now(), suggestion_id, domain),
    )
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET article_count = (
            SELECT COUNT(*) FROM {schema}.storyline_articles WHERE storyline_id = %s
        ),
        updated_at = %s
        WHERE id = %s
        """,
        (storyline_id, datetime.now(), storyline_id),
    )
    return True, None


def register_bulk_routes(router) -> None:
    @router.post("/{domain}/storylines/review-queue/bulk-approve")
    async def bulk_approve_suggestions(
        domain: str = Path(..., pattern="^(politics|finance|science-tech)$"),
        body: BulkSuggestionBody = Body(...),
    ):
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = resolve_domain_schema(domain)
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        approved = 0
        failed: list[dict[str, Any]] = []
        try:
            with conn.cursor() as cur:
                ids: list[tuple[int, int]] = []
                if body.all:
                    where = "WHERE domain_key = %s AND status = 'pending'"
                    params: list[Any] = [domain]
                    if body.storyline_id is not None:
                        where += " AND storyline_id = %s"
                        params.append(body.storyline_id)
                    cur.execute(
                        f"SELECT id, storyline_id FROM public.storyline_article_suggestions {where}",
                        params,
                    )
                    ids = [(int(r[0]), int(r[1])) for r in cur.fetchall()]
                else:
                    for sid in body.suggestion_ids:
                        cur.execute(
                            """
                            SELECT storyline_id FROM public.storyline_article_suggestions
                            WHERE id = %s AND domain_key = %s AND status = 'pending'
                            """,
                            (sid, domain),
                        )
                        row = cur.fetchone()
                        if row:
                            ids.append((sid, int(row[0])))
                        else:
                            failed.append({"suggestion_id": sid, "error": "not_found"})
                for suggestion_id, storyline_id in ids:
                    ok, err = _approve_suggestion_row(
                        cur,
                        domain=domain,
                        schema=schema,
                        storyline_id=storyline_id,
                        suggestion_id=suggestion_id,
                    )
                    if ok:
                        approved += 1
                    else:
                        failed.append(
                            {"suggestion_id": suggestion_id, "error": err or "failed"}
                        )
            conn.commit()
            return {"success": True, "approved": approved, "failed": failed}
        except Exception as e:
            conn.rollback()
            logger.error("bulk_approve: %s", e)
            raise HTTPException(status_code=500, detail=str(e)[:200])
        finally:
            conn.close()

    @router.post("/{domain}/storylines/review-queue/bulk-reject")
    async def bulk_reject_suggestions(
        domain: str = Path(..., pattern="^(politics|finance|science-tech)$"),
        body: BulkSuggestionBody = Body(...),
    ):
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        notes = body.review_notes or body.reason_code or "rejected"
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        rejected = 0
        failed: list[dict[str, Any]] = []
        try:
            with conn.cursor() as cur:
                target_ids = list(body.suggestion_ids)
                if body.all:
                    where = "WHERE domain_key = %s AND status = 'pending'"
                    params: list[Any] = [domain]
                    if body.storyline_id is not None:
                        where += " AND storyline_id = %s"
                        params.append(body.storyline_id)
                    cur.execute(
                        f"SELECT id FROM public.storyline_article_suggestions {where}",
                        params,
                    )
                    target_ids = [int(r[0]) for r in cur.fetchall()]
                for suggestion_id in target_ids:
                    cur.execute(
                        """
                        UPDATE public.storyline_article_suggestions
                        SET status = 'rejected', reviewed_at = %s, review_notes = %s
                        WHERE id = %s AND domain_key = %s AND status = 'pending'
                        """,
                        (datetime.now(), notes, suggestion_id, domain),
                    )
                    if cur.rowcount:
                        rejected += 1
                    else:
                        failed.append({"suggestion_id": suggestion_id, "error": "not_found"})
            conn.commit()
            return {"success": True, "rejected": rejected, "failed": failed}
        except Exception as e:
            conn.rollback()
            logger.error("bulk_reject: %s", e)
            raise HTTPException(status_code=500, detail=str(e)[:200])
        finally:
            conn.close()

    @router.post("/{domain}/storylines/automation/discover")
    async def domain_automation_discover(
        domain: str = Path(..., pattern="^(politics|finance|science-tech)$"),
        force_refresh: bool = Query(False),
        limit: int = Query(15, ge=1, le=100),
    ):
        """Run article discovery for automation-enabled storylines in this domain."""
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        schema = resolve_domain_schema(domain)
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines
                    WHERE automation_enabled = true
                    ORDER BY last_automation_run ASC NULLS FIRST
                    LIMIT %s
                    """,
                    (limit,),
                )
                storyline_ids = [int(r[0]) for r in cur.fetchall()]
        finally:
            conn.close()

        svc = StorylineAutomationService(domain=domain)
        results: list[dict[str, Any]] = []
        total_suggested = 0
        for sid in storyline_ids:
            try:
                result = await svc.discover_articles_for_storyline(
                    sid, force_refresh=force_refresh
                )
                suggested = int(result.get("articles_suggested") or 0)
                total_suggested += suggested
                results.append(
                    {
                        "storyline_id": sid,
                        "success": result.get("success"),
                        "articles_suggested": suggested,
                        "articles_found": result.get("articles_found"),
                    }
                )
            except Exception as e:
                logger.warning("domain discover storyline %s: %s", sid, e)
                results.append({"storyline_id": sid, "success": False, "error": str(e)[:120]})

        return {
            "success": True,
            "domain": domain,
            "storylines_scanned": len(storyline_ids),
            "total_suggested": total_suggested,
            "results": results,
        }
