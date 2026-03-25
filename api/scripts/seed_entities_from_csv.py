#!/usr/bin/env python3
"""
Import entity seeds from CSV into bulk_seed_canonical_entries.

CSV columns (header row required):
  domain_key — e.g. politics
  name — canonical display name
  type — person | organization | subject | ORG | PERSON | …
  aliases — optional; semicolon-separated alternate strings

  PYTHONPATH=api uv run python api/scripts/seed_entities_from_csv.py --csv path/to/entities.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(API_ROOT)
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(API_ROOT, ".env"), override=False)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(PROJECT_ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(PROJECT_ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="Path to CSV")
    p.add_argument("--no-sync", action="store_true")
    args = p.parse_args()

    path = os.path.abspath(args.csv)
    if not os.path.isfile(path):
        print(f"ERROR: not found: {path}")
        return 1

    by_domain: dict[str, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            dk = (row.get("domain_key") or row.get("domain") or "").strip()
            name = (row.get("name") or row.get("canonical_name") or "").strip()
            if not dk or not name:
                continue
            et = (row.get("type") or row.get("entity_type") or "organization").strip()
            aliases_raw = row.get("aliases") or ""
            aliases = [a.strip() for a in str(aliases_raw).split(";") if a.strip()]
            by_domain[dk].append(
                {"name": name, "entity_type": et, "aliases": aliases},
            )

    from shared.domain_registry import is_valid_domain_key

    from services.entity_seed_catalog_service import bulk_seed_canonical_entries

    for dk, entries in by_domain.items():
        if not is_valid_domain_key(dk):
            print(f"skip invalid domain: {dk!r}")
            continue
        out = bulk_seed_canonical_entries(
            dk,
            entries,
            sync_profiles=not args.no_sync,
        )
        print(f"{dk} ({len(entries)} rows): {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
