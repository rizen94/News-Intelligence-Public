#!/usr/bin/env bash
# Save GET backlog_status + automation/status JSON under .local/backlog_snapshots/ (gitignored),
# then print one timeline table across the current snapshot and up to 3 prior snapshots
# (same metrics, oldest → newest, with Δ oldest→now).
# From repo root you can run: ./snapshot_backlog_status
# Optional: BACKLOG_STATUS_URL, AUTOMATION_STATUS_URL (defaults localhost:8000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/.local/backlog_snapshots"
mkdir -p "$OUT_DIR"
TS="$(date -u +%Y%m%d_%H%M%S)"
URL="${BACKLOG_STATUS_URL:-http://127.0.0.1:8000/api/system_monitoring/backlog_status}"
OUT="${OUT_DIR}/backlog_status_${TS}.json"
curl -sS -m 120 "$URL" -o "$OUT"
echo "Wrote $OUT"
AST_URL="${AUTOMATION_STATUS_URL:-http://127.0.0.1:8000/api/system_monitoring/automation/status}"
AOUT="${OUT_DIR}/automation_status_${TS}.json"
curl -sS -m 60 "$AST_URL" -o "$AOUT"
echo "Wrote $AOUT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Current snapshot"
echo "  Files:  $(basename "$OUT")  +  $(basename "$AOUT")"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mapfile -t files < <(ls -1 "$OUT_DIR"/backlog_status_*.json 2>/dev/null | sort || true)
n="${#files[@]}"
newer="$OUT"
new_idx=-1
for ((i = 0; i < n; i++)); do
  if [[ "${files[i]}" == "$newer" ]]; then
    new_idx=$i
    break
  fi
done

if [[ "$new_idx" -lt 0 ]]; then
  echo "warning: new file not found in sorted listing; skipping timeline." >&2
  exit 0
fi

if [[ "$new_idx" -eq 0 ]]; then
  echo ""
  echo "No prior backlog_status snapshots — timeline will appear on the next run."
  exit 0
fi

start=$((new_idx >= 3 ? new_idx - 3 : 0))
timeline_args=()
for ((i = start; i <= new_idx; i++)); do
  timeline_args+=("${files[i]}")
done

echo ""
echo "Progress timeline (${#timeline_args[@]} snapshots, oldest → newest):"
echo ""
uv run python "${ROOT}/scripts/compare_backlog_snapshots.py" timeline "${timeline_args[@]}"

echo ""
echo "Pair diff (last two files only):  ./scripts/backlog_burndown.sh diff"
