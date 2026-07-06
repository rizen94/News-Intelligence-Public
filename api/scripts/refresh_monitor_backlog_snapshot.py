#!/usr/bin/env python3
"""
Force-refresh the Monitor backlog snapshot (automation_state.monitor_backlog_snapshot).

Run on Widow with prod env so DB uses localhost:6432 (PgBouncer), not remote host:

  cd /opt/news-intelligence
  PYTHONPATH=api .venv/bin/python3 api/scripts/refresh_monitor_backlog_snapshot.py

  # JSON output with queue_audit cross-checks:
  PYTHONPATH=api .venv/bin/python3 api/scripts/refresh_monitor_backlog_snapshot.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


def _load_prod_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment,misc]

    if load_dotenv:
        load_dotenv(_API_ROOT / ".env", override=False)
        load_dotenv(_REPO_ROOT / ".env", override=False)

    pw_file = _REPO_ROOT / ".db_password_widow"
    if not os.environ.get("DB_PASSWORD") and pw_file.is_file():
        os.environ.setdefault("DB_PASSWORD", pw_file.read_text().splitlines()[0].strip())

    # Apps on Widow should hit PgBouncer on localhost, not 192.168.93.101:5432.
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "6432")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh monitor_backlog_snapshot in automation_state")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print queue_audit JSON (default: human summary)",
    )
    args = parser.parse_args()

    _load_prod_env()

    from services.monitor_backlog_snapshot_service import refresh_monitor_backlog_snapshot

    payload = refresh_monitor_backlog_snapshot(force=True)
    if not payload:
        print("refresh_monitor_backlog_snapshot returned None", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload.get("queue_audit") or {}, indent=2, sort_keys=True))
        return 0

    refreshed = payload.get("refreshed_at_utc", "?")
    pending = payload.get("pending") or {}
    audit = (payload.get("queue_audit") or {}).get("phases") or {}
    print(f"refreshed_at_utc: {refreshed}")
    print(f"phases pending: {len(pending)}")
    for phase, row in sorted(audit.items()):
        if not isinstance(row, dict):
            continue
        if row.get("error"):
            print(f"  {phase}: ERROR {row['error']}")
            continue
        monitor = row.get("monitor_pending", "?")
        match = row.get("matches_automation_sql")
        tag = "MATCH" if match else "MISMATCH"
        print(f"  {phase}: monitor={monitor} {tag}")
        for key in (
            "actionable_unified_intake",
            "automation_sql_recount",
            "actionable_no_claims_broad",
            "total_no_claims_inventory",
        ):
            if key in row:
                print(f"    {key}: {row[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
