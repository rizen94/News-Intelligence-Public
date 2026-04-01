#!/usr/bin/env bash
# Burndown workflow: snapshot API JSON, pair diff, or 4-snapshot timeline table.
# Usage:
#   ./scripts/backlog_burndown.sh snapshot          # same as snapshot_backlog_status.sh
#   ./scripts/backlog_burndown.sh diff               # last two backlog_status_*.json
#   ./scripts/backlog_burndown.sh diff OLD.json NEW.json
#   ./scripts/backlog_burndown.sh timeline           # up to 4 most recent snapshots, one table (oldest→newest)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/.local/backlog_snapshots"
CMD="${1:-snapshot}"

case "$CMD" in
  snapshot)
    exec bash "${ROOT}/scripts/snapshot_backlog_status.sh"
    ;;
  timeline)
    mkdir -p "$OUT_DIR"
    mapfile -t files < <(ls -1 "$OUT_DIR"/backlog_status_*.json 2>/dev/null | sort || true)
    n="${#files[@]}"
    if [[ "$n" -lt 2 ]]; then
      echo "Need at least two backlog_status_*.json files in $OUT_DIR (run: $0 snapshot)" >&2
      exit 1
    fi
    start=$((n >= 4 ? n - 4 : 0))
    args=()
    for ((i = start; i < n; i++)); do
      args+=("${files[i]}")
    done
    exec uv run python "${ROOT}/scripts/compare_backlog_snapshots.py" timeline "${args[@]}"
    ;;
  diff)
    shift || true
    if [[ $# -eq 2 ]]; then
      exec uv run python "${ROOT}/scripts/compare_backlog_snapshots.py" "$1" "$2"
    fi
    if [[ $# -ne 0 ]]; then
      echo "usage: $0 diff [BACKLOG_OLD.json BACKLOG_NEW.json]" >&2
      exit 2
    fi
    mkdir -p "$OUT_DIR"
    mapfile -t files < <(ls -1 "$OUT_DIR"/backlog_status_*.json 2>/dev/null | sort || true)
    n="${#files[@]}"
    if [[ "$n" -lt 2 ]]; then
      echo "Need at least two backlog_status_*.json files in $OUT_DIR (run: $0 snapshot)" >&2
      exit 1
    fi
    older="${files[$((n - 2))]}"
    newer="${files[$((n - 1))]}"
    echo "older: $older"
    echo "newer: $newer"
    echo ""
    exec uv run python "${ROOT}/scripts/compare_backlog_snapshots.py" "$older" "$newer"
    ;;
  help|-h|--help)
    echo "Usage: $0 snapshot | timeline | diff [BACKLOG_OLD.json BACKLOG_NEW.json]"
    exit 0
    ;;
  *)
    echo "Unknown command: $CMD (use snapshot, diff, or help)" >&2
    exit 2
    ;;
esac
