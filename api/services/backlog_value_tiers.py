"""
Value-tiered pending counts for Monitor (Bucket A).

Tiers (per phase, best-effort under statement_timeout):
  - hot: high-signal / SLO-relevant subset of actionable
  - actionable: matches automation selection (same as pending_records)
  - long_tail: eligible-shaped work held by admission gates (not scheduled)
  - deferred: signal_deferred / pass-marked skip (not LLM work)
  - inventory: reserved (avoid full-table inventory COUNTs on the Monitor path)

``pending_records`` on Monitor remains the actionable count. Tiers explain the rest.
Keep queries cheap: reuse backlog_metrics counters; optional extras fail soft.
"""

from __future__ import annotations

import logging
from typing import Any

api.shared.backlog_selection_contracts import BACKLOG_SELECTION_CONTRACTS, assert_backlog_contracts
api.shared.database import get_db_connection

logger = logging.getLogger(__name__)


def _conn():
    try:
        return get_db_connection()
    except Exception:
        return None


def _tiers_entity_profile_build() -> dict[str, int]:
    from services.backlog_metrics import _count_entity_profile_build_backlog
    api.shared.entity_profile_eligibility import (
        entity_profile_build_min_mentions,
        sql_entity_profile_needs_build,
        sql_entity_profile_sections_empty,
    )
    api.shared.pipeline_domain_sql import pipeline_domain_any_sql

    actionable = int(_count_entity_profile_build_backlog() or 0)
    out = {
        "hot": 0,
        "actionable": actionable,
        "long_tail": 0,
        "deferred": 0,
        "inventory": 0,
    }
    conn = _conn()
    if not conn:
        return out
    needs = sql_entity_profile_needs_build("ep")
    empty = sql_entity_profile_sections_empty("ep")
    domain_sql, domain_keys = pipeline_domain_any_sql(
        "ep.domain_key", phase="entity_profile_build"
    )
    if not domain_keys:
        return out
    min_m = entity_profile_build_min_mentions()
    hot_mentions = max(min_m + 2, 10)
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            if actionable > 0:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM intelligence.entity_profiles ep
                    WHERE {domain_sql} AND {needs}
                      AND (
                        EXISTS (
                          SELECT 1 FROM intelligence.context_entity_mentions cem
                          WHERE cem.entity_profile_id = ep.id
                          GROUP BY cem.entity_profile_id
                          HAVING COUNT(*) >= %s
                        )
                        OR EXISTS (
                          SELECT 1 FROM intelligence.versioned_facts vf
                          WHERE vf.entity_profile_id = ep.id
                        )
                      )
                    """,
                    (domain_keys, hot_mentions),
                )
                out["hot"] = int(cur.fetchone()[0] or 0)
            # Cheap held-by-gate: empty sections + fewer than min mentions (no facts).
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.entity_profiles ep
                WHERE {domain_sql}
                  AND {empty}
                  AND EXISTS (
                    SELECT 1 FROM intelligence.context_entity_mentions cem
                    WHERE cem.entity_profile_id = ep.id
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.context_entity_mentions cem
                    WHERE cem.entity_profile_id = ep.id
                    GROUP BY cem.entity_profile_id
                    HAVING COUNT(*) >= %s
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.versioned_facts vf
                    WHERE vf.entity_profile_id = ep.id
                  )
                """,
                (domain_keys, min_m),
            )
            out["long_tail"] = int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("value_tiers entity_profile_build: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out


def _tiers_claim_extraction() -> dict[str, int]:
    """Use the same pending counter as Monitor; avoid full-table total_no_claims COUNT."""
    from services.backlog_metrics import _count_claim_extraction_backlog

    actionable = int(_count_claim_extraction_backlog() or 0)
    deferred = 0
    conn = _conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.contexts c
                    WHERE (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome')
                          = 'signal_deferred'
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.extracted_claims ec
                        WHERE ec.context_id = c.id
                      )
                    """
                )
                deferred = int(cur.fetchone()[0] or 0)
        except Exception as e:
            logger.debug("value_tiers claim deferred: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    return {
        "hot": 0,
        "actionable": actionable,
        "long_tail": 0,
        "deferred": deferred,
        "inventory": 0,
    }


def _tiers_article_phase(phase: str) -> dict[str, int]:
    """Actionable = full-lane pending counter; deferred left 0 (light defer is pass-mark hygiene)."""
    if phase == "entity_extraction":
        from services.backlog_metrics import _count_entity_extraction_pending

        actionable = int(_count_entity_extraction_pending() or 0)
    elif phase == "event_extraction":
        from services.backlog_metrics import _count_event_extraction_pending

        actionable = int(_count_event_extraction_pending() or 0)
    else:
        actionable = 0
    return {
        "hot": 0,
        "actionable": actionable,
        "long_tail": 0,
        "deferred": 0,
        "inventory": 0,
    }


def _tiers_from_pending_counter(counter_name: str) -> dict[str, int]:
    from services import backlog_metrics as bm

    fn = getattr(bm, counter_name, None)
    actionable = int(fn() or 0) if callable(fn) else 0
    return {
        "hot": 0,
        "actionable": actionable,
        "long_tail": 0,
        "deferred": 0,
        "inventory": 0,
    }


_TIER_BUILDERS = {
    "entity_profile_build": _tiers_entity_profile_build,
    "claim_extraction": _tiers_claim_extraction,
    "entity_extraction": lambda: _tiers_article_phase("entity_extraction"),
    "event_extraction": lambda: _tiers_article_phase("event_extraction"),
    "storyline_discovery": lambda: _tiers_from_pending_counter(
        "_count_storyline_discovery_pending"
    ),
    "proactive_detection": lambda: _tiers_from_pending_counter(
        "_count_proactive_detection_pending"
    ),
    "storyline_assembly": lambda: _tiers_from_pending_counter(
        "_count_storyline_assembly_pending"
    ),
    "content_refinement_queue": lambda: _tiers_from_pending_counter(
        "_count_content_refinement_queue_pending"
    ),
}


def get_phase_value_tiers(*, budget_phases: list[str] | None = None) -> dict[str, dict[str, int]]:
    """Return {phase: {tier: count}} for contracted phases (or subset)."""
    wanted = (
        set(budget_phases)
        if budget_phases is not None
        else {c.phase for c in BACKLOG_SELECTION_CONTRACTS}
    )
    out: dict[str, dict[str, int]] = {}
    for phase in wanted:
        builder = _TIER_BUILDERS.get(phase)
        if not builder:
            continue
        try:
            out[phase] = builder()
        except Exception as e:
            logger.warning("get_phase_value_tiers %s: %s", phase, e)
            out[phase] = {
                "hot": 0,
                "actionable": 0,
                "long_tail": 0,
                "deferred": 0,
                "inventory": 0,
            }
    return out


def get_backlog_measurement_bundle() -> dict[str, Any]:
    """Contracts + tiers snapshot for processing_progress / ops."""
    failures = assert_backlog_contracts()
    tiers = get_phase_value_tiers()
    return {
        "contracts_ok": len(failures) == 0,
        "contract_failures": failures,
        "contracts": [
            {
                "phase": c.phase,
                "selection_predicate": c.selection_predicate,
                "value_tiers": list(c.value_tiers),
            }
            for c in BACKLOG_SELECTION_CONTRACTS
        ],
        "tiers_by_phase": tiers,
    }
