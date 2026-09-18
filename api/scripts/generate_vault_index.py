#!/usr/bin/env python3
"""
Generate consolidated vault index — run manually or from cron.

Outputs: 00_Inbox/vault-index.md with tables for:
- Hypotheses (status, confidence, FTM ID, iteration)
- Tracking candidates (recent runs, ranked)
- Investigations (active, source hypothesis, FTM)

Usage:
    PYTHONPATH=api python3 api/scripts/generate_vault_index.py
    PYTHONPATH=api python3 api/scripts/generate_vault_index.py --json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from services.nri_loop_summarizer import build_vault_index, write_vault_index  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate vault index")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout instead of writing markdown")
    parser.add_argument("--hypothesis-limit", type=int, default=200, help="Max hypotheses to include")
    parser.add_argument("--tracking-days", type=int, default=30, help="Days of tracking candidates to scan")
    args = parser.parse_args()

    index = build_vault_index(
        hypothesis_limit=args.hypothesis_limit,
        tracking_days=args.tracking_days,
    )

    if args.json:
        print(json.dumps(index, indent=2, default=str))
        return 0

    result = write_vault_index(index)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())