"""
Versioned facts lifecycle — verification writeback and near-duplicate supersession.

Phase 3 handoff: closes the loop between fact_verification (read-only) and
intelligence.versioned_facts (append-only promote path). All flags are env-gated.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _fact_ids_for_claim(cur, claim_id: int) -> list[int]:
    """versioned_facts rows whose metadata references this extracted_claim id."""
    cid = str(int(claim_id))
    cur.execute(
        """
        SELECT vf.id
        FROM intelligence.versioned_facts vf
        WHERE vf.metadata->>'source_claim_id' = %s
           OR vf.metadata->'source_claim_ids' ? %s
        """,
        (cid, cid),
    )
    return [int(r[0]) for r in cur.fetchall()]


def writeback_verification_for_claim(
    claim_id: int,
    verification: dict[str, Any],
) -> int:
    """
    Merge verification fields into versioned_facts.metadata for facts promoted from claim_id.
    Returns number of fact rows updated.
    """
    if not verification.get("success"):
        return 0
    conn = get_db_connection()
    if not conn:
        return 0
    payload = {
        "verification_status": verification.get("verification_status"),
        "verification_confidence": verification.get("verification_confidence"),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "corroboration_status": (verification.get("corroboration") or {}).get("status"),
        "reference_boosts": verification.get("reference_boosts") or [],
    }
    updated = 0
    try:
        with conn.cursor() as cur:
            fact_ids = _fact_ids_for_claim(cur, claim_id)
            for fid in fact_ids:
                cur.execute(
                    """
                    UPDATE intelligence.versioned_facts vf
                    SET metadata = COALESCE(vf.metadata, '{}'::jsonb) || %s::jsonb
                    WHERE vf.id = %s
                      AND (vf.metadata->>'superseded_by_fact_id') IS NULL
                    """,
                    (json.dumps(payload), fid),
                )
                updated += max(0, cur.rowcount or 0)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("writeback_verification_for_claim claim=%s: %s", claim_id, e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
    return updated


def writeback_verification_batch(verify_results: list[dict[str, Any]]) -> dict[str, int]:
    """Apply writeback for each entry with claim_id + verification payload."""
    if not _env_bool("FACT_VERIFICATION_WRITEBACK_ENABLED", False):
        return {"skipped": 1, "facts_updated": 0}
    total = 0
    for row in verify_results:
        cid = row.get("claim_id")
        if cid is None:
            continue
        if row.get("verification_status") is not None:
            verification = {
                "success": True,
                "verification_status": row.get("status") or row.get("verification_status"),
                "verification_confidence": row.get("confidence")
                or row.get("verification_confidence"),
                "corroboration": {"status": row.get("corroboration_status")},
                "reference_boosts": row.get("reference_boosts") or [],
            }
        else:
            verification = row
        total += writeback_verification_for_claim(int(cid), verification)
    return {"facts_updated": total}


def supersede_near_duplicate_versioned_facts(batch_size: int | None = None) -> int:
    """
    Mark duplicate facts (same entity_profile_id + normalized fact_text) as superseded.
    Keeps highest confidence (then lowest id). Does not DELETE rows.
    """
    if not _env_bool("VERSIONED_FACTS_SUPERSESSION_ENABLED", False):
        return 0
    bs = batch_size
    if bs is None:
        try:
            bs = int(env_str("VERSIONED_FACTS_SUPERSESSION_BATCH_SIZE", "200"))
        except ValueError:
            bs = 200
    bs = max(10, min(2000, int(bs)))

    conn = get_db_connection()
    if not conn:
        return 0
    superseded = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute(
                """
                WITH ranked AS (
                  SELECT vf.id,
                         vf.entity_profile_id,
                         lower(trim(vf.fact_text)) AS fact_norm,
                         ROW_NUMBER() OVER (
                           PARTITION BY vf.entity_profile_id, lower(trim(vf.fact_text))
                           ORDER BY vf.confidence DESC NULLS LAST, vf.id ASC
                         ) AS rn
                  FROM intelligence.versioned_facts vf
                  WHERE (vf.metadata->>'superseded_by_fact_id') IS NULL
                    AND btrim(COALESCE(vf.fact_text, '')) <> ''
                ),
                losers AS (
                  SELECT l.id AS loser_id, k.id AS keeper_id
                  FROM ranked l
                  JOIN ranked k
                    ON k.entity_profile_id = l.entity_profile_id
                   AND k.fact_norm = l.fact_norm
                   AND k.rn = 1
                  WHERE l.rn > 1
                  LIMIT %s
                )
                UPDATE intelligence.versioned_facts vf
                SET metadata = COALESCE(vf.metadata, '{}'::jsonb) || jsonb_build_object(
                      'superseded_by_fact_id', losers.keeper_id::text,
                      'superseded_at', to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                      'is_current', false
                    )
                FROM losers
                WHERE vf.id = losers.loser_id
                """,
                (bs,),
            )
            superseded = max(0, cur.rowcount or 0)
        conn.commit()
        conn.close()
        if superseded:
            logger.info("Superseded %s near-duplicate versioned_facts row(s)", superseded)
    except Exception as e:
        logger.warning("supersede_near_duplicate_versioned_facts: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
    return superseded
