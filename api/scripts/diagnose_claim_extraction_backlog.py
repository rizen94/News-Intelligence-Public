#!/usr/bin/env python3
"""
Phase 0 — diagnose claim extraction backlog vs pass markers vs automation selection.

  PYTHONPATH=api uv run python api/scripts/diagnose_claim_extraction_backlog.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_ce_path = _API_ROOT / "services" / "claim_extraction_service.py"
_spec = importlib.util.spec_from_file_location("claim_extraction_service", _ce_path)
assert _spec and _spec.loader
_ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ce)

from shared.database.connection import get_db_connection_context
from services.backlog_metrics import get_all_pending_counts


def main() -> int:
    stats = _ce.get_context_claim_backlog_stats()
    print("=== Context claim backlog breakdown ===")
    print(json.dumps(stats, indent=2))

    strict = sorted(_ce._claim_extraction_strict_seeded_domain_keys())
    print("\n=== Claim extraction env ===")
    print(f"CLAIM_EXTRACTION_REQUIRE_SEEDED_DOMAIN_KEYS: {strict or '(none — all domains)'}")
    print(f"CLAIM_EXTRACTION_BATCH_LIMIT: {_ce.get_claim_extraction_batch_limit()}")
    print(f"CLAIM_EXTRACTION_PARALLEL: {_ce.get_claim_extraction_parallel()}")
    print(f"CLAIMS_TO_FACTS_CHUNK_SIZE: {os.environ.get('CLAIMS_TO_FACTS_CHUNK_SIZE', '50')}")
    print(f"PIPELINE_BACKLOG_USE_PASS_MARKERS: {os.environ.get('PIPELINE_BACKLOG_USE_PASS_MARKERS', 'true')}")

    try:
        pending = get_all_pending_counts()
        print("\n=== Pipeline pending counts (automation selection) ===")
        for phase in (
            "claim_extraction",
            "claims_to_facts",
            "entity_extraction",
            "topic_clustering",
            "event_extraction",
        ):
            print(f"  {phase}: {pending.get(phase, 0)}")
    except Exception as e:
        print(f"\nWARN: could not load backlog_metrics: {e}")

    with get_db_connection_context() as conn:
        if not conn:
            print("\nERROR: no database connection", file=sys.stderr)
            return 1
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                """
            )
            claims_24h = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims
                WHERE created_at >= NOW() - INTERVAL '72 hours'
                """
            )
            claims_72h = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                """
            )
            facts_24h_created = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE ingestion_date >= NOW() - INTERVAL '24 hours'
                """
            )
            facts_24h_ingestion = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE created_at >= NOW() - INTERVAL '72 hours'
                """
            )
            facts_72h = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND extraction_method = 'claim_extraction'
                """
            )
            facts_24h_claim = cur.fetchone()[0]
            cur.execute(
                """
                SELECT c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome' AS outcome,
                       COUNT(*) AS n
                FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                  AND (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_pass_at') IS NOT NULL
                GROUP BY 1
                ORDER BY n DESC
                LIMIT 10
                """
            )
            pass_outcomes = cur.fetchall()
            cur.execute(
                """
                SELECT date_trunc('day', created_at)::date AS day, COUNT(*) AS n
                FROM intelligence.versioned_facts
                WHERE created_at >= NOW() - INTERVAL '72 hours'
                GROUP BY 1
                ORDER BY 1
                """
            )
            facts_by_day = cur.fetchall()

        print("\n=== Throughput ===")
        print(f"extracted_claims inserted (24h): {claims_24h}")
        print(f"extracted_claims inserted (72h): {claims_72h}")
        print(f"versioned_facts promoted (24h, created_at): {facts_24h_created}")
        print(f"versioned_facts promoted (24h, ingestion_date): {facts_24h_ingestion}")
        print(f"versioned_facts claim_extraction (24h, created_at): {facts_24h_claim}")
        print(f"versioned_facts promoted (72h, created_at): {facts_72h}")
        print("\n=== versioned_facts by day (72h window) ===")
        for day, n in facts_by_day:
            print(f"  {day}: {n}")
        avg_per_day = facts_72h / 3.0 if facts_72h else 0.0
        print(f"\n72h avg promotion rate: {avg_per_day:.1f} facts/day")
        print("\n=== Pass markers on contexts still without claims ===")
        for outcome, n in pass_outcomes:
            print(f"  {outcome or '(null)'}: {n}")

    if stats.get("passed_no_claims_after_filters", 0) > 0:
        print(
            "\nHint: contexts marked no_claims_after_filters can be requeued after relaxing "
            "CLAIM_EXTRACTION_REQUIRE_SEEDED_DOMAIN_KEYS:\n"
            "  PYTHONPATH=api uv run python api/scripts/requeue_claim_extraction_pass_markers.py --dry-run"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
