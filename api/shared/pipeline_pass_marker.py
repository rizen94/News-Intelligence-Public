"""
Record one successful pipeline phase attempt per row (articles or intelligence.contexts).

Monitor ``pending`` counts treat terminal states under ``metadata.pipeline.<phase>`` as cleared
only when output is real or legitimately empty — not on errors or suspicious empty outcomes.

Terminal states:
  - ``processed_with_output`` — phase produced intelligence (entities, claims, etc.)
  - ``processed_empty_legitimate`` — genuinely nothing to extract (stub/short/filtered)
  - ``failed_needs_retry`` — attempted but should re-queue (error, timeout, suspicious empty)

Env:
- ``PIPELINE_BACKLOG_USE_PASS_MARKERS`` — default ``true``
- ``<PHASE>_BACKLOG_USE_PASS_MARKER`` — per-phase override
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

TERMINAL_PROCESSED_WITH_OUTPUT = "processed_with_output"
TERMINAL_PROCESSED_EMPTY_LEGITIMATE = "processed_empty_legitimate"
TERMINAL_FAILED_NEEDS_RETRY = "failed_needs_retry"

CLEARED_TERMINAL_STATES: frozenset[str] = frozenset(
    {TERMINAL_PROCESSED_WITH_OUTPUT, TERMINAL_PROCESSED_EMPTY_LEGITIMATE}
)

# Legacy outcomes that cleared backlog without terminal_state — reconciliation targets.
LEGACY_FALSE_CLEAR_OUTCOMES: frozenset[str] = frozenset(
    {
        "no_entities_stored",
        "no_claims_after_filters",
    }
)

# Outcomes that map to legitimate empty when terminal_state was not set (migration helper).
LEGITIMATE_EMPTY_OUTCOMES: frozenset[str] = frozenset(
    {
        "skipped_short_text",
        "parsed_empty",
        "no_entities_stored",  # only when content below threshold at record time
        "signal_deferred",
    }
)


def _norm_phase(phase: str) -> str:
    return (phase or "").strip().lower().replace("-", "_")


def phase_backlog_uses_pass_marker(phase: str) -> bool:
    """Whether backlog_metrics / selection SQL should filter by terminal pass state."""
    p = _norm_phase(phase)
    explicit = env_str(f"{p.upper()}_BACKLOG_USE_PASS_MARKER", "").strip()
    if explicit:
        return explicit.lower() in ("1", "true", "yes")
    return env_str("PIPELINE_BACKLOG_USE_PASS_MARKERS", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _pipe_json_path(phase: str, alias: str, table: str = "article") -> str:
    """JSON path to metadata.pipeline.<phase> for SQL fragments."""
    p = _norm_phase(phase)
    if table == "context":
        base = f"(COALESCE({alias}.metadata::jsonb, '{{}}'::jsonb))->'pipeline'->'{p}'"
    else:
        base = f"{alias}.metadata::jsonb->'pipeline'->'{p}'"
    return base


def sql_article_first_pass_only(phase: str, alias: str = "a") -> str:
    """SQL fragment: article has never recorded a pass for ``phase``."""
    pipe = _pipe_json_path(phase, alias, "article")
    return f"({pipe}->>'last_pass_at') IS NULL"


def sql_article_retry_pending(phase: str, alias: str = "a") -> str:
    """SQL fragment: article was attempted for ``phase`` but still needs another pass."""
    pipe = _pipe_json_path(phase, alias, "article")
    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    legacy = "', '".join(sorted(LEGACY_FALSE_CLEAR_OUTCOMES))
    return f"""(
        ({pipe}->>'last_pass_at') IS NOT NULL
        AND (
            COALESCE({pipe}->>'last_terminal_state', '') = '{TERMINAL_FAILED_NEEDS_RETRY}'
            OR (
                COALESCE({pipe}->>'last_terminal_state', '') NOT IN ('{cleared}')
                AND (
                    ({pipe}->>'last_terminal_state') IS NOT NULL
                    OR ({pipe}->>'last_outcome') IN ('{legacy}')
                )
            )
        )
    )"""


def sql_context_first_pass_only(phase: str, alias: str = "c") -> str:
    pipe = _pipe_json_path(phase, alias, "context")
    return f"({pipe}->>'last_pass_at') IS NULL"


def sql_context_retry_pending(phase: str, alias: str = "c") -> str:
    pipe = _pipe_json_path(phase, alias, "context")
    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    legacy = "', '".join(sorted(LEGACY_FALSE_CLEAR_OUTCOMES))
    return f"""(
        ({pipe}->>'last_pass_at') IS NOT NULL
        AND (
            COALESCE({pipe}->>'last_terminal_state', '') = '{TERMINAL_FAILED_NEEDS_RETRY}'
            OR (
                COALESCE({pipe}->>'last_terminal_state', '') NOT IN ('{cleared}')
                AND (
                    ({pipe}->>'last_terminal_state') IS NOT NULL
                    OR ({pipe}->>'last_outcome') IN ('{legacy}')
                )
            )
        )
    )"""


def sql_article_pass_null(phase: str, alias: str = "a") -> str:
    """SQL fragment: article still needs processing for ``phase``."""
    pipe = _pipe_json_path(phase, alias, "article")
    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    legacy = "', '".join(sorted(LEGACY_FALSE_CLEAR_OUTCOMES))
    return f"""(
        ({pipe}->>'last_pass_at') IS NULL
        OR COALESCE({pipe}->>'last_terminal_state', '') = '{TERMINAL_FAILED_NEEDS_RETRY}'
        OR (
            ({pipe}->>'last_pass_at') IS NOT NULL
            AND COALESCE({pipe}->>'last_terminal_state', '') NOT IN ('{cleared}')
            AND (
                ({pipe}->>'last_terminal_state') IS NOT NULL
                OR ({pipe}->>'last_outcome') IN ('{legacy}')
            )
        )
    )"""


def sql_article_pass_cleared(phase: str, alias: str = "a") -> str:
    """SQL fragment: article has a cleared terminal pass for ``phase``."""
    pipe = _pipe_json_path(phase, alias, "article")
    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    return f"COALESCE({pipe}->>'last_terminal_state', '') IN ('{cleared}')"


def sql_context_pass_cleared(phase: str, alias: str = "c") -> str:
    """SQL fragment: context has a cleared terminal pass for ``phase``."""
    pipe = _pipe_json_path(phase, alias, "context")
    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    return f"COALESCE({pipe}->>'last_terminal_state', '') IN ('{cleared}')"


def sql_context_pass_null(phase: str, alias: str = "c") -> str:
    """SQL fragment: context still needs processing for ``phase``."""
    pipe = _pipe_json_path(phase, alias, "context")
    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    legacy = "', '".join(sorted(LEGACY_FALSE_CLEAR_OUTCOMES))
    return f"""(
        ({pipe}->>'last_pass_at') IS NULL
        OR COALESCE({pipe}->>'last_terminal_state', '') = '{TERMINAL_FAILED_NEEDS_RETRY}'
        OR (
            ({pipe}->>'last_pass_at') IS NOT NULL
            AND COALESCE({pipe}->>'last_terminal_state', '') NOT IN ('{cleared}')
            AND (
                ({pipe}->>'last_terminal_state') IS NOT NULL
                OR ({pipe}->>'last_outcome') IN ('{legacy}')
            )
        )
    )"""


def infer_entity_extraction_terminal(
    *,
    entities_count: int,
    content_length: int,
    success: bool,
) -> tuple[str, str]:
    """Return (terminal_state, outcome) for entity extraction."""
    if not success:
        return TERMINAL_FAILED_NEEDS_RETRY, "extraction_failed"
    if entities_count > 0:
        return TERMINAL_PROCESSED_WITH_OUTPUT, "entities_stored"
    short_threshold = int(env_str("ENTITY_EXTRACTION_LEGITIMATE_EMPTY_MAX_CHARS", "400"))
    if content_length < short_threshold:
        return TERMINAL_PROCESSED_EMPTY_LEGITIMATE, "no_entities_stored"
    return TERMINAL_FAILED_NEEDS_RETRY, "no_entities_stored"


def infer_claim_extraction_terminal(*, inserted: int, outcome_hint: str) -> tuple[str, str]:
    """Return (terminal_state, outcome) for claim extraction."""
    if inserted > 0:
        return TERMINAL_PROCESSED_WITH_OUTPUT, "claims_inserted"
    if outcome_hint in ("skipped_short_text", "parsed_empty"):
        return TERMINAL_PROCESSED_EMPTY_LEGITIMATE, outcome_hint
    return TERMINAL_FAILED_NEEDS_RETRY, outcome_hint or "no_claims_after_filters"


def infer_event_extraction_terminal(
    *,
    events_count: int,
    content_length: int,
    success: bool,
) -> tuple[str, str]:
    """Return (terminal_state, outcome) for event extraction."""
    if not success:
        return TERMINAL_FAILED_NEEDS_RETRY, "extraction_failed"
    if events_count > 0:
        return TERMINAL_PROCESSED_WITH_OUTPUT, "timeline_saved"
    short_threshold = int(env_str("EVENT_EXTRACTION_LEGITIMATE_EMPTY_MAX_CHARS", "400"))
    if content_length < short_threshold:
        return TERMINAL_PROCESSED_EMPTY_LEGITIMATE, "no_events_stored"
    return TERMINAL_FAILED_NEEDS_RETRY, "no_events_stored"


def infer_relationship_extraction_terminal(*, pairs_materialized: int, profile_count: int) -> tuple[str, str]:
    """Return (terminal_state, outcome) for relationship extraction from a context."""
    if pairs_materialized > 0:
        return TERMINAL_PROCESSED_WITH_OUTPUT, "relationships_materialized"
    if profile_count < 2:
        return TERMINAL_PROCESSED_EMPTY_LEGITIMATE, "no_co_mentions"
    return TERMINAL_PROCESSED_EMPTY_LEGITIMATE, "no_resolvable_entities"


def record_article_phase_pass(
    schema: str,
    article_id: int,
    phase: str,
    outcome: str,
    terminal_state: str | None = None,
) -> None:
    """Merge pass marker under ``metadata.pipeline.<phase>`` for a domain article."""
    p = _norm_phase(phase)
    iso = datetime.now(timezone.utc).isoformat()
    ts = terminal_state or TERMINAL_PROCESSED_WITH_OUTPUT
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET metadata =
                    COALESCE(metadata, '{{}}'::jsonb)
                    || jsonb_build_object(
                        'pipeline',
                        COALESCE(metadata->'pipeline', '{{}}'::jsonb)
                        || jsonb_build_object(
                            '{p}',
                            COALESCE(metadata->'pipeline'->'{p}', '{{}}'::jsonb)
                            || jsonb_build_object(
                                'last_pass_at', to_jsonb(%s::text),
                                'last_outcome', to_jsonb(%s::text),
                                'last_terminal_state', to_jsonb(%s::text)
                            )
                        )
                    )
                WHERE id = %s
                """,
                (iso, outcome, ts, article_id),
            )
        conn.commit()
    except Exception as e:
        logger.debug("record_article_phase_pass %s/%s/%s: %s", schema, article_id, phase, e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def bulk_record_article_phase_pass(
    schema: str,
    article_ids: list[int],
    phase: str,
    outcome: str,
    terminal_state: str | None = None,
) -> None:
    """Set pass marker for many articles."""
    if not article_ids:
        return
    p = _norm_phase(phase)
    iso = datetime.now(timezone.utc).isoformat()
    ts = terminal_state or TERMINAL_PROCESSED_WITH_OUTPUT
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET metadata =
                    COALESCE(metadata, '{{}}'::jsonb)
                    || jsonb_build_object(
                        'pipeline',
                        COALESCE(metadata->'pipeline', '{{}}'::jsonb)
                        || jsonb_build_object(
                            '{p}',
                            COALESCE(metadata->'pipeline'->'{p}', '{{}}'::jsonb)
                            || jsonb_build_object(
                                'last_pass_at', to_jsonb(%s::text),
                                'last_outcome', to_jsonb(%s::text),
                                'last_terminal_state', to_jsonb(%s::text)
                            )
                        )
                    )
                WHERE id = ANY(%s)
                """,
                (iso, outcome, ts, article_ids),
            )
        conn.commit()
        try:
            from shared.pipeline_status_store import upsert_pipeline_status

            for aid in article_ids:
                upsert_pipeline_status(
                    schema, int(aid), p, outcome=outcome, terminal_state=ts
                )
        except Exception:
            pass
    except Exception as e:
        logger.debug("bulk_record_article_phase_pass %s: %s", schema, e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def clear_article_phase_pass(schema: str, article_id: int, phase: str) -> None:
    """Remove pass marker so article re-enters backlog (reconciliation)."""
    p = _norm_phase(phase)
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET metadata = (COALESCE(metadata, '{{}}'::jsonb) #- '{{pipeline,{p}}}')
                WHERE id = %s
                """,
                (article_id,),
            )
        conn.commit()
    except Exception as e:
        logger.debug("clear_article_phase_pass %s/%s: %s", schema, article_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def record_context_phase_pass(
    context_id: int,
    phase: str,
    outcome: str,
    terminal_state: str | None = None,
) -> None:
    """Merge pass marker into ``intelligence.contexts.metadata``."""
    p = _norm_phase(phase)
    iso = datetime.now(timezone.utc).isoformat()
    ts = terminal_state or TERMINAL_PROCESSED_WITH_OUTPUT
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata FROM intelligence.contexts WHERE id = %s",
                (context_id,),
            )
            row = cur.fetchone()
            raw = row[0] if row else None
            md: dict[str, Any] = {}
            if raw is not None:
                if isinstance(raw, dict):
                    md = dict(raw)
                elif isinstance(raw, str):
                    try:
                        md = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        md = {}
                else:
                    try:
                        md = dict(raw)
                    except (TypeError, ValueError):
                        md = {}
            pipe = md.get("pipeline") if isinstance(md.get("pipeline"), dict) else {}
            inner = pipe.get(p, {}) if isinstance(pipe.get(p), dict) else {}
            inner["last_pass_at"] = iso
            inner["last_outcome"] = outcome
            inner["last_terminal_state"] = ts
            pipe[p] = inner
            md["pipeline"] = pipe
            cur.execute(
                """
                UPDATE intelligence.contexts
                SET metadata = %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (json.dumps(md), context_id),
            )
        conn.commit()
    except Exception as e:
        logger.debug("record_context_phase_pass %s/%s: %s", context_id, phase, e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def clear_context_phase_pass(context_id: int, phase: str) -> None:
    """Remove pass marker from context (reconciliation)."""
    p = _norm_phase(phase)
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.contexts
                SET metadata = (COALESCE(metadata::jsonb, '{}'::jsonb) #- %s::text[]),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                ([f"pipeline,{p}"], context_id),
            )
        conn.commit()
    except Exception as e:
        logger.debug("clear_context_phase_pass %s: %s", context_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def bulk_record_context_phase_pass(context_ids: list[int], phase: str, outcome: str) -> None:
    for cid in context_ids:
        record_context_phase_pass(cid, phase, outcome)
