#!/usr/bin/env python3
"""Apply a single-file migration by id or exact SQL basename.

Canonical entry (replaces per-number boilerplate for simple NNN_*.sql files):

  PYTHONPATH=api uv run python api/scripts/run_migration.py 206
  PYTHONPATH=api uv run python api/scripts/run_migration.py --file 206_finance_2_legacy_silo_extensions.sql

Special cases (post-SQL hooks, multiple files in one run) keep their own scripts, e.g.
``run_migration_180.py``, ``run_migration_140_141.py``, ``run_migrations_140_to_152.py``.
"""

from __future__ import annotations

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import cli_main

if __name__ == "__main__":
    raise SystemExit(cli_main())
