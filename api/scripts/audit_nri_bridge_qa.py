#!/usr/bin/env python3
"""Read-only audit of suspect investigation entity_bridge rows (QA export for ops)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from nri_core.services.integration import audit_bridge_qa  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit NRI entity bridges for QA issues")
    parser.add_argument("--domain-key", default=None)
    parser.add_argument(
        "--qa-status",
        choices=("suspect", "mismatch"),
        default=None,
        help="Filter by QA status (default: all non-ok)",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument(
        "--dry-run-sql",
        action="store_true",
        help="Print commented SQL for manual review (no writes)",
    )
    args = parser.parse_args()

    result = audit_bridge_qa(
        domain_key=args.domain_key,
        qa_status=args.qa_status,
        limit=args.limit,
        offset=args.offset,
    )
    if not result.get("success"):
        print(result.get("error", "audit failed"), file=sys.stderr)
        return 1

    items = result.get("items") or []
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Filtered bridges: {result.get('total_filtered', len(items))} (showing {len(items)})")
        for row in items:
            flags = ",".join(row.get("qa_flags") or [])
            print(
                f"[{row.get('qa_status')}] sim={row.get('name_similarity')} "
                f"profile={row.get('entity_profile_id')} "
                f"ni={row.get('ni_canonical_name')!r} ftm={row.get('caption')!r} "
                f"flags={flags}"
            )

    if args.dry_run_sql and items:
        print("\n-- Dry-run review SQL (read-only; demotion is manual/NRI-side):")
        ids = [str(i["entity_profile_id"]) for i in items if i.get("entity_profile_id")]
        if ids:
            print(
                "SELECT eb.entity_profile_id, eb.ftm_id, fc.caption, ep.metadata->>'canonical_name'\n"
                "FROM intelligence.investigation_entity_bridge eb\n"
                "JOIN intelligence.entity_profiles ep ON ep.id = eb.entity_profile_id\n"
                "LEFT JOIN intelligence.investigation_ftm_entity_cache fc ON fc.ftm_id = eb.ftm_id\n"
                f"WHERE eb.entity_profile_id IN ({', '.join(ids)});"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
