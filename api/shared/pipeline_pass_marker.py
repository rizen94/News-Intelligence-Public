"""
Record one successful pipeline phase attempt per row (articles or intelligence.contexts).

Monitor ``pending`` counts treat ``metadata.pipeline.<phase>.last_pass_at`` as "looked at" so
work does not re-queue forever when outputs are empty or below quality thresholds.

Env:
- ``PIPELINE_BACKLOG_USE_PASS_MARKERS`` — default ``true``; set ``false`` to disable pass
  filtering for phases that consult this module.
- ``<PHASE>_BACKLOG_USE_PASS_MARKER`` — per-phase override (e.g. ``ENTITY_EXTRACTION_BACKLOG_USE_PASS_MARKER``).
  Phase keys use underscores (``claim_extraction``, ``event_tracking``, …).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _norm_phase(phase: str) -> str:
    return (phase or "").strip().lower().replace("-", "_")


def phase_backlog_uses_pass_marker(phase: str) -> bool:
    """Whether backlog_metrics / selection SQL should require ``last_pass_at`` to be unset."""
    p = _norm_phase(phase)
    explicit = os.environ.get(f"{p.upper()}_BACKLOG_USE_PASS_MARKER", "").strip()
    if explicit:
        return explicit.lower() in ("1", "true", "yes")
    return os.environ.get("PIPELINE_BACKLOG_USE_PASS_MARKERS", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def sql_article_pass_null(phase: str, alias: str = "a") -> str:
    """SQL fragment: article has not recorded a pass for ``phase`` (metadata JSONB)."""
    p = _norm_phase(phase)
    return (
        f"({alias}.metadata::jsonb->'pipeline'->'{p}'->>'last_pass_at') IS NULL"
    )


def sql_context_pass_null(phase: str, alias: str = "c") -> str:
    """SQL fragment: context has not recorded a pass for ``phase``."""
    p = _norm_phase(phase)
    return (
        f"((COALESCE({alias}.metadata::jsonb, '{{}}'::jsonb))->'pipeline'->'{p}'->>'last_pass_at') IS NULL"
    )


def record_article_phase_pass(
    schema: str,
    article_id: int,
    phase: str,
    outcome: str,
) -> None:
    """Merge ``last_pass_at`` / ``last_outcome`` under ``metadata.pipeline.<phase>`` for a domain article."""
    p = _norm_phase(phase)
    iso = datetime.now(timezone.utc).isoformat()
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
                                'last_outcome', to_jsonb(%s::text)
                            )
                        )
                    )
                WHERE id = %s
                """,
                (iso, outcome, article_id),
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


def bulk_record_article_phase_pass(schema: str, article_ids: list[int], phase: str, outcome: str) -> None:
    """Set pass marker for many articles (e.g. storyline discovery batch)."""
    if not article_ids:
        return
    p = _norm_phase(phase)
    iso = datetime.now(timezone.utc).isoformat()
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
                                'last_outcome', to_jsonb(%s::text)
                            )
                        )
                    )
                WHERE id = ANY(%s)
                """,
                (iso, outcome, article_ids),
            )
        conn.commit()
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


def record_context_phase_pass(context_id: int, phase: str, outcome: str) -> None:
    """Merge pass marker into ``intelligence.contexts.metadata`` (json/jsonb-safe)."""
    p = _norm_phase(phase)
    iso = datetime.now(timezone.utc).isoformat()
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


def bulk_record_context_phase_pass(context_ids: list[int], phase: str, outcome: str) -> None:
    for cid in context_ids:
        record_context_phase_pass(cid, phase, outcome)
