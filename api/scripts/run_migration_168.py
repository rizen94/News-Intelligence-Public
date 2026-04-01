#!/usr/bin/env python3
"""Run migration 168: automation_state table for v8 pending_collection_queue persistence.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_168.py

Uses DB from env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) or .db_password_widow.
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("168"))
