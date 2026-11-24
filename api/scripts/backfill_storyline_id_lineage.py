#!/usr/bin/env python3
"""Backfill intelligence.storyline_id_lineage from domain storylines.merged_into_id chains."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", action="append", dest="domains", help="Limit to domain key(s)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.shared.database import get_db_connection_context
    from api.shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    from api.shared.storyline_id_lineage import record_storyline_lineage

    domain_keys = args.domains or list(get_pipeline_active_domain_keys())
    total = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in domain_keys:
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT id, merged_into_id
                    FROM {schema}.storylines
                    WHERE merged_into_id IS NOT NULL
                    ORDER BY id
                    """
                )
                rows = cur.fetchall() or []
                for old_id, canonical_id in rows:
                    if not old_id or not canonical_id:
                        continue
                    total += 1
                    if args.dry_run:
                        print(f"[dry-run] {dk}: {old_id} -> {canonical_id}")
                        continue
                    record_storyline_lineage(
                        conn,
                        domain_key=dk,
                        old_storyline_id=int(old_id),
                        canonical_storyline_id=int(canonical_id),
                        reason="backfill_merged_into",
                    )
        if not args.dry_run:
            conn.commit()
    print(f"Done. mappings={'(dry-run) ' if args.dry_run else ''}count={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())