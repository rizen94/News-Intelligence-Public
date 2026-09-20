#!/usr/bin/env python3
"""Dry-run / apply event-core split hygiene (Phase 4).

  PYTHONPATH=api python3 api/scripts/run_event_core_split_hygiene.py
  EVENT_CORE_MEMBERSHIP_ENABLED=1 EVENT_CORE_SPLIT_APPLY=1 \\
    PYTHONPATH=api python3 api/scripts/run_event_core_split_hygiene.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("event_core_split")

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "api") not in sys.path:
    sys.path.insert(0, str(_ROOT / "api"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    from services.storyline_event_split_service import run_event_core_split_hygiene

    result = run_event_core_split_hygiene(dry_run=not args.apply)
    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        logger.info(
            "proposals=%s dry_run=%s te_created=%s attached=%s",
            result.get("proposal_count"),
            result.get("dry_run"),
            result.get("te_created"),
            result.get("membership_attached"),
        )
        for p in result.get("proposals_sample") or []:
            logger.info(
                "  %s/%s n=%s action=%s splits=%s",
                p.get("domain"),
                p.get("storyline_id"),
                p.get("n_members"),
                p.get("action"),
                len(p.get("splits") or []),
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
