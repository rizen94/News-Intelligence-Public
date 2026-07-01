#!/usr/bin/env bash
# Stop NI API + competing work, then run focused unlimited extraction catch-up.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export NEWS_INTEL_ROOT="$ROOT"
PY="${ROOT}/.venv/bin/python3"
LOG="${EXTRACTION_CATCHUP_LOG:-/tmp/ni_extraction_burn_down.log}"
PID_FILE="${ROOT}/data/extraction_catchup.pid"
ENV_OVERLAY="${ROOT}/configs/env.extraction_catchup.env"

echo "==> Stopping existing catch-up / burn-down processes"
pkill -f "api/scripts/run_extraction_burn_down.py" 2>/dev/null || true
pkill -f "api/scripts/run_event_extraction_catchup.py" 2>/dev/null || true
pkill -f "api/scripts/run_major_backlog_catchup.py" 2>/dev/null || true
pkill -f "api/scripts/bulk_catchup.py" 2>/dev/null || true
sleep 2

echo "==> Stopping News Intelligence API (automation competes for GPU)"
if systemctl list-unit-files news-intelligence-api-public.service &>/dev/null 2>&1; then
  if systemctl is-active --quiet news-intelligence-api-public.service 2>/dev/null; then
    sudo systemctl stop news-intelligence-api-public.service
    echo "   stopped news-intelligence-api-public.service"
  else
    echo "   news-intelligence-api-public.service already inactive"
  fi
else
  NI_API_PORT="${NI_API_PORT:-${API_PORT:-8000}}"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${NI_API_PORT}/tcp" 2>/dev/null || true
  fi
  pkill -f "uvicorn main:app" 2>/dev/null || true
  pkill -f "api/main.py" 2>/dev/null || true
  echo "   cleared manual API listeners on port ${NI_API_PORT}"
fi
sleep 2

echo "==> Pausing competing ingest / NRI (API stays down during catch-up)"
if [[ -x "$ROOT/scripts/pause_for_bulk_catchup.sh" ]]; then
  NEWS_INTEL_ROOT="$ROOT" bash "$ROOT/scripts/pause_for_bulk_catchup.sh" || true
else
  mkdir -p "$ROOT/data"
  PYTHONPATH=api python3 - <<'PY'
from shared.bulk_catchup_pause import write_pause_marker
write_pause_marker(reason="start_focused_extraction_catchup.sh", by="operator")
print("Wrote competition pause marker")
PY
fi

set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
# shellcheck disable=SC1091
[[ -f "$ENV_OVERLAY" ]] && source "$ENV_OVERLAY"
# shellcheck disable=SC1091
source "$ROOT/scripts/catchup_env.sh"
set +a
export PYTHONPATH="${PYTHONPATH:-api}"

mkdir -p "$ROOT/data"
echo "==> Entity pre-clear + false-pass reconciliation"
PYTHONPATH=api "$PY" api/scripts/reconcile_false_pass_markers.py --phase entity_preclear --limit 50000
PYTHONPATH=api "$PY" api/scripts/reconcile_false_pass_markers.py --phase entity_false_output --limit 50000

echo "==> Starting unlimited extraction burn-down (unified → topic; PopOS GPU only; log: $LOG)"
nohup "$PY" api/scripts/run_extraction_burn_down.py \
  --force \
  --loops 0 \
  --floor 0 \
  --no-dual-lane \
  --stall-loops "${EXTRACTION_BURN_DOWN_STALL_LOOPS:-8}" \
  --budget-seconds "${UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS:-14400}" \
  --gpu-parallel "${BULK_GPU_PARALLEL:-8}" \
  --cpu-parallel "${BULK_CPU_PARALLEL:-4}" \
  --ollama-timeout "${BULK_OLLAMA_TIMEOUT:-900}" \
  >>"$LOG" 2>&1 &
echo $! >"$PID_FILE"
echo "   PID $(cat "$PID_FILE") — tail -f $LOG"
echo "   Resume API after: $ROOT/scripts/resume_after_extraction_catchup.sh"
