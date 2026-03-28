#!/usr/bin/env python3
"""
Operator report: context-centric claim extraction and claims→facts pressure.

Shows automation backlog keys (same family as Monitor) plus optional breakdown of
contexts still missing extracted_claims by article domain_key.

Usage (from repo root)::

  PYTHONPATH=api uv run python api/scripts/report_context_claim_pipeline_backlog.py

Env: same DB credentials as other api/scripts (DB_*, or .db_password_widow).
"""

from __future__ import annotations

import os
import sys

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(API_ROOT)
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(API_ROOT, ".env"), override=False)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(PROJECT_ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(PROJECT_ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass


def main() -> int:
    from services.backlog_metrics import get_all_pending_counts
    from services.claim_extraction_service import (
        CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL,
        get_claims_to_facts_min_confidence,
    )
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection (set DB_PASSWORD / DB_HOST).")
        return 1

    pending = get_all_pending_counts()
    keys = (
        "context_sync",
        "content_enrichment",
        "claim_extraction",
        "claims_to_facts",
        "entity_extraction",
        "entity_profile_sync",
    )
    print("=== Pending counts (automation / backlog_metrics) ===")
    for k in keys:
        v = int(pending.get(k) or 0)
        print(f"  {k}: {v:,}")

    min_conf = get_claims_to_facts_min_confidence()
    extra_ign = CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT COALESCE(atc.domain_key::text, '(no article_to_context row)') AS dk,
                       COUNT(DISTINCT c.id) AS n
                FROM intelligence.contexts c
                LEFT JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                GROUP BY 1
                ORDER BY n DESC
                LIMIT 25
                """
            )
            by_dk = cur.fetchall()

            cur.execute(
                """
                SELECT
                  COUNT(*)::bigint AS high_conf_claims,
                  SUM(
                    CASE WHEN NOT EXISTS (
                      SELECT 1 FROM intelligence.versioned_facts vf
                      WHERE vf.metadata->>'source_claim_id' = ec.id::text
                    ) THEN 1 ELSE 0 END
                  )::bigint AS unpromoted
                FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= %s
                """
                + extra_ign,
                (min_conf,),
            )
            prom_row = cur.fetchone()
    finally:
        conn.close()

    print()
    print("=== Contexts with zero extracted_claims (by domain_key on article_to_context) ===")
    if not by_dk:
        print("  (none or query failed)")
    else:
        for dk, n in by_dk:
            print(f"  {dk}: {int(n):,}")

    print()
    print(
        f"=== Claims at or above CLAIMS_TO_FACTS_MIN_CONFIDENCE ({min_conf}) "
        "not yet in versioned_facts (respects gap-catalog ignore SQL) ==="
    )
    if prom_row:
        print(f"  high-confidence claims (after gap ignore): {int(prom_row[0] or 0):,}")
        print(f"  still without versioned_facts: {int(prom_row[1] or 0):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
