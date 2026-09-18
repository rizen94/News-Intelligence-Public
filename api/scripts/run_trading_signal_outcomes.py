#!/usr/bin/env python3
"""Score trading_signals retrospectively via Stooq daily CSV.

  PYTHONPATH=api python3 api/scripts/run_trading_signal_outcomes.py
  PYTHONPATH=api python3 api/scripts/run_trading_signal_outcomes.py --limit 10 --lookback 5
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_trading_signal_outcomes")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--lookback", type=int, default=5)
    p.add_argument("--signal-id", type=int, default=None)
    args = p.parse_args()

    from services.trading_signals_service import (
        score_pending_signal_outcomes,
        score_signal_outcome,
    )

    if args.signal_id:
        res = score_signal_outcome(args.signal_id, lookback_days=args.lookback)
        logger.info("single: %s", res)
        return 0 if res.get("ok") else 1

    res = score_pending_signal_outcomes(limit=args.limit, lookback_days=args.lookback)
    logger.info("batch: %s", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
