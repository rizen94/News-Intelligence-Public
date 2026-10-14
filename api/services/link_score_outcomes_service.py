"""Persist link-score calibration outcomes (Narrative Phase 3)."""

from __future__ import annotations

import json
import logging
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)

_ALLOWED_DECISIONS = frozenset(
    {"accept", "reject", "keep", "demote", "unlink", "quarantine", "other"}
)
_ALLOWED_SOURCES = frozenset(
    {
        "review_agent",
        "editorial",
        "membership",
        "desk",
        "embedding_link",
        "collision",
        "other",
    }
)


def desk_accept_reject_logging_enabled() -> bool:
    """Logging-only desk writeback for training rows. Default true."""
    return env_bool("DESK_ACCEPT_REJECT_LOGGING_ENABLED", True)


def record_link_score_outcome(
    *,
    domain_key: str | None,
    score_parts: dict[str, Any] | None,
    decision: str,
    source: str = "desk",
    proposal_id: int | None = None,
    endpoints: dict[str, Any] | None = None,
) -> int | None:
    """
    Insert one training row. Safe no-op on DB errors (never breaks desk path).
    Returns row id or None.
    """
    dec = (decision or "other").strip().lower()
    if dec not in _ALLOWED_DECISIONS:
        dec = "other"
    src = (source or "other").strip().lower()
    if src not in _ALLOWED_SOURCES:
        src = "other"
    parts = score_parts if isinstance(score_parts, dict) else {}
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.link_score_outcomes (
                        domain_key, score_parts, decision, source,
                        proposal_id, endpoints
                    ) VALUES (%s, %s::jsonb, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        domain_key,
                        json.dumps(parts),
                        dec,
                        src,
                        int(proposal_id) if proposal_id is not None else None,
                        json.dumps(endpoints) if endpoints is not None else None,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.debug("record_link_score_outcome: %s", e)
        return None


def maybe_record_from_evidence(
    *,
    domain_key: str | None,
    evidence: dict[str, Any] | None,
    decision: str,
    source: str,
    proposal_id: int | None = None,
    endpoints: dict[str, Any] | None = None,
) -> int | None:
    """Extract score_parts from edge evidence and persist when present."""
    ev = evidence if isinstance(evidence, dict) else {}
    parts = ev.get("score_parts") if isinstance(ev.get("score_parts"), dict) else {}
    if not parts and isinstance(ev, dict):
        # Legacy flat keys
        for k in ("semantic", "entity", "canonical", "temporal", "causal", "overall"):
            if k in ev and isinstance(ev[k], (int, float)):
                parts[k] = float(ev[k])
    if not parts:
        return None
    return record_link_score_outcome(
        domain_key=domain_key,
        score_parts=parts,
        decision=decision,
        source=source,
        proposal_id=proposal_id,
        endpoints=endpoints,
    )
