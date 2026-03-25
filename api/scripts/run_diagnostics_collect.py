#!/usr/bin/env python3
"""
Run diagnostics event collection (same logic as GET /api/system_monitoring/diagnostics/events).

Usage (repo root):

  PYTHONPATH=api uv run python api/scripts/run_diagnostics_collect.py
  PYTHONPATH=api uv run python api/scripts/run_diagnostics_collect.py --since-hours 48 --json > /tmp/diag.json

Cron example (hourly):

  0 * * * * cd /path/to/News\\ Intelligence && PYTHONPATH=api uv run python api/scripts/run_diagnostics_collect.py --summary >> /var/log/news_intel_diagnostics.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure api/ on path
_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))


def main() -> int:
    p = argparse.ArgumentParser(description="Collect diagnostic events from DB + logs")
    p.add_argument("--since-hours", type=float, default=24.0)
    p.add_argument("--max-per-source", type=int, default=200)
    p.add_argument("--no-activity-jsonl", action="store_true")
    p.add_argument("--no-plain-logs", action="store_true")
    p.add_argument("--summary", action="store_true", help="Print counts only")
    p.add_argument("--json", action="store_true", help="Single JSON object to stdout")
    args = p.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(_API / ".env", override=False)
        load_dotenv(_API.parent / ".env", override=False)
    except Exception:
        pass

    from services.diagnostics_event_collector_service import collect_diagnostic_events

    out = collect_diagnostic_events(
        since_hours=args.since_hours,
        max_per_source=args.max_per_source,
        include_activity_jsonl=not args.no_activity_jsonl,
        include_plain_logs=not args.no_plain_logs,
    )
    if args.summary:
        payload = {
            "generated_at_utc": out.get("generated_at_utc"),
            "since_hours": out.get("since_hours"),
            "total": out.get("total"),
            "counts_by_severity": out.get("counts_by_severity"),
            "counts_by_source": out.get("counts_by_source"),
        }
    else:
        payload = out

    if args.json:
        print(json.dumps({"success": True, "data": payload}, default=str))
    else:
        print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
