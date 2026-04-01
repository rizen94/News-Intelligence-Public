#!/usr/bin/env python3
"""Run migration 201: politics-2 / finance-2 silos (schemas politics_2, finance_2).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_201.py
Then record:
  PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 201 \\
    --notes run_migration_201.py --file api/database/migrations/201_politics2_finance2_domain_silos.sql

Enable ``api/config/domains/politics-2.yaml`` and ``finance-2.yaml`` (already in repo), run
``seed_domain_rss_from_yaml.py`` or ``provision_domain.py`` to seed feeds. Set env
``RSS_INGEST_EXCLUDE_DOMAIN_KEYS=politics,finance`` when new feeds are ready so RSS targets the -2 silos only.
"""

import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.migration_sql_runner import run_by_migration_number

if __name__ == "__main__":
    raise SystemExit(run_by_migration_number("201"))
