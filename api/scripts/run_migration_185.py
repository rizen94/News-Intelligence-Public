#!/usr/bin/env python3
"""Run migration 185: domain storylines.master_summary (ML pipeline / API).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_185.py
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("185"))
