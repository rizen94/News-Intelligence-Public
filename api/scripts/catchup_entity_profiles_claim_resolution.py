#!/usr/bin/env python3
"""
Catch up entity profiles on politics/finance to improve claim→fact subject resolution.

Steps per domain:
  1. backfill entity_canonical from article_entities
  2. sync intelligence.entity_profiles + old_entity_to_new
  3. backfill context_entity_mentions (via sync)
  4. optional Wikidata QID backfill
  5. sample unpromoted claim resolution before/after
  6. optional small promote batch

  PYTHONPATH=api uv run python api/scripts/catchup_entity_profiles_claim_resolution.py
  PYTHONPATH=api uv run python api/scripts/catchup_entity_profiles_claim_resolution.py --promote-limit 100
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from services.claim_extraction_service import (  # noqa: E402
    promote_claims_to_versioned_facts,
    sample_unpromoted_claim_resolution_stats,
)
from services.entity_profile_sync_service import (  # noqa: E402
    backfill_entity_canonical,
    sync_domain_entity_profiles,
)


def _profile_counts(domain_key: str) -> dict[str, int]:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    out = {"entity_canonical": 0, "entity_profiles": 0, "old_entity_to_new": 0}
    with get_db_connection_context() as conn:
        if not conn:
            return out
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.entity_canonical")
            out["entity_canonical"] = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.entity_profiles WHERE domain_key = %s
                """,
                (domain_key,),
            )
            out["entity_profiles"] = cur.fetchone()[0] or 0
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.old_entity_to_new WHERE domain_key = %s
                """,
                (domain_key,),
            )
            out["old_entity_to_new"] = cur.fetchone()[0] or 0
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Catch up politics/finance entity profiles for claims")
    parser.add_argument(
        "--domains",
        default="politics,finance",
        help="Comma-separated domain keys (default: politics,finance)",
    )
    parser.add_argument("--promote-limit", type=int, default=0, help="Optional promote batch size (0=skip)")
    parser.add_argument("--wikidata-limit", type=int, default=0, help="Optional QID backfill per domain (0=skip)")
    parser.add_argument("--resolution-sample", type=int, default=500)
    args = parser.parse_args()

    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    print("=== Before ===")
    before = sample_unpromoted_claim_resolution_stats(limit=args.resolution_sample)
    print(json.dumps(before, indent=2))

    for dk in domains:
        print(f"\n=== {dk}: entity profile catch-up ===")
        before_counts = _profile_counts(dk)
        print("before", json.dumps(before_counts))
        canonical_new = backfill_entity_canonical(dk)
        synced = sync_domain_entity_profiles(dk)
        after_counts = _profile_counts(dk)
        print(f"canonical_created={canonical_new} profile_mappings_new={synced}")
        print("after", json.dumps(after_counts))

        if args.wikidata_limit > 0:
            import importlib.util

            _wd_path = _API_ROOT / "scripts" / "backfill_wikidata_qids.py"
            _spec = importlib.util.spec_from_file_location("backfill_wikidata_qids", _wd_path)
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                q = _mod.backfill_domain(dk, limit=args.wikidata_limit)
                print("wikidata_backfill", json.dumps(q))

    print("\n=== After resolution sample ===")
    after = sample_unpromoted_claim_resolution_stats(limit=args.resolution_sample)
    print(json.dumps(after, indent=2))
    if before.get("candidates") and after.get("candidates"):
        br = (before.get("resolved") or 0) / max(1, before["candidates"])
        ar = (after.get("resolved") or 0) / max(1, after["candidates"])
        print(f"resolution rate: {br:.1%} → {ar:.1%}")

    if args.promote_limit > 0:
        print(f"\n=== Promote batch (limit={args.promote_limit}) ===")
        stats = promote_claims_to_versioned_facts(limit=args.promote_limit)
        print(json.dumps(stats, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
