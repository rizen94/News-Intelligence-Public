"""
Page-subject lock for assemble-time prune (pure helpers, no DB).

Soft intake may bridge via a person (Musk → SpaceX + X). After membership
assembles, lock the dominant cluster as the page subject and treat leftover
title tokens as bridges that must not hard-keep off-topic members.
"""

from __future__ import annotations

import math
import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
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
        "for",
        "from",
        "into",
        "latest",
        "live",
        "new",
        "ongoing",
        "over",
        "says",
        "that",
        "the",
        "their",
        "this",
        "update",
        "updates",
        "will",
        "with",
    }
)

_HOLDING_BRANDS = frozenset(
    {
        "spacex",
        "tesla",
        "twitter",
        "neuralink",
        "starlink",
        "xai",
        "boring",
        "openai",
        "microsoft",
        "google",
        "alphabet",
        "meta",
        "amazon",
        "apple",
        "nvidia",
    }
)
_HOLDING_ALIASES: dict[str, frozenset[str]] = {
    "twitter": frozenset({"twitter", "x"}),
    "spacex": frozenset({"spacex", "space"}),
    "boring": frozenset({"boring", "tbc"}),
}
_METHODS_THESIS_CUES = frozenset(
    {
        "ownership",
        "owns",
        "owned",
        "runs",
        "running",
        "management",
        "managing",
        "companies",
        "company",
        "empire",
        "businesses",
        "business",
        "holdings",
        "methods",
        "playbook",
        "control",
        "controlling",
    }
)


def tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def distinctive_title_anchors(title: str) -> set[str]:
    toks = tokenize(title)
    anchors = {
        t for t in toks if len(t) >= 4 and t not in _CORE_TITLE_STOP and not t.isdigit()
    }
    if anchors:
        return anchors
    ranked = sorted((t for t in toks if len(t) >= 4), key=len, reverse=True)
    return set(ranked[:3])


def _title_looks_mega_bag(title: str) -> bool:
    try:
        from services.storyline_coherence_guardrails import title_looks_mega_bag as _mega

        return bool(_mega(title))
    except Exception:
        # Fallback: long bridge titles with amid/as/and stacks
        t = (title or "").lower()
        return (" amid " in t or " as " in t) and len(tokenize(t)) >= 10


def _member_is_founding(member: dict[str, Any]) -> bool:
    rel = (member.get("relationship_type") or "").strip().lower()
    if rel in {"core", "founding", "seed"}:
        return True
    meta = member.get("metadata")
    if isinstance(meta, dict) and meta.get("core_protected") is True:
        return True
    return False


def _parse_embedding(raw: Any) -> list[float] | None:
    try:
        if raw is None:
            return None
        if isinstance(raw, str):
            import json

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


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0:
        return vec
    return [x / norm for x in vec]


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


def member_embedding_vec(member: dict[str, Any]) -> list[float] | None:
    emb = member.get("embedding")
    if isinstance(emb, list) and emb:
        return _l2_normalize([float(x) for x in emb])
    parsed = _parse_embedding(emb)
    return _l2_normalize(parsed) if parsed else None


def member_pair_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    va, vb = member_embedding_vec(a), member_embedding_vec(b)
    cos = cosine_similarity(va, vb)
    if cos is not None:
        return float(cos)
    ta = tokenize(a.get("title") or "")
    tb = tokenize(b.get("title") or "")
    ea = {e.lower() for e in (a.get("entities") or set()) if e}
    eb = {e.lower() for e in (b.get("entities") or set()) if e}
    return 0.6 * jaccard(ta, tb) + 0.4 * jaccard(ea, eb)


def cluster_member_indices(
    member_rows: list[dict[str, Any]],
    *,
    threshold: float = 0.35,
) -> list[list[int]]:
    n = len(member_rows)
    if n == 0:
        return []
    if n == 1:
        return [[0]]
    assigned = [-1] * n
    clusters: list[list[int]] = []
    order = sorted(
        range(n),
        key=lambda i: (0 if _member_is_founding(member_rows[i]) else 1, i),
    )
    for i in order:
        if assigned[i] >= 0:
            continue
        cid = len(clusters)
        clusters.append([i])
        assigned[i] = cid
        grew = True
        while grew:
            grew = False
            for j in range(n):
                if assigned[j] >= 0:
                    continue
                if any(
                    member_pair_similarity(member_rows[j], member_rows[k]) >= threshold
                    for k in clusters[cid]
                ):
                    clusters[cid].append(j)
                    assigned[j] = cid
                    grew = True
    return [c for c in clusters if c]


def holdings_in_text(text: str) -> set[str]:
    toks = tokenize(text)
    title_l = (text or "").lower()
    found: set[str] = set()
    for brand in _HOLDING_BRANDS:
        aliases = _HOLDING_ALIASES.get(brand, frozenset({brand}))
        if any(a in toks or (len(a) >= 3 and f" {a} " in f" {title_l} ") for a in aliases):
            found.add(brand)
        elif brand in toks:
            found.add(brand)
    if "twitter" not in found and re.search(
        r"\b(x platform|site x|quits x|using x)\b", title_l
    ):
        found.add("twitter")
    return found


def multi_holding_methods_thesis(
    *,
    title: str,
    summary: str,
    member_rows: list[dict[str, Any]],
    anchor_signature: dict[str, Any] | None = None,
    story_kind: str | None = None,
) -> bool:
    signals = 0
    holding_mass: dict[str, int] = {}
    for m in member_rows:
        for h in holdings_in_text(m.get("title") or ""):
            holding_mass[h] = holding_mass.get(h, 0) + 1
    multi_mass = sorted(holding_mass.values(), reverse=True)
    span_ok = (
        len(holding_mass) >= 2
        and multi_mass[0] >= 1
        and multi_mass[1] >= 1
        and multi_mass[0] <= max(3, multi_mass[1] * 3)
    )
    if span_ok:
        signals += 1

    sig = anchor_signature if isinstance(anchor_signature, dict) else {}
    identity = " ".join(str(x) for x in (sig.get("identity") or []))
    supporting = " ".join(str(x) for x in (sig.get("supporting") or []))
    kind = (story_kind or "").strip().lower()
    sig_blob = f"{identity} {supporting} {kind}"
    if len(holdings_in_text(sig_blob)) >= 2 or "multi" in kind or "methods" in kind:
        signals += 1

    cue_blob = f"{title or ''} {summary or ''}".lower()
    cue_toks = tokenize(cue_blob)
    if cue_toks & _METHODS_THESIS_CUES and (
        len(holdings_in_text(cue_blob)) >= 2 or span_ok
    ):
        signals += 1

    return signals >= 2


def lock_page_subject_from_members(
    *,
    title: str,
    summary: str,
    member_rows: list[dict[str, Any]],
    title_anchors: set[str] | None = None,
    anchor_signature: dict[str, Any] | None = None,
    story_kind: str | None = None,
) -> dict[str, Any]:
    anchors = set(title_anchors or distinctive_title_anchors(title))
    clusters = cluster_member_indices(member_rows)
    if not clusters:
        return {
            "dominant_indices": [],
            "subject_tokens": anchors or tokenize(title),
            "subject_entities": set(anchors),
            "subject_anchors": anchors,
            "bridge_anchors": set(),
            "multi_holding_thesis": False,
            "centroid": None,
            "cluster_sizes": [],
        }

    founding_idx = next(
        (i for i, m in enumerate(member_rows) if _member_is_founding(m)),
        None,
    )
    clusters_sorted = sorted(clusters, key=len, reverse=True)
    dominant = clusters_sorted[0]
    if founding_idx is not None:
        for c in clusters:
            if founding_idx in c and len(c) >= max(1, int(0.5 * len(dominant))):
                dominant = c
                break

    subject_tokens: set[str] = set()
    subject_entities: set[str] = set()
    vectors: list[list[float]] = []
    for i in dominant:
        m = member_rows[i]
        subject_tokens |= distinctive_title_anchors(m.get("title") or "")
        subject_entities |= {e.lower() for e in (m.get("entities") or set()) if e}
        vec = member_embedding_vec(m)
        if vec:
            vectors.append(vec)
    subject_tokens |= (
        tokenize(" ".join((member_rows[i].get("title") or "") for i in dominant))
        - _CORE_TITLE_STOP
    )

    subject_anchors: set[str] = set()
    need = max(1, int(math.ceil(len(dominant) * 0.34)))
    for a in anchors:
        hits = 0
        for i in dominant:
            blob = (member_rows[i].get("title") or "").lower()
            ents = {e.lower() for e in (member_rows[i].get("entities") or set()) if e}
            if (len(a) >= 4 and a in blob) or a in ents or tokenize(a) & ents:
                hits += 1
        if hits >= need or a in subject_tokens or a in subject_entities:
            subject_anchors.add(a)
    if not subject_anchors and subject_tokens:
        subject_anchors = anchors & subject_tokens
    if not subject_anchors:
        subject_anchors = set(subject_tokens)
        subject_anchors |= {a for a in anchors if a in subject_tokens}

    bridge_anchors = anchors - subject_anchors
    thesis = multi_holding_methods_thesis(
        title=title,
        summary=summary,
        member_rows=member_rows,
        anchor_signature=anchor_signature,
        story_kind=story_kind,
    )
    if thesis:
        for m in member_rows:
            for brand in holdings_in_text(m.get("title") or ""):
                subject_anchors.add(brand)
                subject_tokens.add(brand)
                bridge_anchors.discard(brand)

    return {
        "dominant_indices": list(dominant),
        "subject_tokens": subject_tokens,
        "subject_entities": subject_entities,
        "subject_anchors": subject_anchors,
        "bridge_anchors": bridge_anchors,
        "multi_holding_thesis": thesis,
        "centroid": mean_centroid(vectors),
        "cluster_sizes": [len(c) for c in clusters_sorted],
    }


def member_matches_title_anchor(
    title_anchors: set[str],
    article_title: str,
    article_entities: set[str] | None = None,
) -> bool:
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


def member_matches_subject_anchor(
    subject_anchors: set[str],
    article_title: str,
    article_entities: set[str] | None = None,
    *,
    bridge_anchors: set[str] | None = None,
) -> bool:
    if not member_matches_title_anchor(subject_anchors, article_title, article_entities):
        return False
    if not bridge_anchors:
        return True
    subject_hit = member_matches_title_anchor(
        subject_anchors, article_title, article_entities
    )
    return bool(subject_hit)


def maybe_retitle_from_keepers(
    *,
    title: str,
    keeper_titles: list[str],
    subject_anchors: set[str],
) -> str | None:
    if not keeper_titles:
        return None
    old = (title or "").strip()
    top = (keeper_titles[0] or "").strip()
    if not top or top == old:
        return None
    mega = _title_looks_mega_bag(old)
    old_anchors = distinctive_title_anchors(old)
    subject_overlap = bool(subject_anchors and (old_anchors & subject_anchors))
    if not mega and subject_overlap:
        return None
    new_title = top[:300]
    if new_title.lower() == old.lower():
        return None
    return new_title
