=== home_feed.py ===
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


def _dek_from_row(
    editorial: dict[str, Any],
    description: str | None,
    title: str,
    *,
    document_status: str | None = None,
) -> str:
    from shared.llm_text_sanitize import sanitize_reader_dek

    def _as_text(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, list):
            parts = [str(x).strip() for x in raw if str(x).strip()]
            return "; ".join(parts[:3])
        return str(raw).strip()

    status = str(document_status or "")
    prefer_analysis = status in (
        "package_projected",
        "desk_promoted",
        "refined",
        "rag_analyzed",
    )
    candidates = [
        editorial.get("lede"),
        editorial.get("analysis") if prefer_analysis else None,
        editorial.get("what"),
        description,
    ]
    for raw in candidates:
        cleaned = sanitize_reader_dek(_as_text(raw), title=title, max_length=280)
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
        from shared.llm_text_sanitize import sanitize_reader_dek, sanitize_reader_prose

        brief = (h.get("current_brief") or "").strip()
        headline = h.get("title") or ck
        dek = (
            sanitize_reader_dek(brief, title=str(headline), max_length=240)
            if brief
            else f"Situation index — {member_n} related episodes."
        )
        if not dek:
            dek = f"Situation index — {member_n} related episodes."
        brief_clean = (
            sanitize_reader_prose(brief, title=str(headline), max_length=4000)
            if brief
            else ""
        )
        hub_unit = _story_unit(
            section_label="Situation",
            headline=headline,
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
        if brief_clean:
            hub_unit["current_brief"] = brief_clean
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
        from shared.llm_text_sanitize import sanitize_reader_dek

        headline = ex.get("title") or f"Storyline {sid}"
        dek = (
            sanitize_reader_dek(
                ex.get("summary_md") or "",
                title=str(headline),
                max_length=280,
            )
            or "Morning expansion ready."
        )
        unit = _story_unit(
            section_label="Ongoing" if lane == "ongoing" else "New of note",
            headline=headline,
            dek=dek,
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
        unit["summary_md"] = dek if dek != "Morning expansion ready." else None
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
        from shared.llm_text_sanitize import sanitize_reader_dek

        age_days = int(arc.get("age_days") or 0)
        note_chars = int(arc.get("note_chars") or 0)
        badges = ["ongoing"]
        if note_chars >= 2500:
            badges.append("deep")
        if age_days >= 14:
            badges.append("long-running")
        headline = arc.get("title") or f"Storyline {sid}"
        dek = (
            sanitize_reader_dek(
                arc.get("summary_md") or "",
                title=str(headline),
                max_length=280,
            )
            or "Living vault coverage for this arc."
        )
        unit = _story_unit(
            section_label="Ongoing",
            headline=headline,
            dek=dek,
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
        unit["summary_md"] = (
            dek if dek != "Living vault coverage for this arc." else None
        )
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
            s.document_status,
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
        dek = _dek_from_row(
            editorial,
            row.get("description"),
            title,
            document_status=row.get("document_status"),
        )
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
        status = str(row.get("status") or "active").lower()
        is_news = bool(
            material_at
            and material_at >= news_cutoff
            and dek
            and len(dek) >= 12
            and not is_mega
            and status not in ("dormant", "watching", "concluded", "completed", "failed")
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

=== storyline_pack.py ===
"""
Reader pack for a single storyline: summary, timeline, citations, dossier rail.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)

_HEADING_ONLY_STUB = re.compile(
    r"^(key\s+takeaways|summary|timeline|background|overview)\s*:?\s*$",
    re.IGNORECASE,
)


def _parse_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _article_grounded_summary(
    citations: list[dict[str, Any]], *, title: str = "", max_chars: int = 1400
) -> str:
    """
    Build a short reader brief from member article body/summary when stored
    narratives are inventory fluff or empty.
    """
    from shared.llm_text_sanitize import html_to_visible_text

    chunks: list[str] = []
    # Prefer longest bodies first (substance over thin liveblog stubs)
    ranked = sorted(
        citations,
        key=lambda c: len(str(c.get("content") or c.get("summary") or "")),
        reverse=True,
    )
    for cite in ranked[:3]:
        raw = cite.get("content") or cite.get("summary") or ""
        prose = html_to_visible_text(str(raw), max_length=700)
        if not prose or len(re.sub(r"\W+", "", prose)) < 80:
            continue
        # Drop leading markdown H2 that is often a liveblog section title
        prose = re.sub(r"^##\s+[^\n]+\n+", "", prose).strip()
        # First 2 paragraphs
        paras = [p.strip() for p in re.split(r"\n\s*\n+", prose) if p.strip()]
        excerpt = " ".join(paras[:2]) if paras else prose
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        if len(excerpt) < 80:
            continue
        src = (cite.get("source_domain") or "").strip()
        headline = (cite.get("title") or "").strip()
        lead = excerpt if len(excerpt) <= 520 else excerpt[:500].rsplit(" ", 1)[0] + "…"
        if headline and headline.casefold() != (title or "").casefold():
            prefix = f"**{headline}**" + (f" ({src})" if src else "")
            chunks.append(f"{prefix} — {lead}")
        else:
            chunks.append(lead)
        if sum(len(c) for c in chunks) >= max_chars:
            break
    if not chunks:
        return ""
    out = "\n\n".join(chunks)
    if len(out) > max_chars:
        out = out[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return out


def _usable_summary_text(raw: Any) -> str:
    """Return stripped text, or empty if missing / heading-only stub."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    if _HEADING_ONLY_STUB.match(text):
        return ""
    return text


def _build_dossier_tree(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nest entities by member_of_family / family-like edges when present."""
    by_id = {e["id"]: {**e, "children": []} for e in entities if e.get("id") is not None}
    roots: list[dict[str, Any]] = []
    child_ids: set[Any] = set()

    for rel in relationships:
        rtype = (rel.get("relationship_type") or rel.get("type") or "").lower()
        if rtype not in ("member_of_family", "member_of", "part_of", "subsidiary_of", "works_for"):
            continue
        parent = rel.get("target_entity_id") or rel.get("to_entity_id") or rel.get("parent_id")
        child = rel.get("source_entity_id") or rel.get("from_entity_id") or rel.get("child_id")
        if parent in by_id and child in by_id and parent != child:
            by_id[parent]["children"].append(by_id[child])
            child_ids.add(child)

    for eid, node in by_id.items():
        if eid not in child_ids:
            roots.append(node)

    if not roots:
        return list(by_id.values())
    return roots


def build_storyline_reader_pack(domain: str, storyline_id: int) -> dict[str, Any]:
    if not validate_domain(domain):
        raise ValueError(f"Invalid or inactive domain: {domain}")

    schema = resolve_domain_schema(domain)
    timeline: dict[str, Any] = {"events": []}

    with get_ui_db_connection_context() as conn:
        try:
            from shared.episode_attach_gate import episode_container_assembly_enabled
            from services.episode_container_timeline_service import episode_timeline

            if episode_container_assembly_enabled():
                packed = episode_timeline(domain, storyline_id, limit=100) or {}
                events = packed.get("events") or []
                timeline = {
                    "events": [
                        {
                            "id": e.get("id"),
                            "title": e.get("title"),
                            "date": (
                                e.get("actual_event_date").isoformat()
                                if hasattr(e.get("actual_event_date"), "isoformat")
                                else e.get("actual_event_date")
                            ),
                            "event_type": e.get("event_type"),
                            "summary": e.get("summary"),
                            "source_article_id": e.get("source_article_id"),
                            "link_type": e.get("link_type"),
                            "matched_anchors": e.get("matched_anchors"),
                        }
                        for e in events
                        if isinstance(e, dict)
                    ]
                }
            else:
                from services.timeline_builder_service import TimelineBuilderService

                timeline = (
                    TimelineBuilderService(conn, schema_name=schema).build_timeline(
                        storyline_id
                    )
                    or {"events": []}
                )
        except Exception as exc:
            logger.warning("timeline build failed for %s/%s: %s", domain, storyline_id, exc)
            timeline = {"events": [], "error": str(exc)}

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    s.id, s.title, s.description, s.status,
                    s.created_at, s.updated_at, s.article_count, s.quality_score,
                    s.master_summary, s.background_information,
                    s.editorial_document, s.document_version, s.document_status,
                    s.canonical_narrative, s.timeline_narrative_chronological,
                    s.timeline_narrative_briefing, s.key_entities,
                    s.parent_storyline_id, COALESCE(s.is_mega_storyline, FALSE),
                    s.last_refinement
                FROM {schema}.storylines s
                WHERE s.id = %s AND s.merged_into_id IS NULL
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError(f"Storyline {storyline_id} not found in {domain}")

            (
                sid,
                title,
                description,
                status,
                created_at,
                updated_at,
                article_count,
                quality_score,
                master_summary,
                background_information,
                editorial_document,
                document_version,
                document_status,
                canonical_narrative,
                timeline_narrative_chronological,
                timeline_narrative_briefing,
                key_entities,
                parent_storyline_id,
                is_mega_storyline,
                last_refinement,
            ) = row

            editorial = _parse_json(editorial_document) or {}

            # Citations: prefer EEL (event-grain) when assembly on; bag is fallback only.
            citations: list[dict[str, Any]] = []
            use_eel = False
            try:
                from shared.episode_attach_gate import episode_container_assembly_enabled
                from shared.episode_membership import list_episode_articles_sql

                use_eel = bool(episode_container_assembly_enabled())
            except Exception:
                use_eel = False

            if use_eel:
                try:
                    cur.execute(
                        list_episode_articles_sql(schema, with_content=True) + "\nLIMIT 50",
                        (domain, storyline_id),
                    )
                    citations = [
                        {
                            "id": r[0],
                            "title": r[1],
                            "url": r[2],
                            "source_domain": r[3],
                            "published_at": r[4].isoformat() if r[4] else None,
                            "summary": r[5],
                            "content": r[6] if len(r) > 6 else None,
                        }
                        for r in cur.fetchall()
                    ]
                except Exception as exc:
                    logger.debug("EEL citations failed, bag fallback: %s", exc)
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    citations = []

            if not citations:
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary,
                           left(coalesce(a.content, ''), 8000) AS content
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT 50
                    """,
                    (storyline_id,),
                )
                citations = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "url": r[2],
                        "source_domain": r[3],
                        "published_at": r[4].isoformat() if r[4] else None,
                        "summary": r[5],
                        "content": r[6],
                    }
                    for r in cur.fetchall()
                ]

            # Entities: EEL-linked articles when assembly on
            entities: list[dict[str, Any]] = []
            relationships: list[dict[str, Any]] = []
            try:
                if use_eel:
                    from shared.episode_membership import list_episode_entities_sql

                    cur.execute(list_episode_entities_sql(schema), (domain, storyline_id))
                else:
                    cur.execute(
                        f"""
                        SELECT DISTINCT ON (e.id)
                            e.id, e.name, e.entity_type, e.description
                        FROM {schema}.entities e
                        JOIN {schema}.article_entities ae ON ae.entity_id = e.id
                        JOIN {schema}.storyline_articles sa ON sa.article_id = ae.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY e.id, e.name
                        LIMIT 40
                        """,
                        (storyline_id,),
                    )
                for r in cur.fetchall():
                    entities.append(
                        {
                            "id": r[0],
                            "name": r[1],
                            "entity_type": r[2],
                            "description_short": (r[3] or "")[:240],
                            "who": None,
                            "what": None,
                            "why": None,
                            "href": f"/entities/{r[0]}?domain={domain}",
                        }
                    )
            except Exception as exc:
                logger.debug("entity join fallback: %s", exc)
                conn.rollback()
                # Fall back to key_entities JSON
                ke = _parse_json(key_entities)
                if isinstance(ke, list):
                    for i, item in enumerate(ke[:20]):
                        if isinstance(item, dict):
                            entities.append(
                                {
                                    "id": item.get("id") or f"ke-{i}",
                                    "name": item.get("name") or "Entity",
                                    "entity_type": item.get("type") or item.get("entity_type"),
                                    "description_short": (item.get("description") or "")[:240],
                                    "href": None,
                                }
                            )
                        elif isinstance(item, str):
                            entities.append(
                                {
                                    "id": f"ke-{i}",
                                    "name": item,
                                    "entity_type": None,
                                    "description_short": "",
                                    "href": None,
                                }
                            )

            # Enrich from dossiers when available
            for ent in entities:
                eid = ent.get("id")
                if not isinstance(eid, int):
                    continue
                try:
                    cur.execute(
                        """
                        SELECT chronicle_data, relationships, metadata
                        FROM intelligence.entity_dossiers
                        WHERE entity_id = %s
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT 1
                        """,
                        (eid,),
                    )
                    drow = cur.fetchone()
                    if drow:
                        chronicle = _parse_json(drow[0]) or {}
                        rels = _parse_json(drow[1]) or []
                        meta = _parse_json(drow[2]) or {}
                        ent["who"] = chronicle.get("who") or meta.get("who") or ent.get("description_short")
                        ent["what"] = chronicle.get("what") or meta.get("what")
                        ent["why"] = chronicle.get("why") or meta.get("why")
                        if isinstance(rels, list):
                            for rel in rels:
                                if isinstance(rel, dict):
                                    relationships.append({**rel, "source_entity_id": eid})
                except Exception:
                    conn.rollback()
                    break  # dossier table may be absent

            # Hierarchy siblings / children
            hierarchy = {
                "parent_storyline_id": parent_storyline_id,
                "is_mega_storyline": bool(is_mega_storyline),
                "children": [],
            }
            try:
                cur.execute(
                    f"""
                    SELECT id, title
                    FROM {schema}.storylines
                    WHERE parent_storyline_id = %s AND merged_into_id IS NULL
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 20
                    """,
                    (storyline_id,),
                )
                hierarchy["children"] = [
                    {"id": r[0], "title": r[1], "href": f"/storylines/{domain}/{r[0]}"}
                    for r in cur.fetchall()
                ]
            except Exception:
                conn.rollback()

    from shared.llm_text_sanitize import (
        is_desk_walkthrough,
        is_inventory_metadata_summary,
        is_multi_topic_excerpt_mash,
        sanitize_briefing_lede,
        sanitize_reader_dek,
        sanitize_reader_prose,
        strip_inventory_metadata_summary,
        strip_llm_wrapping_artifacts,
        strip_trailing_llm_json,
    )

    ed = editorial if isinstance(editorial, dict) else {}
    lede_raw = _usable_summary_text(ed.get("lede"))
    analysis_raw = _usable_summary_text(ed.get("analysis"))
    master_raw = strip_inventory_metadata_summary(
        strip_trailing_llm_json(_usable_summary_text(master_summary))
    )
    canonical_raw = strip_inventory_metadata_summary(
        strip_trailing_llm_json(_usable_summary_text(canonical_narrative))
    )
    description_raw = strip_inventory_metadata_summary(_usable_summary_text(description))
    briefing_raw = _usable_summary_text(timeline_narrative_briefing)

    # Prefer dek; fall back to prose sanitize (strips **Storyline:** / **Main Narrative…**)
    # before briefing_lede, which can leave markdown markers.
    lede = (
        sanitize_reader_dek(lede_raw, title=title, max_length=400)
        or sanitize_reader_prose(lede_raw, title=title, max_length=400)
        or sanitize_briefing_lede(lede_raw, max_length=400)
    )

    def _cap_summary(text: str) -> str:
        if len(text) > 12000:
            return text[:11980].rstrip() + "\n…"
        return text

    def _developments_blob(doc: dict[str, Any]) -> str:
        for key in ("developments", "what"):
            raw = doc.get(key)
            if isinstance(raw, list):
                parts = [str(x).strip() for x in raw if str(x).strip()]
                if parts:
                    return "\n".join(f"- {p}" for p in parts[:6])
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    # Durable package/desk projection: prefer composed editorial over thin seeds.
    try:
        from services.editorial_projection_service import QUALITY_DOCUMENT_STATUSES

        quality_status = str(document_status or "") in QUALITY_DOCUMENT_STATUSES
    except Exception:
        quality_status = str(document_status or "") in (
            "package_projected",
            "desk_promoted",
            "refined",
            "rag_analyzed",
            "draft",
        )
    durable_brief = ""
    if quality_status and (lede_raw or analysis_raw):
        parts = [
            p
            for p in (
                sanitize_reader_prose(lede_raw, title=title, max_length=2000),
                sanitize_reader_prose(analysis_raw, title=title, max_length=8000),
                sanitize_reader_prose(
                    _developments_blob(ed), title=title, max_length=2000
                ),
            )
            if p
        ]
        durable_brief = _cap_summary("\n\n".join(parts))

    # Prefer desk walkthrough; never promote ML inventory (Story Overview counts).
    # When neither is a desk walkthrough, prefer the longer article-grounded prose
    # (avoids short hallucinated canonical beating rebuilt master excerpts).
    summary = ""
    if durable_brief and not is_desk_walkthrough(canonical_raw):
        summary = durable_brief
    elif is_desk_walkthrough(canonical_raw):
        summary = _cap_summary(canonical_raw)
    elif is_desk_walkthrough(master_raw):
        summary = _cap_summary(master_raw)
    else:
        candidates: list[str] = []
        for blob in (
            durable_brief,
            master_raw,
            canonical_raw,
            description_raw,
            analysis_raw,
            lede_raw,
            briefing_raw,
        ):
            if not blob or is_inventory_metadata_summary(blob):
                continue
            if is_multi_topic_excerpt_mash(blob):
                continue
            candidates.append(blob)
        if candidates:
            best = max(candidates, key=len)
            if is_desk_walkthrough(best) or (
                "## " in best and len(best) > 800 and not is_inventory_metadata_summary(best)
            ):
                summary = _cap_summary(best)
            elif len(best) >= 500:
                summary = _cap_summary(best)
            else:
                summary = sanitize_reader_dek(
                    best, title=title, max_length=900
                ) or sanitize_briefing_lede(best, max_length=900) or best
            if summary.lstrip().startswith("```"):
                summary = strip_llm_wrapping_artifacts(summary, max_length=12000) or summary
    # Last resort: grounded excerpts — but never stitch unrelated headlines into one "story"
    if not summary or is_inventory_metadata_summary(summary):
        grounded = _article_grounded_summary(citations, title=title)
        if grounded and not is_multi_topic_excerpt_mash(grounded):
            summary = grounded
        else:
            summary = ""
    if summary and is_multi_topic_excerpt_mash(summary):
        summary = ""
    summary = strip_trailing_llm_json(strip_inventory_metadata_summary(summary or ""))

    # Flag kitchen-sink bags so the UI can avoid presenting them as one arc
    try:
        from services.storyline_coherence_guardrails import title_looks_mega_bag
        from services.vault_quality_gates import expansion_coherence_ok

        mega_bag = bool(is_mega_storyline) or title_looks_mega_bag(title or "")
        if not mega_bag and citations:
            member_titles = [
                str(c.get("title") or "")
                for c in citations
                if isinstance(c, dict) and c.get("title")
            ]
            ok_coh, _reason = expansion_coherence_ok(
                title=title or "",
                body=(summary or durable_brief or title or "")[:4000],
                member_titles=member_titles,
                article_count=len(member_titles) or article_count,
            )
            if not ok_coh and "magnet_membership" in (_reason or ""):
                mega_bag = True
    except Exception:
        mega_bag = bool(is_mega_storyline)
    if mega_bag:
        summary = (
            "This listing mixed unrelated coverage under one title and is flagged "
            "for split — use the citations below by topic rather than reading this "
            "as a single story."
        )
    else:
        # Reader Summary is often plain-text (not ReactMarkdown) — strip MD templates.
        if summary:
            cleaned_summary = sanitize_reader_prose(
                summary, title=title, max_length=12000
            )
            if cleaned_summary:
                summary = cleaned_summary
            else:
                summary = summary.replace("**", "").replace("__", "")
        if durable_brief:
            durable_brief = (
                sanitize_reader_prose(durable_brief, title=title, max_length=12000)
                or durable_brief.replace("**", "").replace("__", "")
            )

    dossier_tree = _build_dossier_tree(entities, relationships)

    vault_pack = None
    try:
        pack_ids = [
            int(e["id"])
            for e in entities
            if isinstance(e.get("id"), int)
        ][:8]
        if pack_ids:
            from .vault_context_pack import build_vault_context_pack

            vault_pack = build_vault_context_pack(
                domain_key=domain, entity_ids=pack_ids, hops=2, max_notes=8
            )
    except Exception:
        vault_pack = None

    vault_expansion = None
    try:
        from services.vault_notes_registry_service import get_expansion_for_storyline

        exp = get_expansion_for_storyline(domain, sid)
        if exp and (exp.get("body_md") or exp.get("summary_md")):
            from services.article_context_pull_service import reader_brief_from_expansion

            brief = reader_brief_from_expansion(exp)
            vault_expansion = {
                "title": exp.get("title"),
                "vault_path": exp.get("vault_path"),
                "body_md": brief,
                "summary_md": None,
                "updated_at": exp.get("note_updated_at") or exp.get("updated_at"),
                "source_article_id": (exp.get("metadata") or {}).get(
                    "source_article_id"
                ),
            }
    except Exception:
        vault_expansion = None

    # F8: surface other storyline homes for multi-linked articles (exclusive bag UX).
    # Prefer EEL article ids when assembly is on; bag only as fallback.
    also_in: list[dict[str, Any]] = []
    try:
        article_ids = [int(c["id"]) for c in citations if c.get("id") is not None][:40]
        if article_ids:
            with get_ui_db_connection_context() as conn2:
                with conn2.cursor() as cur2:
                    use_eel_also = False
                    try:
                        from shared.episode_attach_gate import episode_container_assembly_enabled

                        use_eel_also = bool(episode_container_assembly_enabled())
                    except Exception:
                        use_eel_also = False
                    if use_eel_also:
                        cur2.execute(
                            f"""
                            SELECT a.id, a.title, s.id, s.title, COALESCE(s.article_count, 0)
                            FROM intelligence.event_episode_links eel
                            JOIN public.chronological_events ce ON ce.id = eel.event_id
                            JOIN {schema}.articles a ON a.id = ce.source_article_id
                            JOIN {schema}.storylines s ON s.id = eel.episode_id
                            WHERE ce.source_article_id = ANY(%s)
                              AND eel.domain_key = %s
                              AND eel.episode_id <> %s
                              AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                              AND COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
                            ORDER BY COALESCE(s.article_count, 0) DESC, s.id
                            LIMIT 24
                            """,
                            (article_ids, domain, sid),
                        )
                    else:
                        cur2.execute(
                            f"""
                            SELECT a.id, a.title, s.id, s.title, COALESCE(s.article_count, 0)
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.articles a ON a.id = sa.article_id
                            JOIN {schema}.storylines s ON s.id = sa.storyline_id
                            WHERE sa.article_id = ANY(%s)
                              AND sa.storyline_id <> %s
                              AND COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
                            ORDER BY COALESCE(s.article_count, 0) DESC, s.id
                            LIMIT 24
                            """,
                            (article_ids, sid),
                        )
                    seen_homes: set[int] = set()
                    for aid, atitle, osid, otitle, oac in cur2.fetchall() or []:
                        oid = int(osid)
                        if oid in seen_homes:
                            continue
                        seen_homes.add(oid)
                        also_in.append(
                            {
                                "article_id": int(aid),
                                "article_title": atitle,
                                "domain": domain,
                                "storyline_id": oid,
                                "title": otitle,
                                "article_count": int(oac or 0),
                                "href": f"/storylines/{domain}/{oid}",
                            }
                        )
                        if len(also_in) >= 12:
                            break
    except Exception:
        also_in = []

    # Reader brief preference without Pull: vault expansion → durable → summary.
    # UI overlays Pull as brief_source=pull when a living context pull is present.
    expansion_text = ""
    if isinstance(vault_expansion, dict):
        expansion_text = str(
            vault_expansion.get("body_md") or vault_expansion.get("summary_md") or ""
        ).strip()
    if expansion_text:
        brief_source = "vault_expansion"
    elif durable_brief:
        brief_source = "durable"
    elif (summary or "").strip():
        brief_source = "summary"
    else:
        brief_source = "none"

    ed_out: dict[str, Any] = dict(editorial) if isinstance(editorial, dict) else {}
    for _ek in ("lede", "analysis", "what"):
        _ev = ed_out.get(_ek)
        if isinstance(_ev, str) and _ev.strip():
            ed_out[_ek] = (
                sanitize_reader_prose(_ev, title=title, max_length=8000)
                or _ev.replace("**", "").replace("__", "")
            )
        elif isinstance(_ev, list):
            ed_out[_ek] = [
                sanitize_reader_prose(str(x), title=title, max_length=400)
                or str(x).replace("**", "")
                for x in _ev
                if str(x).strip()
            ]

    situation_hub = None
    try:
        from services.vault_cluster_hub_service import storyline_ids_indexed_by_hubs

        hub_map = storyline_ids_indexed_by_hubs(domain)
        stubs = hub_map.get(int(sid)) or []
        if stubs:
            situation_hub = stubs[0]
    except Exception:
        situation_hub = None

    tn = timeline_narrative_chronological
    if isinstance(tn, str) and tn.strip():
        tn = sanitize_reader_prose(tn, title=title, max_length=4000) or tn

    return {
        "domain": domain,
        "storyline_id": sid,
        "title": title,
        "status": status,
        "summary": summary,
        "lede": lede,
        "durable_brief": durable_brief or None,
        "brief_source": brief_source,
        "editorial_document": ed_out,
        "background_information": background_information,
        "timeline_narrative": tn,
        "situation_hub": situation_hub,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "last_refinement": last_refinement.isoformat() if last_refinement else None,
        "article_count": len(citations) if citations else article_count,
        "quality_score": float(quality_score) if quality_score is not None else None,
        "is_mega_storyline": bool(is_mega_storyline) or mega_bag,
        "document_version": document_version,
        "document_status": document_status,
        "timeline": timeline,
        "citations": [
            {k: v for k, v in c.items() if k != "content"} for c in citations
        ],
        "also_in": also_in,
        "dossier_rail": {
            "entities": entities,
            "tree": dossier_tree,
            "hierarchy": hierarchy,
        },
        "vault_context_pack": vault_pack,
        "vault_expansion": vault_expansion,
    }

=== vault_context_pack.py ===
"""
Canned research context packs from vault notes + mirrored links + geo parents.

Given entity IDs (or titles), expand 1–2 hops via vault_note_links and
geo_parent_entity_id, then return tags, linked paths, and significance excerpts
for article summary / editorial consumers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services.vault_bridge_service import _FRONTMATTER_RE, vault_root
from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    AUTO_SIGNIFICANCE_END,
    AUTO_SIGNIFICANCE_START,
    DEFAULT_PACK_HOPS,
    DEFAULT_PACK_MAX_NOTES,
)

logger = logging.getLogger(__name__)

_SIG_RE = re.compile(
    re.escape(AUTO_SIGNIFICANCE_START) + r"(.*?)" + re.escape(AUTO_SIGNIFICANCE_END),
    re.DOTALL,
)


def _read_significance(vault_path: str, *, max_chars: int = 900) -> str | None:
    path = vault_root() / vault_path
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _SIG_RE.search(text)
    if m:
        return (m.group(1) or "").strip()[:max_chars]
    # Fallback: first non-frontmatter paragraph
    body = _FRONTMATTER_RE.sub("", text, count=1).lstrip()
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#") or not line or line.startswith("<!--"):
            continue
        return line[:max_chars]
    return None


def _seed_rows_for_entities(
    domain_key: str, entity_ids: list[int]
) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path, title, note_type, object_id, tags,
                       geo_parent_entity_id, place_kind, note_status, lifecycle
                FROM intelligence.vault_notes
                WHERE domain_key = %s
                  AND note_type = 'entity'
                  AND object_id = ANY(%s)
                  AND COALESCE(lifecycle, 'stub') NOT IN ('index', 'archived')
                """,
                (domain_key, list(entity_ids)),
            )
            rows = cur.fetchall()
    return [
        {
            "vault_path": r[0],
            "title": r[1],
            "note_type": r[2],
            "object_id": r[3],
            "tags": list(r[4] or []),
            "geo_parent_entity_id": r[5],
            "place_kind": r[6],
            "note_status": r[7],
            "lifecycle": r[8],
        }
        for r in rows
    ]


def _expand_hops(
    domain_key: str,
    seed_paths: list[str],
    *,
    hops: int,
    max_notes: int,
) -> list[str]:
    seen: set[str] = set(seed_paths)
    frontier = list(seed_paths)
    ordered = list(seed_paths)
    for _ in range(max(0, hops)):
        if not frontier or len(ordered) >= max_notes:
            break
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT COALESCE(dst_vault_path, '')
                    FROM intelligence.vault_note_links
                    WHERE domain_key = %s
                      AND src_vault_path = ANY(%s)
                      AND link_kind = 'wikilink'
                      AND dst_vault_path IS NOT NULL
                    """,
                    (domain_key, frontier),
                )
                next_paths = [r[0] for r in cur.fetchall() if r[0]]
                # Also follow geo parents of seed entities
                cur.execute(
                    """
                    SELECT vn2.vault_path
                    FROM intelligence.vault_notes vn
                    JOIN intelligence.vault_notes vn2
                      ON vn2.domain_key = vn.domain_key
                     AND vn2.note_type = 'entity'
                     AND vn2.object_id = vn.geo_parent_entity_id
                    WHERE vn.vault_path = ANY(%s)
                      AND vn.geo_parent_entity_id IS NOT NULL
                    """,
                    (frontier,),
                )
                next_paths.extend(r[0] for r in cur.fetchall() if r[0])
        # Prefer grounding wiki (timelines/stories/entities/connections) over
        # clipping volume so hand-curated ledgers stay in the pack window.
        def _hop_rank(p: str) -> tuple[int, str]:
            if p.startswith("40_Reference/timelines/"):
                return (0, p)
            if p.startswith("30_Stories/") and "/expansions/" not in p:
                return (1, p)
            if p.startswith("40_Reference/entities/") or p.startswith(
                "25_Connections/"
            ):
                return (2, p)
            if p.startswith("30_Stories/expansions/"):
                return (3, p)
            if p.startswith("20_Clippings/") or p.startswith("50_Science/20_Clippings/"):
                return (5, p)
            return (4, p)

        nxt: list[str] = []
        for p in sorted(next_paths, key=_hop_rank):
            if p in seen:
                continue
            seen.add(p)
            ordered.append(p)
            nxt.append(p)
            if len(ordered) >= max_notes:
                break
        frontier = nxt
    return ordered[:max_notes]


def _load_note_meta(paths: list[str]) -> dict[str, dict[str, Any]]:
    if not paths:
        return {}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path, title, note_type, object_id, tags,
                       geo_parent_entity_id, place_kind, note_status, lifecycle,
                       domain_key
                FROM intelligence.vault_notes
                WHERE vault_path = ANY(%s)
                """,
                (paths,),
            )
            rows = cur.fetchall()
    return {
        r[0]: {
            "vault_path": r[0],
            "title": r[1],
            "note_type": r[2],
            "object_id": r[3],
            "tags": list(r[4] or []),
            "geo_parent_entity_id": r[5],
            "place_kind": r[6],
            "note_status": r[7],
            "lifecycle": r[8],
            "domain_key": r[9],
        }
        for r in rows
    }


def build_vault_context_pack(
    *,
    domain_key: str = "politics",
    entity_ids: list[int] | None = None,
    titles: list[str] | None = None,
    hops: int = DEFAULT_PACK_HOPS,
    max_notes: int = DEFAULT_PACK_MAX_NOTES,
) -> dict[str, Any]:
    """Assemble canned background for summarizers."""
    seeds = _seed_rows_for_entities(domain_key, entity_ids or [])
    if titles:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for t in titles:
                    cur.execute(
                        """
                        SELECT vault_path, title, note_type, object_id, tags,
                               geo_parent_entity_id, place_kind, note_status, lifecycle
                        FROM intelligence.vault_notes
                        WHERE domain_key = %s AND lower(title) = lower(%s)
                        LIMIT 1
                        """,
                        (domain_key, t),
                    )
                    row = cur.fetchone()
                    if row:
                        seeds.append(
                            {
                                "vault_path": row[0],
                                "title": row[1],
                                "note_type": row[2],
                                "object_id": row[3],
                                "tags": list(row[4] or []),
                                "geo_parent_entity_id": row[5],
                                "place_kind": row[6],
                                "note_status": row[7],
                                "lifecycle": row[8],
                            }
                        )

    seed_paths = [s["vault_path"] for s in seeds if s.get("vault_path")]
    if not seed_paths:
        return {
            "ok": True,
            "domain_key": domain_key,
            "seeds": [],
            "notes": [],
            "actors": [],
            "message": "No vault notes registered for inputs.",
        }

    expanded = _expand_hops(
        domain_key, seed_paths, hops=hops, max_notes=max_notes
    )
    meta = _load_note_meta(expanded)

    notes_out: list[dict[str, Any]] = []
    actors: list[str] = []
    all_tags: list[str] = []
    for path in expanded:
        info = meta.get(path) or {"vault_path": path, "title": path}
        # Hide index/archived stubs from reader context packs (F7).
        if str(info.get("lifecycle") or "") in ("index", "archived"):
            continue
        sig = _read_significance(path)
        try:
            from shared.llm_text_sanitize import sanitize_reader_prose

            sig = sanitize_reader_prose(
                sig,
                title=str(info.get("title") or ""),
                max_length=400,
            )
        except Exception:
            pass
        entry = {
            **info,
            "significance_excerpt": sig,
            "is_seed": path in seed_paths,
        }
        notes_out.append(entry)
        if info.get("title"):
            actors.append(str(info["title"]))
        all_tags.extend(info.get("tags") or [])

    # Dedupe tags preserving order
    seen_t: set[str] = set()
    tags_unique: list[str] = []
    for t in all_tags:
        k = str(t).lower()
        if k in seen_t:
            continue
        seen_t.add(k)
        tags_unique.append(str(t))

    return {
        "ok": True,
        "domain_key": domain_key,
        "hops": hops,
        "seeds": seeds,
        "notes": notes_out,
        "actors": actors[:max_notes],
        "tags": tags_unique[:40],
        "note_count": len(notes_out),
    }


def render_vault_context_pack_for_llm(
    pack: dict[str, Any] | None, *, max_chars: int = 6000
) -> str:
    """Compact living-vault background for narrative / executive-summary prompts."""
    if not pack or not isinstance(pack, dict):
        return ""
    notes = pack.get("notes") if isinstance(pack.get("notes"), list) else []
    if not notes:
        return ""
    lines: list[str] = [
        "Living vault background (Obsidian knowledge notes — durable context, not new facts):"
    ]
    for n in notes:
        if not isinstance(n, dict):
            continue
        title = (n.get("title") or n.get("vault_path") or "Note").strip()
        tags = n.get("tags") if isinstance(n.get("tags"), list) else []
        tag_s = ", ".join(str(t) for t in tags[:8] if t)
        seed = " [seed]" if n.get("is_seed") else ""
        lines.append(f"- {title}{seed}" + (f" ({tag_s})" if tag_s else ""))
        sig = (n.get("significance_excerpt") or "").strip()
        if sig:
            lines.append(f"  Significance: {sig[:700]}")
    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        return text[: max_chars - 20].rstrip() + "\n…"
    return text


def build_vault_pack_for_entity_ids(
    domain_key: str,
    entity_ids: list[int],
    *,
    hops: int = DEFAULT_PACK_HOPS,
    max_notes: int = DEFAULT_PACK_MAX_NOTES,
) -> dict[str, Any]:
    ids = [int(x) for x in entity_ids if isinstance(x, int) or str(x).isdigit()]
    if not ids:
        return {
            "ok": True,
            "domain_key": domain_key,
            "seeds": [],
            "notes": [],
            "actors": [],
            "message": "No entity ids",
        }
    return build_vault_context_pack(
        domain_key=domain_key,
        entity_ids=ids[:24],
        hops=hops,
        max_notes=max_notes,
    )

=== vault_note_read.py ===
"""
Reader helpers: structure headline + vault note body with async-safe status.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.vault_bridge_service import vault_root
from services.vault_notes_registry_service import get_vault_note, get_vault_note_by_path
from shared.vault_note_contract import entity_vault_rel_path


def _read_note_body(vault_path: str | None) -> str | None:
    if not vault_path:
        return None
    path = vault_root() / vault_path
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def build_entity_headline(
    *,
    domain_key: str,
    entity_id: int,
    name: str | None = None,
    mention_count: int | None = None,
) -> dict[str, Any]:
    """
    NI headline from Postgres structure — never blocks on vault LLM.
    note_status: structure_only | note_pending | note_ready
    """
    note = get_vault_note(domain_key=domain_key, note_type="entity", object_id=entity_id)
    # Index/archived stubs are not reader-facing notes (F7).
    if note and str(note.get("lifecycle") or "") in ("index", "archived"):
        note = None
    title = (note or {}).get("title") or name or f"Entity {entity_id}"
    if not note:
        status = "structure_only"
        path = entity_vault_rel_path(title) if name else None
    else:
        status = note.get("note_status") or "note_pending"
        path = note.get("vault_path")
    headline = title
    if mention_count and mention_count >= 100:
        dek = f"Living subject in {domain_key} · {mention_count} mentions"
    elif status == "note_ready":
        dek = "Vault explainer ready"
    elif status == "note_pending":
        dek = "Updating vault note…"
    else:
        dek = "Structure only — note not yet seeded"

    return {
        "domain_key": domain_key,
        "entity_id": entity_id,
        "headline": headline,
        "dek": dek,
        "note_status": status,
        "lifecycle": (note or {}).get("lifecycle") or "absent",
        "vault_path": path,
        "note_updated_at": (note or {}).get("note_updated_at"),
        "mention_count": mention_count or (note or {}).get("mention_count"),
    }


def build_vault_note_payload(
    *,
    domain_key: str,
    note_type: str,
    object_id: int,
    object_id_secondary: int | None = None,
) -> dict[str, Any]:
    note = get_vault_note(
        domain_key=domain_key,
        note_type=note_type,
        object_id=object_id,
        object_id_secondary=object_id_secondary,
    )
    if note and str(note.get("lifecycle") or "") in ("index", "archived"):
        return {
            "ok": True,
            "note_status": "structure_only",
            "lifecycle": note.get("lifecycle"),
            "title": note.get("title"),
            "body": None,
            "updating": False,
            "message": "Index card only — not shown as a living note.",
        }
    if not note:
        return {
            "ok": True,
            "note_status": "structure_only",
            "lifecycle": "absent",
            "title": None,
            "body": None,
            "updating": False,
            "message": "No vault note registered yet.",
        }
    status = note.get("note_status") or "note_pending"
    body = _read_note_body(note.get("vault_path")) if status == "note_ready" else None
    updating = status == "note_pending" or (status == "note_ready" and body is None)
    return {
        "ok": True,
        "note_status": status,
        "lifecycle": note.get("lifecycle"),
        "title": note.get("title"),
        "vault_path": note.get("vault_path"),
        "body": body,
        "updating": updating,
        "note_updated_at": note.get("note_updated_at"),
        "rag_indexed_at": note.get("rag_indexed_at"),
        "tags": note.get("tags") or [],
        "message": "Updating…" if updating and not body else None,
    }


def build_vault_note_by_path(vault_path: str) -> dict[str, Any]:
    note = get_vault_note_by_path(vault_path)
    body = _read_note_body(vault_path)
    if not note and not body:
        return {"ok": False, "error": "not_found", "note_status": "absent"}
    status = (note or {}).get("note_status") or ("note_ready" if body else "structure_only")
    return {
        "ok": True,
        "note_status": status,
        "lifecycle": (note or {}).get("lifecycle"),
        "title": (note or {}).get("title"),
        "vault_path": vault_path,
        "body": body,
        "updating": status == "note_pending",
        "domain_key": (note or {}).get("domain_key"),
        "note_type": (note or {}).get("note_type"),
        "object_id": (note or {}).get("object_id"),
    }
