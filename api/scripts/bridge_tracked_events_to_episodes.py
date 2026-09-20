#!/usr/bin/env python3
"""Bridge intelligence.tracked_events to canonical episodes via anchor overlap.

  PYTHONPATH=api python3 api/scripts/bridge_tracked_events_to_episodes.py --all --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import get_pipeline_active_domain_keys  # noqa: E402
from services.episode_assembly_maintenance_service import bridge_tracked_events_domain  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        ap.error("Pass --domain or --all")

    results = []
    with get_db_connection_context() as conn:
        for dk in domains:
            results.append(bridge_tracked_events_domain(conn, dk, apply=apply, limit=args.limit))
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
