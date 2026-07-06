"""Shared eligibility for entity_profile_build (scheduler, backlog, Monitor).

Rebuild when:
  - profile sections are empty (first build), or
  - new context entity mentions since ``updated_at``, or
  - optional calendar stale when ``ENTITY_PROFILE_STALE_DAYS`` > 0.

Calendar-only refresh (legacy 7-day rolling queue) is disabled by default (``ENTITY_PROFILE_STALE_DAYS=0``).
"""

from __future__ import annotations

from config.runtime import env_str


def entity_profile_stale_days() -> int:
    """Optional calendar stale window; 0 disables time-based re-queue."""
    raw = env_str("ENTITY_PROFILE_STALE_DAYS", "0").strip()
    try:
        return max(0, min(3650, int(raw)))
    except ValueError:
        return 0


def sql_entity_profile_sections_empty(ep_alias: str = "ep") -> str:
    return f"({ep_alias}.sections IS NULL OR {ep_alias}.sections = '[]'::jsonb)"


def sql_entity_profile_source_changed_since_build(ep_alias: str = "ep") -> str:
    """New context mentions since the profile was last built."""
    return f"""EXISTS (
        SELECT 1
        FROM intelligence.context_entity_mentions cem
        WHERE cem.entity_profile_id = {ep_alias}.id
          AND cem.created_at > COALESCE({ep_alias}.updated_at, '1970-01-01'::timestamptz)
    )"""


def sql_entity_profile_calendar_stale(ep_alias: str = "ep") -> str:
    days = entity_profile_stale_days()
    if days <= 0:
        return "FALSE"
    return f"({ep_alias}.updated_at < NOW() - INTERVAL '{int(days)} days')"


def sql_entity_profile_needs_build(ep_alias: str = "ep") -> str:
    """Full pending predicate for entity_profile_build."""
    empty = sql_entity_profile_sections_empty(ep_alias)
    changed = sql_entity_profile_source_changed_since_build(ep_alias)
    calendar = sql_entity_profile_calendar_stale(ep_alias)
    return f"(({empty}) OR ({changed}) OR ({calendar}))"


def sql_entity_profile_refresh_since_build(ep_alias: str = "ep") -> str:
    """Existing profile needing refresh (excludes first-time empty sections)."""
    empty = sql_entity_profile_sections_empty(ep_alias)
    changed = sql_entity_profile_source_changed_since_build(ep_alias)
    calendar = sql_entity_profile_calendar_stale(ep_alias)
    return f"(NOT ({empty}) AND ({changed} OR {calendar}))"
