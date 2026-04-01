#!/usr/bin/env python3
"""Run migration 204: deactivate dead FT/Blaze/C-SPAN rows in politics_2."""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("204"))
