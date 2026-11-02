"""Bulk review-queue and domain discovery routes (included by storyline_automation router)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Body, HTTPException, Path, Query
from pydantic import BaseModel, Field

from shared.database import get_db_connection
from shared.domain_registry import DOMAIN_PATH_PATTERN, get_pipeline_schema_names_active, resolve_domain_schema
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
        domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
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
        domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
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

    @router.post("/{domain}/storylines/review-queue/cleanup")
    async def cleanup_stale_suggestions(
        domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
        max_age_days: int = Query(30, ge=1),
        dry_run: bool = Query(False),
    ):
        """Remove stale pending suggestions (orphaned or exceeding age threshold).

        Returns counts of deleted/orphaned rows before committing.
        Set `dry_run=true` to preview without deleting.
        """
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        try:
            with conn.cursor() as cur:
                # 1. Count orphans (article_id no longer exists in any active schema)
                schema_list = get_pipeline_schema_names_active()
                if schema_list:
                    subqueries = []
                    for s in schema_list:
                        subqueries.append(f"SELECT id FROM {s}.articles")
                    union_sql = " UNION ALL ".join(subqueries)
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM public.storyline_article_suggestions
                        WHERE status = 'pending'
                          AND domain_key = %s
                          AND article_id NOT IN ({union_sql})
                        """,
                        (domain,),
                    )
                    orphan_count = int(cur.fetchone()[0] or 0)
                else:
                    orphan_count = 0

                # 2. Count stale items (by age, cross-domain)
                cur.execute(
                    """
                    SELECT COUNT(*) FROM public.storyline_article_suggestions
                    WHERE status = 'pending' AND suggested_at < NOW() - (%s || ' days')::INTERVAL
                    """,
                    (max_age_days,),
                )
                stale_count = int(cur.fetchone()[0] or 0)

                if dry_run:
                    return {
                        "success": True,
                        "dry_run": True,
                        "would_delete_orphaned": orphan_count,
                        "would_delete_stale": stale_count,
                        "total_would_delete": orphan_count + stale_count,
                    }

                # 3. Delete orphans first (safer — just removes broken refs)
                if schema_list:
                    subqueries = []
                    for s in schema_list:
                        subqueries.append(f"SELECT id FROM {s}.articles")
                    union_sql = " UNION ALL ".join(subqueries)
                    cur.execute(
                        f"""
                        DELETE FROM public.storyline_article_suggestions
                        WHERE status = 'pending' AND domain_key = %s
                          AND article_id NOT IN ({union_sql})
                        """,
                        (domain,),
                    )
                    deleted_orphans = cur.rowcount

                # 4. Delete stale items (by age, cross-domain)
                cur.execute(
                    """
                    DELETE FROM public.storyline_article_suggestions
                    WHERE status = 'pending' AND suggested_at < NOW() - (%s || ' days')::INTERVAL
                    """,
                    (max_age_days,),
                )
                deleted_stale = cur.rowcount

            conn.commit()
            return {
                "success": True,
                "dry_run": False,
                "deleted_orphaned": deleted_orphans,
                "deleted_stale": deleted_stale,
                "total_deleted": deleted_orphans + deleted_stale,
            }
        except Exception as e:
            conn.rollback()
            logger.error("cleanup_stale_suggestions: %s", e)
            raise HTTPException(status_code=500, detail=str(e)[:200])
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Fix 1 – Cron purge route (scheduled stale-pending rows)
    # ------------------------------------------------------------------
    @router.post("/{domain}/storylines/review-queue/cron-purge")
    async def cron_purge_stale_pending(
        domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
        max_age_days: int = Query(30, ge=1),
        dry_run: bool = Query(False),
    ):
        """Purge stale pending suggestions — designed for cron/scheduled execution."""
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        result: dict[str, Any] = {"success": False, "dry_run": dry_run}
        try:
            with conn.cursor() as cur:
                schema_list = get_pipeline_schema_names_active()
                if schema_list:
                    subqueries = [f"SELECT id FROM {s}.articles" for s in schema_list]
                    union_sql = " UNION ALL ".join(subqueries)
                    cur.execute(
                        f"""SELECT COUNT(*) FROM public.storyline_article_suggestions
                        WHERE status = 'pending' AND domain_key = %s
                          AND article_id NOT IN ({union_sql})""", (domain,))
                    orphan_count = int(cur.fetchone()[0] or 0)
                else:
                    orphan_count = 0
                cur.execute(
                    "SELECT COUNT(*) FROM public.storyline_article_suggestions\n"
                    "WHERE status = 'pending' AND domain_key = %s\n"
                    "  AND suggested_at < NOW() - (%s || ' days')::INTERVAL",
                    (domain, max_age_days),
                )
                stale_count = int(cur.fetchone()[0] or 0)
                result["orphan_count"] = orphan_count
                result["stale_count"] = stale_count
                result["total"] = orphan_count + stale_count
                if dry_run:
                    result["success"] = True
                    logger.info(
                        "cron-purge dry-run domain=%s max_age=%d  orphaned=%d stale=%d",
                        domain, max_age_days, orphan_count, stale_count)
                    return result
                if schema_list:
                    subqueries = [f"SELECT id FROM {s}.articles" for s in schema_list]
                    union_sql = " UNION ALL ".join(subqueries)
                    cur.execute(
                        f"""DELETE FROM public.storyline_article_suggestions
                        WHERE status = 'pending' AND domain_key = %s
                          AND article_id NOT IN ({union_sql})""", (domain,))
                    deleted_orphans = cur.rowcount
                else:
                    deleted_orphans = 0
                cur.execute(
                    "DELETE FROM public.storyline_article_suggestions\n"
                    "WHERE status = 'pending' AND domain_key = %s\n"
                    "  AND suggested_at < NOW() - (%s || ' days')::INTERVAL",
                    (domain, max_age_days),
                )
                deleted_stale = cur.rowcount
            conn.commit()
            result.update(success=True, deleted_orphaned=deleted_orphans,
                          deleted_stale=deleted_stale)
            logger.info(
                "cron-purge domain=%s max_age=%d  deleted=%d (%d orphaned + %d stale)",
                domain, max_age_days, deleted_orphans + deleted_stale,
                deleted_orphans, deleted_stale)
            return result
        except Exception as exc:
            conn.rollback()
            logger.error("cron-purge failed domain=%s: %s", domain, exc)
            result["error"] = str(exc)[:200]
            raise HTTPException(status_code=500, detail=f"cron-purge failed: {exc}"[:200])
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Fix 3 – Agent-direct approve_all (no human review required)
    # ------------------------------------------------------------------
    @router.post("/{domain}/storylines/review-queue/approve-all")
    async def approve_all_eligible_suggestions(
        domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
        min_score: float = Query(0.75, ge=0.0, le=1.0),
        max_age_days: int = Query(7, ge=0),
        dry_run: bool = Query(False),
    ):
        """Approve all eligible pending suggestions — for agent/system use."""
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        result: dict[str, Any] = {"success": False, "dry_run": dry_run}
        try:
            schema = resolve_domain_schema(domain)
            with conn.cursor() as cur:
                age_clause = ""
                params: list[Any] = [domain, min_score]
                if max_age_days > 0:
                    age_clause = " AND suggested_at >= NOW() - (%s || ' days')::INTERVAL"
                    params.append(max_age_days)
                cur.execute(
                    f"""SELECT id, storyline_id, article_id, combined_score
                        FROM public.storyline_article_suggestions
                        WHERE status = 'pending' AND domain_key = %s
                          AND combined_score >= %s{age_clause}
                        ORDER BY combined_score DESC""", params)
                eligible = cur.fetchall()
                if dry_run:
                    result.update(
                        success=True, eligible_count=len(eligible),
                        eligible_ids=[int(r[0]) for r in eligible])
                    logger.info("approve-all dry-run domain=%s  eligible=%d",
                                domain, len(eligible))
                    return result
                approved = 0
                now_ts = datetime.now()
                for sug_id, storyline_id, article_id, score in eligible:
                    cur.execute(
                        f"""INSERT INTO {schema}.storyline_articles
                            (storyline_id, article_id, added_at, relevance_score)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (storyline_id, article_id) DO NOTHING""",
                        (storyline_id, article_id, now_ts, score))
                    cur.execute(
                        """UPDATE public.storyline_article_suggestions
                           SET status = 'approved', reviewed_at = %s,
                               review_notes = %s
                           WHERE id = %s AND domain_key = %s""",
                        (now_ts, "approved-via-approve-all-agent", sug_id, domain))
                    if cur.rowcount:
                        approved += 1
                conn.commit()
                result.update(success=True, approved=approved)
                logger.info("approve-all domain=%s  approved=%d eligible=%d",
                            domain, approved, len(eligible))
                return result
        except Exception as exc:
            conn.rollback()
            logger.error("approve-all failed domain=%s: %s", domain, exc)
            result["error"] = str(exc)[:200]
            raise HTTPException(
                status_code=500, detail=f"approve-all failed: {exc}"[:200])
        finally:
            conn.close()

    @router.post("/{domain}/storylines/automation/discover")
    async def domain_automation_discover(
        domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
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
