"""
Intake Fusion — single LLM pass JSON schema for unified article spine extraction.

One batched call decomposes each article into tagged components for fan-out.
"""

from __future__ import annotations

from typing import Any

# Per-article keys in the batch LLM response object.
INTAKE_FUSION_ARTICLE_KEYS = (
    "entities",
    "claims",
    "events",
    "scoring",
    "topic_tags",
    "storyline_hints",
)

# topic_tags item shape
TOPIC_TAG_ITEM_SCHEMA: dict[str, str] = {
    "keyword": "string",
    "type": "subject|entity|theme",
    "confidence": "0.0-1.0",
}

# storyline_hints item shape (lightweight; not full storyline processing)
STORYLINE_HINT_ITEM_SCHEMA: dict[str, str] = {
    "title": "string",
    "primary_entities": "string[]",
    "confidence": "0.0-1.0",
}


def empty_fusion_article_payload() -> dict[str, Any]:
    return {
        "entities": {
            "people": [],
            "organizations": [],
            "subjects": [],
            "recurring_events": [],
            "dates": [],
            "times": [],
            "countries": [],
            "keywords": [],
        },
        "claims": [],
        "events": [],
        "scoring": {
            "sentiment_score": 0.5,
            "sentiment_label": "neutral",
            "quality_score": 0.5,
        },
        "topic_tags": [],
        "storyline_hints": [],
    }


def normalize_topic_tags(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw[:25]:
        if not isinstance(item, dict):
            continue
        kw = (item.get("keyword") or item.get("name") or "").strip()
        if not kw or len(kw) < 2:
            continue
        try:
            conf = float(item.get("confidence", 0.75))
        except (TypeError, ValueError):
            conf = 0.75
        tag_type = (item.get("type") or "subject").strip().lower()[:30]
        out.append(
            {
                "keyword": kw[:200],
                "type": tag_type,
                "confidence": round(max(0.0, min(1.0, conf)), 3),
            }
        )
    return out


def fusion_prompt_schema_block(event_types_str: str) -> str:
    """JSON schema fragment for the unified/fusion LLM prompt."""
    return f"""{{
  "entities": {{
    "people": [{{"name": "Full Name", "confidence": 0.9, "in_headline": true}}],
    "organizations": [{{"name": "Org", "confidence": 0.85, "in_headline": false}}],
    "subjects": [{{"name": "Theme", "confidence": 0.8, "in_headline": false}}],
    "recurring_events": [{{"name": "Hearing", "confidence": 0.85, "in_headline": true}}],
    "dates": [{{"raw": "March 15", "normalized_iso": "2024-03-15", "type": "absolute"}}],
    "times": [{{"raw": "3:00 PM EST", "normalized": "15:00", "timezone": "EST"}}],
    "countries": [{{"name": "Country", "iso_code": "US", "in_headline": false}}],
    "keywords": [{{"keyword": "term", "type": "subject", "in_headline": false}}]
  }},
  "claims": [
    {{"subject": "entity", "predicate": "action or statement", "object": "target", "confidence": 0.9}}
  ],
  "events": [
    {{
      "event_title": "concise title",
      "event_type": "one of [{event_types_str}]",
      "event_date": "YYYY-MM-DD or relative phrase",
      "date_precision": "exact|week|month|quarter|year|unknown",
      "location": "city/country or unknown",
      "key_actors": [{{"name": "Actor", "role": "role"}}],
      "outcome": "1-2 sentences",
      "is_ongoing": false,
      "continuation_signals": []
    }}
  ],
  "scoring": {{
    "sentiment_score": 0.5,
    "sentiment_label": "neutral",
    "quality_score": 0.7
  }},
  "topic_tags": [
    {{"keyword": "specific theme", "type": "subject", "confidence": 0.85}}
  ],
  "storyline_hints": [
    {{"title": "short storyline label", "primary_entities": ["Entity A"], "confidence": 0.8}}
  ]
}}"""
