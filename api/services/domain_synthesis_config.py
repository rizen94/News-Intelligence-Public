"""
Domain Synthesis Configuration Loader

Loads per-domain synthesis config from api/config/domain_synthesis_config.yaml
and provides typed access for synthesis, editorial, discovery, and extraction services.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "domain_synthesis_config.yaml",
)

_cached_raw: Optional[Dict[str, Any]] = None


@dataclass
class TopicFilter:
    exclude_keywords: List[str] = field(default_factory=list)
    exclude_categories: List[str] = field(default_factory=list)
    include_categories: List[str] = field(default_factory=list)


@dataclass
class DomainSynthesisConfig:
    domain_key: str
    focus_areas: List[str] = field(default_factory=list)
    """Cross-cutting themes for topic/storyline alignment (e.g. science-tech: AI, genomics)."""
    macro_subject_axes: List[str] = field(default_factory=list)
    event_type_priorities: List[str] = field(default_factory=list)
    entity_type_weights: Dict[str, float] = field(default_factory=dict)
    storyline_patterns: List[str] = field(default_factory=list)
    editorial_sections: List[str] = field(default_factory=list)
    topic_filter: TopicFilter = field(default_factory=TopicFilter)
    llm_context: str = ""

    # Defaults (overridable per-domain in the YAML)
    max_articles_per_synthesis: int = 50
    max_entities_per_synthesis: int = 30
    min_article_confidence: float = 0.3
    clustering_similarity_threshold: float = 0.65

    def is_excluded_topic(self, text: str) -> bool:
        """Check whether text matches any exclude keyword (case-insensitive)."""
        lower = text.lower()
        return any(kw in lower for kw in self.topic_filter.exclude_keywords)

    def entity_weight(self, entity_type: str) -> float:
        return self.entity_type_weights.get(entity_type, 0.5)

    def prioritised_event_types(self) -> List[str]:
        return list(self.event_type_priorities)


def _load_raw() -> Dict[str, Any]:
    global _cached_raw
    if _cached_raw is not None:
        return _cached_raw
    try:
        with open(_CONFIG_PATH, "r") as fh:
            _cached_raw = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.error("Domain synthesis config not found at %s", _CONFIG_PATH)
        _cached_raw = {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse domain synthesis config: %s", exc)
        _cached_raw = {}
    return _cached_raw


def reload_config() -> None:
    """Force re-read from disk (useful after hot-editing the YAML)."""
    global _cached_raw
    _cached_raw = None
    _load_raw()


def _normalise_domain_key(domain_key: str) -> str:
    """Accept 'science_tech', 'science-tech', 'sciencetech' → 'science-tech'."""
    k = domain_key.lower().strip().replace("_", "-")
    if k in ("sciencetech", "science tech"):
        return "science-tech"
    return k


def get_domain_synthesis_config(domain_key: str) -> DomainSynthesisConfig:
    """Return a typed DomainSynthesisConfig for the given domain.

    Falls back to defaults for unknown domains so callers never get None.
    """
    raw = _load_raw()
    defaults = raw.get("defaults", {})
    norm_key = _normalise_domain_key(domain_key)
    domain_raw = (raw.get("domains") or {}).get(norm_key, {})

    tf_raw = domain_raw.get("topic_filter", {})
    topic_filter = TopicFilter(
        exclude_keywords=[k.lower() for k in (tf_raw.get("exclude_keywords") or [])],
        exclude_categories=[c.lower() for c in (tf_raw.get("exclude_categories") or [])],
        include_categories=[c.lower() for c in (tf_raw.get("include_categories") or [])],
    )

    return DomainSynthesisConfig(
        domain_key=norm_key,
        focus_areas=domain_raw.get("focus_areas", []),
        macro_subject_axes=list(domain_raw.get("macro_subject_axes") or []),
        event_type_priorities=domain_raw.get("event_type_priorities", []),
        entity_type_weights=domain_raw.get("entity_type_weights", {}),
        storyline_patterns=domain_raw.get("storyline_patterns", []),
        editorial_sections=domain_raw.get("editorial_sections", []),
        topic_filter=topic_filter,
        llm_context=(domain_raw.get("llm_context") or "").strip(),
        max_articles_per_synthesis=domain_raw.get(
            "max_articles_per_synthesis",
            defaults.get("max_articles_per_synthesis", 50),
        ),
        max_entities_per_synthesis=domain_raw.get(
            "max_entities_per_synthesis",
            defaults.get("max_entities_per_synthesis", 30),
        ),
        min_article_confidence=domain_raw.get(
            "min_article_confidence",
            defaults.get("min_article_confidence", 0.3),
        ),
        clustering_similarity_threshold=domain_raw.get(
            "clustering_similarity_threshold",
            defaults.get("clustering_similarity_threshold", 0.65),
        ),
    )
