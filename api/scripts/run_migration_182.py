#!/usr/bin/env python3
"""Run migration 182: add_domain_foreign_keys skips missing topic_learning_history.

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_182.py
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("182"))
