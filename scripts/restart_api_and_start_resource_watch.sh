#!/usr/bin/env bash
# Restart the FastAPI process (uvicorn main:app) and start host_resource_watch in the background.
# Default watch: 4 hours, 30s interval, DB stats + CSV under .local/
#
# Usage:
#   ./scripts/restart_api_and_start_resource_watch.sh
#   MINUTES=120 INTERVAL=60 ./scripts/restart_api_and_start_resource_watch.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$ROOT/api"
LOG_DIR="$ROOT/logs"
LOCAL_DIR="$ROOT/.local"
MINUTES="${MINUTES:-240}"
INTERVAL="${INTERVAL:-30}"
VENV_PY="$ROOT/.venv/bin/python"
API_UVICORN_PGREP='uvicorn.*(main|main_v4):app'

mkdir -p "$LOG_DIR" "$LOCAL_DIR"

if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: expected venv at $VENV_PY" >&2
  exit 1
fi

echo "Stopping API (uvicorn)..."
if pgrep -f "$API_UVICORN_PGREP" >/dev/null 2>&1; then
  pkill -f "$API_UVICORN_PGREP" || true
  sleep 2
  if pgrep -f "$API_UVICORN_PGREP" >/dev/null 2>&1; then
    echo "Forcing kill..."
    pkill -9 -f "$API_UVICORN_PGREP" || true
    sleep 1
  fi
else
  echo "(no matching uvicorn process)"
fi

if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
  sleep 1
fi

echo "Starting API..."
cd "$API_DIR"
nohup "$VENV_PY" -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "$LOG_DIR/api_server.log" 2>&1 &
API_PID=$!
echo "$API_PID" > "$LOG_DIR/api.pid"
echo "  PID $API_PID (logs: $LOG_DIR/api_server.log)"

echo "Waiting for health..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8000/api/system_monitoring/health" >/dev/null 2>&1; then
    echo "  Health OK"
    break
  fi
  sleep 2
done
if ! curl -sf "http://127.0.0.1:8000/api/system_monitoring/health" >/dev/null 2>&1; then
  echo "WARNING: health check still failing; see $LOG_DIR/api_server.log" >&2
fi

STAMP="$(date -u +%Y%m%dT%H%MZ)"
CSV="$LOCAL_DIR/host_resource_watch_${STAMP}.csv"
LOG_OUT="$LOCAL_DIR/host_resource_watch_${STAMP}.log"
PID_FILE="$LOCAL_DIR/host_resource_watch_${STAMP}.pid"

echo "Starting host_resource_watch (${MINUTES} min, interval ${INTERVAL}s)..."
echo "  CSV: $CSV"
echo "  Log: $LOG_OUT"
cd "$ROOT"
nohup uv run python scripts/host_resource_watch.py \
  --minutes "$MINUTES" \
  --interval "$INTERVAL" \
  --db-stats \
  --csv "$CSV" >"$LOG_OUT" 2>&1 &
WATCH_PID=$!
echo "$WATCH_PID" >"$PID_FILE"
echo "  Watch PID $WATCH_PID (stop: kill $WATCH_PID)"
echo ""
echo "Review in ~${MINUTES} minutes:"
echo "  tail -80 $LOG_OUT"
echo "  column -t -s, $CSV | tail -20   # optional"
