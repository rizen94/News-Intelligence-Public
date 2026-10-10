"""
Size UIE LLM prompts to Ollama num_ctx and cover long articles.content via chunks.

CONTEXT_CHUNKING_ENABLED only affects intelligence.contexts storage — this module
drives entity/event extraction coverage independently.
"""

from __future__ import annotations

import re
from typing import Any

from config.runtime import env_str
from config.settings import unified_intake_max_article_chars
from shared.context_chunking import _split_by_paragraphs
from shared.services.ollama_model_policy import InvocationKind, num_ctx_for_invocation


# Leave headroom for schema instructions + JSON output inside the model window.
_SCHEMA_OVERHEAD_CHARS = 3500
_CHARS_PER_TOKEN = 3.0
_CTX_FILL_RATIO = 0.55
_MAX_UIE_CHUNKS = 12


def uie_extraction_num_ctx() -> int:
    n = num_ctx_for_invocation(InvocationKind.STRUCTURED_EXTRACTION)
    if n is None:
        try:
            return max(512, min(8192, int(env_str("OLLAMA_EXTRACTION_NUM_CTX", "8192"))))
        except ValueError:
            return 8192
    return int(n)


def uie_per_article_char_budget(*, batch_size: int = 1) -> int:
    """
    Per-article character budget for one STRUCTURED_EXTRACTION call.

    Fits ``batch_size`` articles into the configured extraction num_ctx without
    packing 6×24k into an 8k window.
    """
    n = max(1, int(batch_size))
    total = int(uie_extraction_num_ctx() * _CHARS_PER_TOKEN * _CTX_FILL_RATIO)
    per = max(1500, (total - _SCHEMA_OVERHEAD_CHARS) // n)
    return min(per, unified_intake_max_article_chars())


def split_article_body_for_uie(
    title: str,
    content: str,
    *,
    max_chars: int | None = None,
) -> list[str]:
    """
    Split article body so each piece (+ title overhead) fits ``max_chars``.

    Returns content slices only (caller keeps the headline). Single-element list
    when the body already fits.
    """
    budget = max_chars if max_chars is not None else uie_per_article_char_budget(batch_size=1)
    title_s = (title or "").strip()
    body = (content or "").strip()
    # Reserve room for "Headline: …\n\n" wrapper around content in the prompt.
    title_overhead = len(title_s) + 64
    body_budget = max(800, budget - title_overhead)
    if not body:
        return [""]
    if len(body) <= body_budget:
        return [body]

    overlap = max(200, min(800, body_budget // 10))
    pieces = _split_by_paragraphs(body, max_chars=body_budget, overlap=overlap)
    pieces = [p.strip() for p in pieces if p and p.strip()]
    if not pieces:
        return [body[:body_budget]]
    if len(pieces) > _MAX_UIE_CHUNKS:
        # Prefer covering start+end rather than only the lead when over max chunks.
        head = pieces[: _MAX_UIE_CHUNKS - 1]
        tail = pieces[-1]
        pieces = head + ([tail] if tail not in head else [])
    return pieces[:_MAX_UIE_CHUNKS]


def _norm_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("text") or value.get("entity") or ""
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _entity_key(item: Any) -> str:
    if isinstance(item, dict):
        return _norm_name(item)
    return _norm_name(item)


def _event_key(evt: Any) -> str:
    if not isinstance(evt, dict):
        return _norm_name(evt)
    title = evt.get("event_title") or evt.get("title") or evt.get("name") or ""
    etype = evt.get("event_type") or evt.get("type") or ""
    when = evt.get("event_date") or evt.get("date") or ""
    return f"{_norm_name(title)}|{_norm_name(etype)}|{_norm_name(when)}"


def _claim_key(claim: Any) -> str:
    if not isinstance(claim, dict):
        return _norm_name(claim)
    return "|".join(
        _norm_name(claim.get(k))
        for k in ("subject", "predicate", "object", "claim_text", "text")
    )


def _merge_entity_bucket(dst: list[Any], src: list[Any]) -> list[Any]:
    seen = {_entity_key(x) for x in dst if _entity_key(x)}
    out = list(dst)
    for item in src:
        key = _entity_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def merge_uie_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge per-chunk UIE JSON objects (entities/events/claims/scoring/tags)."""
    if not payloads:
        return {}
    if len(payloads) == 1:
        return payloads[0] if isinstance(payloads[0], dict) else {}

    entities: dict[str, list[Any]] = {}
    events: list[Any] = []
    event_seen: set[str] = set()
    claims: list[Any] = []
    claim_seen: set[str] = set()
    topic_tags: list[Any] = []
    tag_seen: set[str] = set()
    storyline_hints: list[Any] = []
    sentiments: list[float] = []
    qualities: list[float] = []
    labels: list[str] = []

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        ent = payload.get("entities")
        if isinstance(ent, dict):
            for bucket, items in ent.items():
                if not isinstance(items, list):
                    continue
                key = str(bucket)
                entities[key] = _merge_entity_bucket(entities.get(key, []), items)
        for evt in payload.get("events") or []:
            k = _event_key(evt)
            if not k or k in event_seen:
                continue
            event_seen.add(k)
            events.append(evt)
        for claim in payload.get("claims") or []:
            k = _claim_key(claim)
            if not k or k in claim_seen:
                continue
            claim_seen.add(k)
            claims.append(claim)
        for tag in payload.get("topic_tags") or []:
            nk = _norm_name(tag)
            if not nk or nk in tag_seen:
                continue
            tag_seen.add(nk)
            topic_tags.append(tag)
        hints = payload.get("storyline_hints")
        if isinstance(hints, list):
            storyline_hints.extend(h for h in hints if h)
        scoring = payload.get("scoring") if isinstance(payload.get("scoring"), dict) else {}
        try:
            if scoring.get("sentiment_score") is not None:
                sentiments.append(float(scoring["sentiment_score"]))
        except (TypeError, ValueError):
            pass
        try:
            if scoring.get("quality_score") is not None:
                qualities.append(float(scoring["quality_score"]))
        except (TypeError, ValueError):
            pass
        lab = scoring.get("sentiment_label")
        if lab:
            labels.append(str(lab))

    merged_scoring: dict[str, Any] = {}
    if sentiments:
        merged_scoring["sentiment_score"] = sum(sentiments) / len(sentiments)
    if qualities:
        merged_scoring["quality_score"] = max(qualities)
    if labels:
        # Prefer last non-empty label; average score still carried separately.
        merged_scoring["sentiment_label"] = labels[-1]

    return {
        "entities": entities,
        "events": events,
        "claims": claims,
        "scoring": merged_scoring,
        "topic_tags": topic_tags,
        "storyline_hints": storyline_hints,
    }
