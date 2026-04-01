#!/usr/bin/env python3
"""Compare backlog_status JSON files (from snapshot_backlog_status.sh).

Pair mode:  two files, older then newer.
Timeline:  ``timeline`` then 2+ paths in chronological order (oldest first) for a single progress table.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

METRICS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("articles", "backlog"), "articles.backlog"),
    (("documents", "backlog"), "documents.backlog"),
    (("contexts", "backlog"), "contexts.backlog"),
    (("entity_profiles", "backlog"), "entity_profiles.backlog"),
    (("storylines", "backlog"), "storylines.backlog"),
    (("overall_eta_hours",), "overall_eta_hours"),
    (("overall_iterations_to_baseline",), "overall_iterations_to_baseline"),
)


def _validate_json_paths(paths: list[Path], *, pair: bool) -> bool:
    missing = [p for p in paths if not p.is_file()]
    if not missing:
        return True
    for p in missing:
        print(f"error: file not found (or not a file): {p}", file=sys.stderr)
    print("", file=sys.stderr)
    if pair:
        print(
            'Arguments must be real paths to backlog_status_*.json (not the '
            'placeholder names "older.json" / "newer.json" from examples).',
            file=sys.stderr,
        )
        print(
            "  ./scripts/backlog_burndown.sh diff\n"
            "  ls .local/backlog_snapshots/backlog_status_*.json",
            file=sys.stderr,
        )
    else:
        print(
            "  ./scripts/backlog_burndown.sh timeline\n"
            "  ls .local/backlog_snapshots/backlog_status_*.json",
            file=sys.stderr,
        )
    return False


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


def _short_ts_from_name(path: Path) -> str:
    m = re.match(r"^backlog_status_(\d{8})_(\d{6})\.json$", path.name)
    if not m:
        return path.name[:24]
    d, t = m.group(1), m.group(2)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]} {t[0:2]}:{t[2:4]}:{t[4:6]} UTC"


def _fmt_cell(v: object) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v != v:  # NaN
            return "—"
        return f"{v:.1f}" if abs(v - int(v)) > 1e-6 else str(int(v))
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _numeric_delta(first: object, last: object) -> str:
    if first is None or last is None:
        return "—"
    try:
        a = float(first)
        b = float(last)
    except (TypeError, ValueError):
        return "—"
    d = b - a
    if abs(d - int(d)) < 1e-6:
        di = int(d)
        arrow = "↓" if di < 0 else "↑" if di > 0 else "="
        return f"{arrow} {di:+d}"
    arrow = "↓" if d < 0 else "↑" if d > 0 else "="
    return f"{arrow} {d:+.1f}"


def _pair_compare(older: Path, newer: Path) -> int:
    o, n = _load(older), _load(newer)
    print(f"older: {older.name}")
    print(f"newer: {newer.name}")
    print()
    for path, label in METRICS:
        print(_fmt_pair_line(_n(o, *path), _n(n, *path), label))
    print()
    print(
        "Note: ML queue depths are on GET /api/system_monitoring/automation/status "
        "(pending_counts), not backlog_status. Save two automation/status JSON files "
        "and diff with jq if needed."
    )
    return 0


def _fmt_pair_line(old, new, label: str) -> str:
    o = old if old is not None else "—"
    n = new if new is not None else "—"
    try:
        oi, ni = int(o), int(n)
        d = ni - oi
        arrow = "↓" if d < 0 else "↑" if d > 0 else "="
        return f"  {label}: {oi} → {ni} ({arrow} {d:+d})"
    except (TypeError, ValueError):
        return f"  {label}: {o} → {n}"


def _timeline(paths: list[Path]) -> int:
    if len(paths) < 2:
        print("timeline mode needs at least 2 backlog_status JSON files", file=sys.stderr)
        return 2
    datas = [_load(p) for p in paths]

    print("Backlog progress timeline (oldest → newest)\n")
    for i, p in enumerate(paths):
        print(f"  [{i + 1}] {_short_ts_from_name(p)}  {p.name}")
    print()

    # Column widths: label + each snapshot + delta
    label_w = max(len(lbl) for _, lbl in METRICS) + 1
    ncols = len(paths)

    def row(metric_label: str, cells: list[str], delta_s: str) -> None:
        pad = metric_label.ljust(label_w)
        body = "".join(c.rjust(14) for c in cells)
        print(f"{pad}{body}   {delta_s}")

    hdr_cells = [f"[{i + 1}]" for i in range(ncols)]
    row("metric", hdr_cells, "oldest→now")
    row("-" * min(label_w, 32), ["-" * 12] * ncols, "----------")

    for path_keys, name in METRICS:
        raw_vals = [_n(d, *path_keys) for d in datas]
        cells = [_fmt_cell(v) for v in raw_vals]
        delta_s = _numeric_delta(raw_vals[0], raw_vals[-1])
        row(name, cells, delta_s)

    print()
    print(
        "Note: ML queue depths are on GET /api/system_monitoring/automation/status "
        "(pending_counts), not backlog_status. Pair automation_status_*.json with jq if needed."
    )
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] == "timeline":
        paths = [Path(x) for x in argv[1:]]
        if not _validate_json_paths(paths, pair=False):
            return 2
        return _timeline(paths)
    if len(argv) == 2:
        a, b = Path(argv[0]), Path(argv[1])
        if not _validate_json_paths([a, b], pair=True):
            return 2
        return _pair_compare(a, b)
    print(
        "usage:\n"
        "  compare_backlog_snapshots.py BACKLOG_OLD.json BACKLOG_NEW.json\n"
        "    (paths under .local/backlog_snapshots/backlog_status_*.json — not literal older.json)\n"
        "  compare_backlog_snapshots.py timeline OLD.json ... NEW.json\n"
        "\n"
        "Shortcuts:\n"
        "  ./scripts/backlog_burndown.sh diff\n"
        "  ./scripts/backlog_burndown.sh timeline",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
