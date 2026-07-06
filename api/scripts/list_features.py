#!/usr/bin/env python3
"""List registered backend features by lifecycle, enabled state, and replacement graph."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Search News Intelligence feature registry")
    parser.add_argument("--lifecycle", choices=[
        "under_developed", "staged", "incorporated", "deprecated", "archived"
    ])
    parser.add_argument("--enabled", choices=["true", "false"])
    parser.add_argument("--has-replacement", action="store_true")
    parser.add_argument("--replaces", metavar="FEATURE_KEY")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--counts", action="store_true")
    args = parser.parse_args()

    from config.feature_registry import (
        get_feature_registry,
        is_feature_enabled,
        lifecycle_counts,
        list_features,
    )

    if args.counts:
        payload = {"lifecycle_counts": lifecycle_counts(), "total": len(get_feature_registry())}
        print(json.dumps(payload, indent=2))
        return 0

    enabled = None
    if args.enabled == "true":
        enabled = True
    elif args.enabled == "false":
        enabled = False

    items = list_features(
        lifecycle=args.lifecycle,
        enabled=enabled,
        has_replacement=True if args.has_replacement else None,
        replaces=args.replaces,
    )
    for item in items:
        item["runtime_enabled"] = is_feature_enabled(item["key"])

    if args.json:
        print(json.dumps({"features": items, "as_of_utc": datetime.now(timezone.utc).isoformat()}, indent=2))
        return 0

    for item in items:
        key = item.get("key", "?")
        lc = item.get("lifecycle", "?")
        run = is_feature_enabled(key)
        rep = item.get("replaced_by") or ""
        print(f"{key:40} lifecycle={lc:18} runtime_enabled={run!s:5}  replaced_by={rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
