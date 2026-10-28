"""
Fast NER pre-pass for intake extraction (spaCy + optional GLiNER).

Produces entity dicts compatible with ArticleEntityExtractionService._parse_response
shape for merge before LLM fan-out.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from config.settings import fast_ner_backend, fast_ner_enabled, fast_ner_gliner_labels, fast_ner_max_chars
from shared.services.spacy_ner_service import get_spacy_ner_service, is_garbage_entity_name

logger = logging.getLogger(__name__)

_SPACY_LABEL_MAP = {
    "PERSON": "people",
    "ORG": "organizations",
    "GPE": "countries",
    "LOC": "countries",
    "EVENT": "recurring_events",
    "LAW": "subjects",
    "PRODUCT": "subjects",
    "WORK_OF_ART": "subjects",
    "FAC": "organizations",
    "NORP": "subjects",
}

_GLINER_LABEL_MAP = {
    "person": "people",
    "organization": "organizations",
    "company": "organizations",
    "location": "countries",
    "country": "countries",
    "event": "recurring_events",
    "law": "subjects",
    "product": "subjects",
}

_gliner_model = None
_gliner_load_attempted = False


def _empty_entities() -> dict[str, list[dict[str, Any]]]:
    return {
        "people": [],
        "organizations": [],
        "subjects": [],
        "recurring_events": [],
        "dates": [],
        "times": [],
        "countries": [],
        "keywords": [],
    }


def _headline_set(headline: str) -> set[str]:
    h = (headline or "").lower()
    return {w for w in re.findall(r"[a-z0-9']+", h) if len(w) >= 3}


def _append_entity(
    out: dict[str, list[dict[str, Any]]],
    bucket: str,
    name: str,
    *,
    confidence: float,
    headline: str,
    source: str,
) -> None:
    name = (name or "").strip()
    if not name or is_garbage_entity_name(name):
        return
    if bucket not in out:
        bucket = "subjects"
    tokens = _headline_set(headline)
    in_headline = any(t in name.lower() for t in tokens) if tokens else False
    key = name.lower()
    for existing in out[bucket]:
        if not isinstance(existing, dict):
            continue
        if (existing.get("name") or "").strip().lower() == key:
            if confidence > float(existing.get("confidence") or 0):
                existing["confidence"] = confidence
                existing["fast_ner_source"] = source
            return
    out[bucket].append(
        {
            "name": name,
            "confidence": round(min(1.0, max(0.0, confidence)), 3),
            "in_headline": in_headline,
            "fast_ner_source": source,
        }
    )


def _extract_spacy(text: str, headline: str) -> dict[str, list[dict[str, Any]]]:
    out = _empty_entities()
    svc = get_spacy_ner_service()
    if not svc.is_available:
        return out
    try:
        svc._ensure_loaded()
        doc = svc._nlp(text[:fast_ner_max_chars()])
        for ent in doc.ents:
            bucket = _SPACY_LABEL_MAP.get(ent.label_)
            if not bucket:
                continue
            _append_entity(
                out,
                bucket,
                ent.text,
                confidence=0.82,
                headline=headline,
                source="spacy",
            )
    except Exception as e:
        logger.debug("fast_ner spacy: %s", e)
    return out


def _get_gliner_model():
    global _gliner_model, _gliner_load_attempted
    if _gliner_load_attempted:
        return _gliner_model
    _gliner_load_attempted = True
    backend = fast_ner_backend()
    if backend not in ("gliner", "both", "auto"):
        return None
    try:
        from gliner import GLiNER

        model_name = "urchade/gliner_medium-v2.1"
        _gliner_model = GLiNER.from_pretrained(model_name)
        logger.info("fast_ner: loaded GLiNER %s", model_name)
    except Exception as e:
        logger.warning("fast_ner GLiNER unavailable: %s", e)
        _gliner_model = None
    return _gliner_model


def _extract_gliner(text: str, headline: str) -> dict[str, list[dict[str, Any]]]:
    out = _empty_entities()
    model = _get_gliner_model()
    if model is None:
        return out
    labels = fast_ner_gliner_labels()
    try:
        entities = model.predict_entities(text[:fast_ner_max_chars()], labels, threshold=0.45)
        for ent in entities:
            label = (ent.get("label") or "").strip().lower()
            bucket = _GLINER_LABEL_MAP.get(label, "subjects")
            _append_entity(
                out,
                bucket,
                ent.get("text") or "",
                confidence=float(ent.get("score") or 0.75),
                headline=headline,
                source="gliner",
            )
    except Exception as e:
        logger.debug("fast_ner gliner: %s", e)
    return out


def extract_fast_entities(title: str, content: str) -> dict[str, list[dict[str, Any]]]:
    """Run configured fast NER backends on title + body."""
    if not fast_ner_enabled():
        return _empty_entities()
    combined = f"{title or ''}\n\n{content or ''}".strip()
    if len(combined) < 50:
        return _empty_entities()

    backend = fast_ner_backend()
    merged = _empty_entities()
    if backend in ("spacy", "both", "auto"):
        sp = _extract_spacy(combined, title or "")
        for k, items in sp.items():
            for item in items:
                _append_entity(
                    merged,
                    k,
                    item.get("name") or "",
                    confidence=float(item.get("confidence") or 0.8),
                    headline=title or "",
                    source="spacy",
                )
    if backend in ("gliner", "both", "auto"):
        gl = _extract_gliner(combined, title or "")
        for k, items in gl.items():
            for item in items:
                _append_entity(
                    merged,
                    k,
                    item.get("name") or "",
                    confidence=float(item.get("confidence") or 0.75),
                    headline=title or "",
                    source="gliner",
                )
    return merged


def _coerce_entity_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return item
    if isinstance(item, str):
        name = item.strip()
        if name:
            return {"name": name, "confidence": 0.8}
    return None


def merge_entity_dicts(
    base: dict[str, list[dict[str, Any]]],
    extra: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Merge fast NER into LLM entity payload (dedupe by bucket + lower name)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for bucket, items in base.items():
        out[bucket] = []
        if not isinstance(items, list):
            continue
        for item in items:
            coerced = _coerce_entity_item(item)
            if coerced:
                out[bucket].append(coerced)
    for bucket, items in extra.items():
        if bucket not in out:
            out[bucket] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            _append_entity(
                out,
                bucket,
                item.get("name") or "",
                confidence=float(item.get("confidence") or 0.75),
                headline="",
                source=str(item.get("fast_ner_source") or "merge"),
            )
    return out


def format_ner_hints_for_prompt(entities: dict[str, list[dict[str, Any]]]) -> str:
    """Compact hint block for unified / entity LLM prompts."""
    lines: list[str] = []
    for bucket in ("people", "organizations", "countries", "recurring_events", "subjects"):
        names = [
            (e.get("name") or "").strip()
            for e in entities.get(bucket, [])
            if isinstance(e, dict) and (e.get("name") or "").strip()
        ]
        if names:
            lines.append(f"{bucket}: {', '.join(names[:25])}")
    if not lines:
        return ""
    return "Pre-detected entities (verify, extend, or correct):\n" + "\n".join(lines)


def fast_ner_entity_count(entities: dict[str, list[dict[str, Any]]]) -> int:
    return sum(len(entities.get(k) or []) for k in ("people", "organizations", "subjects", "recurring_events"))
