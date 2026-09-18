#!/usr/bin/env python3
"""Run pulse digest: compute ranking, stamp follows, persist snapshot.

Schedule every 6h via cron. GET /api/pulse always computes live; snapshots are audit history.

  PYTHONPATH=api python3 api/scripts/run_pulse_digest.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from services.pulse_service import run_pulse_digest_job  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", type=int, default=48)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--user-key", default="operator")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        from services.pulse_service import compute_pulse, stamp_followed_movement

        payload = compute_pulse(window_hours=args.window, limit=args.limit)
        items = payload.get("items") or []
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "items": len(items),
                    "would_stamp": len(items),
                },
                indent=2,
            )
        )
        return 0

    result = run_pulse_digest_job(
        window_hours=args.window,
        limit=args.limit,
        user_key=args.user_key,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
