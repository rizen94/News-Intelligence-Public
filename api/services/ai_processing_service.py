"""
Thin shim for automation phases that expect get_ai_service() with
analyze_sentiment, extract_entities, score_article_quality.
Delegates to shared.services.llm_service and adapts return shapes.
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_ai_service: Any = None


def get_ai_service() -> "AIProcessingAdapter":
    """Return the singleton adapter used by entity_extraction, sentiment_analysis, quality_scoring."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIProcessingAdapter()
    return _ai_service


class AIProcessingAdapter:
    """Adapts LLMService to the interface expected by automation_manager."""

    def __init__(self):
        from shared.services.llm_service import LLMService
        self._llm = LLMService()

    async def analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """Return dict with 'score' (0–1) and 'label' (positive/negative/neutral)."""
        out = await self._llm.analyze_sentiment(content)
        if not out.get("success"):
            return {"score": 0.5, "label": "neutral"}
        sentiment = out.get("sentiment") or {}
        if isinstance(sentiment, dict):
            overall = (sentiment.get("overall_sentiment") or "neutral").lower()
            conf = min(100, max(0, sentiment.get("confidence", 50))) / 100.0
            if "positive" in overall:
                score = 0.5 + 0.5 * conf
            elif "negative" in overall:
                score = 0.5 - 0.5 * conf
            else:
                score = 0.5
            score = max(0.0, min(1.0, score))
            return {"score": score, "label": overall}
        return {"score": 0.5, "label": "neutral"}

    async def extract_entities(self, content: str) -> List[Dict[str, Any]]:
        """Return list of entities for JSON storage in articles.entities."""
        out = await self._llm.extract_entities(content)
        if not out.get("success"):
            return []
        data = out.get("entities") or {}
        entities: List[Dict[str, Any]] = []
        for key in ("people", "organizations", "locations", "events", "dates"):
            for name in (data.get(key) or []):
                if isinstance(name, str) and name.strip():
                    entities.append({"name": name.strip(), "type": key[:-1] if key.endswith("s") else key})
        return entities

    async def score_article_quality(self, content: str, title: str = "") -> Dict[str, Any]:
        """Return dict with 'score' (0–1). Stub: no LLM call; returns 0.5."""
        # Optional: call LLM for real scoring; for now avoid extra load
        return {"score": 0.5}
