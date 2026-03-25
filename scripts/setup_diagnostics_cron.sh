#!/bin/bash
# Install cron: run diagnostics collector every 4 hours (same machine as the repo / API).
# Run once; paths are quoted for spaces (e.g. "News Intelligence").
# Requires: repo-root .venv with dependencies (uv sync / pip install).

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/logs/diagnostics_cron.log"
PY="${PROJECT_DIR}/.venv/bin/python"
SCRIPT="${PROJECT_DIR}/api/scripts/run_diagnostics_collect.py"

if [[ ! -x "$PY" ]]; then
  echo "❌ Expected venv python not found or not executable: $PY"
  echo "   Create venv and install deps (e.g. uv sync from repo root), then re-run."
  exit 1
fi

if [[ ! -f "$SCRIPT" ]]; then
  echo "❌ Script not found: $SCRIPT"
  exit 1
fi

mkdir -p "${PROJECT_DIR}/logs"

# Every 4 hours at minute 0: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
CRON_LINE="0 */4 * * * cd \"${PROJECT_DIR}\" && PYTHONPATH=api \"${PY}\" \"${SCRIPT}\" --summary >> \"${LOG_FILE}\" 2>&1"

CURRENT=$(crontab -l 2>/dev/null || true)
FILTERED=$(echo "$CURRENT" | grep -v "run_diagnostics_collect.py" | grep -v "News Intelligence.*diagnostics_cron.log" || true)

{
  echo "$FILTERED"
  echo ""
  echo "# News Intelligence — diagnostics summary every 4h (see docs/DIAGNOSTICS_EVENT_COLLECTOR.md)"
  echo "$CRON_LINE"
} | crontab -

echo "✅ Diagnostics cron installed (every 4 hours, --summary → logs/diagnostics_cron.log)."
echo "   Project: $PROJECT_DIR"
echo "   Verify:  crontab -l"
