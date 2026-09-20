"""
Reader home feed: News / Current Events / One-offs with StoryUnit fields.

News = material narrative update in last 48h with a real dek — NOT membership-only
``last_article_added_at`` bumps.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import (
    get_active_domain_keys,
    pipeline_url_schema_pairs,
    resolve_domain_schema,
)

from .expected_dates import extract_expected_dates

logger = logging.getLogger(__name__)

NEWS_WINDOW_HOURS = 48
READ_WPM = 220


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_editorial(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _dek_from_row(editorial: dict[str, Any], description: str | None, title: str) -> str:
    lede = (editorial.get("lede") or "").strip()
    if lede:
        return lede
    what = (editorial.get("what") or "").strip()
    if what:
        return what
    desc = (description or "").strip()
    if desc:
        # First sentence-ish
        cut = desc.find(". ")
        return (desc[: cut + 1] if cut > 40 else desc)[:280]
    return ""


def _read_minutes(text: str, article_count: int = 0) -> int:
    words = max(len((text or "").split()), article_count * 180)
    return max(1, min(45, math.ceil(words / READ_WPM)))


def _updated_label(dt: datetime | None) -> str:
    if not dt:
        return ""
    aware = _as_aware(dt)
    if not aware:
        return ""
    delta = _utcnow() - aware
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return "Updated just now"
    if hours < 24:
        return f"Updated {hours}h ago"
    days = hours // 24
    if days == 1:
        return "Updated yesterday"
    return f"Updated {days}d ago"


def _resolve_domain_pairs(domain: str | None) -> list[tuple[str, str]]:
    pairs = list(pipeline_url_schema_pairs())
    if not pairs:
        pairs = [(dk, resolve_domain_schema(dk)) for dk in get_active_domain_keys()]
    if domain:
        key = domain.strip().lower()
        pairs = [(dk, sch) for dk, sch in pairs if dk == key]
    return pairs


def _story_unit(
    *,
    section_label: str,
    headline: str,
    dek: str,
    domain: str,
    storyline_id: int,
    updated_at: datetime | None,
    article_count: int,
    badges: list[str],
    thumb_url: str | None = None,
    announced_on: str | None = None,
    expected_on: str | None = None,
    date_precision: str | None = None,
    surface_kind: str,
) -> dict[str, Any]:
    body_for_read = f"{headline} {dek}"
    return {
        "section_label": section_label,
        "headline": headline,
        "dek": dek,
        "domain": domain,
        "storyline_id": storyline_id,
        "updated_label": _updated_label(updated_at),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "read_minutes": _read_minutes(body_for_read, article_count),
        "badges": badges,
        "thumb_url": thumb_url,
        "article_count": article_count,
        "announced_on": announced_on,
        "expected_on": expected_on,
        "date_precision": date_precision,
        "surface_kind": surface_kind,
        "href": f"/v2/storylines/{domain}/{storyline_id}",
    }


def _fetch_candidate_rows(cur, schema: str, domain_key: str, since: datetime) -> list[dict[str, Any]]:
    """Pull recent non-merged storylines with editorial + hierarchy signals."""
    cur.execute(
        f"""
        SELECT
            s.id,
            s.title,
            s.description,
            s.status,
            s.updated_at,
            s.last_refinement,
            s.editorial_document,
            s.article_count,
            s.parent_storyline_id,
            COALESCE(s.is_mega_storyline, FALSE) AS is_mega_storyline,
            s.created_at,
            (
                SELECT MAX(sa.added_at)
                FROM {schema}.storyline_articles sa
                WHERE sa.storyline_id = s.id
            ) AS last_article_added_at,
            (
                SELECT COUNT(*)
                FROM {schema}.storyline_articles sa
                WHERE sa.storyline_id = s.id
                  AND sa.added_at >= %s - INTERVAL '21 days'
            ) AS articles_21d
        FROM {schema}.storylines s
        WHERE s.merged_into_id IS NULL
          AND COALESCE(s.status, 'active') NOT IN ('archived', 'merged', 'deleted')
          AND (
                s.updated_at >= %s - INTERVAL '90 days'
             OR s.last_refinement >= %s - INTERVAL '90 days'
             OR EXISTS (
                    SELECT 1 FROM {schema}.storyline_articles sa2
                    WHERE sa2.storyline_id = s.id
                      AND sa2.added_at >= %s - INTERVAL '90 days'
                )
          )
        ORDER BY s.updated_at DESC NULLS LAST
        LIMIT 200
        """,
        (since, since, since, since),
    )
    cols = [d[0] for d in cur.description]
    rows = []
    for tup in cur.fetchall():
        row = dict(zip(cols, tup))
        row["domain"] = domain_key
        rows.append(row)
    return rows


def _has_open_tracked_event(cur, domain_key: str, storyline_id: int) -> bool:
    try:
        cur.execute(
            """
            SELECT 1
            FROM intelligence.tracked_events te
            WHERE te.status IS DISTINCT FROM 'closed'
              AND (
                    te.storyline_id::text = %s
                 OR (te.domain_keys IS NOT NULL AND %s = ANY(te.domain_keys))
              )
              AND (
                    te.event_name ILIKE %s
                 OR te.event_type ILIKE %s
                 OR COALESCE(te.editorial_briefing, '') ILIKE %s
              )
            LIMIT 1
            """,
            (
                str(storyline_id),
                domain_key,
                f"%#{storyline_id}%",
                f"%storyline {storyline_id}%",
                f"%storyline_id={storyline_id}%",
            ),
        )
        return cur.fetchone() is not None
    except Exception:
        # tracked_events shape may vary; ignore for scoring
        return False


def classify_and_build_feeds(
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    check_tracked=None,
) -> dict[str, list[dict[str, Any]]]:
    """Pure-ish classification used by the route and unit tests."""
    now = _as_aware(now) or _utcnow()
    news_cutoff = now - timedelta(hours=NEWS_WINDOW_HOURS)
    news: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    one_offs: list[dict[str, Any]] = []

    for row in rows:
        editorial = _parse_editorial(row.get("editorial_document"))
        title = (row.get("title") or "Untitled").strip()
        dek = _dek_from_row(editorial, row.get("description"), title)
        domain = row["domain"]
        sid = int(row["id"])
        updated_at = _as_aware(row.get("updated_at"))
        last_refinement = _as_aware(row.get("last_refinement"))
        material_at = max(
            (t for t in (updated_at, last_refinement) if t is not None),
            default=None,
        )
        article_count = int(row.get("article_count") or 0)
        is_mega = bool(row.get("is_mega_storyline"))
        parent_id = row.get("parent_storyline_id")
        articles_21d = int(row.get("articles_21d") or 0)
        created_at = _as_aware(row.get("created_at"))
        age_days = (now - created_at).days if created_at else 0

        # --- News: material update in 48h + non-empty dek ---
        is_news = bool(
            material_at
            and material_at >= news_cutoff
            and dek
            and len(dek) >= 12
        )
        # Reject shells / membership-only (material_at already excludes last_article_added_at alone)
        if is_news and article_count <= 0 and not editorial.get("lede"):
            is_news = False

        # --- Current events: mega / parent / longevity + cadence ---
        has_tracked = False
        if check_tracked:
            has_tracked = bool(check_tracked(domain, sid))
        is_current = bool(
            is_mega
            or parent_id is not None
            or has_tracked
            or (age_days >= 14 and articles_21d >= 3 and article_count >= 5)
        )

        # --- One-offs: announcement-like, no ongoing arc ---
        blob = " ".join(
            filter(
                None,
                [
                    title,
                    dek,
                    row.get("description") or "",
                    editorial.get("when") or "",
                    editorial.get("outlook") or "",
                ],
            )
        )
        dates = extract_expected_dates(blob, reference=now.date())
        announce_like = any(
            k in blob.lower()
            for k in (
                "announce",
                "launch",
                "release",
                "paper",
                "report due",
                "hearing scheduled",
                "will unveil",
                "scheduled for",
            )
        )
        is_one_off = bool(
            (dates.get("expected_on") or dates.get("announced_on"))
            and not is_mega
            and parent_id is None
            and (announce_like or age_days < 21)
            and articles_21d <= 4
        )

        badges: list[str] = []
        if is_news:
            badges.append("Updated")
            if material_at and (now - material_at) < timedelta(hours=6):
                badges.append("Breaking")

        if is_news:
            news.append(
                _story_unit(
                    section_label="NEWS",
                    headline=title,
                    dek=dek,
                    domain=domain,
                    storyline_id=sid,
                    updated_at=material_at,
                    article_count=article_count,
                    badges=badges,
                    surface_kind="news",
                )
            )

        if is_current:
            current.append(
                _story_unit(
                    section_label="CURRENT",
                    headline=title,
                    dek=dek or (row.get("description") or "")[:280],
                    domain=domain,
                    storyline_id=sid,
                    updated_at=material_at or updated_at,
                    article_count=article_count,
                    badges=["Live"] if has_tracked or is_mega else [],
                    surface_kind="current_events",
                )
            )

        if is_one_off and (dates.get("expected_on") or dates.get("announced_on")):
            one_offs.append(
                _story_unit(
                    section_label="ONE-OFF",
                    headline=title,
                    dek=dek or (row.get("description") or "")[:280],
                    domain=domain,
                    storyline_id=sid,
                    updated_at=material_at or updated_at,
                    article_count=article_count,
                    badges=[],
                    announced_on=dates.get("announced_on"),
                    expected_on=dates.get("expected_on"),
                    date_precision=dates.get("date_precision"),
                    surface_kind="one_off",
                )
            )

    # Deduplicate by (domain, id) within each list; prefer richer dek
    def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, int]] = set()
        out: list[dict[str, Any]] = []
        for it in items:
            key = (it["domain"], it["storyline_id"])
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    news = _dedupe(sorted(news, key=lambda x: x.get("updated_at") or "", reverse=True))
    current = _dedupe(sorted(current, key=lambda x: x.get("updated_at") or "", reverse=True))
    one_offs = _dedupe(
        sorted(
            one_offs,
            key=lambda x: x.get("expected_on") or x.get("announced_on") or "",
        )
    )

    # Avoid showing the same lead in every rail: drop news items from current if already top news
    news_ids = {(n["domain"], n["storyline_id"]) for n in news[:12]}
    current = [c for c in current if (c["domain"], c["storyline_id"]) not in news_ids]

    return {
        "news": news,
        "current_events": current,
        "one_offs": one_offs,
    }


def _paginate(items: list[dict[str, Any]], *, page: int, page_size: int) -> dict[str, Any]:
    total = len(items)
    page = max(1, int(page or 1))
    page_size = max(1, min(50, int(page_size or 12)))
    pages = max(1, math.ceil(total / page_size)) if total else 1
    if page > pages:
        page = pages
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }


def build_reader_home(
    domain: str | None = None,
    *,
    page: int = 1,
    page_size: int = 12,
    section: str | None = None,
) -> dict[str, Any]:
    pairs = _resolve_domain_pairs(domain)
    now = _utcnow()
    all_rows: list[dict[str, Any]] = []

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            for domain_key, schema in pairs:
                try:
                    all_rows.extend(_fetch_candidate_rows(cur, schema, domain_key, now))
                except Exception as exc:
                    logger.warning("reader home skip domain %s: %s", domain_key, exc)
                    conn.rollback()

            def _tracked(dk: str, sid: int) -> bool:
                return _has_open_tracked_event(cur, dk, sid)

            feeds = classify_and_build_feeds(all_rows, now=now, check_tracked=_tracked)

    # Cap raw pools before paging (keeps classify cheap for UI)
    news = feeds["news"][:80]
    current = feeds["current_events"][:80]
    one_offs = feeds["one_offs"][:80]

    news_page = _paginate(news, page=page, page_size=page_size)
    current_page = _paginate(current, page=page, page_size=page_size)
    one_offs_page = _paginate(one_offs, page=page, page_size=page_size)

    section_key = (section or "").strip().lower()
    if section_key in ("news", "current", "current_events", "one_offs", "one-offs"):
        if section_key in ("current", "current_events"):
            paged = current_page
            key = "current_events"
        elif section_key in ("one_offs", "one-offs"):
            paged = one_offs_page
            key = "one_offs"
        else:
            paged = news_page
            key = "news"
        return {
            "domain": domain,
            "generated_at": now.isoformat(),
            "news_window_hours": NEWS_WINDOW_HOURS,
            "section": key,
            key: paged["items"],
            "pagination": {
                "page": paged["page"],
                "page_size": paged["page_size"],
                "total": paged["total"],
                "total_pages": paged["total_pages"],
                "has_prev": paged["has_prev"],
                "has_next": paged["has_next"],
            },
            "nav_ids": [
                {"domain": it["domain"], "storyline_id": it["storyline_id"], "href": it["href"]}
                for it in paged["items"]
            ],
        }

    return {
        "domain": domain,
        "generated_at": now.isoformat(),
        "news_window_hours": NEWS_WINDOW_HOURS,
        "news": news_page["items"],
        "current_events": current_page["items"],
        "one_offs": one_offs_page["items"],
        "pagination": {
            "news": {
                "page": news_page["page"],
                "page_size": news_page["page_size"],
                "total": news_page["total"],
                "total_pages": news_page["total_pages"],
                "has_prev": news_page["has_prev"],
                "has_next": news_page["has_next"],
            },
            "current_events": {
                "page": current_page["page"],
                "page_size": current_page["page_size"],
                "total": current_page["total"],
                "total_pages": current_page["total_pages"],
                "has_prev": current_page["has_prev"],
                "has_next": current_page["has_next"],
            },
            "one_offs": {
                "page": one_offs_page["page"],
                "page_size": one_offs_page["page_size"],
                "total": one_offs_page["total"],
                "total_pages": one_offs_page["total_pages"],
                "has_prev": one_offs_page["has_prev"],
                "has_next": one_offs_page["has_next"],
            },
        },
    }
