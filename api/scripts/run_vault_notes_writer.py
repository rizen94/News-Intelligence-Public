#!/usr/bin/env python3
"""Run one vault notes writer cycle (claim queue → patch → reindex)."""

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
    parser.add_argument("--fanout-article", type=int, default=None, help="Also fan out this article id")
    parser.add_argument("--domain", default="politics")
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")

    if args.fanout_article:
        from services.vault_notes_fanout_service import fanout_article_to_vault_queue

        print(json.dumps(fanout_article_to_vault_queue(args.domain, args.fanout_article), indent=2))

    from services.vault_note_writer_service import run_vault_notes_writer_cycle_sync

    stats = run_vault_notes_writer_cycle_sync(limit=args.limit)
    print(json.dumps(stats, indent=2, default=str))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
