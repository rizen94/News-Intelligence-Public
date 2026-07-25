"""
Storyline core prune — drop parts dissimilar to the storyline core before synthesis.

Builds a core signature (title tokens + SEI entities + high-fit member centroid),
scores members / chronological_events / narrative chunks, auto-drops high-confidence
outliers, and queues mid-band rows with reason_code=dissimilar_to_core.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_int, env_str
from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.storyline_article_counts import sync_counts_update_sql, sync_storyline_derived_metrics

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_REASON_DISSIMILAR = "dissimilar_to_core"
# Common title glue — exclude when deriving title-anchored core for polluted bags
_CORE_TITLE_STOP = frozenset(
    {
        "about",
        "addresses",
        "after",
        "against",
        "amid",
        "and",
        "as",
        "breaking",
        "champion",
        "champions",
        "center",
        "climate",
        "concern",
        "concerns",
        "could",
        "court",
        "courts",
        "during",
        "empowerment",
        "focus",
        "for",
        "from",
        "highlights",
        "into",
        "journalists",
        "landscape",
        "latest",
        "live",
        "minister",
        "new",
        "ongoing",
        "over",
        "peace",
        "political",
        "politics",
        "president",
        "presidential",
        "propose",
        "proposed",
        "proposes",
        "rejects",
        "says",
        "scotus",
        "shifts",
        "sparks",
        "stage",
        "take",
        "takes",
        "that",
        "the",
        "their",
        "this",
        "update",
        "updates",
        "will",
        "with",
        "women",
        "women's",
        "womens",
    }
)


def core_prune_enabled() -> bool:
    return env_str("STORYLINE_CORE_PRUNE_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def core_prune_auto_apply() -> bool:
    """When true, apply clear drops; mid-band still queues. Default on."""
    return env_str("STORYLINE_CORE_PRUNE_AUTO_APPLY", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _unlink_score() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_UNLINK_SCORE", "0.28"))
    except ValueError:
        return 0.28


def _demote_score() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_DEMOTE_SCORE", "0.35"))
    except ValueError:
        return 0.35


def _embedding_cosine_floor() -> float:
    try:
        return float(env_str("STORYLINE_CORE_PRUNE_EMBEDDING_FLOOR", "0.42"))
    except ValueError:
        return 0.42


def _title_jaccard_floor() -> float:
    try:
        return float(env_str("STORYLINE_CORE_PRUNE_TITLE_JACCARD_FLOOR", "0.08"))
    except ValueError:
        return 0.08


def _min_remaining() -> int:
    return max(1, env_int("STORYLINE_MEMBERSHIP_MIN_REMAINING", 3))


def _max_unlinks() -> int:
    return max(0, env_int("STORYLINE_CORE_PRUNE_MAX_UNLINKS", 40))


def _outlier_gate_threshold() -> int:
    """Pre-synthesis: prune if at least this many dissimilar outliers remain."""
    return max(1, env_int("STORYLINE_CORE_PRUNE_OUTLIER_GATE", 5))


def _mega_article_floor() -> int:
    return max(10, env_int("STORYLINE_CORE_PRUNE_MEGA_ARTICLES", 50))


def _large_drop_pct() -> float:
    try:
        return float(env_str("STORYLINE_CORE_PRUNE_REGEN_DROP_PCT", "0.15"))
    except ValueError:
        return 0.15


def tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def narrative_body_looks_polluted(summary: str) -> bool:
    """
    True when stored narrative is a kitchen-sink 'Global Update' bag rather than
    a coherent storyline body. Used to keep core tokens title-anchored.
    """
    s = (summary or "").strip().lower()
    if not s:
        return False
    if "global update" in s:
        return True
    # Common LLM kitchen-sink openings that look identical across storylines
    for phrase in (
        "global tensions escalate",
        "global turmoil",
        "global politics and economy",
        "global conflict escalates",
        "global power dynamics",
        "world is witnessing a significant",
        "latest developments from around the world",
        "complex tapestry of poli",
        "complex web of geopolitics",
        "complex web of international",
        "current global news landscape",
        "international tensions and domestic politics",
        "escalating tensions across the globe",
        "across the globe, highlighting the escalating",
    ):
        if phrase in s[:280]:
            return True
    if s.lstrip().startswith("**global ") or s.lstrip().startswith("# global "):
        return True
    if "here's a breakdown of some key developments" in s:
        return True
    if "**politics:**" in s and "**" in s[s.find("**politics:**") + 12 :]:
        return True
    # Meta / auto-assembled mega narratives (Iran LIVE UPDATES style)
    if "automatically" in s and ("articles" in s or "coverage" in s):
        return True
    if "comprehensive" in s and "coverage" in s and "chronological" in s:
        return True
    # Model meta-commentary (failed to write a storyline summary)
    for phrase in (
        "it appears that the text you provided",
        "collection of news articles",
        "here is a summary of the news articles and external context",
        "here are the answers to your questions",
        "the text appears to be a collection",
        "external context provided is not directly related",
        "unfortunately, i was unable to find",
        "analysis withheld:",
    ):
        if phrase in s[:350]:
            return True
    return False


def title_looks_mega_bag(title: str) -> bool:
    """LIVE UPDATES / Ongoing / Global Update: kitchen-sink magnets — title-anchor."""
    lower = (title or "").strip().lower()
    if not lower:
        return False
    if "live update" in lower:
        return True
    if lower.startswith("ongoing:") or lower.startswith("ongoing "):
        return True
    if "global update" in lower:
        return True
    return False


def distinctive_title_anchors(title: str) -> set[str]:
    """Topic/place-like tokens from the storyline title (kitchen-sink safe)."""
    toks = tokenize(title)
    anchors = {
        t for t in toks if len(t) >= 4 and t not in _CORE_TITLE_STOP and not t.isdigit()
    }
    if anchors:
        return anchors
    # Last resort: longest title tokens
    ranked = sorted((t for t in toks if len(t) >= 4), key=len, reverse=True)
    return set(ranked[:3])


def sei_diverges_from_title_anchors(title: str, sei_entities: set[str]) -> bool:
    """
    True when SEI is kitchen-sink relative to the title (e.g. Trump-heavy bag
    under a Nepal-anchored title). Sticky title-anchoring must stay on.
    """
    anchors = distinctive_title_anchors(title)
    if not anchors:
        return False
    if not sei_entities:
        return True
    overlap = {
        e
        for e in sei_entities
        if tokenize(e) & anchors or (e and e.lower() in anchors)
    }
    if not overlap:
        return True
    if len(sei_entities) >= 8 and (len(overlap) / float(len(sei_entities))) < 0.15:
        return True
    return False


def member_is_core_protected(member: dict[str, Any]) -> bool:
    """Members marked relationship_type=core (or restore metadata) must never auto-unlink."""
    rel = (member.get("relationship_type") or "").strip().lower()
    if rel == "core":
        return True
    meta = member.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = None
    if not isinstance(meta, dict):
        return False
    if meta.get("core_protected") is True:
        return True
    src = (meta.get("source") or "").strip().lower()
    if src in {"core_prune_restore", "manual_core_protect"}:
        return True
    reason = (meta.get("reason") or "").strip().lower()
    if "reprotect" in reason or "core_protect" in reason:
        return True
    return False


def member_matches_title_anchor(
    title_anchors: set[str],
    article_title: str,
    article_entities: set[str] | None = None,
) -> bool:
    """True when article title/entities share a distinctive title geo/topic anchor."""
    if not title_anchors:
        return False
    title_l = (article_title or "").lower()
    for a in title_anchors:
        if len(a) >= 4 and a in title_l:
            return True
    for e in article_entities or set():
        el = (e or "").strip().lower()
        if not el:
            continue
        if el in title_anchors or tokenize(el) & title_anchors:
            return True
    return False


def should_use_keeper_only_evidence(
    *,
    title: str,
    summary: str = "",
    prefer_regenerate_from_keepers: bool = False,
    kitchen_sink: bool | None = None,
) -> bool:
    """
    True when RAG/finisher/headline evidence must be limited to keepers.

    Triggers: prefer_regenerate_from_keepers, mega/shell titles, polluted body,
    or explicit kitchen-sink flag.
    """
    if prefer_regenerate_from_keepers:
        return True
    if kitchen_sink is True:
        return True
    if title_looks_mega_bag(title):
        return True
    if narrative_body_looks_polluted(summary):
        return True
    # Bare / Ongoing shells (align with automation is_shell_title without importing it)
    t = (title or "").strip()
    lower = t.lower()
    if lower.startswith("ongoing:") or lower.startswith("ongoing "):
        return True
    words = [
        w
        for w in re.findall(r"[A-Za-z]{2,}", t)
        if w.lower() not in {"the", "and", "of"}
    ]
    if words and len(words) <= 2 and len(t) <= 40:
        return True
    return False


def member_qualifies_as_keeper_evidence(
    member: dict[str, Any],
    *,
    core_tokens: set[str],
    core_entities: set[str],
    title_anchors: set[str],
    min_fit: float | None = None,
) -> bool:
    """
    Keeper for evidence assembly: relationship_type=core / protect metadata,
    title-anchor match, or core similarity at/above demote floor.
    """
    if member_is_core_protected(member):
        return True
    art_title = member.get("title") or ""
    ents = {e.lower() for e in (member.get("entities") or set()) if e}
    if member_matches_title_anchor(title_anchors, art_title, ents):
        return True
    fit = member.get("fit")
    if fit is None:
        from services.storyline_membership_review_service import compute_article_fit_score

        fit = compute_article_fit_score(
            core_tokens=core_tokens,
            core_entities=core_entities,
            article_title=art_title,
            article_entities=ents,
            relevance_score=member.get("relevance"),
        )
    floor = _demote_score() if min_fit is None else float(min_fit)
    return float(fit) >= floor


def filter_articles_for_keeper_evidence(
    *,
    storyline_title: str,
    storyline_summary: str = "",
    articles: list[dict[str, Any]],
    sei_entities: set[str] | None = None,
    prefer_regenerate_from_keepers: bool = False,
    kitchen_sink: bool | None = None,
    min_fit: float | None = None,
) -> list[dict[str, Any]]:
    """
    When keeper-only mode is active, drop weak/polluted members from evidence bundles.

    Event-core (I2): if any members are typed TE evidence, select among those only —
    never use keeper-as-dirt-mask to hide untyped pollution while keeping a thin core.
    Untyped leftovers on a storyline that also has typed members are membership defects.
    """
    if not articles:
        return []

    # Event-core: prefer typed evidence membership over dirt-mask heuristics
    try:
        from services.event_core_membership_service import (
            MEMBERSHIP_TYPES,
            event_core_membership_enabled,
        )

        if event_core_membership_enabled():
            typed = [
                a
                for a in articles
                if (a.get("membership_type") or "").strip() in MEMBERSHIP_TYPES
                or (a.get("relationship_type") or "").strip() in MEMBERSHIP_TYPES
                or bool(a.get("event_core_typed"))
            ]
            if typed:
                if len(typed) < len(articles):
                    logger.info(
                        "Event-core evidence: using %s typed members of %s "
                        "(untyped remainder is a membership defect, not keeper-masked)",
                        len(typed),
                        len(articles),
                    )
                return list(typed)
    except Exception:
        pass

    if not should_use_keeper_only_evidence(
        title=storyline_title,
        summary=storyline_summary,
        prefer_regenerate_from_keepers=prefer_regenerate_from_keepers,
        kitchen_sink=kitchen_sink,
    ):
        return list(articles)

    member_rows: list[dict[str, Any]] = []
    for a in articles:
        ents = a.get("entities")
        if ents is None:
            ents = set()
        elif isinstance(ents, (list, tuple)):
            ents = {str(e).lower() for e in ents if e}
        elif isinstance(ents, set):
            ents = {str(e).lower() for e in ents if e}
        else:
            ents = set()
        member_rows.append(
            {
                "article_id": a.get("id") if a.get("id") is not None else a.get("article_id"),
                "title": a.get("title") or "",
                "entities": ents,
                "relevance": a.get("relevance")
                if a.get("relevance") is not None
                else a.get("relevance_score"),
                "relationship_type": a.get("relationship_type") or "",
                "metadata": a.get("metadata"),
            }
        )

    sei_rows: list[tuple[Any, ...]] = [
        (e, 5, True) for e in (sei_entities or set()) if e
    ]
    if not sei_rows:
        for anchor in distinctive_title_anchors(storyline_title):
            sei_rows.append((anchor, 5, True))

    core = build_core_signature_from_rows(
        title=storyline_title,
        summary=storyline_summary or "",
        sei_rows=sei_rows,
        member_rows=member_rows,
    )
    core_tokens = core.get("core_tokens") or set()
    core_entities = core.get("core_entities") or set()
    title_anchors = core.get("title_anchors") or distinctive_title_anchors(
        storyline_title
    )
    scored_by_id = {
        m.get("article_id"): m for m in (core.get("scored_members") or [])
    }

    kept: list[dict[str, Any]] = []
    for a in articles:
        aid = a.get("id") if a.get("id") is not None else a.get("article_id")
        scored = scored_by_id.get(aid)
        if scored is None:
            scored = {
                "title": a.get("title") or "",
                "entities": a.get("entities") or set(),
                "relevance": a.get("relevance") or a.get("relevance_score"),
                "relationship_type": a.get("relationship_type") or "",
                "metadata": a.get("metadata"),
                "fit": None,
            }
        if member_qualifies_as_keeper_evidence(
            scored,
            core_tokens=core_tokens,
            core_entities=core_entities,
            title_anchors=title_anchors,
            min_fit=min_fit,
        ):
            kept.append(a)
    return kept


def core_text_for_signature(
    title: str,
    summary: str,
    *,
    sei_entities: set[str] | None = None,
) -> tuple[str, bool]:
    """
    Text used for core_tokens. When the body is a kitchen-sink Global Update,
    return title only so SEI/members are scored against the storyline label.

    Also sticky-title-anchors when:
    - mega / Ongoing / Global Update titles
    - empty/cleared narrative after a prune pass (must not fall back to SEI)
    - SEI diverges from distinctive title anchors (polluted leftovers)
    """
    t = (title or "").strip()
    s = (summary or "").strip()
    if title_looks_mega_bag(t) or narrative_body_looks_polluted(s):
        return t, True
    title_toks = tokenize(t)
    summary_toks = tokenize(s)
    if (
        title_toks
        and summary_toks
        and len(summary_toks) >= 80
        and len(title_toks & summary_toks) < max(2, len(title_toks) // 3)
    ):
        return t, True
    # Cleared body after prior prune: keep title sticky so polluted SEI cannot redefine core
    if not s and distinctive_title_anchors(t):
        return t, True
    if sei_entities is not None and sei_diverges_from_title_anchors(t, sei_entities):
        return t, True
    return f"{t} {s}".strip(), False


def anchor_core_entities(
    title: str,
    sei_entities: set[str],
    *,
    polluted: bool,
) -> set[str]:
    """
    When narrative/SEI are kitchen-sink polluted, keep only entities that
    overlap distinctive title anchors (or those anchors themselves).
    """
    if not polluted:
        return sei_entities
    title_anchors = distinctive_title_anchors(title)
    if not title_anchors:
        return sei_entities
    filtered = {
        e
        for e in sei_entities
        if tokenize(e) & title_anchors or (e and e.lower() in title_anchors)
    }
    # Always keep distinctive title anchors (e.g. iran/nepal) even when SEI is Trump-heavy
    return filtered | set(title_anchors)


def editorial_blob_to_text(raw: Any) -> str:
    """Normalize jsonb/text editorial_document into plain text for chunk scoring."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        parts: list[str] = []
        for k in ("lede", "body", "narrative", "summary", "text", "content"):
            v = raw.get(k)
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
        if parts:
            return "\n\n".join(parts)
        try:
            return json.dumps(raw, ensure_ascii=False)
        except Exception:
            return str(raw)
    if isinstance(raw, (list, tuple)):
        return "\n\n".join(str(x) for x in raw if x)
    text = str(raw).strip()
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            return editorial_blob_to_text(parsed)
        except Exception:
            return text
    return text


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0:
        return vec
    return [x / norm for x in vec]


def _parse_embedding(raw: Any) -> list[float] | None:
    try:
        if raw is None:
            return None
        if isinstance(raw, str):
            emb = json.loads(raw)
        elif isinstance(raw, (list, tuple)):
            emb = list(raw)
        else:
            return None
        if not emb:
            return None
        return [float(x) for x in emb]
    except Exception:
        return None


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    return float(sum(x * y for x, y in zip(a, b)))


def mean_centroid(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    mean = [0.0] * dim
    n = 0
    for v in vectors:
        if len(v) != dim:
            continue
        for i, x in enumerate(v):
            mean[i] += x
        n += 1
    if n <= 0:
        return None
    mean = [x / float(n) for x in mean]
    return _l2_normalize(mean)


def decide_dissimilar_member_action(
    *,
    fit_score: float,
    entity_jaccard: float,
    embedding_cosine: float | None,
    unlink_floor: float | None = None,
    demote_floor: float | None = None,
    embedding_floor: float | None = None,
) -> tuple[str, str, bool]:
    """
    Return (action, rationale, high_confidence).

    action: keep | demote | unlink
    high_confidence: True → safe to auto-drop when auto_apply is on.
    """
    unlink_floor = _unlink_score() if unlink_floor is None else unlink_floor
    demote_floor = _demote_score() if demote_floor is None else demote_floor
    embedding_floor = (
        _embedding_cosine_floor() if embedding_floor is None else embedding_floor
    )

    emb_far = (
        embedding_cosine is not None
        and embedding_cosine < embedding_floor
        and entity_jaccard <= 0.0
        and fit_score < demote_floor
    )
    if fit_score < unlink_floor or emb_far:
        reason = (
            f"fit={fit_score:.3f} < unlink {unlink_floor}"
            if fit_score < unlink_floor
            else (
                f"embedding_cosine={embedding_cosine:.3f} < {embedding_floor} "
                f"and entity_jaccard=0"
            )
        )
        return "unlink", f"{_REASON_DISSIMILAR}: {reason}", True

    if fit_score < demote_floor:
        return (
            "demote",
            f"{_REASON_DISSIMILAR}: fit={fit_score:.3f} mid-band "
            f"[{unlink_floor},{demote_floor})",
            False,
        )

    return "keep", f"fit={fit_score:.3f} near core", False


def decide_dissimilar_event_action(
    *,
    entity_overlap: int,
    title_jaccard: float,
    title_floor: float | None = None,
) -> tuple[str, str, bool]:
    """action: keep | detach | queue."""
    title_floor = _title_jaccard_floor() if title_floor is None else title_floor
    if entity_overlap <= 0 and title_jaccard < title_floor:
        return (
            "detach",
            (
                f"{_REASON_DISSIMILAR}: event entity_overlap=0 "
                f"title_jaccard={title_jaccard:.3f} < {title_floor}"
            ),
            True,
        )
    if entity_overlap <= 0 and title_jaccard < title_floor * 2:
        return (
            "queue",
            (
                f"{_REASON_DISSIMILAR}: weak event title_jaccard={title_jaccard:.3f} "
                f"entity_overlap=0"
            ),
            False,
        )
    return "keep", "event near core", False


def split_narrative_chunks(text: str) -> list[str]:
    """Split stored narrative into paragraph / bullet-ish chunks."""
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"\n\s*\n+", raw)
    chunks: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Also split long single paragraphs on bullet lines
        if "\n- " in p or p.startswith("- "):
            for line in p.split("\n"):
                line = line.strip()
                if len(line) >= 24:
                    chunks.append(line)
        elif len(p) >= 24:
            chunks.append(p)
    return chunks


def decide_dissimilar_chunk_action(
    *,
    entity_jaccard: float,
    title_jaccard: float,
    embedding_cosine: float | None = None,
    embedding_floor: float | None = None,
) -> tuple[str, str, bool]:
    embedding_floor = (
        _embedding_cosine_floor() if embedding_floor is None else embedding_floor
    )
    emb_far = embedding_cosine is not None and embedding_cosine < embedding_floor
    if (entity_jaccard <= 0.0 and title_jaccard < 0.05) or (
        emb_far and entity_jaccard <= 0.0
    ):
        return (
            "deprecate",
            f"{_REASON_DISSIMILAR}: narrative chunk disjoint from core",
            True,
        )
    if entity_jaccard < 0.05 and title_jaccard < 0.12:
        return (
            "queue",
            f"{_REASON_DISSIMILAR}: weak narrative chunk overlap",
            False,
        )
    return "keep", "chunk near core", False


def _entity_names_from_json(raw: Any) -> set[str]:
    out: set[str] = set()
    if raw is None:
        return out
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return out
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                out.add(item.strip().lower())
            elif isinstance(item, dict):
                for k in ("name", "entity", "canonical_name", "label"):
                    v = item.get(k)
                    if isinstance(v, str) and v.strip():
                        out.add(v.strip().lower())
                        break
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, str) and v.strip():
                out.add(v.strip().lower())
    return out


def _enqueue_membership_action(
    cur,
    *,
    domain_key: str,
    storyline_id: int,
    action: str,
    fit_score: float | None,
    rationale: str,
    article_id: int | None = None,
    tracked_event_id: int | None = None,
    status: str = "pending",
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Enqueue via shared allowlist + SAVEPOINT helper.

    Unsupported actions (trim_narrative_chunk, detach_chronological_event, …)
    are skipped — store excerpts in prune audit / narrative meta instead.
    """
    meta = dict(metadata or {})
    meta.setdefault("reason_code", _REASON_DISSIMILAR)
    meta.setdefault("source", "core_prune")
    from services.storyline_membership_review_service import (
        MEMBERSHIP_ACTIONS_ALLOWED,
        _enqueue_action,
    )

    if action not in MEMBERSHIP_ACTIONS_ALLOWED:
        meta["skipped_action"] = action
        logger.debug(
            "core_prune skip membership enqueue for unsupported action=%s storyline=%s",
            action,
            storyline_id,
        )
        return
    _enqueue_action(
        cur,
        domain_key=domain_key,
        storyline_id=storyline_id,
        article_id=article_id,
        tracked_event_id=tracked_event_id,
        action=action,
        fit_score=fit_score,
        rationale=rationale,
        status=status,
        metadata=meta,
    )


def cleanup_sei_after_unlinks(
    cur,
    schema: str,
    storyline_id: int,
    title: str,
    dropped_article_ids: list[int],
    *,
    domain_key: str,
) -> dict[str, int]:
    """
    After unlinking dissimilar members, demote/remove their SEI glue tokens so the
    next absorb/core build cannot re-attach via Trump/Ukraine leftovers.

    - DELETE SEI rows whose entity no longer appears on any remaining member
    - Demote is_core_entity for leftover entities that do not overlap title anchors
    """
    stats = {"sei_deleted": 0, "sei_demoted": 0}
    ids = [int(x) for x in dropped_article_ids if int(x) > 0]
    if not ids:
        return stats

    # Entity names mentioned on dropped articles (best-effort; table may vary)
    dropped_names: set[str] = set()
    try:
        cur.execute(
            f"""
            SELECT DISTINCT lower(trim(entity_name))
            FROM {schema}.article_entities
            WHERE article_id = ANY(%s)
              AND entity_name IS NOT NULL
              AND length(trim(entity_name)) >= 2
            """,
            (ids,),
        )
        for (name,) in cur.fetchall() or []:
            if name:
                dropped_names.add(str(name).strip().lower())
    except Exception as e:
        logger.debug("cleanup_sei article_entities load: %s", e)
        return stats

    if not dropped_names:
        return stats

    title_anchors = distinctive_title_anchors(title)

    # Delete SEI entities with zero remaining member mentions
    try:
        cur.execute(
            f"""
            DELETE FROM {schema}.story_entity_index sei
            WHERE sei.storyline_id = %s
              AND lower(trim(sei.entity_name)) = ANY(%s)
              AND NOT EXISTS (
                SELECT 1
                FROM {schema}.storyline_articles sa
                JOIN {schema}.article_entities ae
                  ON ae.article_id = sa.article_id
                WHERE sa.storyline_id = %s
                  AND lower(trim(ae.entity_name)) = lower(trim(sei.entity_name))
              )
            """,
            (storyline_id, list(dropped_names), storyline_id),
        )
        stats["sei_deleted"] = int(cur.rowcount or 0)
    except Exception as e:
        logger.debug("cleanup_sei delete: %s", e)

    # Demote core flag on remaining SEI that came from dropped set and miss title anchors
    try:
        from services.storyline_membership_review_service import _enqueue_action

        cur.execute(
            f"""
            SELECT entity_name, COALESCE(is_core_entity, false)
            FROM {schema}.story_entity_index
            WHERE storyline_id = %s
              AND lower(trim(entity_name)) = ANY(%s)
              AND COALESCE(is_core_entity, false) = true
            """,
            (storyline_id, list(dropped_names)),
        )
        for ename, _is_core in cur.fetchall() or []:
            name_l = (ename or "").strip().lower()
            if not name_l:
                continue
            if title_anchors and (
                name_l in title_anchors or tokenize(name_l) & title_anchors
            ):
                continue
            cur.execute(
                f"""
                UPDATE {schema}.story_entity_index
                SET is_core_entity = false
                WHERE storyline_id = %s AND entity_name = %s AND is_core_entity = true
                """,
                (storyline_id, ename),
            )
            if cur.rowcount:
                stats["sei_demoted"] += 1
                _enqueue_action(
                    cur,
                    domain_key=domain_key,
                    storyline_id=storyline_id,
                    action="demote_entity",
                    fit_score=None,
                    rationale="sei cleanup after dissimilar unlink",
                    entity_name=ename,
                    status="applied",
                    metadata={
                        "source": "core_prune_sei_cleanup",
                        "reason_code": _REASON_DISSIMILAR,
                    },
                )
    except Exception as e:
        logger.debug("cleanup_sei demote: %s", e)

    return stats


def _unlink_article(cur, schema: str, storyline_id: int, article_id: int) -> bool:
    cur.execute(
        f"""
        DELETE FROM {schema}.storyline_articles
        WHERE storyline_id = %s AND article_id = %s
        """,
        (storyline_id, article_id),
    )
    if cur.rowcount <= 0:
        return False
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET {sync_counts_update_sql(schema)},
            updated_at = %s
        WHERE id = %s
        """,
        (storyline_id, storyline_id, datetime.now(timezone.utc), storyline_id),
    )
    sync_storyline_derived_metrics(cur, schema, storyline_id)
    return True


def _persist_prune_audit(
    cur,
    schema: str,
    storyline_id: int,
    audit: dict[str, Any],
) -> None:
    """Merge prune audit into narrative_finisher_meta (and quality_metrics if present)."""
    payload = json.dumps({"core_prune": audit})
    cur.execute("SAVEPOINT core_prune_audit")
    try:
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET narrative_finisher_meta =
                  COALESCE(narrative_finisher_meta, '{{}}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (payload, storyline_id),
        )
        cur.execute("RELEASE SAVEPOINT core_prune_audit")
        return
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT core_prune_audit")
        logger.debug("persist prune audit meta: %s", e)
    cur.execute("SAVEPOINT core_prune_audit_qm")
    try:
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET quality_metrics =
                  COALESCE(quality_metrics, '{{}}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (payload, storyline_id),
        )
        cur.execute("RELEASE SAVEPOINT core_prune_audit_qm")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT core_prune_audit_qm")


def build_core_signature_from_rows(
    *,
    title: str,
    summary: str,
    sei_rows: list[tuple[Any, ...]],
    member_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Pure helper: build core tokens/entities + high-fit centroid from preloaded rows.

    member_rows items: title, entities (set), relevance, embedding (optional), fit (optional),
    relationship_type / metadata (optional, for core protection).

    When title-anchored (polluted / mega / empty body / SEI diverge), core tokens stay
    title-sticky across passes and protected core members seed entities + centroid.
    """
    from services.storyline_membership_review_service import compute_article_fit_score

    sei_entities = {
        (r[0] or "").strip().lower()
        for r in sei_rows
        if r[0] and (r[2] or int(r[1] or 0) >= 3)
    }
    if not sei_entities:
        sei_entities = {(r[0] or "").strip().lower() for r in sei_rows[:15] if r[0]}

    core_text, polluted = core_text_for_signature(
        title, summary, sei_entities=sei_entities
    )
    title_anchors = distinctive_title_anchors(title)
    if polluted:
        # Prefer distinctive anchors so title_jaccard is not diluted by glue words
        core_tokens = title_anchors or tokenize(core_text)
    else:
        core_tokens = tokenize(core_text)
    # Title tokens must survive later passes even if SEI leftovers dominate mention counts
    if title_anchors:
        core_tokens = set(core_tokens) | set(title_anchors)

    core_entities = anchor_core_entities(title, sei_entities, polluted=polluted)

    # Seed core from protected keepers (manual restores / relationship_type=core)
    protected_entities: set[str] = set()
    for m in member_rows:
        if not member_is_core_protected(m):
            continue
        protected_entities |= {e.lower() for e in (m.get("entities") or set()) if e}
        # Distinctive anchors from protected titles only (avoid kitchen-sink token bleed)
        core_tokens |= distinctive_title_anchors(m.get("title") or "")
    if protected_entities:
        if polluted and title_anchors:
            # Prefer protected ents that align with title; still keep all if none overlap
            aligned = {
                e
                for e in protected_entities
                if tokenize(e) & title_anchors or e in title_anchors
            }
            core_entities |= aligned or protected_entities
        else:
            core_entities |= protected_entities
    if polluted and title_anchors:
        core_entities |= set(title_anchors)

    scored: list[dict[str, Any]] = []
    for m in member_rows:
        ents = {e.lower() for e in (m.get("entities") or set()) if e}
        fit = m.get("fit")
        art_title = m.get("title") or ""
        protected = member_is_core_protected(m)
        anchor_hit = member_matches_title_anchor(title_anchors, art_title, ents)
        if fit is None:
            fit = compute_article_fit_score(
                core_tokens=core_tokens,
                core_entities=core_entities,
                article_title=art_title,
                article_entities=ents,
                relevance_score=m.get("relevance"),
            )
        # Title-anchor / protected rescue: never let kitchen-sink SEI demote keepers
        if protected:
            fit = max(float(fit), 0.85)
        elif polluted and anchor_hit:
            fit = max(float(fit), 0.60)
        elif polluted and core_entities:
            title_l = art_title.lower()
            if any(len(e) >= 4 and e in title_l for e in core_entities):
                fit = max(float(fit), 0.60)
        scored.append(
            {
                **m,
                "fit": float(fit),
                "entities": ents,
                "core_protected": protected,
                "title_anchor_hit": anchor_hit,
            }
        )

    scored.sort(key=lambda x: float(x.get("fit") or 0), reverse=True)
    if polluted:
        # Centroid from title-anchored / protected keepers only — not Trump leftovers
        anchored_pool = [
            m
            for m in scored
            if m.get("core_protected") or m.get("title_anchor_hit")
        ]
        top = (
            anchored_pool[: max(1, len(anchored_pool))]
            if anchored_pool
            else scored[: max(1, len(scored) // 4)]
        )
    else:
        top = scored[: max(1, len(scored) // 4)] if scored else []

    vectors: list[list[float]] = []
    for m in top:
        emb = m.get("embedding")
        if isinstance(emb, list) and emb:
            vectors.append([float(x) for x in emb])
        else:
            parsed = _parse_embedding(emb)
            if parsed:
                vectors.append(parsed)

    centroid = mean_centroid(vectors)
    return {
        "core_tokens": core_tokens,
        "core_entities": core_entities,
        "centroid": centroid,
        "polluted_body": polluted,
        "title_anchors": title_anchors,
        "high_fit_member_ids": [m.get("article_id") for m in top if m.get("article_id")],
        "scored_members": scored,
    }


def count_dissimilar_outliers(
    domain: str,
    storyline_id: int,
) -> dict[str, Any]:
    """
    Lightweight scan: how many members would auto-unlink as dissimilar_to_core.
    Used by pre-synthesis gate (no writes).
    """
    result = prune_dissimilar_parts(domain, storyline_id, dry_run=True, count_only=True)
    return result


def should_gate_synthesis(
    domain: str,
    storyline_id: int,
    *,
    article_count: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """
    True when mega/kitchen-sink storyline still has dissimilar outliers above threshold.
    Caller should prune (or synthesize from keepers) before finisher/RAG.
    """
    if not core_prune_enabled():
        return False, {"skipped": True, "reason": "core_prune_disabled"}

    mega_floor = _mega_article_floor()
    outlier_gate = _outlier_gate_threshold()
    info: dict[str, Any] = {
        "mega_floor": mega_floor,
        "outlier_gate": outlier_gate,
        "article_count": article_count,
    }

    if article_count is not None and int(article_count) < mega_floor:
        # Still check kitchen-sink for mid-size bags
        try:
            from services.storyline_coherence_guardrails import assess_kitchen_sink_risk

            # Without article sample, only size gate applies
            info["kitchen_sink"] = False
        except Exception:
            pass
        return False, {**info, "gated": False, "reason": "below_mega_floor"}

    scan = prune_dissimilar_parts(
        domain, storyline_id, dry_run=True, count_only=True
    )
    outliers = int(scan.get("would_unlink") or 0) + int(scan.get("would_detach_events") or 0)
    info["scan"] = {
        "would_unlink": scan.get("would_unlink"),
        "would_detach_events": scan.get("would_detach_events"),
        "article_count": scan.get("article_count"),
    }
    ac = int(scan.get("article_count") or article_count or 0)
    kitchen = bool(scan.get("kitchen_sink"))
    if ac < mega_floor and not kitchen:
        return False, {**info, "gated": False, "reason": "below_mega_floor"}
    if outliers >= outlier_gate:
        return True, {**info, "gated": True, "outliers": outliers}
    return False, {**info, "gated": False, "outliers": outliers}


def prune_dissimilar_parts(
    domain: str,
    storyline_id: int,
    *,
    dry_run: bool = False,
    count_only: bool = False,
    manage_freeze: bool = True,
) -> dict[str, Any]:
    """
    Score members / events / narrative chunks vs core; drop dissimilar parts.

    Returns counts and audit. When dry_run/count_only, no destructive writes
    (count_only skips membership action inserts too).

    When ``manage_freeze`` is False (caller already holds membership freeze,
    e.g. narrative_finisher), skip set/clear so nested prune does not drop
    the outer lock mid-regen.
    """
    schema = resolve_domain_schema(domain)
    unlink_floor = _unlink_score()
    demote_floor = _demote_score()
    emb_floor = _embedding_cosine_floor()
    auto_apply = (not dry_run) and (not count_only) and core_prune_auto_apply()
    min_remain = _min_remaining()
    max_unlinks = _max_unlinks()

    stats: dict[str, Any] = {
        "domain": domain,
        "storyline_id": storyline_id,
        "dry_run": dry_run or count_only,
        "auto_apply": auto_apply,
        "scored_members": 0,
        "kept_members": 0,
        "unlinked": 0,
        "queued": 0,
        "would_unlink": 0,
        "events_scored": 0,
        "events_detached": 0,
        "would_detach_events": 0,
        "chunks_scored": 0,
        "chunks_deprecated": 0,
        "chunks_queued": 0,
        "protected_kept": 0,
        "title_anchor_kept": 0,
        "rebuild_evidence_from_keepers": False,
        "prefer_regenerate_from_keepers": False,
        "reason_code": _REASON_DISSIMILAR,
        "errors": 0,
    }

    if not core_prune_enabled() and not dry_run and not count_only:
        return {**stats, "skipped": True, "reason": "core_prune_disabled"}

    freeze_active = False
    if auto_apply and manage_freeze:
        try:
            from services.storyline_membership_ops_lock import set_membership_freeze

            freeze_active = set_membership_freeze(
                schema, storyline_id, "core_prune"
            )
        except Exception as e:
            logger.debug("core_prune freeze set: %s", e)

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title,
                           COALESCE(canonical_narrative, master_summary, summary,
                                    analysis_summary, description, ''),
                           COALESCE(article_count, 0),
                           COALESCE(canonical_narrative, ''),
                           COALESCE(analysis_summary, ''),
                           COALESCE(editorial_document::text, '')
                    FROM {schema}.storylines
                    WHERE id = %s AND merged_into_id IS NULL
                    """,
                    (storyline_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {**stats, "error": "storyline_not_found"}

                title = row[1] or ""
                summary = row[2] or ""
                article_count = int(row[3] or 0)
                canonical = row[4] or ""
                analysis_summary = row[5] or ""
                editorial_raw = row[6]
                editorial_document = editorial_blob_to_text(editorial_raw)
                stats["article_count"] = article_count
                stats["title"] = title

                try:
                    from services.storyline_coherence_guardrails import (
                        assess_kitchen_sink_risk,
                    )

                    # Cheap kitchen-sink signal from title alone when large
                    sink, sink_reason = assess_kitchen_sink_risk(title, [])
                    if not sink and narrative_body_looks_polluted(summary):
                        sink, sink_reason = True, "global_update_body"
                    if not sink and title_looks_mega_bag(title):
                        sink, sink_reason = True, "live_updates_or_ongoing_title"
                    stats["kitchen_sink"] = bool(sink)
                    if sink:
                        stats["kitchen_sink_reason"] = sink_reason
                except Exception:
                    stats["kitchen_sink"] = (
                        narrative_body_looks_polluted(summary)
                        or title_looks_mega_bag(title)
                    )
                    if stats["kitchen_sink"]:
                        stats["kitchen_sink_reason"] = "polluted_or_mega_title"

                cur.execute(
                    f"""
                    SELECT entity_name, COALESCE(mention_count, 0),
                           COALESCE(is_core_entity, false)
                    FROM {schema}.story_entity_index
                    WHERE storyline_id = %s
                    ORDER BY is_core_entity DESC NULLS LAST,
                             mention_count DESC NULLS LAST
                    LIMIT 40
                    """,
                    (storyline_id,),
                )
                sei_rows = list(cur.fetchall() or [])

                cur.execute(
                    f"""
                    SELECT sa.article_id, sa.relevance_score, a.title,
                           a.embedding_vector,
                           COALESCE(
                             (SELECT array_agg(DISTINCT lower(ae.entity_name))
                              FROM {schema}.article_entities ae
                              WHERE ae.article_id = sa.article_id
                                AND ae.entity_name IS NOT NULL),
                             ARRAY[]::text[]
                           ),
                           COALESCE(sa.relationship_type, ''),
                           sa.metadata
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    """,
                    (storyline_id,),
                )
                member_db = cur.fetchall() or []
                member_rows = [
                    {
                        "article_id": int(r[0]),
                        "relevance": float(r[1]) if r[1] is not None else None,
                        "title": r[2] or "",
                        "embedding": r[3],
                        "entities": {e for e in (r[4] or []) if e},
                        "relationship_type": (r[5] or "").strip().lower(),
                        "metadata": r[6],
                    }
                    for r in member_db
                ]

                core = build_core_signature_from_rows(
                    title=title,
                    summary=summary,
                    sei_rows=sei_rows,
                    member_rows=member_rows,
                )
                core_tokens: set[str] = core["core_tokens"]
                core_entities: set[str] = core["core_entities"]
                centroid: list[float] | None = core["centroid"]
                title_anchors: set[str] = set(core.get("title_anchors") or set())
                stats["core_entity_count"] = len(core_entities)
                stats["has_centroid"] = centroid is not None
                stats["polluted_body"] = bool(core.get("polluted_body"))
                stats["title_anchors_sample"] = sorted(title_anchors)[:24]
                stats["core_tokens_sample"] = sorted(core_tokens)[:24]
                stats["core_entities_sample"] = sorted(core_entities)[:20]
                stats["protected_core_members"] = sum(
                    1 for m in core["scored_members"] if m.get("core_protected")
                )
                sample_unlink: list[dict[str, Any]] = []
                sample_keep: list[dict[str, Any]] = []
                sample_demote: list[dict[str, Any]] = []
                sample_protected: list[dict[str, Any]] = []

                # Prefer shared centroid helper if we lack high-fit vectors
                if centroid is None:
                    try:
                        from services.storyline_centroid import get_storyline_centroid

                        centroid = get_storyline_centroid(
                            schema, storyline_id, conn=conn, limit_articles=40
                        )
                        stats["has_centroid"] = centroid is not None
                    except Exception:
                        pass

                remaining = max(article_count, len(member_rows))
                unlinks_done = 0
                dropped_ids: list[int] = []

                for m in core["scored_members"]:
                    stats["scored_members"] += 1
                    article_id = int(m["article_id"])
                    ents = m.get("entities") or set()
                    fit = float(m.get("fit") or 0)
                    protected = bool(m.get("core_protected"))
                    anchor_hit = bool(m.get("title_anchor_hit"))
                    if not anchor_hit and title_anchors:
                        anchor_hit = member_matches_title_anchor(
                            title_anchors, m.get("title") or "", ents
                        )
                    ent_j = jaccard(core_entities, ents)
                    emb = m.get("embedding")
                    if isinstance(emb, list):
                        emb_vec = [float(x) for x in emb] if emb else None
                    else:
                        emb_vec = _parse_embedding(emb)
                    emb_cos = cosine_similarity(
                        _l2_normalize(emb_vec) if emb_vec else None, centroid
                    )

                    action, rationale, high_conf = decide_dissimilar_member_action(
                        fit_score=fit,
                        entity_jaccard=ent_j,
                        embedding_cosine=emb_cos,
                        unlink_floor=unlink_floor,
                        demote_floor=demote_floor,
                        embedding_floor=emb_floor,
                    )
                    # Hard keep: protected core + title-anchor geo/topic matches
                    if protected:
                        action, rationale, high_conf = (
                            "keep",
                            "core_protected: relationship_type/metadata",
                            False,
                        )
                        stats["protected_kept"] = int(stats.get("protected_kept") or 0) + 1
                        if len(sample_protected) < 12:
                            sample_protected.append(
                                {
                                    "article_id": article_id,
                                    "fit": round(fit, 3),
                                    "title": (m.get("title") or "")[:120],
                                    "reason": "core_protected",
                                }
                            )
                    elif title_anchors and anchor_hit and action != "keep":
                        action, rationale, high_conf = (
                            "keep",
                            (
                                f"title_anchor_keep: matches "
                                f"{sorted(title_anchors)[:6]}"
                            ),
                            False,
                        )
                        stats["title_anchor_kept"] = (
                            int(stats.get("title_anchor_kept") or 0) + 1
                        )

                    sample_row = {
                        "article_id": article_id,
                        "fit": round(fit, 3),
                        "title": (m.get("title") or "")[:120],
                    }
                    if action == "keep":
                        stats["kept_members"] += 1
                        if len(sample_keep) < 8:
                            sample_keep.append(sample_row)
                        continue

                    if action == "unlink":
                        stats["would_unlink"] += 1
                        if len(sample_unlink) < 12:
                            sample_unlink.append(sample_row)
                        if remaining - 1 < min_remain or unlinks_done >= max_unlinks:
                            action = "demote"
                            high_conf = False
                            rationale += " [min_remaining/max_unlinks]"

                    if action == "demote" and len(sample_demote) < 8:
                        sample_demote.append(sample_row)

                    if count_only:
                        if action == "demote":
                            stats["queued"] += 1
                        continue

                    if action == "unlink" and high_conf and auto_apply:
                        if _unlink_article(cur, schema, storyline_id, article_id):
                            remaining -= 1
                            unlinks_done += 1
                            stats["unlinked"] += 1
                            dropped_ids.append(article_id)
                            _enqueue_membership_action(
                                cur,
                                domain_key=domain,
                                storyline_id=storyline_id,
                                article_id=article_id,
                                action="unlink",
                                fit_score=fit,
                                rationale=rationale,
                                status="applied",
                                metadata={
                                    "entity_jaccard": ent_j,
                                    "embedding_cosine": emb_cos,
                                },
                            )
                        else:
                            stats["errors"] += 1
                        continue

                    # Mid-band or no auto_apply → queue
                    queue_action = "unlink" if action == "unlink" else "demote_relevance"
                    _enqueue_membership_action(
                        cur,
                        domain_key=domain,
                        storyline_id=storyline_id,
                        article_id=article_id,
                        action=queue_action,
                        fit_score=fit,
                        rationale=rationale + (" [dry_run]" if dry_run else ""),
                        status="dry_run" if dry_run else "pending",
                        metadata={
                            "entity_jaccard": ent_j,
                            "embedding_cosine": emb_cos,
                        },
                    )
                    stats["queued"] += 1

                # --- Chronological events ---
                try:
                    cur.execute(
                        """
                        SELECT id, COALESCE(title, ''), COALESCE(location, ''),
                               entities, key_actors
                        FROM public.chronological_events
                        WHERE storyline_id = %s
                           OR storyline_id = %s
                        LIMIT 200
                        """,
                        (str(storyline_id), f"{schema}:{storyline_id}"),
                    )
                    event_rows = cur.fetchall() or []
                except Exception as e:
                    logger.debug("core_prune events load: %s", e)
                    event_rows = []

                for ev_id, ev_title, location, entities_json, actors_json in event_rows:
                    stats["events_scored"] += 1
                    ev_ents = _entity_names_from_json(entities_json)
                    ev_ents |= _entity_names_from_json(actors_json)
                    if location and str(location).strip():
                        ev_ents.add(str(location).strip().lower())
                    overlap = len(ev_ents & core_entities) if core_entities else 0
                    tj = jaccard(core_tokens, tokenize(ev_title or ""))
                    eaction, erationale, ehigh = decide_dissimilar_event_action(
                        entity_overlap=overlap,
                        title_jaccard=tj,
                    )
                    if eaction == "keep":
                        continue
                    if eaction == "detach":
                        stats["would_detach_events"] += 1
                    if count_only:
                        continue
                    if eaction == "detach" and ehigh and auto_apply:
                        try:
                            cur.execute(
                                """
                                UPDATE public.chronological_events
                                SET storyline_id = NULL, updated_at = NOW()
                                WHERE id = %s
                                """,
                                (int(ev_id),),
                            )
                            if cur.rowcount:
                                stats["events_detached"] += 1
                                _enqueue_membership_action(
                                    cur,
                                    domain_key=domain,
                                    storyline_id=storyline_id,
                                    action="detach_chronological_event",
                                    fit_score=tj,
                                    rationale=erationale,
                                    status="applied",
                                    metadata={"chronological_event_id": int(ev_id)},
                                )
                        except Exception as e:
                            logger.debug("detach chronological_event: %s", e)
                            stats["errors"] += 1
                    else:
                        _enqueue_membership_action(
                            cur,
                            domain_key=domain,
                            storyline_id=storyline_id,
                            action="detach_chronological_event",
                            fit_score=tj,
                            rationale=erationale + (" [dry_run]" if dry_run else ""),
                            status="dry_run" if dry_run else "pending",
                            metadata={"chronological_event_id": int(ev_id)},
                        )
                        stats["queued"] += 1

                # --- Narrative chunks ---
                deprecated_spans: list[str] = []
                if not count_only:
                    blob = "\n\n".join(
                        p
                        for p in (canonical, analysis_summary, editorial_document)
                        if p and str(p).strip()
                    )
                    chunks = split_narrative_chunks(blob)
                    for chunk in chunks[:80]:
                        stats["chunks_scored"] += 1
                        cj = jaccard(core_tokens, tokenize(chunk))
                        # Cheap entity proxy: token overlap with core entity tokens
                        ent_tokens = set()
                        for e in core_entities:
                            ent_tokens |= tokenize(e)
                        ej = jaccard(ent_tokens, tokenize(chunk))
                        caction, crationale, chigh = decide_dissimilar_chunk_action(
                            entity_jaccard=ej,
                            title_jaccard=cj,
                        )
                        if caction == "keep":
                            continue
                        if caction == "deprecate" and chigh and auto_apply:
                            deprecated_spans.append(chunk[:500])
                            stats["chunks_deprecated"] += 1
                        else:
                            _enqueue_membership_action(
                                cur,
                                domain_key=domain,
                                storyline_id=storyline_id,
                                action="trim_narrative_chunk",
                                fit_score=cj,
                                rationale=crationale + (" [dry_run]" if dry_run else ""),
                                status="dry_run" if dry_run else "pending",
                                metadata={"chunk_excerpt": chunk[:400]},
                            )
                            stats["chunks_queued"] += 1

                    if deprecated_spans and auto_apply:
                        from services.storyline_narrative_finisher_service import (
                            apply_sections_to_deprecate_or_trim,
                        )

                        new_canon, applied_c, unmatched_c = (
                            apply_sections_to_deprecate_or_trim(
                                canonical, deprecated_spans
                            )
                        )
                        new_analysis, applied_a, unmatched_a = (
                            apply_sections_to_deprecate_or_trim(
                                analysis_summary, deprecated_spans
                            )
                        )
                        # editorial_document is jsonb — score/queue only; do not
                        # write plain-text trims back into the JSON column.
                        _new_editorial, _applied_e, unmatched_e = (
                            apply_sections_to_deprecate_or_trim(
                                editorial_document, deprecated_spans
                            )
                        )
                        unmatched = unmatched_c + unmatched_a + unmatched_e
                        for span in unmatched:
                            _enqueue_membership_action(
                                cur,
                                domain_key=domain,
                                storyline_id=storyline_id,
                                action="trim_narrative_chunk",
                                fit_score=None,
                                rationale=(
                                    f"{_REASON_DISSIMILAR}: unsafe string match; HITL"
                                ),
                                status="pending",
                                metadata={"chunk_excerpt": span[:400]},
                            )
                            stats["chunks_queued"] += 1
                        if applied_c or applied_a:
                            cur.execute(
                                f"""
                                UPDATE {schema}.storylines
                                SET canonical_narrative = %s,
                                    analysis_summary = %s,
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (
                                    new_canon if applied_c else canonical,
                                    new_analysis if applied_a else analysis_summary,
                                    storyline_id,
                                ),
                            )

                members_before = max(1, len(member_rows))
                drop_pct = float(stats["unlinked"]) / float(members_before)
                if stats["unlinked"] > 0:
                    stats["rebuild_evidence_from_keepers"] = True
                    if auto_apply and dropped_ids:
                        sei_stats = cleanup_sei_after_unlinks(
                            cur,
                            schema,
                            storyline_id,
                            title,
                            dropped_ids,
                            domain_key=domain,
                        )
                        stats["sei_deleted"] = int(sei_stats.get("sei_deleted") or 0)
                        stats["sei_demoted"] = int(sei_stats.get("sei_demoted") or 0)
                if drop_pct >= _large_drop_pct():
                    stats["prefer_regenerate_from_keepers"] = True

                stats["sample_would_unlink"] = sample_unlink
                stats["sample_kept"] = sample_keep
                stats["sample_demote"] = sample_demote
                stats["sample_protected"] = sample_protected
                stats.setdefault("protected_kept", 0)
                stats.setdefault("title_anchor_kept", 0)
                stats.setdefault("sei_deleted", 0)
                stats.setdefault("sei_demoted", 0)

                audit = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "dry_run": bool(dry_run or count_only),
                    "unlinked": stats["unlinked"],
                    "would_unlink": stats["would_unlink"],
                    "events_detached": stats["events_detached"],
                    "chunks_deprecated": stats["chunks_deprecated"],
                    "queued": stats["queued"],
                    "sei_deleted": stats["sei_deleted"],
                    "sei_demoted": stats["sei_demoted"],
                    "dropped_article_ids": dropped_ids[:100],
                    "rebuild_evidence_from_keepers": stats[
                        "rebuild_evidence_from_keepers"
                    ],
                    "prefer_regenerate_from_keepers": stats[
                        "prefer_regenerate_from_keepers"
                    ],
                    "reason_code": _REASON_DISSIMILAR,
                }
                stats["audit"] = audit

                if not count_only:
                    _persist_prune_audit(cur, schema, storyline_id, audit)
                    if not dry_run:
                        conn.commit()
                    else:
                        conn.rollback()
                else:
                    conn.rollback()

    except Exception as e:
        logger.exception("prune_dissimilar_parts: %s", e)
        stats["errors"] += 1
        stats["error"] = str(e)[:300]
    finally:
        if freeze_active:
            try:
                from services.storyline_membership_ops_lock import clear_membership_freeze

                clear_membership_freeze(schema, storyline_id)
            except Exception as e:
                logger.debug("core_prune freeze clear: %s", e)

    return stats
