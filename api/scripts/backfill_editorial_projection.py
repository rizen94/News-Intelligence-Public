#!/usr/bin/env python3
"""Backfill: project published editorial packages into storyline/event editorial fields.

Usage (Widow /opt or workspace, with PYTHONPATH=api):

  python api/scripts/backfill_editorial_projection.py --limit 50
  python api/scripts/backfill_editorial_projection.py --limit 100 --force
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-project even when document_status looks durable",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from services.editorial_projection_service import backfill_published_packages

    out = backfill_published_packages(limit=args.limit, only_missing=not args.force)
    print(json.dumps(out, default=str, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
