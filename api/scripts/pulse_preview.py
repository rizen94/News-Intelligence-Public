#!/usr/bin/env python3
"""Print current pulse ranking as a table for operator review.

  PYTHONPATH=api python3 api/scripts/pulse_preview.py
  PYTHONPATH=api python3 api/scripts/pulse_preview.py --window 72 --limit 30 --domain politics
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from services.pulse_service import compute_pulse  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", type=int, default=48)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--domain")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    payload = compute_pulse(
        window_hours=args.window,
        limit=args.limit,
        domain_filter=args.domain,
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0

    items = payload.get("items") or []
    print(f"Pulse ({payload.get('window_hours')}h window, {len(items)} items)")
    print("-" * 100)
    for i, card in enumerate(items, 1):
        score = card.get("score")
        bd = card.get("score_breakdown") or {}
        bd_s = ", ".join(f"{k}={v}" for k, v in bd.items())
        moves = card.get("movement_summary") or []
        top = "; ".join((m.get("title") or "")[:60] for m in moves[:2])
        print(
            f"{i:2}. [{score:5.1f}] {card.get('domain_key')}/{card.get('id')} "
            f"{card.get('object_kind')} {card.get('episode_state') or ''} "
            f"v={card.get('velocity')} | {(card.get('title') or '')[:70]}"
        )
        print(f"    {bd_s}")
        if top:
            print(f"    → {top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
