#!/usr/bin/env python3
"""Compare two backlog_status JSON responses (files from snapshot_backlog_status.sh)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(path: Path) -> dict:
    with path.open() as f:
        raw = json.load(f)
    if not raw.get("success"):
        print(f"warning: {path} success=false", file=sys.stderr)
    return raw.get("data") or {}


def _n(d: dict, *keys: str):
    x: object = d
    for k in keys:
        if not isinstance(x, dict):
            return None
        x = x.get(k)
    return x


def _fmt(old, new, label: str) -> str:
    o = old if old is not None else "—"
    n = new if new is not None else "—"
    try:
        oi, ni = int(o), int(n)
        d = ni - oi
        arrow = "↓" if d < 0 else "↑" if d > 0 else "="
        return f"  {label}: {oi} → {ni} ({arrow} {d:+d})"
    except (TypeError, ValueError):
        return f"  {label}: {o} → {n}"


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: compare_backlog_snapshots.py <older.json> <newer.json>",
            file=sys.stderr,
        )
        return 2
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    o, n = _load(a), _load(b)
    print(f"older: {a.name}")
    print(f"newer: {b.name}")
    print()
    for path, label in (
        (("articles", "backlog"), "articles.backlog"),
        (("documents", "backlog"), "documents.backlog"),
        (("contexts", "backlog"), "contexts.backlog"),
        (("entity_profiles", "backlog"), "entity_profiles.backlog"),
        (("storylines", "backlog"), "storylines.backlog"),
        (("overall_eta_hours",), "overall_eta_hours"),
        (("overall_iterations_to_baseline",), "overall_iterations_to_baseline"),
    ):
        print(_fmt(_n(o, *path), _n(n, *path), label))
    print()
    print(
        "Note: ML queue depths are on GET /api/system_monitoring/automation/status "
        "(pending_counts), not backlog_status. Save two automation/status JSON files "
        "and diff with jq if needed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
