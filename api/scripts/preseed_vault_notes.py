#!/usr/bin/env python3
"""CLI: preseed NI Obsidian vault from top Postgres entities + storylines.

Usage (from api/ with env loaded):
  PYTHONPATH=. python scripts/preseed_vault_notes.py
  PYTHONPATH=. python scripts/preseed_vault_notes.py --dry-run
  PYTHONPATH=. python scripts/preseed_vault_notes.py --force --entity-limit 40
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Ensure api root on path when run as script
_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("preseed_vault_notes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default="politics")
    parser.add_argument("--entity-limit", type=int, default=35)
    parser.add_argument("--storyline-limit", type=int, default=20)
    parser.add_argument("--force", action="store_true", help="Overwrite existing vault files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Default vault path used by vault_bridge
    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")

    from services.vault_notes_preseed_service import preseed_vault_notes

    stats = preseed_vault_notes(
        domain_key=args.domain,
        entity_limit=args.entity_limit,
        storyline_limit=args.storyline_limit,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(stats, indent=2, default=str))
    return 0 if stats.get("entities_written", 0) or stats.get("entities_skipped", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
