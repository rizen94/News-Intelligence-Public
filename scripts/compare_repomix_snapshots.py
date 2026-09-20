#!/usr/bin/env python3
"""Compare two Repomix markdown packs: file lists, sizes, refactor checklist."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FILE_HEADER_RE = re.compile(r"^## File: (.+)$", re.MULTILINE)

REFACTOR_CHECKLIST: dict[str, list[str]] = {
    "Entity routes": ["api/domains/intelligence_hub/routes/entity_resolution.py"],
    "Entity facade": ["api/services/entity_service_facade.py"],
    "API deprecation": ["api/shared/api_deprecation.py"],
    "Shared kernel": [
        "api/shared/kernel/domain_events.py",
        "api/shared/services/article_query_service.py",
    ],
    "Config": [
        "api/config/schedulers.yaml",
        "api/config/CONFIG_INDEX.md",
        "api/config/runtime.py",
    ],
    "Docs": ["docs/BACKGROUND_SERVICES.md", "docs/ENTITY_SERVICES.md"],
    "NRI": [
        "api/nri_core/vault/validator/firewall.py",
        "api/nri_core/loop/detect/cooccurrence.py",
    ],
}


def parse_files(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(FILE_HEADER_RE.findall(text))


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def grep_count(path: Path, needle: str) -> int:
    if not path.exists():
        return 0
    return path.read_text(encoding="utf-8", errors="replace").count(needle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Repomix markdown snapshots")
    parser.add_argument("--old", required=True, type=Path, help="Baseline pack path")
    parser.add_argument("--new", required=True, type=Path, help="Current pack path")
    parser.add_argument("--label", default="pack", help="Label for JSON output")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    args = parser.parse_args()

    old_files = parse_files(args.old)
    new_files = parse_files(args.new)
    added = sorted(new_files - old_files)
    removed = sorted(old_files - new_files)
    unchanged = sorted(old_files & new_files)

    checklist: dict[str, dict[str, bool]] = {}
    for area, paths in REFACTOR_CHECKLIST.items():
        checklist[area] = {p: p in new_files for p in paths}

    result = {
        "label": args.label,
        "old_path": str(args.old),
        "new_path": str(args.new),
        "old_bytes": file_size(args.old),
        "new_bytes": file_size(args.new),
        "old_file_count": len(old_files),
        "new_file_count": len(new_files),
        "added_count": len(added),
        "removed_count": len(removed),
        "unchanged_count": len(unchanged),
        "added": added,
        "removed": removed,
        "refactor_checklist": checklist,
        "symbols": {
            "deprecated_gone_response_old": grep_count(args.old, "deprecated_gone_response"),
            "deprecated_gone_response_new": grep_count(args.new, "deprecated_gone_response"),
            "entity_service_facade_old": grep_count(args.old, "entity_service_facade"),
            "entity_service_facade_new": grep_count(args.new, "entity_service_facade"),
            "nri_core_loop_import_old": grep_count(args.old, "nri_core.loop"),
            "nri_core_loop_import_new": grep_count(args.new, "nri_core.loop"),
        },
    }

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"=== {args.label} Repomix comparison ===")
    print(f"Old: {args.old} ({result['old_file_count']} files, {result['old_bytes']:,} bytes)")
    print(f"New: {args.new} ({result['new_file_count']} files, {result['new_bytes']:,} bytes)")
    print(f"Delta: +{len(added)} added, -{len(removed)} removed, {len(unchanged)} unchanged")
    print(f"Size delta: {result['new_bytes'] - result['old_bytes']:+,} bytes")
    print()
    print("Refactor checklist (in new pack):")
    for area, paths in checklist.items():
        status = ", ".join(f"{p}: {'yes' if ok else 'NO'}" for p, ok in paths.items())
        print(f"  {area}: {status}")
    print()
    if added:
        print(f"Added files ({len(added)}):")
        for p in added[:40]:
            print(f"  + {p}")
        if len(added) > 40:
            print(f"  ... and {len(added) - 40} more")
    if removed:
        print(f"\nRemoved files ({len(removed)}):")
        for p in removed[:20]:
            print(f"  - {p}")
        if len(removed) > 20:
            print(f"  ... and {len(removed) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
