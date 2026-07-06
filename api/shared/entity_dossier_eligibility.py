"""Shared eligibility for entity_dossier_compile (scheduler, backlog, Monitor).

Recompile when:
  - no dossier row exists (first compile), or
  - upstream source data changed after ``compilation_date``, or
  - optional calendar stale when ``ENTITY_DOSSIER_STALE_DAYS`` > 0.

Calendar-only refresh (legacy 7-day rolling queue) is disabled by default (``ENTITY_DOSSIER_STALE_DAYS=0``).
"""

from __future__ import annotations

from functools import lru_cache

from config.runtime import env_int, env_str
from shared.domain_registry import iter_pipeline_url_schema_pairs


def entity_dossier_stale_days() -> int:
    """Optional calendar stale window; 0 disables time-based re-queue."""
    raw = env_str("ENTITY_DOSSIER_STALE_DAYS", "0").strip()
    try:
        return max(0, min(3650, int(raw)))
    except ValueError:
        return 0


def _date_after_compile(column: str, ed_alias: str = "ed") -> str:
    """True when ``column`` (timestamptz/date) is after dossier ``compilation_date``."""
    return f"({column})::date > {ed_alias}.compilation_date"


@lru_cache(maxsize=1)
def _sql_new_articles_since_compile(ep_alias: str, ed_alias: str) -> str:
    branches: list[str] = []
    for domain_key, schema_name in iter_pipeline_url_schema_pairs():
        dk = domain_key.replace("'", "''")
        branches.append(
            f"""(
                {ep_alias}.domain_key = '{dk}'
                AND EXISTS (
                    SELECT 1
                    FROM {schema_name}.article_entities ae
                    JOIN {schema_name}.articles a ON a.id = ae.article_id
                    WHERE ae.canonical_entity_id = {ep_alias}.canonical_entity_id
                      AND {_date_after_compile('COALESCE(a.published_at, a.created_at)', ed_alias)}
                )
            )"""
        )
    if not branches:
        return "FALSE"
    return "(" + " OR ".join(branches) + ")"


def sql_entity_dossier_source_changed_since_compile(
    ep_alias: str = "ep",
    ed_alias: str = "ed",
) -> str:
    """Upstream inputs that ``compile_dossier`` reads changed after last compile."""
    articles = _sql_new_articles_since_compile(ep_alias, ed_alias)
    return f"""(
        EXISTS (
            SELECT 1
            FROM intelligence.context_entity_mentions cem
            WHERE cem.entity_profile_id = {ep_alias}.id
              AND {_date_after_compile('cem.created_at', ed_alias)}
        )
        OR {articles}
        OR EXISTS (
            SELECT 1
            FROM intelligence.entity_relationships er
            WHERE (
                (er.source_domain = {ep_alias}.domain_key AND er.source_entity_id = {ep_alias}.canonical_entity_id)
                OR (er.target_domain = {ep_alias}.domain_key AND er.target_entity_id = {ep_alias}.canonical_entity_id)
            )
              AND {_date_after_compile('COALESCE(er.last_seen_at, er.created_at)', ed_alias)}
        )
        OR EXISTS (
            SELECT 1
            FROM intelligence.entity_positions pos
            WHERE pos.domain_key = {ep_alias}.domain_key
              AND pos.entity_id = {ep_alias}.canonical_entity_id
              AND {_date_after_compile('pos.created_at', ed_alias)}
        )
    )"""


def sql_entity_dossier_calendar_stale(ed_alias: str = "ed") -> str:
    days = entity_dossier_stale_days()
    if days <= 0:
        return "FALSE"
    return f"({ed_alias}.compilation_date < CURRENT_DATE - INTERVAL '{int(days)} days')"


def sql_entity_dossier_needs_compile(
    ep_alias: str = "ep",
    ed_alias: str = "ed",
) -> str:
    """Full pending predicate for entity_dossier_compile."""
    source_changed = sql_entity_dossier_source_changed_since_compile(ep_alias, ed_alias)
    calendar = sql_entity_dossier_calendar_stale(ed_alias)
    return f"""(
        {ed_alias}.id IS NULL
        OR {source_changed}
        OR {calendar}
    )"""


def sql_entity_dossier_refresh_since_compile(
    ep_alias: str = "ep",
    ed_alias: str = "ed",
) -> str:
    """Existing dossier that needs refresh (excludes first-time compile)."""
    source_changed = sql_entity_dossier_source_changed_since_compile(ep_alias, ed_alias)
    calendar = sql_entity_dossier_calendar_stale(ed_alias)
    return f"""(
        {ed_alias}.id IS NOT NULL
        AND ({source_changed} OR {calendar})
    )"""
