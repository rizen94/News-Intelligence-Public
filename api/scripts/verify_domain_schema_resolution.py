#!/usr/bin/env python3
"""Verify URL domain keys resolve to schemas that contain live storyline data."""

from __future__ import annotations

import sys

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_active_domain_keys, resolve_domain_schema


def main() -> int:
    errors: list[str] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for domain_key in get_active_domain_keys():
                schema = resolve_domain_schema(domain_key)
                naive = domain_key.replace("-", "_")
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {schema}.storylines
                    WHERE merged_into_id IS NULL
                    """
                )
                live_count = cur.fetchone()[0]
                naive_count = None
                if naive != schema:
                    try:
                        cur.execute(f"SELECT COUNT(*)::int FROM {naive}.storylines")
                        naive_count = cur.fetchone()[0]
                    except Exception:
                        naive_count = -1
                print(
                    f"{domain_key:28} -> {schema:28} live_storylines={live_count}"
                    + (
                        f"  (naive {naive} has {naive_count} rows — do not use replace)"
                        if naive != schema and naive_count not in (None, live_count)
                        else ""
                    )
                )
                if naive != schema and live_count > 0 and naive_count == 0:
                    errors.append(
                        f"{domain_key}: data in {schema} but naive schema {naive} is empty"
                    )
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines
                    WHERE merged_into_id IS NULL
                    ORDER BY id DESC LIMIT 1
                    """
                )
                sample = cur.fetchone()
                if sample:
                    sid = sample[0]
                    cur.execute(
                        f"SELECT 1 FROM {schema}.storylines WHERE id = %s",
                        (sid,),
                    )
                    if not cur.fetchone():
                        errors.append(f"{domain_key}: sample id {sid} missing in {schema}")

    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        return 1
    print("OK: all active domains resolve to schemas with storyline data or are empty silos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
