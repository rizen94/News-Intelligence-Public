#!/usr/bin/env python3
"""Link clustered chronological_events to existing episodes via event_cluster_id.

  PYTHONPATH=api python3 api/scripts/link_clustered_events_to_episodes.py --all --apply --limit-clusters 500
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from services.episode_assembly_maintenance_service import link_orphan_clusters  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-clusters", type=int, default=500)
    ap.add_argument(
        "--allow-founding",
        action="store_true",
        help="Found episode via continuation when cluster has no existing match",
    )
    args = ap.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domain_key = None if args.all or not args.domain else args.domain

    with get_db_connection_context() as conn:
        result = link_orphan_clusters(
            conn,
            domain_key=domain_key,
            apply=apply,
            limit_clusters=args.limit_clusters,
            allow_founding=bool(args.allow_founding),
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
