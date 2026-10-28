#!/usr/bin/env python3
"""Sync Obsidian vault tags + wikilinks into Postgres mirror tables."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("DB_PORT", os.environ.get("DB_PORT", "6432"))

    from services.vault_tag_link_sync_service import sync_vault_tags_and_links

    stats = sync_vault_tags_and_links(limit=args.limit)
    print(json.dumps(stats, indent=2, default=str))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
