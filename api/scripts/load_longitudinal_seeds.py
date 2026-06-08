#!/usr/bin/env python3
"""Load reference_events_seed.yaml and sync historical_arcs.yaml to DB.

  PYTHONPATH=api uv run python api/scripts/load_longitudinal_seeds.py
  PYTHONPATH=api uv run python api/scripts/load_longitudinal_seeds.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from services.arc_catalog_service import sync_arc_definitions_from_yaml
from services.reference_events_loader import load_reference_events_from_yaml


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--events-only", action="store_true")
    p.add_argument("--arcs-only", action="store_true")
    args = p.parse_args()

    if not args.arcs_only:
        ev = load_reference_events_from_yaml(dry_run=args.dry_run)
        print("reference_events:", ev)
    if not args.events_only:
        arcs = sync_arc_definitions_from_yaml()
        print("arc_definitions:", arcs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
