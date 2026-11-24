#!/usr/bin/env python3
"""
Reconcile vault situation hubs: drop member_storyline_ids that no longer resolve.

Ghost members come from pre–honest-spine corpus ids re-asserted by brief metadata
merges and discovery unions. Safe to run repeatedly (--dry-run first).

After metadata reconcile, optionally refresh Obsidian hub bodies via write_cluster_hub.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default=None, help="Limit to one domain key")
    parser.add_argument("--limit", type=int, default=500, help="Max hubs to scan")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report stale hubs only; do not patch registry",
    )
    parser.add_argument(
        "--refresh-vault",
        action="store_true",
        help="After reconcile, run refresh_all_cluster_hubs (rewrites timelines)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Pass force=True to vault refresh",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print stats JSON only",
    )
    args = parser.parse_args()

    from services.vault_cluster_hub_service import (
        reconcile_all_hub_member_registries,
        refresh_all_cluster_hubs,
    )

    stats = reconcile_all_hub_member_registries(
        domain_key=args.domain,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    if args.refresh_vault and not args.dry_run:
        stats["vault_refresh"] = refresh_all_cluster_hubs(
            domain_key=args.domain,
            force=args.force,
            limit=args.limit,
        )

    if args.json:
        print(json.dumps(stats, indent=2, default=str))
    else:
        print(
            f"scanned={stats.get('scanned')} "
            f"patched={stats.get('patched')} "
            f"stale_ids_total={stats.get('stale_total')} "
            f"dry_run={stats.get('dry_run')}"
        )
        for row in stats.get("hubs") or []:
            print(
                f"  hub {row.get('id')} {row.get('cluster_key')}: "
                f"registry={row.get('registry_n')} active={row.get('active_n')} "
                f"stale={row.get('stale_n')}"
            )
        if stats.get("vault_refresh"):
            vr = stats["vault_refresh"]
            print(f"vault_refresh ok={vr.get('ok')} refreshed={vr.get('refreshed')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())