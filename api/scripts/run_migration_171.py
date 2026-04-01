#!/usr/bin/env python3
"""Run migration 171: Add storyline_id to intelligence.tracked_events.

From project root:
  PYTHONPATH=api python3 api/scripts/run_migration_171.py

Uses DB from env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) or .db_password_widow.
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("171"))
