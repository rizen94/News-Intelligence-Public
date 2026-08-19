"""Shared link ranking score (admit ≠ rank).

``blend_link_score`` ranks candidates only — never admits episode membership.
Admit path is ``episode_attach_gate.allow_event_episode_attach``.
"""

from __future__ import annotations

from config.runtime import env_bool

# Small additive boost when a typed causal edge exists between the pair.
_CAUSAL_BOOST_CAP = 0.06


def blend_link_score(
    *,
    semantic: float,
    entity_jaccard: float = 0.0,
    canonical_jaccard: float = 0.0,
    temporal_proximity: float = 1.0,
    domain_key: str | None = None,
    causal_boost: float = 0.0,
    arc_stage_prior: float | None = None,
) -> float:
    """
    Profile-aware link score → overall confidence in [0, 1].

    Legacy callers (no domain_key): 0.80 semantic + 0.20 name-entity Jaccard.
    With domain_key: load link_score_profile temporal + canonical weights;
    remaining mass split 80/20 semantic / name-entity.
    Optional ``causal_boost`` (0–1) adds up to ``_CAUSAL_BOOST_CAP`` when a
    causal edge exists between the endpoints.
    """
    s = max(0.0, min(1.0, float(semantic)))
    e = max(0.0, min(1.0, float(entity_jaccard)))
    c = max(0.0, min(1.0, float(canonical_jaccard)))
    t = max(
        0.0,
        min(1.0, float(temporal_proximity if temporal_proximity is not None else 1.0)),
    )
    cb = max(0.0, min(1.0, float(causal_boost or 0.0)))

    def _apply_causal(score: float) -> float:
        if cb <= 0:
            return score
        return max(0.0, min(1.0, score + min(_CAUSAL_BOOST_CAP, cb * _CAUSAL_BOOST_CAP)))

    if not domain_key:
        return _apply_causal(max(0.0, min(1.0, 0.80 * s + 0.20 * e)))

    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain_key)
        profile = cfg.link_score_profile
        tw = float(profile.temporal_weight)
        cw = float(profile.canonical_entity_weight)
        aw = 0.0
        a = 0.5
        if arc_stage_prior is not None:
            try:
                from services.arc_stage_service import arc_stage_enabled

                if arc_stage_enabled():
                    aw = 0.05
                    a = max(0.0, min(1.0, float(arc_stage_prior)))
            except Exception:
                aw = 0.0
        left = max(0.05, 1.0 - tw - cw - aw)
        score = left * 0.80 * s + left * 0.20 * e + cw * c + tw * t + aw * a
        if cfg.is_chemistry_kind() and not profile.allow_storyline_merge:
            score = min(score, float(profile.auto_approve_combined) - 0.01)
        return _apply_causal(max(0.0, min(1.0, score)))
    except Exception:
        return _apply_causal(max(0.0, min(1.0, 0.80 * s + 0.20 * e)))


def causal_boost_for_storyline_pair(
    domain_key: str | None,
    storyline_a: int,
    storyline_b: int,
) -> float:
    """Return 0..1 boost weight when an active causal edge links the storylines."""
    try:
        from services.causal_edges_service import has_causal_edge_between

        if has_causal_edge_between(
            "storyline",
            int(storyline_a),
            "storyline",
            int(storyline_b),
            domain_key=domain_key,
        ):
            return 1.0
    except Exception:
        pass
    return 0.0


def auto_republish_enabled() -> bool:
    """Quiet republish of published stories when new members arrive. Default on."""
    return env_bool("NEWS_STORY_AUTO_REPUBLISH", True)
