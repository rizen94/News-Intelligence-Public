"""Vault quality gates — readable/reliable notes only.

Policy (see docs/VAULT_NOTES_AND_PULL_CONTEXT.md):
  - Entity markdown only for followed / hub-seed / hot entities (or existing living files).
  - Expansions must pass title↔body coherence + membership sanity before write.
  - Daily briefings require cited slate members; skip rather than invent.
  - Reject HTML / tag-soup titles for clippings and cluster hubs.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_JUNK_TITLE_RE = re.compile(
    r"(class\s*=|rrssb|</?[a-z]{1,12}\b|&nbsp;|span>|</a>|</li>|<b>|Sponsors</b>)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)


def entity_note_min_hits() -> int:
    try:
        return max(1, int(os.getenv("NI_VAULT_ENTITY_NOTE_MIN_HITS", "3")))
    except ValueError:
        return 3


def entity_note_window_days() -> int:
    try:
        return max(1, int(os.getenv("NI_VAULT_ENTITY_NOTE_WINDOW_DAYS", "14")))
    except ValueError:
        return 14


def expansion_coherence_gate_enabled() -> bool:
    raw = (os.getenv("NI_VAULT_EXPANSION_COHERENCE_GATE", "true") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def briefing_require_citations_enabled() -> bool:
    raw = (os.getenv("NI_VAULT_BRIEFING_REQUIRE_CITATIONS", "true") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_junk_title(title: str | None) -> bool:
    """True when title looks like HTML soup or unusable for a human note."""
    t = (title or "").strip()
    if not t or len(t) < 3:
        return True
    if len(t) > 220:
        return True
    if _HTML_TAG_RE.search(t) or _JUNK_TITLE_RE.search(t):
        return True
    # Mostly punctuation / leftover markup crumbs
    letters = sum(1 for c in t if c.isalpha())
    if letters < 4:
        return True
    return False


def sanitize_vault_prose(text: str | None, *, max_length: int = 12000) -> str:
    from shared.llm_text_sanitize import html_to_visible_text, strip_trailing_llm_json

    cleaned = strip_trailing_llm_json(text)
    return (html_to_visible_text(cleaned, max_length=max_length) or "").strip()


def _tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "amid",
        "after",
        "into",
        "over",
        "under",
        "says",
        "said",
        "will",
        "have",
        "has",
        "are",
        "was",
        "were",
        "been",
        "new",
        "year",
        "years",
    }
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "") if m.group(0).lower() not in stop}


def title_body_token_overlap(title: str, body: str) -> float:
    """Jaccard-ish overlap of content tokens (0–1)."""
    a = _tokens(title)
    b = _tokens(body)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / float(max(1, len(a)))


def expansion_coherence_ok(
    *,
    title: str,
    body: str,
    member_titles: list[str] | None = None,
    article_count: int | None = None,
) -> tuple[bool, str]:
    """Fail-closed coherence for morning expansions."""
    if not expansion_coherence_gate_enabled():
        return True, "gate_disabled"
    clean_title = sanitize_vault_prose(title, max_length=300)
    clean_body = sanitize_vault_prose(body, max_length=12000)
    if is_junk_title(clean_title):
        return False, "junk_title"
    if len(clean_body) < 120:
        return False, "body_too_short"
    # Title tokens should appear in body (avoid mismatched RAG dump)
    overlap = title_body_token_overlap(clean_title, clean_body)
    if overlap < 0.15 and len(_tokens(clean_title)) >= 3:
        return False, f"title_body_overlap:{overlap:.2f}"
    # Magnet / kitchen-sink bags: members whose titles barely share tokens
    # with the storyline title. Small discovery seeds (3–11 articles) were
    # slipping through when the gate only ran at article_count >= 12.
    # Require ≥2 shared tokens per hit so a lone "Musk"/"Trump" bridge
    # does not count ICE airports as on-title for a SpaceX earnings bag.
    members = [m for m in (member_titles or []) if m]
    n_members = len(members)
    ac = int(article_count) if article_count is not None else n_members
    if members and max(ac, n_members) >= 3:
        hits = 0
        tset = _tokens(clean_title)
        for mt in members[:40]:
            mset = _tokens(mt)
            if tset and mset and len(tset & mset) >= 2:
                hits += 1
        ratio = hits / float(max(1, min(n_members, 40)))
        # Stricter for tiny bags: one SpaceX hit + ICE/gas noise must fail.
        min_ratio = 0.5 if max(ac, n_members) < 12 else 0.25
        if ratio < min_ratio:
            return False, f"magnet_membership:{ratio:.2f}"
    return True, "ok"


def briefing_citations_ok(
    body: str,
    *,
    expansions: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Require briefing body to reference slate storyline ids or titles."""
    if not briefing_require_citations_enabled():
        return True, "gate_disabled"
    text = sanitize_vault_prose(body, max_length=14000)
    if len(text) < 40:
        return False, "empty_body"
    if not expansions:
        return False, "empty_slate"
    cited = 0
    for ex in expansions:
        sid = ex.get("storyline_id")
        title = str(ex.get("title") or "")
        domain = str(ex.get("domain_key") or "")
        markers = []
        if sid is not None:
            markers.append(f"{domain}/{sid}")
            markers.append(str(sid))
        if title:
            # First meaningful chunk of title
            markers.append(title[:40])
        if any(m and m in text for m in markers):
            cited += 1
    if cited < 1:
        return False, "no_slate_citations"
    # Reject known hallucination patterns when slate was empty of science facts
    bad = ("CERN", "Great Barrier Reef", "previously undiscovered species of coral", "Gaia spacecraft")
    if any(b in text for b in bad) and cited < max(1, len(expansions) // 2):
        # Soft: only fail if few citations AND inventiveness markers
        if cited < 2:
            return False, "uncited_invention_markers"
    return True, f"cited:{cited}"


def expansions_for_briefing_day(briefing_day: str | None, *, limit: int = 40) -> list[dict[str, Any]]:
    """Load expansion notes for a briefing day (reader/write citation checks)."""
    day = (briefing_day or "").strip()[:10]
    if not day:
        return []
    try:
        from shared.database.connection import get_db_connection_context
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT domain_key, object_id, title
                    FROM intelligence.vault_notes
                    WHERE note_type = 'expansion'
                      AND COALESCE(body_md, summary_md, '') <> ''
                      AND (
                        (metadata->>'briefing_day') = %s
                        OR (metadata->>'window_end') = %s
                        OR note_updated_at::date = %s::date
                      )
                    ORDER BY note_updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (day, day, day, int(limit)),
                )
                for dk, oid, title in cur.fetchall() or []:
                    out.append(
                        {
                            "domain_key": dk,
                            "storyline_id": int(oid) if oid is not None else None,
                            "title": title,
                        }
                    )
    except Exception:
        return []
    return out


def daily_briefing_serve_allowed(
    body: str | None,
    *,
    briefing_day: str | None = None,
    expansions: list[dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """Reader/serve gate: do not surface uncited day cards when citations required."""
    if not briefing_require_citations_enabled():
        return True, "gate_disabled"
    exps = expansions
    if exps is None:
        exps = expansions_for_briefing_day(briefing_day)
    return briefing_citations_ok(body or "", expansions=exps)


def _entity_is_followed(canonical_entity_id: int) -> bool:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM intelligence.followed_items
                    WHERE status <> 'archived'
                      AND (
                        (object_kind IN ('entity', 'canonical_entity') AND object_id = %s)
                        OR (metadata->>'canonical_entity_id') = %s
                      )
                    LIMIT 1
                    """,
                    (int(canonical_entity_id), str(int(canonical_entity_id))),
                )
                return bool(cur.fetchone())
    except Exception as e:
        logger.debug("follow check failed: %s", e)
        return False


def _entity_is_hub_seed(canonical_entity_id: int) -> bool:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM intelligence.vault_notes
                    WHERE note_type = 'cluster'
                      AND COALESCE((metadata->>'hub')::boolean, false) = true
                      AND (
                        metadata->'seed_entity_ids' @> to_jsonb(%s::int)
                        OR metadata->'seed_entity_ids' @> %s::jsonb
                      )
                    LIMIT 1
                    """,
                    (int(canonical_entity_id), f"[{int(canonical_entity_id)}]"),
                )
                return bool(cur.fetchone())
    except Exception as e:
        logger.debug("hub seed check failed: %s", e)
        return False


def _entity_recent_article_hits(domain_key: str, canonical_entity_id: int) -> int:
    """Count distinct articles mentioning entity in the hot window."""
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import resolve_domain_schema

        schema = resolve_domain_schema(domain_key)
        days = entity_note_window_days()
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT ae.article_id)::int
                    FROM {schema}.article_entities ae
                    JOIN {schema}.articles a ON a.id = ae.article_id
                    WHERE ae.canonical_entity_id = %s
                      AND COALESCE(a.published_at, a.created_at, a.discovered_at)
                          >= NOW() - (%s || ' days')::interval
                    """,
                    (int(canonical_entity_id), str(days)),
                )
                row = cur.fetchone()
                return int(row[0] or 0) if row else 0
    except Exception as e:
        logger.debug("entity hit count failed: %s", e)
        return 0


def entity_md_write_allowed(
    *,
    domain_key: str,
    canonical_entity_id: int | None,
    existing_lifecycle: str | None = None,
    file_exists: bool = False,
) -> tuple[bool, str]:
    """
    Whether to create/update entity markdown on disk.

    Always allow updates to existing living notes. New files require
    followed / hub seed / hot (≥ min hits in window).
    """
    life = (existing_lifecycle or "").strip().lower()
    if file_exists and life in ("living", "frozen", "seeded"):
        return True, f"existing:{life or 'file'}"
    if file_exists and life in ("stub", "index", "absent", ""):
        # Existing stub: only promote/update if policy passes
        pass
    if canonical_entity_id is None or int(canonical_entity_id) <= 0:
        return False, "no_entity_id"
    eid = int(canonical_entity_id)
    if _entity_is_followed(eid):
        return True, "followed"
    if _entity_is_hub_seed(eid):
        return True, "hub_seed"
    hits = _entity_recent_article_hits(domain_key, eid)
    if hits >= entity_note_min_hits():
        return True, f"hot:{hits}"
    if file_exists:
        return False, f"stub_not_hot:{hits}"
    return False, f"no_md:{hits}"


def load_storyline_member_titles(domain_key: str, storyline_id: int, *, limit: int = 40) -> list[str]:
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import resolve_domain_schema

        schema = resolve_domain_schema(domain_key)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.title
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (int(storyline_id), int(limit)),
                )
                return [str(r[0] or "") for r in cur.fetchall()]
    except Exception as e:
        logger.debug("member titles load failed: %s", e)
        return []
