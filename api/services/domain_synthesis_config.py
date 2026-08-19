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


def _coerce_str_list(raw: Any) -> list[str]:
    """Normalize YAML focus_areas / patterns: dict items become 'k: v' strings."""
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        if item is None:
            continue
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
            continue
        if isinstance(item, dict):
            for k, v in item.items():
                if v is None or v == "":
                    text = str(k).strip()
                else:
                    text = f"{k}: {v}".strip()
                if text:
                    out.append(text)
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


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
    min_relevance_score: float | None = None
    min_semantic_score: float | None = None
    min_quality_tier: int | None = None


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
class LinkScoreProfile:
    """Per-domain attach-score blend (chemistry model). Weights should sum ~1.0."""

    relevance_weight: float = 0.40
    semantic_weight: float = 0.15
    keyword_weight: float = 0.10
    quality_weight: float = 0.10
    temporal_weight: float = 0.10
    canonical_entity_weight: float = 0.15
    temporal_half_life_days: float = 14.0
    auto_approve_combined: float = 0.75
    aggressive_membership: bool = True
    allow_storyline_merge: bool = True
    # Hard stop for silent attach (chemistry evidence threads default via env/YAML).
    max_member_articles: int | None = None


HUB_FACET_ROLES = frozenset({"who", "what", "where"})


@dataclass(frozen=True)
class HubFacet:
    """High-level who/what/where categorization — never solo Mode B admit keys."""

    key: str
    role: str  # who | what | where
    names: tuple[str, ...] = ()

    def name_set_lower(self) -> frozenset[str]:
        return frozenset(n.strip().lower() for n in self.names if n and str(n).strip())


# Domain protein shapes — keep storylines table; behavior differs by kind.
STORY_KINDS = frozenset(
    {
        "event_narrative",
        "market_regulatory_arc",
        "matter_docket",
        "evidence_thread",
        "research_topic",
    }
)


@dataclass
class DomainSynthesisConfig:
    domain_key: str
    story_kind: str = "event_narrative"
    link_score_profile: LinkScoreProfile = field(default_factory=LinkScoreProfile)
    hub_facets: list[HubFacet] = field(default_factory=list)
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

    def hub_name_set(self) -> frozenset[str]:
        names: set[str] = set()
        for facet in self.hub_facets:
            names |= set(facet.name_set_lower())
        return frozenset(names)

    def match_hub_facet(self, entity_name: str | None) -> HubFacet | None:
        """Return hub facet if entity_name equals or contains a configured hub alias."""
        raw = (entity_name or "").strip().lower()
        if not raw:
            return None
        # Exact alias first
        for facet in self.hub_facets:
            if raw in facet.name_set_lower():
                return facet
        # Short hubs (e.g. "Court") only exact; longer aliases allow containment
        for facet in self.hub_facets:
            for alias in facet.name_set_lower():
                if len(alias) < 5:
                    continue
                if alias in raw or raw in alias:
                    return facet
        return None

    def is_hub_entity_name(self, entity_name: str | None) -> bool:
        return self.match_hub_facet(entity_name) is not None

    def membership_min_shared_non_hub(self) -> int:
        """Chemistry kinds need denser non-hub overlap before silent attach."""
        return 2 if self.is_chemistry_kind() else 1

    def prioritised_event_types(self) -> list[str]:
        return list(self.event_type_priorities)

    def is_chemistry_kind(self) -> bool:
        """Research/evidence/docket kinds prefer loose bonds over hard membership."""
        return self.story_kind in (
            "research_topic",
            "evidence_thread",
            "matter_docket",
        )

    def narrative_prompt_context(self) -> str:
        """Bundle domain LLM context with storyline patterns for title/summary generation."""
        parts: list[str] = []
        if self.llm_context:
            parts.append(self.llm_context.strip())
        parts.append(f"Story kind: {self.story_kind}")
        focus = _coerce_str_list(self.focus_areas)
        if focus:
            parts.append("Focus areas: " + "; ".join(focus[:8]))
        patterns = _coerce_str_list(self.storyline_patterns)
        if patterns:
            label = (
                "Preferred research threads"
                if self.story_kind == "research_topic"
                else "Preferred storyline arcs"
            )
            parts.append(f"{label}: " + "; ".join(patterns[:6]))
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
    """Normalize domain keys without requiring a live DB (domain_registry import)."""
    normalized = (domain_key or "").strip().lower().replace("_", "-")
    try:
        from shared.domain_registry_constants import RETIRED_DOMAIN_KEY_ALIASES

        if normalized in RETIRED_DOMAIN_KEY_ALIASES or normalized in (
            "sciencetech",
            "science tech",
        ):
            return "artificial-intelligence"
    except Exception:
        pass
    return normalized


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
    _mq_raw = auto_dom.get("min_quality_tier", auto_def.get("min_quality_tier"))
    _mr_raw = auto_dom.get("min_relevance_score", auto_def.get("min_relevance_score"))
    _ms_raw = auto_dom.get("min_semantic_score", auto_def.get("min_semantic_score"))
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
        min_relevance_score=float(_mr_raw) if _mr_raw is not None else None,
        min_semantic_score=float(_ms_raw) if _ms_raw is not None else None,
        min_quality_tier=_int(_mq_raw, 3) if _mq_raw is not None else None,
    )
    return StorylineDevelopmentConfig(
        discovery=discovery,
        proactive=proactive,
        consolidation=consolidation,
        narrative=narrative,
        automation=automation,
    )


def _merge_link_score_profile(
    defaults: dict[str, Any],
    domain_raw: dict[str, Any],
) -> LinkScoreProfile:
    def_p = defaults.get("link_score_profile") or {}
    dom_p = domain_raw.get("link_score_profile") or {}
    return LinkScoreProfile(
        relevance_weight=_float(
            dom_p.get("relevance_weight"), _float(def_p.get("relevance_weight"), 0.40)
        ),
        semantic_weight=_float(
            dom_p.get("semantic_weight"), _float(def_p.get("semantic_weight"), 0.15)
        ),
        keyword_weight=_float(
            dom_p.get("keyword_weight"), _float(def_p.get("keyword_weight"), 0.10)
        ),
        quality_weight=_float(
            dom_p.get("quality_weight"), _float(def_p.get("quality_weight"), 0.10)
        ),
        temporal_weight=_float(
            dom_p.get("temporal_weight"), _float(def_p.get("temporal_weight"), 0.10)
        ),
        canonical_entity_weight=_float(
            dom_p.get("canonical_entity_weight"),
            _float(def_p.get("canonical_entity_weight"), 0.15),
        ),
        temporal_half_life_days=_float(
            dom_p.get("temporal_half_life_days"),
            _float(def_p.get("temporal_half_life_days"), 14.0),
        ),
        auto_approve_combined=_float(
            dom_p.get("auto_approve_combined"),
            _float(def_p.get("auto_approve_combined"), 0.75),
        ),
        aggressive_membership=bool(
            dom_p.get(
                "aggressive_membership",
                def_p.get("aggressive_membership", True),
            )
        ),
        allow_storyline_merge=bool(
            dom_p.get(
                "allow_storyline_merge",
                def_p.get("allow_storyline_merge", True),
            )
        ),
        max_member_articles=(
            int(dom_p["max_member_articles"])
            if dom_p.get("max_member_articles") is not None
            else (
                int(def_p["max_member_articles"])
                if def_p.get("max_member_articles") is not None
                else None
            )
        ),
    )


def _merge_hub_facets(
    defaults: dict[str, Any],
    domain_raw: dict[str, Any],
) -> list[HubFacet]:
    """Domain list replaces defaults when present; else use defaults."""
    raw_list = domain_raw.get("hub_facets")
    if raw_list is None:
        raw_list = defaults.get("hub_facets") or []
    out: list[HubFacet] = []
    seen_keys: set[str] = set()
    for item in raw_list or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip().lower()
        if not key or key in seen_keys:
            continue
        role = str(item.get("role") or "what").strip().lower()
        if role not in HUB_FACET_ROLES:
            role = "what"
        names_raw = item.get("names") or []
        names = tuple(
            str(n).strip()
            for n in names_raw
            if n is not None and str(n).strip()
        )
        if not names:
            continue
        seen_keys.add(key)
        out.append(HubFacet(key=key, role=role, names=names))
    return out


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
    kind_raw = str(
        domain_raw.get("story_kind") or defaults.get("story_kind") or "event_narrative"
    ).strip()
    story_kind = kind_raw if kind_raw in STORY_KINDS else "event_narrative"
    link_score_profile = _merge_link_score_profile(defaults, domain_raw)
    hub_facets = _merge_hub_facets(defaults, domain_raw)

    return DomainSynthesisConfig(
        domain_key=norm_key,
        story_kind=story_kind,
        link_score_profile=link_score_profile,
        hub_facets=hub_facets,
        focus_areas=_coerce_str_list(domain_raw.get("focus_areas", [])),
        macro_subject_axes=list(domain_raw.get("macro_subject_axes") or []),
        event_type_priorities=domain_raw.get("event_type_priorities", []),
        entity_type_weights=domain_raw.get("entity_type_weights", {}),
        storyline_patterns=_coerce_str_list(domain_raw.get("storyline_patterns", [])),
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


def get_domain_hub_facets(domain_key: str) -> list[HubFacet]:
    return list(get_domain_synthesis_config(domain_key).hub_facets)


def get_domain_story_kind(domain_key: str) -> str:
    return get_domain_synthesis_config(domain_key).story_kind


def temporal_proximity_score(
    days_apart: float | None,
    *,
    half_life_days: float = 14.0,
) -> float:
    """1.0 = same day; exponential decay by half-life. Missing dates → 1.0 (no penalty)."""
    if days_apart is None:
        return 1.0
    hl = max(0.5, float(half_life_days))
    return max(0.0, min(1.0, 0.5 ** (abs(float(days_apart)) / hl)))


def canonical_entity_jaccard(a: set[int] | set[str], b: set[int] | set[str]) -> float:
    """Jaccard over canonical entity IDs (prefer int); empty sets → 0."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def combined_attach_score(
    domain_key: str,
    *,
    relevance: float = 0.0,
    semantic: float = 0.0,
    keyword: float = 0.0,
    quality: float = 0.5,
    temporal: float = 1.0,
    canonical_jaccard: float = 0.0,
) -> float:
    """Legacy suggestion rank helper — not an episode admit formula.

    Prefer blend_link_score for ranking. Dead YAML relevance/keyword/quality
    weights are ignored; uses temporal + canonical (+ relevance as soft prior).
    """
    profile = get_domain_synthesis_config(domain_key).link_score_profile
    # Rank-only collapse: ignore relevance_weight / keyword_weight / quality_weight / semantic_weight
    tw = float(profile.temporal_weight or 0.1)
    cw = float(profile.canonical_entity_weight or 0.15)
    left = max(0.0, 1.0 - tw - cw)
    score = (
        left * float(relevance or semantic or 0)
        + float(temporal if temporal is not None else 1.0) * tw
        + float(canonical_jaccard or 0) * cw
    )
    return round(max(0.0, min(1.0, score)), 4)