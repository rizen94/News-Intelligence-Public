#!/usr/bin/env python3
"""Run migration 188: artificial_intelligence domain silo (schema + table parity).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_188.py

Pairs with api/config/domains/artificial-intelligence.yaml and provision_domain.py.
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("188"))
