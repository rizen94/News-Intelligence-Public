#!/usr/bin/env python3
"""Load api/config/seed_world_entities.yaml and bulk-seed entity_canonical + entity_profiles per domain."""

from __future__ import annotations

import argparse
import os
import sys

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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yaml",
        default=os.path.join(API_ROOT, "config", "seed_world_entities.yaml"),
        help="Path to YAML catalog",
    )
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        help="Only seed these domain_key(s). Repeatable. Default: all keys in file.",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip sync_domain_entity_profiles (not recommended)",
    )
    args = parser.parse_args()

    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML required (uv sync)")
        return 1

    path = os.path.abspath(args.yaml)
    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}")
        return 1

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        print("ERROR: YAML root must be a mapping of domain_key -> list of entities")
        return 1

    from shared.domain_registry import is_valid_domain_key

    from services.entity_seed_catalog_service import bulk_seed_canonical_entries

    domains = args.domains
    total = 0
    for domain_key, entries in data.items():
        if not isinstance(domain_key, str) or not isinstance(entries, list):
            continue
        dk = domain_key.strip()
        if not dk or not is_valid_domain_key(dk):
            print(f"skip invalid domain key: {domain_key!r}")
            continue
        if domains and dk not in domains:
            continue
        normalized: list[dict] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            if not (item.get("name") or item.get("canonical_name")):
                continue
            normalized.append(item)
        if not normalized:
            continue
        print(f"Seeding {dk} ({len(normalized)} entries)...", flush=True)
        out = bulk_seed_canonical_entries(
            dk,
            normalized,
            sync_profiles=not args.no_sync,
        )
        print(f"{dk}: {out}")
        if out.get("success"):
            total += int(out.get("inserted", 0) or 0)
    print(f"Done. Total new canonical rows inserted (sum): {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
