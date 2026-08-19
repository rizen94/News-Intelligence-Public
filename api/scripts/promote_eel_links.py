#!/usr/bin/env python3
"""Promote candidate event_episode_links to established when episode is mature.

  PYTHONPATH=api python3 api/scripts/promote_eel_links.py --all
  PYTHONPATH=api python3 api/scripts/promote_eel_links.py --domain politics --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys

from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema


def promote_domain(domain_key: str, *, dry_run: bool = False) -> dict:
    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"domain": domain_key, "error": "no_db", "promoted": 0}

    try:
        with conn.cursor() as cur:
            if dry_run:
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM intelligence.event_episode_links eel
                    JOIN {schema}.storylines s ON s.id = eel.episode_id
                    WHERE eel.domain_key = %s
                      AND eel.inference_stage = 'candidate'
                      AND s.merged_into_id IS NULL
                      AND (
                        s.signature_locked_at IS NOT NULL
                        OR (
                          SELECT COUNT(DISTINCT e2.event_id)
                          FROM intelligence.event_episode_links e2
                          WHERE e2.episode_id = s.id
                            AND e2.domain_key = eel.domain_key
                            AND e2.inference_stage <> 'quarantined'
                        ) >= 2
                      )
                    """,
                    (domain_key,),
                )
                count = int((cur.fetchone() or [0])[0] or 0)
                return {"domain": domain_key, "promoted": count, "dry_run": True}

            cur.execute(
                f"""
                UPDATE intelligence.event_episode_links eel
                SET inference_stage = 'established', updated_at = NOW()
                FROM {schema}.storylines s
                WHERE eel.episode_id = s.id
                  AND eel.domain_key = %s
                  AND eel.inference_stage = 'candidate'
                  AND s.merged_into_id IS NULL
                  AND (
                    s.signature_locked_at IS NOT NULL
                    OR (
                      SELECT COUNT(DISTINCT e2.event_id)
                      FROM intelligence.event_episode_links e2
                      WHERE e2.episode_id = s.id
                        AND e2.domain_key = eel.domain_key
                        AND e2.inference_stage <> 'quarantined'
                    ) >= 2
                  )
                """,
                (domain_key,),
            )
            promoted = int(cur.rowcount or 0)
        conn.commit()
        return {"domain": domain_key, "promoted": promoted, "dry_run": False}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        ap.error("Pass --domain or --all")

    results = [promote_domain(dk, dry_run=args.dry_run) for dk in domains]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
