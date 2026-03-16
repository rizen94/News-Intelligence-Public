"""
Briefing filter helper — load low-priority entities/keywords from config and score text
so briefing and feed ordering can demote sports/celebrity/entertainment content.
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "briefing_filters.yaml"
_entities: List[str] = []
_keywords: List[str] = []
_loaded = False


def _load_config() -> None:
    global _entities, _keywords, _loaded
    if _loaded:
        return
    _loaded = True
    try:
        import yaml
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
            _entities = [s.strip() for s in (data.get("low_priority_entities") or []) if s and isinstance(s, str)]
            _keywords = [s.strip().lower() for s in (data.get("low_priority_keywords") or []) if s and isinstance(s, str)]
        else:
            logger.debug("briefing_filters.yaml not found, using empty low-priority lists")
    except Exception as e:
        logger.warning("Failed to load briefing_filters.yaml: %s", e)


def is_low_priority_for_briefing(text: str) -> bool:
    """
    Return True if the given title/lede/summary text should be demoted in briefing order
    (sports, celebrity, entertainment, or configured entity names).
    """
    if not (text or "").strip():
        return False
    _load_config()
    lower = text.lower()
    for entity in _entities:
        if entity and entity.lower() in lower:
            return True
    for kw in _keywords:
        if kw and re.search(r"\b" + re.escape(kw) + r"\b", lower):
            return True
    return False


def sort_briefing_items_by_priority(
    items: List[dict],
    title_key: str = "title",
    summary_key: str = "summary",
    lede_key: str = "lede",
) -> List[dict]:
    """
    Sort a list of briefing items (headlines, ledes, storylines) so low-priority
    (sports/celebrity/entertainment) appear at the end. Modifies order only.
    """
    def combined_text(item: dict) -> str:
        parts = [
            (item.get(title_key) or ""),
            (item.get(summary_key) or ""),
            (item.get(lede_key) or ""),
        ]
        return " ".join(p for p in parts if p)

    low = []
    high = []
    for item in items:
        if is_low_priority_for_briefing(combined_text(item)):
            low.append(item)
        else:
            high.append(item)
    return high + low
