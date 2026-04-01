#!/usr/bin/env python3
"""Run migration 149 (historic context schema).

From project root: PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_149.py
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("149"))
