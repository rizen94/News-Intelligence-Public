#!/usr/bin/env python3
"""Enrich vault Situation hubs + living entities with Wikipedia wiki RAG.

Uses local ``intelligence.wikipedia_knowledge`` then Wikipedia summary API.
Appends/replaces a clearly attributed ``## Wikipedia background`` section —
no LLM prose.

Usage (Widow)::

  set -a && source .env && set +a
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  PYTHONPATH=api python api/scripts/enrich_vault_wiki_rag.py --force --sync \\
    --entity-limit 15

Dry-run first::

  PYTHONPATH=api python api/scripts/enrich_vault_wiki_rag.py --dry-run
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
logger = logging.getLogger("enrich_vault_wiki_rag")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-write Wikipedia section even if wiki_enriched_at is set",
    )
    parser.add_argument("--sync", action="store_true", help="Mirror tags/links after write")
    parser.add_argument(
        "--hubs-only",
        action="store_true",
        help="Skip living-entity enrichment",
    )
    parser.add_argument(
        "--entities-only",
        action="store_true",
        help="Skip Situation hub enrichment",
    )
    parser.add_argument("--entity-limit", type=int, default=15)
    parser.add_argument("--hub-max-hits", type=int, default=4)
    parser.add_argument(
        "--hub",
        action="append",
        dest="hubs",
        help="Limit to cluster_key (repeatable); default = priority set",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Do not call Wikipedia HTTP API (local dump/cache only)",
    )
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")

    from services.vault_wiki_enrichment_service import (
        DEFAULT_PRIORITY_HUBS,
        enrich_priority_vault_wiki,
    )

    hubs = None if args.entities_only else (args.hubs or list(DEFAULT_PRIORITY_HUBS))
    if args.entities_only:
        hubs = []

    stats: dict = {
        "ok": True,
        "started_at": _now(),
        "enrichment": enrich_priority_vault_wiki(
            hubs=hubs,
            entity_limit=0 if args.hubs_only else max(0, args.entity_limit),
            include_entities=not args.hubs_only,
            force=args.force,
            dry_run=args.dry_run,
            allow_api_fallback=not args.local_only,
            hub_max_hits=max(1, args.hub_max_hits),
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
