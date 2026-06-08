"""
Briefing filter helper — load low-priority entities/keywords from config and score text
so briefing and feed ordering can demote sports/celebrity/entertainment content.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "briefing_filters.yaml"
_entities: list[str] = []
_keywords: list[str] = []
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
            _entities = [
                s.strip()
                for s in (data.get("low_priority_entities") or [])
                if s and isinstance(s, str)
            ]
            _keywords = [
                s.strip().lower()
                for s in (data.get("low_priority_keywords") or [])
                if s and isinstance(s, str)
            ]
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


def get_ingest_exclude_keywords(domain_key: str | None = None) -> list[str]:
    """
    Keywords that cause RSS ingest rejection (not just briefing demotion).
    Merges global ingest_exclude_keywords with per-domain exclude_keywords from briefing_filters.yaml.
    """
    _load_config()
    out: list[str] = []
    seen: set[str] = set()
    try:
        import yaml

        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
            for kw in data.get("ingest_exclude_keywords") or []:
                if isinstance(kw, str):
                    k = kw.strip().lower()
                    if k and k not in seen:
                        seen.add(k)
                        out.append(k)
            domains = data.get("domains") or {}
            if domain_key:
                dk = domain_key.strip().lower().replace("_", "-")
                dom = domains.get(dk) or domains.get(dk.replace("-", "_")) or {}
                for kw in dom.get("exclude_keywords") or []:
                    if isinstance(kw, str):
                        k = kw.strip().lower()
                        if k and k not in seen:
                            seen.add(k)
                            out.append(k)
    except Exception as e:
        logger.debug("get_ingest_exclude_keywords: %s", e)
    return out


def sort_briefing_items_by_priority(
    items: list[dict],
    title_key: str = "title",
    summary_key: str = "summary",
    lede_key: str = "lede",
) -> list[dict]:
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


def apply_arc_feedback_priority_boost(
    items: list[dict],
    *,
    arc_id: str | None = None,
    title_key: str = "title",
    summary_key: str = "summary",
) -> list[dict]:
    """
    Re-rank briefing items using operator arc feedback (Phase 6).

    Sections rated useful in the last 90 days get keyword hints that boost matching headlines.
    """
    if not items or not arc_id:
        return items
    try:
        from services.arc_feedback_service import get_arc_feedback_summary

        summary = get_arc_feedback_summary(arc_id)
        useful_sections = [
            s["section_key"]
            for s in summary.get("by_section") or []
            if (s.get("useful_count") or 0) >= 1 or (s.get("avg_rating") or 0) >= 4
        ]
        if not useful_sections:
            return items
        hints = {
            "what_changed": ("announced", "signed", "passed", "sanctions", "embargo"),
            "the_numbers": ("percent", "billion", "million", "barrel", "gdp", "index"),
            "prior_analogues": ("similar", "echoes", "recalls", "historical", "analog"),
            "where_this_fits": ("chapter", "arc", "decade", "era", "since"),
        }
        keywords: set[str] = set()
        for sec in useful_sections:
            keywords.update(hints.get(sec, (sec.replace("_", " "),)))
        if not keywords:
            return items

        def score(item: dict) -> tuple[int, str]:
            text = " ".join(
                (item.get(title_key) or "", item.get(summary_key) or "", item.get("lede") or "")
            ).lower()
            hits = sum(1 for kw in keywords if kw in text)
            return (-hits, text)

        return sorted(items, key=score)
    except Exception as e:
        logger.debug("arc feedback briefing boost skipped: %s", e)
        return items
