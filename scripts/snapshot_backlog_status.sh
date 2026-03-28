#!/usr/bin/env bash
# Save GET /api/system_monitoring/backlog_status JSON for burndown comparison.
# Outputs under .local/backlog_snapshots/ (gitignored). Compare with compare_backlog_snapshots.py.
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
echo "Compare backlog: uv run python scripts/compare_backlog_snapshots.py <older.json> <newer.json>"
