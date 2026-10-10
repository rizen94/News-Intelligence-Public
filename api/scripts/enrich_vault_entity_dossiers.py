#!/usr/bin/env python3
"""Enrich living vault entity notes from ``intelligence.entity_dossiers``.

Writes replaceable ``## Entity dossier`` sections from stored dossier JSON only
(no LLM). Priority set includes Fed / oil / gold / State / OPEC+ / etc.

Usage (Widow)::

  set -a && source .env && set +a
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  PYTHONPATH=api python3 api/scripts/enrich_vault_entity_dossiers.py --force --sync \\
    --limit 15

Dry-run first::

  PYTHONPATH=api python3 api/scripts/enrich_vault_entity_dossiers.py --dry-run --limit 15
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("enrich_vault_entity_dossiers")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-write Entity dossier section even if dossier_enriched_at is set",
    )
    parser.add_argument("--sync", action="store_true", help="Mirror tags/links after write")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument(
        "--title",
        action="append",
        dest="titles",
        help="Limit to vault note title (repeatable); default = priority set",
    )
    parser.add_argument(
        "--living-only",
        action="store_true",
        help="Only lifecycle=living (skip seeded priority entities like oil/gold)",
    )
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")

    from services.vault_dossier_enrichment_service import (
        PRIORITY_ENTITY_TITLES,
        enrich_priority_entity_dossiers,
    )

    stats: dict = {
        "ok": True,
        "started_at": _now(),
        "enrichment": enrich_priority_entity_dossiers(
            titles=args.titles or list(PRIORITY_ENTITY_TITLES),
            limit=max(0, args.limit),
            force=args.force,
            dry_run=args.dry_run,
            living_only=args.living_only,
        ),
    }

    if args.sync and not args.dry_run:
        try:
            from services.vault_bridge_service import vault_root
            from services.vault_tag_link_sync_service import sync_vault_file

            root = vault_root()
            paths = [
                r["path"]
                for r in (stats["enrichment"].get("results") or [])
                if r.get("path") and r.get("ok") and not r.get("skipped")
            ]
            for p in paths:
                sync_vault_file(root / p)
            stats["sync"] = {"n": len(paths)}
        except Exception as e:
            logger.exception("sync")
            stats["sync_error"] = str(e)

    print(json.dumps(stats, indent=2, default=str))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
