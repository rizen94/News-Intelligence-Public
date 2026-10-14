"""Shared eligibility for entity_profile_build (scheduler, backlog, Monitor).

Rebuild when:
  - profile sections are empty (first build), or
  - new context entity mentions since ``updated_at``, or
  - optional calendar stale when ``ENTITY_PROFILE_STALE_DAYS`` > 0,

and the profile clears the mention / hotness gate (see ``ENTITY_PROFILE_BUILD_MIN_MENTIONS``).

Calendar-only refresh (legacy 7-day rolling rebuild) is disabled by default
(``ENTITY_PROFILE_STALE_DAYS=0``). Prefer mention-driven refresh; use a long
stale window only if you intentionally want calendar churn.

Builders also fingerprint the context window fed to the LLM and skip rewrite when
evidence is unchanged (see entity_profile_builder_service).
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


def entity_profile_build_min_mentions() -> int:
    """Minimum context mentions before a profile is worth LLM sections (default 3)."""
    raw = env_str("ENTITY_PROFILE_BUILD_MIN_MENTIONS", "3").strip()
    try:
        return max(1, min(50, int(raw)))
    except ValueError:
        return 3


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


def sql_entity_profile_mention_gate(ep_alias: str = "ep") -> str:
    """Enough mentions, or already tied to a promoted fact."""
    n = entity_profile_build_min_mentions()
    # Prefer EXISTS+HAVING over scalar COUNT(*) — cheaper under backlog COUNT timeouts.
    return f"""(
        EXISTS (
            SELECT 1
            FROM intelligence.context_entity_mentions cem
            WHERE cem.entity_profile_id = {ep_alias}.id
            GROUP BY cem.entity_profile_id
            HAVING COUNT(*) >= {int(n)}
        )
        OR EXISTS (
            SELECT 1 FROM intelligence.versioned_facts vf
            WHERE vf.entity_profile_id = {ep_alias}.id
        )
    )"""


def sql_entity_profile_has_context_mentions(ep_alias: str = "ep") -> str:
    """Builder needs at least one CEM row to load LLM context (fact-only profiles cannot build)."""
    return f"""EXISTS (
        SELECT 1
        FROM intelligence.context_entity_mentions cem
        WHERE cem.entity_profile_id = {ep_alias}.id
    )"""


def sql_entity_profile_needs_build(ep_alias: str = "ep") -> str:
    """Materiality + mention/fact gate (Monitor inventory). Selection adds CEM + optional upstream."""
    empty = sql_entity_profile_sections_empty(ep_alias)
    changed = sql_entity_profile_source_changed_since_build(ep_alias)
    calendar = sql_entity_profile_calendar_stale(ep_alias)
    mention = sql_entity_profile_mention_gate(ep_alias)
    return f"((({empty}) OR ({changed}) OR ({calendar})) AND ({mention}))"


def sql_entity_profile_selectable_for_build(ep_alias: str = "ep") -> str:
    """Matches ``get_entity_profile_ids_to_build`` core filters (needs_build + has CEM).

    Upstream-cleared gate is applied by the builder when enabled — backlog callers
    should append it the same way when ``ENTITY_PROFILE_BUILD_UPSTREAM_GATE`` is on.
    """
    needs = sql_entity_profile_needs_build(ep_alias)
    has_cem = sql_entity_profile_has_context_mentions(ep_alias)
    return f"(({needs}) AND ({has_cem}))"


def sql_entity_profile_refresh_since_build(ep_alias: str = "ep") -> str:
    """Existing profile needing refresh (excludes first-time empty sections)."""
    empty = sql_entity_profile_sections_empty(ep_alias)
    changed = sql_entity_profile_source_changed_since_build(ep_alias)
    calendar = sql_entity_profile_calendar_stale(ep_alias)
    mention = sql_entity_profile_mention_gate(ep_alias)
    return f"(NOT ({empty}) AND ({changed} OR {calendar}) AND ({mention}))"
