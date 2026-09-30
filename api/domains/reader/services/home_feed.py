"""
Reader home feed: News / Current Events / One-offs with StoryUnit fields.

News = material narrative update in last 48h with a real dek — NOT membership-only
``last_article_added_at`` bumps.
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
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
# Artificial Intelligence: one paper (or a thin 1–2 article cluster) is an explainer
# one-off, not an evolving storyline. Multi-source arcs stay on News/Current.
AI_RESEARCH_ONE_OFF_MAX_ARTICLES = 2
AI_DOMAIN_KEY = "artificial-intelligence"

_HOME_CACHE_TTL = float(os.environ.get("READER_HOME_CACHE_TTL", "30"))
_HOME_CACHE_MAX = 64
_HOME_CACHE_LOCK = threading.Lock()
_HOME_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


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
    from shared.llm_text_sanitize import sanitize_reader_dek

    for raw in (
        editorial.get("lede"),
        editorial.get("what"),
        description,
    ):
        cleaned = sanitize_reader_dek(raw, title=title, max_length=280)
        if cleaned:
            return cleaned
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


def _normalize_section(section: str | None) -> str | None:
    key = (section or "").strip().lower()
    if key in ("news",):
        return "news"
    if key in ("current", "current_events"):
        return "current_events"
    if key in ("one_offs", "one-offs"):
        return "one_offs"
    if key == "research":
        return "research"
    return None


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
    href: str | None = None,
) -> dict[str, Any]:
    """Lean StoryUnit for list/home endpoints (omit null optional fields)."""
    body_for_read = f"{headline} {dek}"
    unit: dict[str, Any] = {
        "section_label": section_label,
        "headline": headline,
        "dek": dek,
        "domain": domain,
        "storyline_id": storyline_id,
        "updated_label": _updated_label(updated_at),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "read_minutes": _read_minutes(body_for_read, article_count),
        "badges": badges,
        "article_count": article_count,
        "surface_kind": surface_kind,
        "href": href or f"/storylines/{domain}/{storyline_id}",
    }
    if thumb_url:
        unit["thumb_url"] = thumb_url
    if announced_on:
        unit["announced_on"] = announced_on
    if expected_on:
        unit["expected_on"] = expected_on
    if date_precision:
        unit["date_precision"] = date_precision
    return unit


def _article_id_sets_for_storylines(
    domain_key: str,
    storyline_ids: list[int],
) -> dict[int, set[int]]:
    if not storyline_ids:
        return {}
    schema = resolve_domain_schema(domain_key)
    out: dict[int, set[int]] = {int(s): set() for s in storyline_ids}
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT storyline_id, article_id
                    FROM {schema}.storyline_articles
                    WHERE storyline_id = ANY(%s)
                    """,
                    (list(storyline_ids),),
                )
                for sid, aid in cur.fetchall() or []:
                    out.setdefault(int(sid), set()).add(int(aid))
    except Exception as e:
        logger.debug("article id sets: %s", e)
    return out


def _jaccard_sets(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / float(len(a | b))


def _apply_vault_hub_feed_hygiene(
    items: list[dict[str, Any]],
    *,
    domain_filter: str | None = None,
    inject_hubs: bool = True,
    overlap_threshold: float = 0.35,
) -> list[dict[str, Any]]:
    """Inject vault_hub cards; fold near-dupe hub members under their hub."""
    try:
        from services.vault_cluster_hub_service import (
            list_cluster_hubs,
            storyline_ids_indexed_by_hubs,
            vault_cluster_hubs_enabled,
        )
    except Exception:
        return items
    if not vault_cluster_hubs_enabled():
        return items

    hubs = list_cluster_hubs(domain_key=domain_filter, limit=40)
    if not hubs:
        return items

    by_domain_index: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for h in hubs:
        dk = str(h.get("domain_key") or "politics")
        if domain_filter and dk != domain_filter:
            continue
        if dk not in by_domain_index:
            by_domain_index[dk] = storyline_ids_indexed_by_hubs(dk)

    feed_sids_by_domain: dict[str, list[int]] = {}
    for it in items:
        if it.get("surface_kind") == "vault_hub":
            continue
        dk = str(it.get("domain") or "")
        sid = int(it.get("storyline_id") or 0)
        if not dk or sid <= 0:
            continue
        idx = by_domain_index.get(dk) or {}
        if sid in idx:
            feed_sids_by_domain.setdefault(dk, []).append(sid)

    art_sets: dict[tuple[str, int], set[int]] = {}
    for dk, sids in feed_sids_by_domain.items():
        for sid, arts in _article_id_sets_for_storylines(dk, sids).items():
            art_sets[(dk, sid)] = arts

    hub_activity: list[tuple[int, dict[str, Any], list[dict[str, Any]]]] = []
    for h in hubs:
        dk = str(h.get("domain_key") or "politics")
        if domain_filter and dk != domain_filter:
            continue
        members = set(int(x) for x in (h.get("member_storyline_ids") or []))
        present = [
            it
            for it in items
            if int(it.get("storyline_id") or 0) in members and it.get("domain") == dk
        ]
        if present:
            hub_activity.append((len(present), h, present))
    hub_activity.sort(key=lambda x: -x[0])

    folded_keys: set[tuple[str, int]] = set()

    for _n, h, present in hub_activity:
        present_sorted = sorted(
            present,
            key=lambda it: it.get("updated_at") or "",
            reverse=True,
        )
        if not present_sorted:
            continue
        keep = present_sorted[0]
        keep_sid = int(keep["storyline_id"])
        dk = str(keep["domain"])
        keep_arts = art_sets.get((dk, keep_sid), set())
        for other in present_sorted[1:]:
            oid = int(other["storyline_id"])
            oarts = art_sets.get((dk, oid), set())
            if _jaccard_sets(keep_arts, oarts) >= overlap_threshold or (
                keep_arts and oarts and len(keep_arts & oarts) >= 3
            ):
                folded_keys.add((dk, oid))

    filtered: list[dict[str, Any]] = []
    for it in items:
        if it.get("surface_kind") == "vault_hub":
            filtered.append(it)
            continue
        key = (str(it.get("domain") or ""), int(it.get("storyline_id") or 0))
        if key in folded_keys:
            continue
        filtered.append(it)

    if not inject_hubs or not hub_activity:
        return filtered

    hub_units: list[dict[str, Any]] = []
    for _n, h, _present in hub_activity[:5]:
        ck = h.get("cluster_key") or str(h["id"])
        member_n = len(h.get("member_storyline_ids") or [])
        updated = None
        if h.get("updated_at"):
            try:
                updated = _as_aware(datetime.fromisoformat(str(h["updated_at"])))
            except Exception:
                updated = None
        brief = (h.get("current_brief") or "").strip()
        dek = (
            (brief[:240] + ("…" if len(brief) > 240 else ""))
            if brief
            else f"Situation index — {member_n} related episodes."
        )
        hub_unit = _story_unit(
            section_label="Situation",
            headline=h.get("title") or ck,
            dek=dek,
            domain=str(h.get("domain_key") or "politics"),
            storyline_id=0,
            updated_at=updated,
            article_count=member_n,
            badges=["situation"],
            surface_kind="vault_hub",
            href=h.get("href") or f"/hubs/{ck}",
        )
        hub_unit["cluster_key"] = ck
        hub_unit["hub_id"] = int(h["id"])
        if brief:
            hub_unit["current_brief"] = brief
        hub_units.append(hub_unit)

    # Place primary hub after the lead story when present
    if not filtered:
        return hub_units + filtered
    return [filtered[0]] + hub_units + filtered[1:]


def _inject_daily_briefing_lead(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """No-op: morning brief is not a news article.

    Stories from the morning slate are injected as ``storyline_expansion`` units
    via ``_inject_morning_expansion_catalog`` (each links to its storyline reader).
    The daily briefing markdown stays in the vault / MemPalace diary for operators.
    """
    return [
        it
        for it in items
        if it.get("surface_kind") != "daily_briefing"
    ]


def _morning_expansion_units(*, lane_filter: str | None = None) -> list[dict[str, Any]]:
    """Build StoryUnits from morning expansions (optional lane filter)."""
    from datetime import date, datetime

    from services.vault_notes_registry_service import list_morning_expansions

    expansions = list_morning_expansions(
        briefing_day=date.today().isoformat(), limit=40
    )
    if not expansions:
        expansions = list_morning_expansions(briefing_day=None, limit=40)

    out: list[dict[str, Any]] = []
    for ex in expansions:
        dk = str(ex.get("domain_key") or "politics")
        sid = int(ex.get("object_id") or 0)
        if sid <= 0:
            continue
        lane = str(ex.get("briefing_lane") or "new")
        if lane not in ("ongoing", "new"):
            lane = "new"
        if lane_filter and lane != lane_filter:
            continue
        updated_at = None
        raw_u = ex.get("note_updated_at")
        if isinstance(raw_u, datetime):
            updated_at = raw_u
        elif isinstance(raw_u, str) and raw_u:
            try:
                updated_at = datetime.fromisoformat(raw_u.replace("Z", "+00:00"))
            except ValueError:
                updated_at = None
        unit = _story_unit(
            section_label="Ongoing" if lane == "ongoing" else "New of note",
            headline=ex.get("title") or f"Storyline {sid}",
            dek=(ex.get("summary_md") or "").strip()[:320]
            or "Morning expansion ready.",
            domain=dk,
            storyline_id=sid,
            updated_at=updated_at,
            article_count=0,
            badges=[lane],
            surface_kind="storyline_expansion",
            href=f"/storylines/{dk}/{sid}",
        )
        unit["briefing_lane"] = lane
        unit["vault_path"] = ex.get("vault_path")
        unit["summary_md"] = ex.get("summary_md")
        out.append(unit)
    return out


def _inject_morning_expansion_catalog(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """News lead: new-of-note expansions (ongoing arcs live under Current Events)."""
    catalog = _morning_expansion_units(lane_filter="new")
    # If manager marked nothing as new, still surface a short mixed slate on News.
    if not catalog:
        catalog = _morning_expansion_units(lane_filter=None)[:8]
    if not catalog:
        return _inject_daily_briefing_lead(items)

    rest = [
        it
        for it in items
        if it.get("surface_kind") not in ("daily_briefing", "storyline_expansion")
    ]
    seen = {(u["domain"], u["storyline_id"]) for u in catalog}
    rest_f = [
        it
        for it in rest
        if (it.get("domain"), it.get("storyline_id")) not in seen
    ]
    return catalog + rest_f


def _priority_current_event_units(*, limit: int = 40) -> list[dict[str, Any]]:
    """Current Events from biggest / freshest / longest-running vault event notes."""
    from datetime import datetime

    from services.vault_notes_registry_service import list_priority_current_event_arcs

    arcs = list_priority_current_event_arcs(limit=limit)
    out: list[dict[str, Any]] = []
    for arc in arcs:
        dk = str(arc.get("domain_key") or "politics")
        sid = int(arc.get("storyline_id") or arc.get("object_id") or 0)
        if sid <= 0:
            continue
        updated_at = None
        raw_u = arc.get("note_updated_at")
        if isinstance(raw_u, datetime):
            updated_at = raw_u
        elif isinstance(raw_u, str) and raw_u:
            try:
                updated_at = datetime.fromisoformat(raw_u.replace("Z", "+00:00"))
            except ValueError:
                updated_at = None
        age_days = int(arc.get("age_days") or 0)
        note_chars = int(arc.get("note_chars") or 0)
        badges = ["ongoing"]
        if note_chars >= 2500:
            badges.append("deep")
        if age_days >= 14:
            badges.append("long-running")
        unit = _story_unit(
            section_label="Ongoing",
            headline=arc.get("title") or f"Storyline {sid}",
            dek=(arc.get("summary_md") or "").strip()[:320]
            or "Living vault coverage for this arc.",
            domain=dk,
            storyline_id=sid,
            updated_at=updated_at,
            article_count=0,
            badges=badges,
            surface_kind="storyline_expansion",
            href=f"/storylines/{dk}/{sid}",
        )
        unit["briefing_lane"] = "ongoing"
        unit["vault_path"] = arc.get("vault_path")
        unit["summary_md"] = arc.get("summary_md")
        unit["note_chars"] = note_chars
        unit["age_days"] = age_days
        out.append(unit)
    return out


def _inject_morning_ongoing_into_current(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Current Events lead: weightiest vault event notes as storyline articles."""
    catalog = _priority_current_event_units(limit=40)
    if not catalog:
        # Fallback to morning ongoing lane if vault weight ranking is empty.
        catalog = _morning_expansion_units(lane_filter="ongoing")
    if not catalog:
        return items
    rest = [
        it
        for it in items
        if it.get("surface_kind") != "storyline_expansion"
    ]
    seen = {(u["domain"], u["storyline_id"]) for u in catalog}
    rest_f = [
        it
        for it in rest
        if (it.get("domain"), it.get("storyline_id")) not in seen
    ]
    return catalog + rest_f


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
            s.story_kind,
            agg.last_article_added_at,
            COALESCE(agg.articles_21d, 0) AS articles_21d
        FROM {schema}.storylines s
        LEFT JOIN LATERAL (
            SELECT
                MAX(sa.added_at) AS last_article_added_at,
                COUNT(*) FILTER (
                    WHERE sa.added_at >= %s - INTERVAL '21 days'
                ) AS articles_21d
            FROM {schema}.storyline_articles sa
            WHERE sa.storyline_id = s.id
        ) agg ON TRUE
        WHERE s.merged_into_id IS NULL
          AND COALESCE(s.status, 'active') NOT IN ('archived', 'merged', 'deleted')
          AND (
                s.updated_at >= %s - INTERVAL '90 days'
             OR s.last_refinement >= %s - INTERVAL '90 days'
             OR agg.last_article_added_at >= %s - INTERVAL '90 days'
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


def _batch_open_tracked(
    cur,
    pairs: list[tuple[str, int]],
) -> set[tuple[str, int]]:
    """Return {(domain, storyline_id)} with an open tracked-event hit (one query)."""
    if not pairs:
        return set()
    domains = sorted({dk for dk, _ in pairs})
    ids = sorted({sid for _, sid in pairs})
    id_strs = [str(i) for i in ids]
    try:
        cur.execute(
            """
            SELECT
                te.storyline_id::text,
                te.domain_keys,
                COALESCE(te.event_name, ''),
                COALESCE(te.event_type, ''),
                COALESCE(te.editorial_briefing, '')
            FROM intelligence.tracked_events te
            WHERE te.status IS DISTINCT FROM 'closed'
              AND (
                    te.storyline_id = ANY(%s)
                 OR (te.domain_keys IS NOT NULL AND te.domain_keys && %s::text[])
              )
            """,
            (id_strs, domains),
        )
        events = cur.fetchall()
    except Exception as exc:
        logger.debug("batch tracked_events: %s", exc)
        return set()

    wanted = set(pairs)
    hits: set[tuple[str, int]] = set()
    for sid_raw, dkeys, ename, etype, brief in events:
        blob = f"{ename} {etype} {brief}".lower()
        dkey_list = list(dkeys) if dkeys else []
        for domain, sid in wanted:
            if (domain, sid) in hits:
                continue
            sid_s = str(sid)
            domain_ok = (sid_raw == sid_s) or (domain in dkey_list)
            if not domain_ok:
                continue
            text_ok = (
                f"#{sid_s}" in blob
                or f"storyline {sid_s}" in blob
                or f"storyline_id={sid_s}" in blob
            )
            if text_ok:
                hits.add((domain, sid))
    return hits


def classify_and_build_feeds(
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    check_tracked=None,
    include_news: bool = True,
    include_current: bool = True,
    include_one_offs: bool = True,
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

        # --- Current events: intentional long arcs (not every mega bag) ---
        # Prefer tracked watches + parent trees + sustained cadence.
        # Bare is_mega alone flooded Current with kitchen-sink Bloomberg magnets.
        has_tracked = False
        if include_current and check_tracked:
            has_tracked = bool(check_tracked(domain, sid))
        is_current = bool(
            parent_id is not None
            or has_tracked
            or (
                age_days >= 21
                and articles_21d >= 5
                and article_count >= 8
                and not is_mega
            )
        )

        # --- One-offs: announcement-like, no ongoing arc ---
        dates: dict[str, Any] = {}
        announce_like = False
        if include_one_offs:
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
            include_one_offs
            and (dates.get("expected_on") or dates.get("announced_on"))
            and not is_mega
            and parent_id is None
            and (announce_like or age_days < 21)
            and articles_21d <= 4
        )

        # AI research: thin clusters (1–2 sources/articles) are paper explainers → One-offs.
        # Always suppress News/Current for these, even when the one-offs rail is skipped.
        story_kind = (row.get("story_kind") or "").strip().lower()
        is_ai_research_one_off = bool(
            (
                story_kind == "one_off"
                or (
                    domain == AI_DOMAIN_KEY
                    and 1 <= article_count <= AI_RESEARCH_ONE_OFF_MAX_ARTICLES
                )
            )
            and not is_mega
            and parent_id is None
        )
        if is_ai_research_one_off:
            is_news = False
            is_current = False
            if include_one_offs:
                is_one_off = True
                if not dates.get("announced_on") and not dates.get("expected_on"):
                    # Prefer article drop date for calendar grouping when prose has no date.
                    announced = created_at or material_at or updated_at
                    if announced:
                        dates["announced_on"] = announced.date().isoformat()
                        dates["date_precision"] = "day"

        badges: list[str] = []
        if is_news:
            badges.append("Updated")
            if material_at and (now - material_at) < timedelta(hours=6):
                badges.append("Breaking")
        if is_ai_research_one_off:
            badges = ["Paper"] if article_count <= 1 else ["Papers"]

        if include_news and is_news:
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

        if include_current and is_current:
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

        if include_one_offs and is_one_off and (dates.get("expected_on") or dates.get("announced_on")):
            one_offs.append(
                _story_unit(
                    section_label="ONE-OFF",
                    headline=title,
                    dek=dek or (row.get("description") or "")[:280],
                    domain=domain,
                    storyline_id=sid,
                    updated_at=material_at or updated_at,
                    article_count=article_count,
                    badges=badges if is_ai_research_one_off else [],
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
    if include_news and include_current:
        news_ids = {(n["domain"], n["storyline_id"]) for n in news[:12]}
        current = [c for c in current if (c["domain"], c["storyline_id"]) not in news_ids]

    return {
        "news": news,
        "current_events": current,
        "one_offs": one_offs,
        "research": [],
    }


def _research_badges(facets: Any, subjects: Any) -> list[str]:
    badges: list[str] = ["Paper"]
    if isinstance(facets, dict):
        dep = str(facets.get("deployment_class") or "").lower()
        if dep in ("frontier", "local", "both"):
            badges.append(dep.capitalize() if dep != "both" else "Frontier+Local")
        models = facets.get("models") or []
        if isinstance(models, list) and models:
            badges.append("LLM" if any(
                str((m or {}).get("class") if isinstance(m, dict) else "").lower() == "llm"
                or "llm" in str(m).lower()
                for m in models[:5]
            ) else "Models")
    return badges[:4]


def _fetch_research_units(
    cur,
    pairs: list[tuple[str, str]],
    *,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Profile-backed research cards from intelligence.research_paper_profiles."""
    out: list[dict[str, Any]] = []
    domain_filter = [dk for dk, _ in pairs]
    if not domain_filter:
        return out
    try:
        cur.execute(
            """
            SELECT p.domain_key, p.article_id, p.research_question, p.findings_summary,
                   p.implications, p.domain_facets, p.subjects_studied, p.extracted_at,
                   p.arxiv_id, p.doi
            FROM intelligence.research_paper_profiles p
            WHERE p.extraction_status = 'done'
              AND p.domain_key = ANY(%s)
            ORDER BY COALESCE(p.extracted_at, p.updated_at) DESC NULLS LAST
            LIMIT %s
            """,
            (domain_filter, limit),
        )
        profile_rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    except Exception as e:
        logger.debug("research profiles query: %s", e)
        return out

    schema_by_domain = {dk: sch for dk, sch in pairs}
    profiles = [dict(zip(cols, tup)) for tup in profile_rows]

    # Batch article lookups per schema (avoid N+1)
    ids_by_schema: dict[str, list[int]] = {}
    for row in profiles:
        schema = schema_by_domain.get(row["domain_key"])
        if not schema:
            continue
        ids_by_schema.setdefault(schema, []).append(int(row["article_id"]))

    articles_by_schema: dict[str, dict[int, tuple[Any, ...]]] = {}
    for schema, aids in ids_by_schema.items():
        uniq = sorted(set(aids))
        try:
            cur.execute(
                f"""
                SELECT id, title, url, published_at, created_at
                FROM {schema}.articles
                WHERE id = ANY(%s)
                """,
                (uniq,),
            )
            articles_by_schema[schema] = {
                int(r[0]): r[1:] for r in cur.fetchall()
            }
        except Exception:
            articles_by_schema[schema] = {}

    for row in profiles:
        dk = row["domain_key"]
        schema = schema_by_domain.get(dk)
        if not schema:
            continue
        aid = int(row["article_id"])
        art = articles_by_schema.get(schema, {}).get(aid)
        if not art:
            continue
        title, url, published, created = art
        if not title:
            continue
        published = published or created
        dek = (row.get("research_question") or row.get("findings_summary") or "")[:280]
        facets = row.get("domain_facets")
        if isinstance(facets, str):
            try:
                facets = json.loads(facets)
            except Exception:
                facets = {}
        announced = None
        if published:
            pa = _as_aware(published)
            if pa:
                announced = pa.date().isoformat()
        href = url or f"/research?domain={dk}"
        out.append(
            _story_unit(
                section_label="RESEARCH",
                headline=title.strip(),
                dek=dek,
                domain=dk,
                storyline_id=aid,
                updated_at=_as_aware(row.get("extracted_at")) or _as_aware(published),
                article_count=1,
                badges=_research_badges(facets, row.get("subjects_studied")),
                announced_on=announced,
                date_precision="day" if announced else None,
                surface_kind="research",
                href=href,
            )
        )
    return out


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


def _cache_key(domain: str | None, section: str | None, page: int, page_size: int) -> str:
    return f"{domain or '*'}|{section or 'all'}|{page}|{page_size}"


def _cache_get(key: str) -> dict[str, Any] | None:
    if _HOME_CACHE_TTL <= 0:
        return None
    with _HOME_CACHE_LOCK:
        hit = _HOME_CACHE.get(key)
        if not hit:
            return None
        expires, payload = hit
        if time.monotonic() > expires:
            _HOME_CACHE.pop(key, None)
            return None
        return payload


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    if _HOME_CACHE_TTL <= 0:
        return
    with _HOME_CACHE_LOCK:
        if len(_HOME_CACHE) >= _HOME_CACHE_MAX:
            # Drop oldest expiry first
            oldest = sorted(_HOME_CACHE.items(), key=lambda kv: kv[1][0])[: max(1, _HOME_CACHE_MAX // 4)]
            for k, _ in oldest:
                _HOME_CACHE.pop(k, None)
        _HOME_CACHE[key] = (time.monotonic() + _HOME_CACHE_TTL, payload)


def build_reader_home(
    domain: str | None = None,
    *,
    page: int = 1,
    page_size: int = 12,
    section: str | None = None,
) -> dict[str, Any]:
    section_key = _normalize_section(section)
    ck = _cache_key(domain, section_key, page, page_size)
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    pairs = _resolve_domain_pairs(domain)
    now = _utcnow()

    need_candidates = section_key != "research"
    need_research = section_key in (None, "research", "one_offs")
    include_news = section_key in (None, "news")
    include_current = section_key in (None, "current_events")
    include_one_offs = section_key in (None, "one_offs")
    need_tracked = include_current

    all_rows: list[dict[str, Any]] = []
    research: list[dict[str, Any]] = []
    feeds = {
        "news": [],
        "current_events": [],
        "one_offs": [],
        "research": [],
    }

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if need_candidates:
                for domain_key, schema in pairs:
                    try:
                        all_rows.extend(_fetch_candidate_rows(cur, schema, domain_key, now))
                    except Exception as exc:
                        logger.warning("reader home skip domain %s: %s", domain_key, exc)
                        conn.rollback()

                tracked_hits: set[tuple[str, int]] = set()
                if need_tracked and all_rows:
                    pairs_ids = [(str(r["domain"]), int(r["id"])) for r in all_rows]
                    tracked_hits = _batch_open_tracked(cur, pairs_ids)

                def _tracked(dk: str, sid: int) -> bool:
                    return (dk, sid) in tracked_hits

                feeds = classify_and_build_feeds(
                    all_rows,
                    now=now,
                    check_tracked=_tracked if need_tracked else None,
                    include_news=include_news,
                    include_current=include_current,
                    include_one_offs=include_one_offs,
                )

            if need_research:
                try:
                    research = _fetch_research_units(cur, pairs, limit=80)
                except Exception as exc:
                    logger.warning("reader research feed: %s", exc)
                    conn.rollback()
                    research = []

    # Cap raw pools before paging (keeps classify cheap for UI)
    news = feeds["news"][:80]
    current = feeds["current_events"][:80]
    one_offs = feeds["one_offs"][:80]

    # Inject vault cluster hubs + demote near-dupe members under hubs
    try:
        news = _apply_vault_hub_feed_hygiene(news, domain_filter=domain)
        current = _apply_vault_hub_feed_hygiene(current, domain_filter=domain, inject_hubs=False)
    except Exception as hub_exc:
        logger.debug("vault hub feed hygiene: %s", hub_exc)

    # Morning expansion catalog for News (new-of-note) — not a briefing article
    try:
        news = _inject_morning_expansion_catalog(news)
    except Exception as cat_exc:
        logger.debug("morning expansion catalog: %s", cat_exc)
    try:
        news = _inject_daily_briefing_lead(news)
    except Exception as brief_exc:
        logger.debug("daily briefing strip: %s", brief_exc)
    # Current Events: ongoing morning expansions as storyline articles
    try:
        current = _inject_morning_ongoing_into_current(current)
    except Exception as cur_exc:
        logger.debug("morning ongoing into current: %s", cur_exc)

    # Dated research papers also appear on the One-offs calendar
    if include_one_offs:
        for ru in research:
            if ru.get("announced_on") or ru.get("expected_on"):
                one_offs.append(ru)
        # Dedupe one_offs after merge
        seen_oo: set[tuple[str, int, str]] = set()
        deduped_oo: list[dict[str, Any]] = []
        for it in one_offs:
            key = (it["domain"], it["storyline_id"], it.get("surface_kind") or "")
            if key in seen_oo:
                continue
            seen_oo.add(key)
            deduped_oo.append(it)
        one_offs = sorted(
            deduped_oo,
            key=lambda x: x.get("expected_on") or x.get("announced_on") or "",
        )[:80]

    news_page = _paginate(news, page=page, page_size=page_size)
    current_page = _paginate(current, page=page, page_size=page_size)
    one_offs_page = _paginate(one_offs, page=page, page_size=page_size)
    research_page = _paginate(research[:80], page=page, page_size=page_size)

    if section_key:
        if section_key == "current_events":
            paged = current_page
            key = "current_events"
        elif section_key == "one_offs":
            paged = one_offs_page
            key = "one_offs"
        elif section_key == "research":
            paged = research_page
            key = "research"
        else:
            paged = news_page
            key = "news"
        result = {
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
        _cache_set(ck, result)
        return result

    result = {
        "domain": domain,
        "generated_at": now.isoformat(),
        "news_window_hours": NEWS_WINDOW_HOURS,
        "news": news_page["items"],
        "current_events": current_page["items"],
        "one_offs": one_offs_page["items"],
        "research": research_page["items"],
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
            "research": {
                "page": research_page["page"],
                "page_size": research_page["page_size"],
                "total": research_page["total"],
                "total_pages": research_page["total_pages"],
                "has_prev": research_page["has_prev"],
                "has_next": research_page["has_next"],
            },
        },
    }
    _cache_set(ck, result)
    return result
