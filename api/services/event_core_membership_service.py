"""
Event-core membership — quality-type founding and typed TE evidence membership.

Quality type (cyclosporiasis is an *example*, not the scoreboard):
  - Distinctive identity (rare name / instrument ID / bounded episode)
  - Multi-article co-reference over time
  - Owns a megathread; must not absorb into geopolitics bags
  - Domain-agnostic facets; summaries use typed members

When EVENT_CORE_MEMBERSHIP_ENABLED is on:
  - Distinctive anchors mint/own a tracked_event before mega absorb
  - Silent storyline absorb is blocked when the article matches an owned or unowned rare anchor
    that does not belong to the target storyline's TE
  - SEI widening is skipped for event-core membership writes (I3)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)

MEMBERSHIP_TYPES = frozenset(
    {"same_event", "causal_link", "same_instrument", "actor_episode"}
)

# Seed *examples* of the quality type — not an exclusive allowlist / scoreboard.
# Cyclosporiasis illustrates the pattern; instrument IDs + morph patterns find peers.
QUALITY_TYPE_SEED_EXAMPLES: tuple[str, ...] = (
    "cyclosporiasis",
    "cyclospora",
    "hantavirus",
    "lettuce recall",
    "produce recall",
)
# Back-compat alias
DEFAULT_RARE_ANCHORS = QUALITY_TYPE_SEED_EXAMPLES

_COMMON_NEVER_DISTINCTIVE = frozenset(
    {
        "trump",
        "biden",
        "fda",
        "cdc",
        "who",
        "oil",
        "iran",
        "china",
        "outbreak",
        "epidemic",
        "pandemic",
        "war",
        "conflict",
        "foodborne",
        "food poisoning",
        "lettuce",
        "produce",
        "recall",
        "diagnosis",
        "prognosis",
        "tuberculosis",
        "coronavirus",
        "norovirus",
        "rotavirus",
        "adenovirus",
        "papillomavirus",
        "retrovirus",
        "herpesvirus",
        "endometriosis",
        "osteoporosis",
        "atherosclerosis",
        "cirrhosis",
        "fibrosis",
        "psychosis",
        "sclerosis",
        "necrosis",
        "apoptosis",
        "metamorphosis",
        "symbiosis",
    }
)

# High-precision instrument identifiers (bounded episode anchors).
_INSTRUMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(nct\d{8})\b", re.I), "trial_registration"),
    (re.compile(r"\b(\d{1,2}:\d{2}-(?:cv|cr)-\d+)\b", re.I), "docket"),
    (re.compile(r"\b(fda-\d{4}-[a-z]?\d+)\b", re.I), "fda_id"),
    (re.compile(r"\b(epa-[a-z]?\d{4,})\b", re.I), "epa_id"),
)

# Morphological rare-name peers of cyclosporiasis (disease/episode class).
_MORPH_IASIS = re.compile(r"\b([a-z]{6,}iasis)\b", re.I)
_MORPH_OSIS = re.compile(r"\b([a-z]{10,}osis)\b", re.I)
_MORPH_VIRUS = re.compile(r"\b([a-z]{5,}virus)\b", re.I)


def event_core_membership_enabled() -> bool:
    if env_bool("EVENT_CORE_MEMBERSHIP_ENABLED", False):
        return True
    try:
        from config.feature_registry import is_feature_enabled

        return bool(is_feature_enabled("event_core_membership", default=False))
    except Exception:
        return False


def rare_anchor_lexicon() -> list[str]:
    """Seed examples + distinctive domain keywords (still not the only founding path)."""
    out: list[str] = []
    seen: set[str] = set()
    for a in QUALITY_TYPE_SEED_EXAMPLES:
        key = a.strip().lower()
        if key and key not in seen and key not in _COMMON_NEVER_DISTINCTIVE:
            seen.add(key)
            out.append(key)
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config
        from shared.domain_registry import get_pipeline_active_domain_keys

        for dk in get_pipeline_active_domain_keys() or []:
            cfg = get_domain_synthesis_config(dk)
            narrative = getattr(cfg.storyline_development, "narrative", None)
            kws = list(getattr(narrative, "outbreak_keywords", None) or [])
            for raw in kws:
                key = str(raw or "").strip().lower()
                if (
                    not key
                    or key in seen
                    or key in _COMMON_NEVER_DISTINCTIVE
                    or len(key) < 5
                ):
                    continue
                # Broad class words never found megathreads alone
                if key in {"cdc", "fda", "who", "outbreak", "epidemic"}:
                    continue
                # Prefer multi-word or morph-rare single tokens from domain YAML
                if " " not in key and not (
                    key.endswith("iasis") or key.endswith("virus")
                ):
                    continue
                seen.add(key)
                out.append(key)
    except Exception as e:
        logger.debug("rare_anchor_lexicon domain keywords: %s", e)
    return out


def article_text_blob(article: dict[str, Any]) -> str:
    parts = [
        str(article.get("title") or ""),
        str(article.get("summary") or ""),
        str(article.get("content") or "")[:4000],
    ]
    return " ".join(parts).lower()


def _lexicon_hits(blob: str, lexicon: list[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for anchor in lexicon:
        if len(anchor) < 5:
            continue
        if " " in anchor:
            if anchor in blob:
                hits.append({"value": anchor, "kind": "seed_example"})
        else:
            if re.search(rf"(?<![a-z0-9]){re.escape(anchor)}(?![a-z0-9])", blob):
                hits.append({"value": anchor, "kind": "seed_example"})
    return hits


def _instrument_hits(blob: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for pat, kind in _INSTRUMENT_PATTERNS:
        for m in pat.finditer(blob):
            val = (m.group(1) or "").strip().lower()
            if val and val not in _COMMON_NEVER_DISTINCTIVE:
                hits.append({"value": val, "kind": kind})
    return hits


def _morph_rare_name_hits(blob: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for m in _MORPH_IASIS.finditer(blob):
        val = (m.group(1) or "").strip().lower()
        if val and val not in _COMMON_NEVER_DISTINCTIVE:
            hits.append({"value": val, "kind": "morph_iasis"})
    for m in _MORPH_OSIS.finditer(blob):
        val = (m.group(1) or "").strip().lower()
        if val and val not in _COMMON_NEVER_DISTINCTIVE:
            hits.append({"value": val, "kind": "morph_osis"})
    for m in _MORPH_VIRUS.finditer(blob):
        val = (m.group(1) or "").strip().lower()
        if val and val not in _COMMON_NEVER_DISTINCTIVE:
            hits.append({"value": val, "kind": "morph_virus"})
    return hits


def find_quality_anchors_in_text(
    text: str, lexicon: list[str] | None = None
) -> list[dict[str, str]]:
    """
    Return distinctive anchors with kinds for quality-type founding.
    Combines seed examples, instrument IDs, and morphological rare names.
    """
    blob = (text or "").lower()
    if not blob:
        return []
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for hit in (
        _lexicon_hits(blob, lexicon or rare_anchor_lexicon())
        + _instrument_hits(blob)
        + _morph_rare_name_hits(blob)
    ):
        val = hit["value"]
        if val in seen:
            continue
        seen.add(val)
        out.append(hit)
    return out


def find_rare_anchors_in_text(text: str, lexicon: list[str] | None = None) -> list[str]:
    """Values-only view of quality anchors (backward compatible)."""
    return [h["value"] for h in find_quality_anchors_in_text(text, lexicon=lexicon)]


def find_rare_anchors_in_article(
    article: dict[str, Any], lexicon: list[str] | None = None
) -> list[str]:
    return find_rare_anchors_in_text(article_text_blob(article), lexicon=lexicon)


def find_quality_anchors_in_article(
    article: dict[str, Any], lexicon: list[str] | None = None
) -> list[dict[str, str]]:
    return find_quality_anchors_in_text(article_text_blob(article), lexicon=lexicon)


def _get_conn():
    from shared.database.connection import get_db_connection

    return get_db_connection()


def find_tracked_event_owning_anchor(cur, anchor: str) -> int | None:
    """Return tracked_event_id that owns this anchor, if any."""
    a = (anchor or "").strip().lower()
    if not a:
        return None
    cur.execute(
        """
        SELECT id
        FROM intelligence.tracked_events
        WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements(COALESCE(anchors, '[]'::jsonb)) e
            WHERE lower(COALESCE(e->>'value', '')) = %s
        )
        OR lower(event_name) LIKE %s
        ORDER BY id
        LIMIT 1
        """,
        (a, f"%{a}%"),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def mint_tracked_event_for_anchor(
    cur,
    *,
    anchor: str,
    domain_key: str,
    event_name: str | None = None,
    geographic_scope: str | None = None,
    particulars: dict[str, Any] | None = None,
    kind: str = "rare_name",
) -> int:
    """Insert a TE owned by this quality-type anchor. Caller commits."""
    a = anchor.strip().lower()
    name = (event_name or f"{a.title()} (event-core)").strip()[:200]
    domains = [domain_key] if domain_key else []
    anchors = [{"value": a, "kind": kind or "rare_name", "owned": True}]
    cur.execute(
        """
        INSERT INTO intelligence.tracked_events
        (event_type, event_name, start_date, geographic_scope,
         key_participant_entity_ids, milestones, domain_keys,
         editorial_briefing, editorial_briefing_json,
         briefing_version, briefing_status,
         anchors, particulars, arc_state)
        VALUES (
            'disaster', %s, %s, %s,
            '[]', '[]', %s,
            NULL, NULL,
            1, 'draft',
            %s::jsonb, %s::jsonb, 'emerging'
        )
        RETURNING id
        """,
        (
            name,
            date.today(),
            geographic_scope,
            domains,
            json.dumps(anchors),
            json.dumps(particulars or {"primary_anchor": a}),
        ),
    )
    return int(cur.fetchone()[0])


def ensure_tracked_event_for_anchor(
    cur,
    *,
    anchor: str,
    domain_key: str,
    event_name: str | None = None,
    kind: str = "rare_name",
) -> tuple[int, bool]:
    """Return (tracked_event_id, created)."""
    existing = find_tracked_event_owning_anchor(cur, anchor)
    a = anchor.strip().lower()
    k = kind or "rare_name"
    if existing:
        # Ensure anchor object present
        cur.execute(
            """
            UPDATE intelligence.tracked_events
            SET anchors = CASE
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(COALESCE(anchors, '[]'::jsonb)) e
                    WHERE lower(COALESCE(e->>'value', '')) = %s
                ) THEN anchors
                ELSE COALESCE(anchors, '[]'::jsonb) || %s::jsonb
            END,
            domain_keys = (
                SELECT ARRAY(
                    SELECT DISTINCT unnest(
                        COALESCE(domain_keys, '{}'::text[]) || %s::text[]
                    )
                )
            ),
            updated_at = NOW()
            WHERE id = %s
            """,
            (
                a,
                json.dumps([{"value": a, "kind": k, "owned": True}]),
                [domain_key] if domain_key else [],
                existing,
            ),
        )
        return existing, False
    te_id = mint_tracked_event_for_anchor(
        cur, anchor=anchor, domain_key=domain_key, event_name=event_name, kind=k
    )
    return te_id, True


def add_event_article_membership(
    cur,
    *,
    tracked_event_id: int,
    domain_key: str,
    article_id: int,
    membership_type: str = "same_event",
    anchor_ref: str,
    facet: str | None = None,
    added_by: str = "event_core",
    grounds: dict[str, Any] | None = None,
) -> bool:
    """Insert typed TE membership. Returns True if a row was inserted."""
    mt = (membership_type or "same_event").strip()
    if mt not in MEMBERSHIP_TYPES:
        raise ValueError(f"inadmissible membership_type={membership_type!r}")
    facet_val = facet or _facet_for_domain(domain_key)
    cur.execute(
        """
        INSERT INTO intelligence.event_article_membership
        (tracked_event_id, domain_key, article_id, membership_type,
         anchor_ref, facet, added_by, grounds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (tracked_event_id, domain_key, article_id) DO NOTHING
        """,
        (
            tracked_event_id,
            domain_key,
            article_id,
            mt,
            (anchor_ref or "").strip().lower(),
            facet_val,
            added_by,
            json.dumps(grounds or {}),
        ),
    )
    return cur.rowcount > 0


def link_te_storyline_facet(
    cur,
    *,
    tracked_event_id: int,
    domain_key: str,
    storyline_id: int,
    facet: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO intelligence.tracked_event_storyline_facets
        (tracked_event_id, domain_key, storyline_id, facet)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tracked_event_id, domain_key, storyline_id) DO NOTHING
        """,
        (
            tracked_event_id,
            domain_key,
            storyline_id,
            facet or _facet_for_domain(domain_key),
        ),
    )


# Dominant storyline accepted only when it covers enough TE members; mega bags
# with thin overlap are treated as false-absorb and skipped (ensure projection).
_FACET_MIN_COVERAGE = 0.5
_FACET_MEGA_SIZE = 40
_FACET_MEGA_MIN_COVERAGE = 0.8


def _dominant_coverage_ok(
    *, n_overlap: int, n_members: int, storyline_size: int
) -> bool:
    if n_overlap <= 0 or n_members <= 0:
        return False
    ratio = n_overlap / float(n_members)
    if storyline_size >= _FACET_MEGA_SIZE and ratio < _FACET_MEGA_MIN_COVERAGE:
        return False
    return ratio >= _FACET_MIN_COVERAGE


def _ensure_facet_projection_storyline(
    cur,
    *,
    schema: str,
    domain_key: str,
    tracked_event_id: int,
    event_name: str,
    article_ids: list[int],
) -> tuple[int, bool]:
    """
    Idempotent Stories facet for a TE+domain: reuse storyline tagged with this
    TE in metadata, else mint one.

    Under episode_container_assembly, mint as container_index with **no** article
    membership (containers never own articles).
    """
    episode_mode = False
    try:
        from shared.episode_attach_gate import episode_container_assembly_enabled

        episode_mode = bool(episode_container_assembly_enabled())
    except Exception:
        pass

    cur.execute(
        f"""
        SELECT id FROM {schema}.storylines
        WHERE COALESCE(status, 'active') = 'active'
          AND COALESCE(metadata->>'event_core_te_id', '') = %s
        ORDER BY id ASC
        LIMIT 1
        """,
        (str(tracked_event_id),),
    )
    row = cur.fetchone()
    if row:
        sid = int(row[0])
        created = False
    else:
        title = (event_name or f"Tracked event {tracked_event_id}").strip()[:200]
        description = (
            f"Event-core facet projection ({domain_key}) for tracked_event {tracked_event_id}."
        )
        meta = json.dumps(
            {
                "source": "event_core_facet_projection",
                "event_core_te_id": tracked_event_id,
                "domain_key": domain_key,
                "as_container": episode_mode,
            }
        )
        cur.execute(
            f"""
            INSERT INTO {schema}.storylines
            (storyline_uuid, title, description, status, processing_status,
             ml_processing_status, article_count, total_articles, metadata,
             created_at, updated_at, story_kind, is_mega_storyline)
            VALUES (
                gen_random_uuid(), %s, %s, 'active', 'pending', 'pending',
                0, 0, %s::jsonb, NOW(), NOW(),
                %s, %s
            )
            RETURNING id
            """,
            (
                title,
                description,
                meta,
                "container_index" if episode_mode else None,
                bool(episode_mode),
            ),
        )
        sid = int(cur.fetchone()[0])
        created = True

    attached = 0
    if not episode_mode:
        from shared.membership_store import MembershipIntent, admit as membership_admit

        for aid in article_ids:
            ok, _reason = membership_admit(
                cur.connection,
                domain_key=domain_key,
                schema=schema,
                episode_id=int(sid),
                article_id=int(aid),
                intent=MembershipIntent.AUTOMATION,
                blend_score=0.95,
                added_by="event_core_facet",
            )
            if ok:
                attached += 1
    if attached or created:
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET article_count = (
                    SELECT COUNT(*) FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                ),
                total_articles = (
                    SELECT COUNT(*) FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                ),
                updated_at = NOW()
            WHERE id = %s
            """,
            (sid, sid, sid),
        )
    return sid, created


def link_facets_from_article_membership(
    conn=None,
    *,
    tracked_event_ids: list[int] | None = None,
    apply: bool = False,
    ensure_projections: bool = True,
) -> dict[str, Any]:
    """
    Bridge TE evidence → Stories facets.

    Per (tracked_event, domain_key):
      1. Prefer the active storyline holding the most member articles when
         coverage is adequate (≥50%; mega bags need ≥80% to avoid false absorb).
      2. Else (ensure_projections): mint/reuse a dedicated facet storyline,
         attach TE member articles, then link_te_storyline_facet.

    Conservative semantics (OPERATOR_ANSWERS / STORYLINE_CANONICAL_MODEL): one
    dominant facet storyline per TE+domain. Idempotent via UNIQUE + metadata tag.
    """
    from shared.domain_registry import resolve_domain_schema

    own_conn = conn is None
    if own_conn:
        conn = _get_conn()
    if not conn:
        return {"ok": False, "error": "no_db"}

    stats: dict[str, Any] = {
        "ok": True,
        "dry_run": not apply,
        "ensure_projections": ensure_projections,
        "te_domain_pairs_scanned": 0,
        "candidates": 0,
        "linked": 0,
        "already_present": 0,
        "projections_created": 0,
        "projections_reused": 0,
        "no_storyline": 0,
        "skipped_thin_mega": 0,
        "links": [],
    }
    try:
        with conn.cursor() as cur:
            if tracked_event_ids:
                cur.execute(
                    """
                    SELECT DISTINCT tracked_event_id, domain_key
                    FROM intelligence.event_article_membership
                    WHERE tracked_event_id = ANY(%s)
                    ORDER BY tracked_event_id, domain_key
                    """,
                    (list(tracked_event_ids),),
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT tracked_event_id, domain_key
                    FROM intelligence.event_article_membership
                    ORDER BY tracked_event_id, domain_key
                    """
                )
            pairs = [(int(r[0]), str(r[1])) for r in (cur.fetchall() or [])]
            for te_id, domain_key in pairs:
                stats["te_domain_pairs_scanned"] += 1
                schema = resolve_domain_schema(domain_key)
                facet_val = _facet_for_domain(domain_key)
                if apply:
                    cur.execute("SAVEPOINT facet_pair")
                try:
                    cur.execute(
                        """
                        SELECT event_name FROM intelligence.tracked_events
                        WHERE id = %s
                        """,
                        (te_id,),
                    )
                    en_row = cur.fetchone()
                    event_name = str((en_row and en_row[0]) or f"Tracked event {te_id}")

                    cur.execute(
                        """
                        SELECT article_id,
                               COALESCE(NULLIF(facet, ''), %s) AS facet
                        FROM intelligence.event_article_membership
                        WHERE tracked_event_id = %s AND domain_key = %s
                        """,
                        (facet_val, te_id, domain_key),
                    )
                    mem_rows = cur.fetchall() or []
                    article_ids = [int(r[0]) for r in mem_rows]
                    if mem_rows and mem_rows[0][1]:
                        facet_val = str(mem_rows[0][1])
                    n_members = len(article_ids)

                    cur.execute(
                        f"""
                        SELECT sa.storyline_id,
                               COUNT(*)::int AS n_overlap,
                               COALESCE(
                                   (SELECT COUNT(*)::int
                                    FROM {schema}.storyline_articles sa2
                                    WHERE sa2.storyline_id = sa.storyline_id),
                                   0
                               ) AS storyline_size
                        FROM intelligence.event_article_membership eam
                        JOIN {schema}.storyline_articles sa
                          ON sa.article_id = eam.article_id
                        JOIN {schema}.storylines s
                          ON s.id = sa.storyline_id
                         AND COALESCE(s.status, 'active') = 'active'
                        WHERE eam.tracked_event_id = %s
                          AND eam.domain_key = %s
                        GROUP BY sa.storyline_id
                        ORDER BY COUNT(*) DESC, sa.storyline_id ASC
                        LIMIT 1
                        """,
                        (te_id, domain_key),
                    )
                    dom = cur.fetchone()

                    storyline_id: int | None = None
                    n_overlap = 0
                    source = "dominant_overlap"
                    if dom:
                        cand_id = int(dom[0])
                        n_overlap = int(dom[1] or 0)
                        sl_size = int(dom[2] or 0)
                        if _dominant_coverage_ok(
                            n_overlap=n_overlap,
                            n_members=n_members,
                            storyline_size=sl_size,
                        ):
                            storyline_id = cand_id
                        else:
                            stats["skipped_thin_mega"] += 1

                    if storyline_id is None:
                        if not ensure_projections or not article_ids:
                            stats["no_storyline"] += 1
                            continue
                        source = "facet_projection"
                        if apply:
                            storyline_id, created = _ensure_facet_projection_storyline(
                                cur,
                                schema=schema,
                                domain_key=domain_key,
                                tracked_event_id=te_id,
                                event_name=event_name,
                                article_ids=article_ids,
                            )
                            if created:
                                stats["projections_created"] += 1
                            else:
                                stats["projections_reused"] += 1
                            n_overlap = n_members
                        else:
                            # Dry-run: would mint/reuse projection
                            stats["candidates"] += 1
                            stats["links"].append(
                                {
                                    "tracked_event_id": te_id,
                                    "domain_key": domain_key,
                                    "storyline_id": None,
                                    "facet": facet_val,
                                    "n_overlap": n_members,
                                    "source": source,
                                    "would_ensure_projection": True,
                                }
                            )
                            continue

                    stats["candidates"] += 1
                    link_info = {
                        "tracked_event_id": te_id,
                        "domain_key": domain_key,
                        "storyline_id": storyline_id,
                        "facet": facet_val,
                        "n_overlap": n_overlap,
                        "source": source,
                    }
                    stats["links"].append(link_info)
                    if not apply:
                        continue
                    cur.execute(
                        """
                        SELECT 1 FROM intelligence.tracked_event_storyline_facets
                        WHERE tracked_event_id = %s
                          AND domain_key = %s
                          AND storyline_id = %s
                        """,
                        (te_id, domain_key, storyline_id),
                    )
                    if cur.fetchone():
                        stats["already_present"] += 1
                        continue
                    link_te_storyline_facet(
                        cur,
                        tracked_event_id=te_id,
                        domain_key=domain_key,
                        storyline_id=int(storyline_id),
                        facet=facet_val,
                    )
                    stats["linked"] += 1
                    if apply:
                        cur.execute("RELEASE SAVEPOINT facet_pair")
                except Exception as e:
                    logger.warning(
                        "link_facets_from_article_membership %s te=%s: %s",
                        domain_key,
                        te_id,
                        e,
                    )
                    try:
                        if apply:
                            cur.execute("ROLLBACK TO SAVEPOINT facet_pair")
                        else:
                            conn.rollback()
                    except Exception:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    stats["no_storyline"] += 1
                    continue
            if apply:
                conn.commit()
            else:
                conn.rollback()
        return stats
    except Exception as e:
        logger.warning("link_facets_from_article_membership: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "error": str(e), **stats}
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _facet_for_domain(domain_key: str) -> str:
    return {
        "medicine": "clinical",
        "politics": "regulatory",
        "finance": "market",
        "legal": "legal",
        "artificial-intelligence": "research",
    }.get(domain_key or "", "primary")


def storyline_linked_tracked_event_ids(cur, domain_key: str, storyline_id: int) -> list[int]:
    ids: list[int] = []
    cur.execute(
        """
        SELECT tracked_event_id
        FROM intelligence.tracked_event_storyline_facets
        WHERE domain_key = %s AND storyline_id = %s
        """,
        (domain_key, storyline_id),
    )
    ids.extend(int(r[0]) for r in (cur.fetchall() or []))
    # Legacy soft link
    cur.execute(
        """
        SELECT id FROM intelligence.tracked_events
        WHERE storyline_id = %s
        """,
        (f"{domain_key}:{storyline_id}",),
    )
    ids.extend(int(r[0]) for r in (cur.fetchall() or []))
    return sorted(set(ids))


def should_block_mega_absorb(
    cur,
    *,
    domain_key: str,
    storyline_id: int,
    article: dict[str, Any],
) -> tuple[bool, str, list[str]]:
    """
    If article hits a rare anchor not owned by this storyline's TE(s), block absorb.
    Returns (block, reason, anchors_hit).
    """
    if not event_core_membership_enabled():
        return False, "", []
    anchors = find_rare_anchors_in_article(article)
    if not anchors:
        return False, "", []
    linked = set(storyline_linked_tracked_event_ids(cur, domain_key, storyline_id))
    for a in anchors:
        owner = find_tracked_event_owning_anchor(cur, a)
        if owner is None:
            # Unowned rare anchor — founding wins; do not absorb into incumbent mega
            return True, f"unowned_rare_anchor:{a}", anchors
        if owner not in linked:
            return True, f"anchor_owned_elsewhere:{a}:te={owner}", anchors
    return False, "", anchors


def found_and_attach_rare_anchors(
    cur,
    *,
    domain_key: str,
    article: dict[str, Any],
    storyline_id: int | None = None,
) -> dict[str, Any]:
    """
    Mint/ensure TE for each quality-type anchor in article; write typed membership.
    Optionally link a facet storyline. Does NOT widen SEI.
    """
    art_id = article.get("id")
    if art_id is None:
        return {"ok": False, "error": "no_article_id"}
    quality = find_quality_anchors_in_article(article)
    if not quality:
        return {"ok": False, "error": "no_rare_anchors"}
    created: list[int] = []
    attached: list[int] = []
    anchors = [h["value"] for h in quality]
    for hit in quality:
        a = hit["value"]
        kind = hit.get("kind") or "rare_name"
        if kind in {"trial_registration", "docket", "fda_id", "epa_id"}:
            event_name = f"{a.upper()} ({kind.replace('_', ' ')})"
            membership_type = "same_instrument"
        else:
            event_name = f"{a.title()} outbreak / episode"
            membership_type = "same_event"
        te_id, was_new = ensure_tracked_event_for_anchor(
            cur,
            anchor=a,
            domain_key=domain_key,
            event_name=event_name,
            kind=kind,
        )
        if was_new:
            created.append(te_id)
        inserted = add_event_article_membership(
            cur,
            tracked_event_id=te_id,
            domain_key=domain_key,
            article_id=int(art_id),
            membership_type=membership_type,
            anchor_ref=a,
            facet=_facet_for_domain(domain_key),
            added_by="event_core_founding",
            grounds={
                "anchor": a,
                "kind": kind,
                "article_title": (article.get("title") or "")[:200],
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if inserted:
            attached.append(te_id)
        if storyline_id is not None:
            link_te_storyline_facet(
                cur,
                tracked_event_id=te_id,
                domain_key=domain_key,
                storyline_id=int(storyline_id),
            )
    return {
        "ok": True,
        "anchors": anchors,
        "quality_anchors": quality,
        "created_te_ids": created,
        "attached_te_ids": attached,
        "article_id": int(art_id),
    }


def list_typed_members_for_tracked_event(
    cur, tracked_event_id: int, *, limit: int = 100
) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT tracked_event_id, domain_key, article_id, membership_type,
               anchor_ref, facet, added_by, grounds, created_at
        FROM intelligence.event_article_membership
        WHERE tracked_event_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (tracked_event_id, limit),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in (cur.fetchall() or [])]


def run_rare_anchor_founding_scan(
    domain_key: str,
    *,
    lookback_hours: int = 168,
    limit: int = 80,
) -> dict[str, Any]:
    """
    Scan recent domain articles for rare anchors; mint/attach TE membership.
    Forward path for assembly when EVENT_CORE_MEMBERSHIP_ENABLED.
    """
    if not event_core_membership_enabled():
        return {"skipped": True, "reason": "flag_off"}
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    lexicon = rare_anchor_lexicon()
    conn = _get_conn()
    if not conn:
        return {"ok": False, "error": "no_db"}
    scanned = 0
    founded = 0
    attached_rows = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, summary, left(COALESCE(content, ''), 4000) AS content
                FROM {schema}.articles
                WHERE COALESCE(published_at, created_at) >= NOW() - (%s || ' hours')::interval
                ORDER BY COALESCE(published_at, created_at) DESC
                LIMIT %s
                """,
                (int(lookback_hours), int(limit)),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in (cur.fetchall() or [])]
            for art in rows:
                scanned += 1
                hits = find_rare_anchors_in_article(art, lexicon=lexicon)
                if not hits:
                    continue
                result = found_and_attach_rare_anchors(
                    cur, domain_key=domain_key, article=art, storyline_id=None
                )
                if result.get("created_te_ids"):
                    founded += len(result["created_te_ids"])
                if result.get("attached_te_ids"):
                    attached_rows += len(result["attached_te_ids"])
            conn.commit()
        return {
            "ok": True,
            "domain": domain_key,
            "scanned": scanned,
            "te_created": founded,
            "membership_writes": attached_rows,
            "lexicon_size": len(lexicon),
        }
    except Exception as e:
        logger.warning("rare_anchor_founding_scan %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def sei_widen_allowed_on_silent_attach() -> bool:
    """I3: when event-core is on, silent absorb must not widen SEI match surface."""
    return not event_core_membership_enabled()
