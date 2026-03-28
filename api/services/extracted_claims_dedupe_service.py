"""
Deduplicate ``intelligence.extracted_claims`` rows that share the same context and
normalized subject/predicate/object. Keeps highest confidence (then lowest id).
Skips rows referenced by ``versioned_facts.metadata.source_claim_id``.

Used by ``scripts/merge_duplicate_extracted_claims.py`` and AutomationManager phase
``extracted_claims_dedupe``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def count_duplicate_extracted_claim_rows() -> int:
    """Rows that would be removed (rn > 1 in partition), excluding versioned_fact-backed ids."""
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute(
                """
                WITH ranked AS (
                  SELECT ec.id,
                    ROW_NUMBER() OVER (
                      PARTITION BY ec.context_id,
                        lower(trim(COALESCE(ec.subject_text, ''))),
                        lower(trim(COALESCE(ec.predicate_text, ''))),
                        lower(trim(COALESCE(ec.object_text, '')))
                      ORDER BY ec.confidence DESC, ec.id ASC
                    ) AS rn
                  FROM intelligence.extracted_claims ec
                  WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.versioned_facts vf
                    WHERE vf.metadata->>'source_claim_id' = ec.id::text
                  )
                )
                SELECT COUNT(*)::bigint FROM ranked WHERE rn > 1
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("count_duplicate_extracted_claim_rows: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def delete_duplicate_extracted_claims_batch(batch_size: int) -> int:
    """Delete up to ``batch_size`` duplicate rows; returns number deleted."""
    bs = max(100, min(50_000, int(batch_size)))
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute(
                """
                WITH ranked AS (
                  SELECT ec.id,
                    ROW_NUMBER() OVER (
                      PARTITION BY ec.context_id,
                        lower(trim(COALESCE(ec.subject_text, ''))),
                        lower(trim(COALESCE(ec.predicate_text, ''))),
                        lower(trim(COALESCE(ec.object_text, '')))
                      ORDER BY ec.confidence DESC, ec.id ASC
                    ) AS rn
                  FROM intelligence.extracted_claims ec
                  WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.versioned_facts vf
                    WHERE vf.metadata->>'source_claim_id' = ec.id::text
                  )
                ),
                to_remove AS (
                  SELECT id FROM ranked WHERE rn > 1 LIMIT %s
                )
                DELETE FROM intelligence.extracted_claims ec
                WHERE ec.id IN (SELECT id FROM to_remove)
                """,
                (bs,),
            )
            n = cur.rowcount or 0
        conn.commit()
        return int(n)
    except Exception as e:
        logger.warning("delete_duplicate_extracted_claims_batch: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_dedupe_cycle() -> dict[str, Any]:
    """
    Delete duplicates in bounded batches (one automation tick).

    Env:
      EXTRACTED_CLAIMS_DEDUPE_BATCH_SIZE (default 8000)
      EXTRACTED_CLAIMS_DEDUPE_MAX_BATCHES (default 5, 0 = unlimited until empty)
    """
    try:
        batch = int(os.environ.get("EXTRACTED_CLAIMS_DEDUPE_BATCH_SIZE", "8000"))
    except ValueError:
        batch = 8000
    try:
        max_batches = int(os.environ.get("EXTRACTED_CLAIMS_DEDUPE_MAX_BATCHES", "5"))
    except ValueError:
        max_batches = 5

    before = count_duplicate_extracted_claim_rows()
    deleted_total = 0
    batches = 0
    while True:
        if max_batches > 0 and batches >= max_batches:
            break
        n = delete_duplicate_extracted_claims_batch(batch)
        batches += 1
        deleted_total += n
        if n == 0:
            break

    after = count_duplicate_extracted_claim_rows()
    out = {
        "success": True,
        "duplicates_before": before,
        "deleted": deleted_total,
        "batches_run": batches,
        "duplicates_after": after,
    }
    if deleted_total:
        logger.info(
            "extracted_claims dedupe: deleted=%s batches=%s remaining_dup_estimate=%s",
            deleted_total,
            batches,
            after,
        )
    return out
