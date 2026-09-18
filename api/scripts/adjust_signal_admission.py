#!/usr/bin/env python3
"""Nightly adjuster for adaptive signal admission threshold (v10.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from services.signal_admission_governor_service import adjust_admission_threshold

    result = adjust_admission_threshold(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result)
    return 0 if result.get("action") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
