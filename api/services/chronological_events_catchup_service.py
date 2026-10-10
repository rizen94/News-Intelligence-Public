"""
Catch up `public.chronological_events` for articles that already completed unified
intake but have no chronological_events rows (common after flush_all_storylines).

Does **not** re-run full UIE — only EventExtractionService.extract + save_events.
Leaves unified_intake_extraction pass markers intact; refreshes event_extraction /
timeline_* flags.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool, env_int
from shared.database.connection import get_db_connection_context
from shared.domain_registry import pipeline_url_schema_pairs

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return env_bool("CHRONOLOGICAL_EVENTS_CATCHUP_ENABLED", True)


def batch_limit() -> int:
    return max(1, min(50, env_int("CHRONOLOGICAL_EVENTS_CATCHUP_BATCH", 5)))


def get_lookback_days() -> int:
    return max(7, min(730, env_int("CHRONOLOGICAL_EVENTS_CATCHUP_LOOKBACK_DAYS", 180)))


def ce_write_watchdog_hours() -> int:
    return max(1, min(168, env_int("CE_WRITE_WATCHDOG_HOURS", 6)))


def count_uie_without_chrono(
    *,
    hours: int | None = None,
) -> dict[str, Any]:
    """UIE-passed articles with no CE rows and no completed_empty event_extraction marker.

    This is the silent-failure mode that emptied the timeline while pass markers looked healthy.
    """
    window = hours if hours is not None else ce_write_watchdog_hours()
    per_domain: list[dict[str, Any]] = []
    total = 0
    for dk, schema in pipeline_url_schema_pairs():
        sql = f"""
            SELECT COUNT(*)::bigint
            FROM {schema}.articles a
            WHERE (a.metadata #>> '{{pipeline,unified_intake_extraction,last_pass_at}}') IS NOT NULL
              AND (a.metadata #>> '{{pipeline,unified_intake_extraction,last_pass_at}}')::timestamptz
                  >= NOW() - (%s || ' hours')::interval
              AND NOT EXISTS (
                    SELECT 1 FROM public.chronological_events ce
                    WHERE ce.source_article_id = a.id
              )
              AND COALESCE(
                    a.metadata #>> '{{pipeline,event_extraction,last_terminal_state}}',
                    ''
                  ) NOT IN (
                    'completed_empty',
                    'processed_empty_legitimate',
                    'TERMINAL_PROCESSED_EMPTY_LEGITIMATE'
                  )
              AND COALESCE(
                    a.metadata #>> '{{pipeline,event_extraction,status}}',
                    ''
                  ) NOT IN ('completed_empty', 'processed_empty')
        """
        n = 0
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (str(window),))
                    row = cur.fetchone()
                    n = int(row[0] or 0) if row else 0
        except Exception as e:
            logger.debug("ce_write_watchdog %s: %s", schema, e)
            per_domain.append({"domain_key": dk, "schema": schema, "missing_ce": 0, "error": str(e)[:120]})
            continue
        total += n
        per_domain.append({"domain_key": dk, "schema": schema, "missing_ce": n})
    alert = total > 0
    return {
        "window_hours": window,
        "missing_ce_total": total,
        "alert": alert,
        "per_domain": per_domain,
        "note": (
            "UIE-passed articles in window with zero chronological_events and no "
            "completed_empty event_extraction marker — check save_events / unique index."
        ),
    }


def list_articles_needing_chrono(
    *,
    schema: str,
    limit: int,
    lookback_days: int | None = None,
) -> list[dict[str, Any]]:
    """UIE-complete articles with no CE rows for this schema's article ids.

    Excludes articles already marked ``event_extraction`` empty/legitimate so
    catchup does not re-burn the same no-event rows forever while unmarked
    work (or a stale probe) remains.
    """
    days = lookback_days if lookback_days is not None else get_lookback_days()
    lim = max(1, min(100, int(limit)))
    sql = f"""
        SELECT a.id, a.content, a.published_at, a.title,
               (
                   SELECT sa.storyline_id::text
                   FROM {schema}.storyline_articles sa
                   WHERE sa.article_id = a.id
                   ORDER BY sa.added_at DESC NULLS LAST, sa.created_at DESC NULLS LAST
                   LIMIT 1
               ) AS storyline_id
        FROM {schema}.articles a
        WHERE a.content IS NOT NULL
          AND LENGTH(TRIM(a.content)) > 100
          AND (
                (a.metadata #>> '{{pipeline,unified_intake_extraction,last_pass_at}}') IS NOT NULL
             OR (a.metadata #>> '{{pipeline,unified_intake,last_pass_at}}') IS NOT NULL
          )
          AND NOT EXISTS (
                SELECT 1 FROM public.chronological_events ce
                WHERE ce.source_article_id = a.id
          )
          AND COALESCE(
                a.metadata #>> '{{pipeline,event_extraction,last_terminal_state}}',
                ''
              ) NOT IN (
                'completed_empty',
                'processed_empty_legitimate',
                'TERMINAL_PROCESSED_EMPTY_LEGITIMATE'
              )
          AND COALESCE(
                a.metadata #>> '{{pipeline,event_extraction,status}}',
                ''
              ) NOT IN ('completed_empty', 'processed_empty')
          AND (
                a.published_at IS NULL
             OR a.published_at >= NOW() - (%s || ' days')::interval
             OR a.created_at >= NOW() - (%s || ' days')::interval
          )
        ORDER BY a.published_at DESC NULLS LAST, a.id DESC
        LIMIT %s
    """
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (str(days), str(days), lim))
                cols = [d[0] for d in cur.description or []]
                for row in cur.fetchall() or []:
                    out.append(dict(zip(cols, row)))
    except Exception as e:
        logger.warning("list_articles_needing_chrono %s: %s", schema, e)
    return out


def _mark_timeline(conn, schema: str, article_id: int, events_saved: int) -> None:
    """Stamp timeline flags on the shared connection (no nested DB checkout).

    Pass-marker metadata is written after commit via ``_record_event_extraction_pass``
    so we never open a second pool connection while this transaction holds the
    articles row lock (that deadlocks the catchup batch).
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {schema}.articles
            SET timeline_processed = TRUE,
                timeline_events_generated = GREATEST(
                    COALESCE(timeline_events_generated, 0), %s
                ),
                updated_at = NOW()
            WHERE id = %s
            """,
            (int(events_saved), int(article_id)),
        )


def _record_event_extraction_pass(schema: str, article_id: int, events_saved: int) -> None:
    try:
        from shared.pipeline_pass_marker import (
            TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
            TERMINAL_PROCESSED_WITH_OUTPUT,
            record_article_phase_pass,
        )

        terminal = (
            TERMINAL_PROCESSED_WITH_OUTPUT
            if events_saved > 0
            else TERMINAL_PROCESSED_EMPTY_LEGITIMATE
        )
        record_article_phase_pass(
            schema,
            int(article_id),
            "event_extraction",
            "completed" if events_saved > 0 else "completed_empty",
            terminal_state=terminal,
        )
    except Exception as e:
        logger.debug("event_extraction pass marker: %s", e)


async def catchup_article(
    *,
    schema: str,
    domain_key: str,
    article: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    from services.event_extraction_service import EventExtractionService

    aid = int(article["id"])
    content = article.get("content") or ""
    pub = article.get("published_at") or datetime.now(timezone.utc)
    if hasattr(pub, "tzinfo") and pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    storyline_id = article.get("storyline_id")

    svc = EventExtractionService()
    events = await svc.extract_events_from_article(
        aid,
        content,
        pub if isinstance(pub, datetime) else datetime.now(timezone.utc),
        storyline_id=str(storyline_id) if storyline_id else None,
        domain=domain_key,
    )
    if dry_run:
        return {
            "article_id": aid,
            "extracted": len(events),
            "saved": 0,
            "dry_run": True,
        }

    saved = 0
    with get_db_connection_context() as conn:
        if not conn:
            return {"article_id": aid, "extracted": len(events), "saved": 0, "error": "no_db"}
        try:
            if events:
                saved = int(await svc.save_events(events, conn, commit=False) or 0)
            _mark_timeline(conn, schema, aid, saved)
            conn.commit()
            _record_event_extraction_pass(schema, aid, saved)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.warning("catchup_article %s/%s failed: %s", schema, aid, e)
            return {
                "article_id": aid,
                "extracted": len(events),
                "saved": 0,
                "error": str(e)[:200],
            }
    return {"article_id": aid, "extracted": len(events), "saved": saved, "dry_run": False}


async def catchup_articles_batched(
    *,
    schema: str,
    domain_key: str,
    articles: list[dict[str, Any]],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Extract events for several articles in one LLM call, then persist per article."""
    from services.event_extraction_service import EventExtractionService

    if not articles:
        return []

    svc = EventExtractionService()
    payload = []
    for art in articles:
        pub = art.get("published_at") or datetime.now(timezone.utc)
        if hasattr(pub, "tzinfo") and pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        sid = art.get("storyline_id")
        payload.append(
            {
                "article_id": int(art["id"]),
                "content": art.get("content") or "",
                "pub_date": pub if isinstance(pub, datetime) else datetime.now(timezone.utc),
                "storyline_id": str(sid) if sid else None,
            }
        )

    try:
        by_article = await svc.extract_events_batch(payload, domain=domain_key)
    except Exception as e:
        logger.warning("catchup batch extraction %s: %s", schema, e)
        by_article = {}

    results: list[dict[str, Any]] = []
    for art in articles:
        aid = int(art["id"])
        events = by_article.get(aid) or []
        if dry_run:
            results.append(
                {
                    "article_id": aid,
                    "extracted": len(events),
                    "saved": 0,
                    "dry_run": True,
                    "domain_key": domain_key,
                    "schema": schema,
                }
            )
            continue
        saved = 0
        error: str | None = None
        with get_db_connection_context() as conn:
            if not conn:
                error = "no_db"
            else:
                try:
                    if events:
                        saved = int(await svc.save_events(events, conn, commit=False) or 0)
                    _mark_timeline(conn, schema, aid, saved)
                    conn.commit()
                    _record_event_extraction_pass(schema, aid, saved)
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    error = str(e)[:200]
                    logger.warning("catchup save %s/%s failed: %s", schema, aid, e)
        row = {
            "article_id": aid,
            "extracted": len(events),
            "saved": saved,
            "dry_run": False,
            "domain_key": domain_key,
            "schema": schema,
        }
        if error:
            row["error"] = error
        results.append(row)
    return results


def llm_batch_size() -> int:
    """Articles per batched extraction call (1 disables batching)."""
    return max(1, min(12, env_int("CHRONOLOGICAL_EVENTS_CATCHUP_LLM_BATCH", 4)))


async def run_catchup_batch(
    *,
    limit: int | None = None,
    lookback_days: int | None = None,
    domain_key: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    llm_batch: int | None = None,
) -> dict[str, Any]:
    if not is_enabled() and not force:
        return {
            "skipped": True,
            "reason": "CHRONOLOGICAL_EVENTS_CATCHUP_ENABLED=false",
            "processed": 0,
        }

    lim = limit if limit is not None else batch_limit()
    days = lookback_days if lookback_days is not None else get_lookback_days()
    chunk = llm_batch if llm_batch is not None else llm_batch_size()
    pairs = list(pipeline_url_schema_pairs())
    if domain_key:
        dk = domain_key.strip().lower()
        pairs = [(k, s) for k, s in pairs if k == dk]
    results: list[dict[str, Any]] = []
    remaining = lim
    for dk, schema in pairs:
        if remaining <= 0:
            break
        articles = list_articles_needing_chrono(
            schema=schema, limit=remaining, lookback_days=days
        )
        for start in range(0, len(articles), chunk):
            if remaining <= 0:
                break
            group = articles[start : start + chunk]
            group = group[:remaining]
            try:
                if chunk > 1 and len(group) > 1:
                    results.extend(
                        await catchup_articles_batched(
                            schema=schema,
                            domain_key=dk,
                            articles=group,
                            dry_run=dry_run,
                        )
                    )
                else:
                    for art in group:
                        r = await catchup_article(
                            schema=schema,
                            domain_key=dk,
                            article=art,
                            dry_run=dry_run,
                        )
                        r["domain_key"] = dk
                        r["schema"] = schema
                        results.append(r)
            except Exception as e:
                logger.warning("catchup group %s@%s: %s", schema, start, e)
                for art in group:
                    results.append(
                        {
                            "article_id": art.get("id"),
                            "domain_key": dk,
                            "schema": schema,
                            "error": str(e)[:200],
                        }
                    )
            remaining -= len(group)

    return {
        "skipped": False,
        "processed": len(results),
        "extracted_total": sum(int(r.get("extracted") or 0) for r in results),
        "saved_total": sum(int(r.get("saved") or 0) for r in results),
        "dry_run": dry_run,
        "lookback_days": days,
        "llm_batch": chunk,
        "results": results,
    }


def run_catchup_batch_sync(**kwargs: Any) -> dict[str, Any]:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(run_catchup_batch(**kwargs))).result()
    return asyncio.run(run_catchup_batch(**kwargs))
