"""72-hour intake brief — discovery as launch pad, not package publisher.

Surfaces recent articles / events / topics so an operator can pick an idea and
call POST /api/research/assemble. Does not create editorial packages.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.runtime import env_int
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)


def intake_window_hours() -> int:
    return max(6, min(168, env_int("DISCOVERY_INTAKE_BRIEF_HOURS", 72)))


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _domain_article_rows(
    cur,
    *,
    schema: str,
    domain_key: str,
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    try:
        cur.execute(
            f"""
            SELECT a.id, a.title, a.url, a.published_at, a.source_name
            FROM {schema}.articles a
            WHERE COALESCE(a.published_at, a.created_at) >= %s
            ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
            LIMIT %s
            """,
            (since, int(limit)),
        )
    except Exception as exc:
        logger.debug("intake articles %s: %s", domain_key, exc)
        return []
    out: list[dict[str, Any]] = []
    for aid, title, url, published, source in cur.fetchall() or []:
        out.append(
            {
                "id": int(aid),
                "domain_key": domain_key,
                "title": (title or "")[:240],
                "source_url": url,
                "source_name": source,
                "published_at": _iso(published),
                "assemble_hint": (title or "")[:180],
            }
        )
    return out


def _domain_event_rows(
    cur,
    *,
    schema: str,
    domain_key: str,
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    try:
        cur.execute(
            f"""
            SELECT ce.id, ce.title, ce.actual_event_date, ce.source_article_id
            FROM public.chronological_events ce
            JOIN {schema}.articles a ON a.id = ce.source_article_id
            WHERE COALESCE(a.published_at, a.created_at) >= %s
            ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
            LIMIT %s
            """,
            (since, int(limit)),
        )
    except Exception as exc:
        logger.debug("intake events %s: %s", domain_key, exc)
        return []
    out: list[dict[str, Any]] = []
    for eid, title, ed, aid in cur.fetchall() or []:
        out.append(
            {
                "id": int(eid),
                "domain_key": domain_key,
                "title": (title or "")[:240],
                "event_date": ed.isoformat() if ed else None,
                "source_article_id": int(aid) if aid is not None else None,
                "assemble_hint": (title or "")[:180],
            }
        )
    return out


def _domain_topic_rows(
    cur,
    *,
    schema: str,
    domain_key: str,
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    """High-level topics from recent per-domain storylines."""
    out: list[dict[str, Any]] = []
    try:
        cur.execute(
            f"""
            SELECT id, title, updated_at, created_at, article_count
            FROM {schema}.storylines
            WHERE COALESCE(updated_at, created_at, last_event_at) >= %s
            ORDER BY COALESCE(article_count, 0) DESC NULLS LAST,
                     COALESCE(updated_at, created_at) DESC NULLS LAST
            LIMIT %s
            """,
            (since, int(limit)),
        )
        for sid, title, updated, created, count in cur.fetchall() or []:
            out.append(
                {
                    "id": int(sid),
                    "domain_key": domain_key,
                    "kind": "storyline",
                    "title": (title or "")[:240],
                    "article_count": int(count or 0),
                    "updated_at": _iso(updated or created),
                    "assemble_hint": (title or "")[:180],
                }
            )
    except Exception as exc:
        logger.debug("intake storylines %s: %s", domain_key, exc)

    if len(out) >= limit:
        return out[:limit]

    try:
        cur.execute(
            f"""
            SELECT id,
                   COALESCE(NULLIF(display_name, ''), name) AS title,
                   updated_at, created_at
            FROM {schema}.topics
            WHERE COALESCE(updated_at, created_at, last_seen_at) >= %s
            ORDER BY COALESCE(updated_at, created_at, last_seen_at) DESC NULLS LAST
            LIMIT %s
            """,
            (since, int(limit) - len(out)),
        )
        for tid, title, updated, created in cur.fetchall() or []:
            out.append(
                {
                    "id": int(tid),
                    "domain_key": domain_key,
                    "kind": "topic",
                    "title": (title or "")[:240],
                    "updated_at": _iso(updated or created),
                    "assemble_hint": (title or "")[:180],
                }
            )
    except Exception as exc:
        logger.debug("intake topics %s: %s", domain_key, exc)
    return out[:limit]


def build_intake_brief(
    *,
    hours: int | None = None,
    domain_key: str | None = None,
    limit_per_domain: int = 25,
) -> dict[str, Any]:
    """Return a 72h (default) intake brief across pipeline domains."""
    window = int(hours if hours is not None else intake_window_hours())
    since = datetime.now(timezone.utc) - timedelta(hours=window)
    domains = (
        [str(domain_key).strip()]
        if domain_key and str(domain_key).strip()
        else list(get_pipeline_active_domain_keys())
    )
    per = max(5, min(60, int(limit_per_domain)))

    by_domain: dict[str, Any] = {}
    highlights: list[dict[str, Any]] = []
    totals = {"articles": 0, "events": 0, "topics": 0}

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for dk in domains:
                    try:
                        schema = resolve_domain_schema(dk)
                    except Exception:
                        continue
                    if not schema:
                        continue
                    articles = _domain_article_rows(
                        cur, schema=schema, domain_key=dk, since=since, limit=per
                    )
                    events = _domain_event_rows(
                        cur, schema=schema, domain_key=dk, since=since, limit=per
                    )
                    topics = _domain_topic_rows(
                        cur,
                        schema=schema,
                        domain_key=dk,
                        since=since,
                        limit=max(5, per // 2),
                    )
                    by_domain[dk] = {
                        "articles": articles,
                        "events": events,
                        "topics": topics,
                        "counts": {
                            "articles": len(articles),
                            "events": len(events),
                            "topics": len(topics),
                        },
                    }
                    totals["articles"] += len(articles)
                    totals["events"] += len(events)
                    totals["topics"] += len(topics)
                    for a in articles[:5]:
                        highlights.append({**a, "kind": "article"})
                    for e in events[:3]:
                        highlights.append({**e, "kind": "event"})
                    for t in topics[:3]:
                        highlights.append({**t, "kind": "topic"})
    except Exception as exc:
        logger.warning("build_intake_brief: %s", exc)
        return {
            "ok": False,
            "error": str(exc)[:200],
            "window_hours": window,
            "since": since.isoformat(),
        }

    # Stable highlight order: newest-ish articles first (already ordered per domain).
    highlights = highlights[:40]
    return {
        "ok": True,
        "window_hours": window,
        "since": since.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "domains": by_domain,
        "highlights": highlights,
        "launch": {
            "assemble_endpoint": "POST /api/research/assemble",
            "body_example": {
                "idea": "China dropping US bonds and moving to gold — historic view",
                "domain_key": "finance",
            },
            "note": (
                "Pick a highlight or paste your own idea. "
                "Assemble builds a research/narrative package with a claim/event spine; "
                "discovery no longer auto-publishes packages."
            ),
        },
    }
