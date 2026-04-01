#!/usr/bin/env python3
"""Run migration 175: public.chronological_events + v5 columns + domain storylines (silo-safe).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_175.py

Uses DB from env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) or .db_password_widow.
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("175"))
