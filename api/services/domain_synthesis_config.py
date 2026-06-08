"""
Domain Synthesis Configuration Loader

Loads per-domain synthesis config from api/config/domain_synthesis_config.yaml
and provides typed access for synthesis, editorial, discovery, and extraction services.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "domain_synthesis_config.yaml",
)

_cached_raw: dict[str, Any] | None = None


@dataclass
class TopicFilter:
    exclude_keywords: list[str] = field(default_factory=list)
    exclude_categories: list[str] = field(default_factory=list)
    include_categories: list[str] = field(default_factory=list)


@dataclass
class StorylineDiscoveryConfig:
    clustering_similarity_threshold: float = 0.70
    min_cluster_size: int = 3
    semantic_weight: float = 0.85
    entity_weight: float = 0.10
    temporal_weight: float = 0.05


@dataclass
class StorylineProactiveConfig:
    keyword_similarity_threshold: float = 0.30
    min_articles: int = 3
    promote_min_articles: int = 4
    promote_min_confidence: float = 0.55
    lookback_hours: int = 72


@dataclass
class StorylineConsolidationConfig:
    merge_similarity_threshold: float = 0.65
    parent_similarity_threshold: float = 0.50
    min_articles_for_mega: int = 10


@dataclass
class StorylineNarrativeConfig:
    outbreak_keywords: list[str] = field(default_factory=list)
    allow_promote_pair_on_outbreak: bool = False
    credible_source_domains: list[str] = field(default_factory=list)


@dataclass
class StorylineAutomationConfig:
    default_mode: str = "auto_approve"
    assembly_after_enrichment: bool = True
    unlinked_article_threshold: int = 25
    automation_batch_per_assembly: int = 20


@dataclass
class StorylineDevelopmentConfig:
    discovery: StorylineDiscoveryConfig = field(default_factory=StorylineDiscoveryConfig)
    proactive: StorylineProactiveConfig = field(default_factory=StorylineProactiveConfig)
    consolidation: StorylineConsolidationConfig = field(
        default_factory=StorylineConsolidationConfig
    )
    narrative: StorylineNarrativeConfig = field(default_factory=StorylineNarrativeConfig)
    automation: StorylineAutomationConfig = field(default_factory=StorylineAutomationConfig)


@dataclass
class DomainSynthesisConfig:
    domain_key: str
    focus_areas: list[str] = field(default_factory=list)
    macro_subject_axes: list[str] = field(default_factory=list)
    event_type_priorities: list[str] = field(default_factory=list)
    entity_type_weights: dict[str, float] = field(default_factory=dict)
    storyline_patterns: list[str] = field(default_factory=list)
    editorial_sections: list[str] = field(default_factory=list)
    topic_filter: TopicFilter = field(default_factory=TopicFilter)
    llm_context: str = ""
    storyline_development: StorylineDevelopmentConfig = field(
        default_factory=StorylineDevelopmentConfig
    )

    max_articles_per_synthesis: int = 50
    max_entities_per_synthesis: int = 30
    min_article_confidence: float = 0.3

    @property
    def clustering_similarity_threshold(self) -> float:
        return self.storyline_development.discovery.clustering_similarity_threshold

    @property
    def storyline_min_cluster_size(self) -> int:
        return self.storyline_development.discovery.min_cluster_size

    def is_excluded_topic(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in self.topic_filter.exclude_keywords)

    def entity_weight(self, entity_type: str) -> float:
        return self.entity_type_weights.get(entity_type, 0.5)

    def prioritised_event_types(self) -> list[str]:
        return list(self.event_type_priorities)

    def narrative_prompt_context(self) -> str:
        """Bundle domain LLM context with storyline patterns for title/summary generation."""
        parts: list[str] = []
        if self.llm_context:
            parts.append(self.llm_context.strip())
        if self.focus_areas:
            parts.append("Focus areas: " + "; ".join(self.focus_areas[:8]))
        if self.storyline_patterns:
            parts.append(
                "Preferred storyline arcs: " + "; ".join(self.storyline_patterns[:6])
            )
        return "\n".join(parts)


def _load_raw() -> dict[str, Any]:
    global _cached_raw
    if _cached_raw is not None:
        return _cached_raw
    try:
        with open(_CONFIG_PATH) as fh:
            _cached_raw = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.error("Domain synthesis config not found at %s", _CONFIG_PATH)
        _cached_raw = {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse domain synthesis config: %s", exc)
        _cached_raw = {}
    return _cached_raw


def reload_config() -> None:
    global _cached_raw
    _cached_raw = None
    _load_raw()


def _normalise_domain_key(domain_key: str) -> str:
    k = domain_key.lower().strip().replace("_", "-")
    if k in ("sciencetech", "science tech", "science-tech"):
        return "artificial-intelligence"
    return k


def _float(val: Any, default: float) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _int(val: Any, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _merge_storyline_development(
    defaults: dict[str, Any],
    domain_raw: dict[str, Any],
) -> StorylineDevelopmentConfig:
    def_block = defaults.get("storyline_development") or {}
    dom_block = domain_raw.get("storyline_development") or {}
    disc_def = def_block.get("discovery") or {}
    disc_dom = dom_block.get("discovery") or {}
    pro_def = def_block.get("proactive") or {}
    pro_dom = dom_block.get("proactive") or {}
    con_def = def_block.get("consolidation") or {}
    con_dom = dom_block.get("consolidation") or {}
    nar_def = def_block.get("narrative") or {}
    nar_dom = dom_block.get("narrative") or {}
    auto_def = def_block.get("automation") or {}
    auto_dom = dom_block.get("automation") or {}

    # Legacy top-level discovery keys (legal/medicine)
    legacy_sim = domain_raw.get("clustering_similarity_threshold")
    legacy_min = domain_raw.get("storyline_min_cluster_size")
    if legacy_sim is not None and "clustering_similarity_threshold" not in disc_dom:
        disc_dom = {**disc_dom, "clustering_similarity_threshold": legacy_sim}
    if legacy_min is not None and "min_cluster_size" not in disc_dom:
        disc_dom = {**disc_dom, "min_cluster_size": legacy_min}

    discovery = StorylineDiscoveryConfig(
        clustering_similarity_threshold=_float(
            disc_dom.get("clustering_similarity_threshold"),
            _float(
                disc_def.get("clustering_similarity_threshold"),
                _float(defaults.get("clustering_similarity_threshold"), 0.70),
            ),
        ),
        min_cluster_size=_int(
            disc_dom.get("min_cluster_size"),
            _int(
                disc_def.get("min_cluster_size"),
                _int(defaults.get("storyline_min_cluster_size"), 3),
            ),
        ),
        semantic_weight=_float(disc_dom.get("semantic_weight"), _float(disc_def.get("semantic_weight"), 0.85)),
        entity_weight=_float(disc_dom.get("entity_weight"), _float(disc_def.get("entity_weight"), 0.10)),
        temporal_weight=_float(
            disc_dom.get("temporal_weight"), _float(disc_def.get("temporal_weight"), 0.05)
        ),
    )
    proactive = StorylineProactiveConfig(
        keyword_similarity_threshold=_float(
            pro_dom.get("keyword_similarity_threshold"),
            _float(pro_def.get("keyword_similarity_threshold"), 0.30),
        ),
        min_articles=_int(pro_dom.get("min_articles"), _int(pro_def.get("min_articles"), 3)),
        promote_min_articles=_int(
            pro_dom.get("promote_min_articles"), _int(pro_def.get("promote_min_articles"), 4)
        ),
        promote_min_confidence=_float(
            pro_dom.get("promote_min_confidence"),
            _float(pro_def.get("promote_min_confidence"), 0.55),
        ),
        lookback_hours=_int(pro_dom.get("lookback_hours"), _int(pro_def.get("lookback_hours"), 72)),
    )
    consolidation = StorylineConsolidationConfig(
        merge_similarity_threshold=_float(
            con_dom.get("merge_similarity_threshold"),
            _float(con_def.get("merge_similarity_threshold"), 0.65),
        ),
        parent_similarity_threshold=_float(
            con_dom.get("parent_similarity_threshold"),
            _float(con_def.get("parent_similarity_threshold"), 0.50),
        ),
        min_articles_for_mega=_int(
            con_dom.get("min_articles_for_mega"),
            _int(con_def.get("min_articles_for_mega"), 10),
        ),
    )
    outbreak_kw = nar_dom.get("outbreak_keywords") or nar_def.get("outbreak_keywords") or []
    credible = nar_dom.get("credible_source_domains") or nar_def.get("credible_source_domains") or []
    narrative = StorylineNarrativeConfig(
        outbreak_keywords=[str(k).lower() for k in outbreak_kw],
        allow_promote_pair_on_outbreak=bool(
            nar_dom.get(
                "allow_promote_pair_on_outbreak",
                nar_def.get("allow_promote_pair_on_outbreak", False),
            )
        ),
        credible_source_domains=[str(d).lower() for d in credible],
    )
    automation = StorylineAutomationConfig(
        default_mode=str(
            auto_dom.get("default_mode", auto_def.get("default_mode", "auto_approve"))
        ),
        assembly_after_enrichment=bool(
            auto_dom.get(
                "assembly_after_enrichment",
                auto_def.get("assembly_after_enrichment", True),
            )
        ),
        unlinked_article_threshold=_int(
            auto_dom.get("unlinked_article_threshold"),
            _int(auto_def.get("unlinked_article_threshold"), 25),
        ),
        automation_batch_per_assembly=_int(
            auto_dom.get("automation_batch_per_assembly"),
            _int(auto_def.get("automation_batch_per_assembly"), 20),
        ),
    )
    return StorylineDevelopmentConfig(
        discovery=discovery,
        proactive=proactive,
        consolidation=consolidation,
        narrative=narrative,
        automation=automation,
    )


def get_domain_synthesis_config(domain_key: str) -> DomainSynthesisConfig:
    raw = _load_raw()
    defaults = raw.get("defaults", {}) or {}
    norm_key = _normalise_domain_key(domain_key)
    domain_raw = (raw.get("domains") or {}).get(norm_key, {}) or {}

    tf_defaults = defaults.get("topic_filter") or {}
    tf_raw = domain_raw.get("topic_filter") or {}
    base_kw = [k.lower() for k in (tf_defaults.get("exclude_keywords") or [])]
    dom_kw = [k.lower() for k in (tf_raw.get("exclude_keywords") or [])]
    merged_kw = list(dict.fromkeys(base_kw + dom_kw))
    base_cat = [c.lower() for c in (tf_defaults.get("exclude_categories") or [])]
    dom_cat = [c.lower() for c in (tf_raw.get("exclude_categories") or [])]
    merged_cat = list(dict.fromkeys(base_cat + dom_cat))
    topic_filter = TopicFilter(
        exclude_keywords=merged_kw,
        exclude_categories=merged_cat,
        include_categories=[c.lower() for c in (tf_raw.get("include_categories") or [])],
    )

    storyline_development = _merge_storyline_development(defaults, domain_raw)

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
        storyline_development=storyline_development,
        max_articles_per_synthesis=_int(
            domain_raw.get("max_articles_per_synthesis"),
            _int(defaults.get("max_articles_per_synthesis"), 50),
        ),
        max_entities_per_synthesis=_int(
            domain_raw.get("max_entities_per_synthesis"),
            _int(defaults.get("max_entities_per_synthesis"), 30),
        ),
        min_article_confidence=_float(
            domain_raw.get("min_article_confidence"),
            _float(defaults.get("min_article_confidence"), 0.3),
        ),
    )


def get_storyline_development_config(domain_key: str) -> StorylineDevelopmentConfig:
    return get_domain_synthesis_config(domain_key).storyline_development
