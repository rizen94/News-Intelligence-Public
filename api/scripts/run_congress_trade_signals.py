#!/usr/bin/env python3
"""Run congressional trade signals pipeline (enrich → score → paper → HITL).

  PYTHONPATH=api python3 api/scripts/run_congress_trade_signals.py
  PYTHONPATH=api python3 api/scripts/run_congress_trade_signals.py --skip-paper --skip-hitl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_congress_trade_signals")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--enrich-limit", type=int, default=500)
    p.add_argument("--score-limit", type=int, default=500)
    p.add_argument("--skip-paper", action="store_true")
    p.add_argument("--skip-hitl", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    from services.congress_trade_signals_service import run_congress_trade_signals_pipeline

    res = run_congress_trade_signals_pipeline(
        enrich_limit=args.enrich_limit,
        score_limit=args.score_limit,
        rebuild_paper=not args.skip_paper,
        promote_hitl=not args.skip_hitl,
    )
    if args.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        logger.info("%s", res)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
