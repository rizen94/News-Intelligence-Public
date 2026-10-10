"""Membership mode — single policy enum derived from existing v12 flags."""

from __future__ import annotations

from enum import Enum


class MembershipMode(str, Enum):
    """How article→episode membership writes are routed."""

    LEGACY_BAG = "legacy_bag"
    EPISODE_EEL = "episode_eel"
    EPISODE_EEL_DUAL_WRITE = "episode_eel_dual_write"


def get_membership_mode() -> MembershipMode:
    """Derive mode from episode assembly + dual-write env (no new flags)."""
    try:
        from shared.episode_attach_gate import episode_container_assembly_enabled
        from shared.assembly_link_funnel import storyline_articles_dual_write_enabled

        if episode_container_assembly_enabled():
            if storyline_articles_dual_write_enabled():
                return MembershipMode.EPISODE_EEL_DUAL_WRITE
            return MembershipMode.EPISODE_EEL
    except Exception:
        pass
    return MembershipMode.LEGACY_BAG


def bag_writes_allowed() -> bool:
    """True when storyline_articles rows may be inserted."""
    mode = get_membership_mode()
    return mode in (MembershipMode.LEGACY_BAG, MembershipMode.EPISODE_EEL_DUAL_WRITE)
