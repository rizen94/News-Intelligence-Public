"""
Hard caps on storyline membership size.

Chemistry kinds (evidence_thread / research_topic / matter_docket) must stay
entity- or matter-scoped — not geopolitics-style mega bags. Soft membership
review was skipping medicine/AI/legal, which let ILIKE absorb grow to thousands
of unrelated articles.
"""

from __future__ import annotations

from config.runtime import env_int


# Default max members for evidence/research/docket proteins.
_CHEMISTRY_MEMBER_CAP_DEFAULT = 48
# Politics/finance narrative megas still use HITL suggest-only above this.
_NARRATIVE_HITL_CAP_DEFAULT = 150


def chemistry_member_cap(domain_key: str | None = None) -> int:
    """Max storyline_articles for chemistry-kind domains before attach is blocked."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        if domain_key:
            cfg = get_domain_synthesis_config(domain_key)
            profile = cfg.link_score_profile
            if getattr(profile, "max_member_articles", None):
                return max(8, int(profile.max_member_articles))
            if cfg.is_chemistry_kind():
                return max(8, env_int("STORYLINE_CHEMISTRY_MEMBER_CAP", _CHEMISTRY_MEMBER_CAP_DEFAULT))
    except Exception:
        pass
    return max(8, env_int("STORYLINE_CHEMISTRY_MEMBER_CAP", _CHEMISTRY_MEMBER_CAP_DEFAULT))


def narrative_hitl_cap() -> int:
    return max(50, env_int("STORYLINE_ATTACH_HITL_CAP", _NARRATIVE_HITL_CAP_DEFAULT))


def attach_hard_cap(domain_key: str) -> int:
    """
    Absolute size at which silent auto-add is forbidden (suggest-only / skip).

    Chemistry kinds use the lower evidence-thread cap; narrative domains keep HITL cap.
    """
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        if get_domain_synthesis_config(domain_key).is_chemistry_kind():
            return chemistry_member_cap(domain_key)
    except Exception:
        pass
    return narrative_hitl_cap()


def storyline_at_or_over_attach_cap(domain_key: str, article_count: int) -> bool:
    return int(article_count or 0) >= attach_hard_cap(domain_key)


def chemistry_oversize_needs_prune(domain_key: str, article_count: int) -> bool:
    """True when a chemistry protein has grown past the evidence-thread member cap."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        if not get_domain_synthesis_config(domain_key).is_chemistry_kind():
            return False
    except Exception:
        return False
    return int(article_count or 0) > chemistry_member_cap(domain_key)
