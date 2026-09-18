#!/usr/bin/env python3
"""Seed editorial packages from act-verb CE top-K (v12 THIN kernel).

  PYTHONPATH=api python api/scripts/run_act_verb_kernel.py --dry-run
  PYTHONPATH=api python api/scripts/run_act_verb_kernel.py --domain finance --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("act_verb_kernel")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--domain", default=None, help="Optional domain_key tag on package")
    p.add_argument("--day", default=None, help="YYYY-MM-DD (default: today UTC)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--modal", default="narrative")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(_API / ".env", override=False)
        load_dotenv(_API.parent / ".env", override=False)
    except Exception:
        pass

    day = date.fromisoformat(args.day) if args.day else None

    if args.dry_run:
        from shared.act_verb_kernel import list_act_verb_events_for_day

        events = list_act_verb_events_for_day(
            day=day, domain_key=args.domain, limit=args.limit
        )
        payload = {"dry_run": True, "count": len(events), "kernel_events": events}
    else:
        from services.editorial_package_service import ensure_package_from_kernel

        payload = ensure_package_from_kernel(
            domain_key=args.domain,
            day=day,
            limit=args.limit,
            modal=args.modal,
        )

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        logger.info(
            "kernel dry_run=%s count=%s package_id=%s",
            bool(args.dry_run),
            payload.get("count")
            or len(payload.get("kernel_events") or payload.get("attached_members") or []),
            (payload.get("id") if isinstance(payload, dict) else None),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
