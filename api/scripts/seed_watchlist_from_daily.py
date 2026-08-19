#!/usr/bin/env python3
"""Seed public.watchlist from today's Daily report moved episodes.

  PYTHONPATH=api python3 api/scripts/seed_watchlist_from_daily.py --all --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection  # noqa: E402
from shared.domain_registry import get_pipeline_active_domain_keys  # noqa: E402
from services.daily_report_service import assemble_daily  # noqa: E402


def seed_domain(domain_key: str, *, limit: int, dry_run: bool) -> dict:
    payload = assemble_daily(domain_key, limit=limit)
    if not payload.get("ok"):
        return {"domain": domain_key, "error": payload.get("error"), "seeded": 0}

    moved = (payload.get("moved_today") or [])[:limit]
    ep_ids = []
    seen: set[int] = set()
    for item in moved:
        eid = item.get("episode_id")
        if eid is None:
            continue
        eid = int(eid)
        if eid in seen:
            continue
        seen.add(eid)
        ep_ids.append(eid)

    if not ep_ids:
        return {"domain": domain_key, "seeded": 0, "candidates": 0}

    conn = get_db_connection()
    if not conn:
        return {"domain": domain_key, "error": "no_db", "seeded": 0}

    seeded = 0
    try:
        with conn.cursor() as cur:
            for sid in ep_ids:
                if dry_run:
                    seeded += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO public.watchlist (storyline_id, alert_on_reactivation, weekly_digest, notes)
                    VALUES (%s, TRUE, FALSE, %s)
                    ON CONFLICT (storyline_id) DO UPDATE
                    SET alert_on_reactivation = TRUE,
                        notes = COALESCE(public.watchlist.notes, EXCLUDED.notes)
                    """,
                    (sid, f"Seeded from daily report ({domain_key})"),
                )
                seeded += 1
        if not dry_run:
            conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {"domain": domain_key, "seeded": seeded, "candidates": len(ep_ids), "dry_run": dry_run}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        ap.error("Pass --domain or --all")

    results = [seed_domain(dk, limit=args.limit, dry_run=args.dry_run) for dk in domains]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
