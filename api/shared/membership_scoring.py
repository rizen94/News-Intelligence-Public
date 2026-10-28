"""Content-aware article↔storyline membership scoring (SSOT).

``score_article_storyline_membership`` is the single formula for admit, review,
and cleanup. Weights come from domain ``link_score_profile``.

``blend_link_score`` remains for storyline↔storyline graph ranking only.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.I)


@dataclass
class MembershipScore:
    combined: float
    parts: dict[str, float] = field(default_factory=dict)
    rejected: bool = False
    reject_reason: str = ""

    def as_metadata(self) -> dict[str, Any]:
        return {
            "score_parts": dict(self.parts),
            "combined": round(float(self.combined), 4),
            "rejected": bool(self.rejected),
            "reject_reason": self.reject_reason or None,
            "scorer": "membership_scoring_v1",
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _jaccard(a: set[Any], b: set[Any]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter <= 0:
        return 0.0
    return inter / float(len(a | b))


def _tokenize(text: str) -> set[str]:
    raw = {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}
    out: set[str] = set(raw)
    for t in raw:
        for part in t.split("-"):
            if len(part) >= 3:
                out.add(part)
        # Light morphology: yemeni→yemen, iranian→iran
        if t.endswith("ian") and len(t) > 5:
            out.add(t[:-3])
        elif t.endswith("ians") and len(t) > 6:
            out.add(t[:-4])
        elif t.endswith("i") and len(t) > 4 and not t.endswith("si"):
            out.add(t[:-1])
    return out


def _parse_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, (list, tuple)) and raw:
            return [float(x) for x in raw]
    except Exception:
        return None
    return None


def _temporal_proximity(
    article_published_at: datetime | None,
    story_ref_time: datetime | None,
    half_life_days: float,
) -> float:
    if article_published_at is None or story_ref_time is None:
        return 0.7  # neutral when unknown
    try:
        a = article_published_at
        b = story_ref_time
        if a.tzinfo is None:
            a = a.replace(tzinfo=timezone.utc)
        if b.tzinfo is None:
            b = b.replace(tzinfo=timezone.utc)
        days = abs((a - b).total_seconds()) / 86400.0
        hl = max(1.0, float(half_life_days))
        return _clamp01(math.exp(-math.log(2.0) * days / hl))
    except Exception:
        return 0.7


def _quality_from_article_row(
    quality_score: Any,
    quality_tier: Any,
    clickbait_probability: Any,
) -> float:
    try:
        if quality_score is not None:
            q = float(quality_score)
            if q > 1.0 and q <= 10.0:
                q = q / 10.0
            return _clamp01(q)
    except (TypeError, ValueError):
        pass
    try:
        tier = int(quality_tier) if quality_tier is not None else 3
        # tier 1=best … 4=worst
        q = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}.get(tier, 0.5)
    except (TypeError, ValueError):
        q = 0.5
    try:
        if clickbait_probability is not None:
            q = q * (1.0 - _clamp01(float(clickbait_probability)))
    except (TypeError, ValueError):
        pass
    return _clamp01(q)


def combine_membership_parts(
    *,
    domain_key: str,
    canonical: float,
    relevance: float,
    semantic: float,
    keyword: float,
    quality: float,
    temporal: float,
    vault_boost: float = 0.0,
) -> MembershipScore:
    """
    Weighted combine using domain link_score_profile.

    Hard reject when canonical==0 and semantic < semantic_alone_floor.
    """
    from services.domain_synthesis_config import get_domain_synthesis_config

    cfg = get_domain_synthesis_config(domain_key)
    p = cfg.link_score_profile

    c = _clamp01(canonical)
    r = _clamp01(relevance)
    s = _clamp01(semantic)
    k = _clamp01(keyword)
    q = _clamp01(quality)
    t = _clamp01(temporal)
    vb = max(0.0, min(float(p.vault_boost_cap), float(vault_boost or 0.0)))

    parts = {
        "canonical": round(c, 4),
        "relevance": round(r, 4),
        "semantic": round(s, 4),
        "keyword": round(k, 4),
        "quality": round(q, 4),
        "temporal": round(t, 4),
        "vault_boost": round(vb, 4),
    }

    floor = float(p.semantic_alone_floor)
    # Embedding similarity alone is not enough for kitchen-sink rejection —
    # require keyword or name relevance when there is no canonical overlap.
    if c <= 0.0 and s < floor:
        return MembershipScore(
            combined=0.0,
            parts=parts,
            rejected=True,
            reject_reason=f"no_canonical_and_semantic_{s:.3f}_lt_{floor:.3f}",
        )
    if c <= 0.0 and k < 0.05 and r < 0.15:
        return MembershipScore(
            combined=0.0,
            parts=parts,
            rejected=True,
            reject_reason="no_canonical_and_weak_keyword_entity",
        )

    w_sum = (
        float(p.canonical_entity_weight)
        + float(p.relevance_weight)
        + float(p.semantic_weight)
        + float(p.keyword_weight)
        + float(p.quality_weight)
        + float(p.temporal_weight)
    )
    if w_sum <= 0:
        w_sum = 1.0

    combined = (
        float(p.canonical_entity_weight) * c
        + float(p.relevance_weight) * r
        + float(p.semantic_weight) * s
        + float(p.keyword_weight) * k
        + float(p.quality_weight) * q
        + float(p.temporal_weight) * t
    ) / w_sum
    combined = _clamp01(combined + vb)
    parts["overall"] = round(combined, 4)
    return MembershipScore(combined=combined, parts=parts)


def score_article_against_signals(
    *,
    domain_key: str,
    article_canonical_ids: set[int],
    article_entity_names: set[str],
    article_title: str,
    article_embedding: list[float] | None,
    article_quality: float,
    article_published_at: datetime | None,
    story_canonical_ids: set[int],
    story_core_entities: set[str],
    story_title: str,
    story_keywords: set[str],
    story_centroid: list[float] | None,
    story_ref_time: datetime | None,
    vault_boost: float = 0.0,
    half_life_days: float | None = None,
) -> MembershipScore:
    """Score from pre-fetched signals (usable for discovery cluster admit)."""
    from services.domain_synthesis_config import get_domain_synthesis_config
    from services.storyline_centroid import centroid_cosine

    cfg = get_domain_synthesis_config(domain_key)
    hl = (
        float(half_life_days)
        if half_life_days is not None
        else float(cfg.link_score_profile.temporal_half_life_days)
    )

    canonical = _jaccard(
        {int(x) for x in article_canonical_ids if int(x) > 0},
        {int(x) for x in story_canonical_ids if int(x) > 0},
    )
    # Relevance: core SEI / entity-name overlap; fall back to title-token overlap
    # so empty SEI does not zero out 40% of the blend.
    art_names = {e.strip().lower() for e in article_entity_names if e and e.strip()}
    core = {e.strip().lower() for e in story_core_entities if e and e.strip()}
    if core:
        relevance = _jaccard(art_names, core)
    else:
        relevance = _jaccard(art_names, _tokenize(story_title))

    semantic = 0.0
    if article_embedding and story_centroid:
        semantic = _clamp01(centroid_cosine(article_embedding, story_centroid))

    title_toks = _tokenize(article_title)
    kw = set(story_keywords) | _tokenize(story_title)
    keyword = _jaccard(title_toks, kw)

    temporal = _temporal_proximity(article_published_at, story_ref_time, hl)

    # When SEI/name relevance is empty but canonical overlap is strong, borrow
    # canonical into the relevance slot so entity mass is not wasted.
    relevance_eff = relevance if relevance > 0.05 else max(relevance, canonical)

    return combine_membership_parts(
        domain_key=domain_key,
        canonical=canonical,
        relevance=relevance_eff,
        semantic=semantic,
        keyword=keyword,
        quality=article_quality,
        temporal=temporal,
        vault_boost=vault_boost,
    )


def _anchor_cids(sig: Any) -> set[int]:
    out: set[int] = set()
    if not isinstance(sig, dict):
        return out
    for bucket in ("identity", "supporting"):
        for tok in sig.get(bucket) or []:
            s = str(tok).strip().lower()
            if s.startswith("cid:"):
                try:
                    out.add(int(s.split(":", 1)[1]))
                except ValueError:
                    continue
            elif s.isdigit():
                out.add(int(s))
    return out


def _vault_tag_boost(conn, schema: str, article_id: int, story_canonical_ids: set[int]) -> float:
    """Small boost when article entities share vault tags with storyline canonicals."""
    if not story_canonical_ids:
        return 0.0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT ae.canonical_entity_id
                FROM {schema}.article_entities ae
                WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                """,
                (int(article_id),),
            )
            art_cids = {int(r[0]) for r in (cur.fetchall() or []) if r and r[0]}
            shared = art_cids & story_canonical_ids
            if not shared:
                return 0.0
            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM intelligence.vault_notes vn
                WHERE vn.note_type = 'entity'
                  AND vn.object_id = ANY(%s)
                  AND COALESCE(cardinality(vn.tags), 0) > 0
                """,
                (list(shared),),
            )
            n = int((cur.fetchone() or [0])[0] or 0)
            if n <= 0:
                return 0.0
            return min(1.0, 0.5 + 0.1 * n)
    except Exception as e:
        logger.debug("vault_tag_boost: %s", e)
        return 0.0


def score_article_storyline_membership(
    conn,
    *,
    domain_key: str,
    storyline_id: int,
    article_id: int,
    schema: str | None = None,
) -> MembershipScore:
    """Load article + storyline signals and return content-aware membership score."""
    from shared.domain_registry import resolve_domain_schema
    from services.storyline_centroid import get_storyline_centroid, matching_centroid

    sch = schema or resolve_domain_schema(domain_key)
    sid = int(storyline_id)
    aid = int(article_id)

    article_canonical: set[int] = set()
    article_names: set[str] = set()
    title = ""
    published_at: datetime | None = None
    quality = 0.5
    art_emb: list[float] | None = None

    story_canonical: set[int] = set()
    story_core: set[str] = set()
    story_title = ""
    story_keywords: set[str] = set()
    story_ref: datetime | None = None
    anchor_sig: Any = None

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.title, a.published_at, a.quality_score, a.quality_tier,
                       a.clickbait_probability, a.embedding_vector
                FROM {sch}.articles a
                WHERE a.id = %s
                """,
                (aid,),
            )
            row = cur.fetchone()
            if not row:
                return MembershipScore(
                    combined=0.0,
                    parts={},
                    rejected=True,
                    reject_reason="article_missing",
                )
            title = row[0] or ""
            published_at = row[1]
            quality = _quality_from_article_row(row[2], row[3], row[4])
            art_emb = _parse_embedding(row[5])

            cur.execute(
                f"""
                SELECT DISTINCT canonical_entity_id, lower(entity_name)
                FROM {sch}.article_entities
                WHERE article_id = %s
                """,
                (aid,),
            )
            for cid, ename in cur.fetchall() or []:
                if cid:
                    article_canonical.add(int(cid))
                if ename:
                    article_names.add(str(ename))

            cur.execute(
                f"""
                SELECT title, search_keywords, key_entities, anchor_signature,
                       last_event_at, updated_at, created_at
                FROM {sch}.storylines WHERE id = %s
                """,
                (sid,),
            )
            srow = cur.fetchone()
            if not srow:
                return MembershipScore(
                    combined=0.0,
                    parts={},
                    rejected=True,
                    reject_reason="storyline_missing",
                )
            story_title = srow[0] or ""
            for kw in srow[1] or []:
                if kw:
                    story_keywords.add(str(kw).lower())
            # key_entities may be jsonb list of strings or objects
            ke = srow[2]
            if isinstance(ke, list):
                for item in ke:
                    if isinstance(item, str) and item.strip():
                        story_core.add(item.strip().lower())
                    elif isinstance(item, dict):
                        n = item.get("name") or item.get("entity_name")
                        if n:
                            story_core.add(str(n).strip().lower())
            anchor_sig = srow[3]
            story_ref = srow[4] or srow[5] or srow[6]

            cur.execute(
                f"""
                SELECT DISTINCT lower(entity_name), is_core_entity
                FROM {sch}.story_entity_index
                WHERE storyline_id = %s
                """,
                (sid,),
            )
            for ename, is_core in cur.fetchall() or []:
                if ename and is_core:
                    story_core.add(str(ename))

            # Storyline canonical set = member articles ∪ locked cid anchors
            cur.execute(
                f"""
                SELECT DISTINCT ae.canonical_entity_id
                FROM {sch}.storyline_articles sa
                JOIN {sch}.article_entities ae ON ae.article_id = sa.article_id
                WHERE sa.storyline_id = %s
                  AND ae.canonical_entity_id IS NOT NULL
                """,
                (sid,),
            )
            for (cid,) in cur.fetchall() or []:
                if cid:
                    story_canonical.add(int(cid))
            story_canonical |= _anchor_cids(anchor_sig)

    except Exception as e:
        logger.warning(
            "score_article_storyline_membership load %s/%s/%s: %s",
            domain_key,
            sid,
            aid,
            e,
        )
        return MembershipScore(
            combined=0.0,
            parts={},
            rejected=True,
            reject_reason=f"load_error:{e}",
        )

    centroid = None
    try:
        centroid = matching_centroid(sch, sid, conn=conn) or get_storyline_centroid(
            sch, sid, conn=conn
        )
    except Exception:
        centroid = None

    vault = _vault_tag_boost(conn, sch, aid, story_canonical)

    return score_article_against_signals(
        domain_key=domain_key,
        article_canonical_ids=article_canonical,
        article_entity_names=article_names,
        article_title=title,
        article_embedding=art_emb,
        article_quality=quality,
        article_published_at=published_at,
        story_canonical_ids=story_canonical,
        story_core_entities=story_core,
        story_title=story_title,
        story_keywords=story_keywords,
        story_centroid=centroid,
        story_ref_time=story_ref,
        vault_boost=vault,
    )
