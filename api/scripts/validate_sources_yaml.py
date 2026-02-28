#!/usr/bin/env python3
"""
Validate config/sources.yaml — required fields, credentials, dataset structure.
Run: python scripts/validate_sources_yaml.py (from api/ directory)
"""

import os
import sys
import yaml
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
SOURCES_PATH = API_DIR / "config" / "sources.yaml"
REQUIRED_KEYS = {"name", "type", "module_path", "credentials", "rate_limit", "datasets"}


def main():
    if not SOURCES_PATH.exists():
        print(f"FAIL: {SOURCES_PATH} not found")
        sys.exit(1)

    with open(SOURCES_PATH) as f:
        data = yaml.safe_load(f)

    if not data:
        print("FAIL: sources.yaml is empty")
        sys.exit(1)

    errors = []
    for source_key, source_val in data.items():
        if not isinstance(source_val, dict):
            errors.append(f"{source_key}: must be a dict")
            continue
        missing = REQUIRED_KEYS - set(source_val.keys())
        if missing:
            errors.append(f"{source_key}: missing {missing}")
        else:
            datasets = source_val.get("datasets") or {}
            creds = source_val.get("credentials") or []
            print(f"  {source_val.get('name', source_key)}: {len(datasets)} datasets, creds={creds}")

    if errors:
        print("Errors:", errors)
        sys.exit(1)

    print(f"\nOK: {SOURCES_PATH} valid ({len(data)} sources)")


if __name__ == "__main__":
    main()
