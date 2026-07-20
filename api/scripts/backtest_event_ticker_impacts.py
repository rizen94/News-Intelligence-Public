#!/usr/bin/env python3
"""Light event-date log-return study for trading signal coefficient calibration (Phase C).

Usage (from repo root, with DB env):
  python3 api/scripts/backtest_event_ticker_impacts.py --days 90 --ticker USO
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
API = ROOT / "api"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backtest_event_ticker_impacts")


def _synthetic_log_return(direction: str, move_pct: float) -> float:
    """Placeholder return when market helpers unavailable."""
    sign = -1.0 if direction == "down" else 1.0
    return sign * (float(move_pct or 0) / 100.0) * 0.6


def run(*, days: int, ticker: str | None) -> dict:
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    rows: list[dict] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT id, created_at, ticker, expected_move_pct, confidence,
                       direction, method, tracked_event_id
                FROM intelligence.event_ticker_impacts
                WHERE created_at >= %s
            """
            params: list = [cutoff]
            if ticker:
                sql += " AND ticker = %s"
                params.append(ticker.upper())
            sql += " ORDER BY created_at DESC LIMIT 500"
            cur.execute(sql, params)
            rows = [dict(r) for r in (cur.fetchall() or [])]

    results = []
    for r in rows:
        realized = _synthetic_log_return(
            str(r.get("direction") or "unknown"),
            float(r.get("expected_move_pct") or 0),
        )
        expected = float(r.get("expected_move_pct") or 0) / 100.0
        results.append(
            {
                "impact_id": r["id"],
                "ticker": r["ticker"],
                "expected_move_pct": r.get("expected_move_pct"),
                "realized_log_return_proxy": round(realized, 5),
                "signed_error": round(realized - expected, 5),
                "method": r.get("method"),
            }
        )

    n = len(results)
    mean_err = sum(x["signed_error"] for x in results) / n if n else 0.0
    summary = {
        "n": n,
        "mean_signed_error": round(mean_err, 5),
        "ticker_filter": ticker,
        "days": days,
        "note": "Proxy returns only — wire FRED/Yahoo helpers for live calibration.",
        "rows": results[:50],
    }
    print(json.dumps(summary, indent=2, default=str))
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--ticker", type=str, default=None)
    args = p.parse_args()
    run(days=args.days, ticker=args.ticker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
