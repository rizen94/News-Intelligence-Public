#!/usr/bin/env python3
"""Run migration 155 (quality_feedback_schema: claim_validations, event_validations, source_reliability).

From project root: .venv/bin/python api/scripts/run_migration_155.py
Or from api/: python scripts/run_migration_155.py (with PYTHONPATH=.)
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("155"))
