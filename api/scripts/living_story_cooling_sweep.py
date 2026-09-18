#!/usr/bin/env python3
"""Pause living follows whose episodes have been dormant beyond LIVING_COOLING_DAYS.

Does not recall stories or mutate episode membership.

  PYTHONPATH=api python3 api/scripts/living_story_cooling_sweep.py
  PYTHONPATH=api python3 api/scripts/living_story_cooling_sweep.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from services.living_story_service import run_cooling_sweep  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    result = run_cooling_sweep(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
