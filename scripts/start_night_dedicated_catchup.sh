#!/usr/bin/env bash
# Stop NI API + competitors, then drain all remaining GPU catch-up on PopOS (unified intake first).
# Run on Widow: bash scripts/start_night_dedicated_catchup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export NEWS_INTEL_ROOT="$ROOT"

LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR" "${ROOT}/data"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/night_dedicated_catchup_${STAMP}.log"
PID_FILE="${ROOT}/data/night_dedicated_catchup.pid"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Night catch-up already running (pid $old_pid). Log: $(ls -t ${LOG_DIR}/night_dedicated_catchup_*.log 2>/dev/null | head -1)"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

echo "==> Quiesce Widow (API, cron, competing catch-ups)"
if systemctl is-active --quiet news-intelligence-api-public.service 2>/dev/null; then
  echo "ERROR: news-intelligence-api-public is still active."
  echo "Stop API first: sudo systemctl stop news-intelligence-api-public.service"
  echo "Dedicated catch-up must not run alongside the API (DB pool exhaustion)."
  exit 1
fi
bash "$ROOT/scripts/quiesce_for_hyperfocus.sh"

echo "==> Starting full PopOS GPU catch-up chain (log: $LOG)"
# Override steady-state .env for dedicated overnight burndown (PopOS 5090 saturated).
export BULK_USE_POPOS_GPU=true
export BULK_DUAL_LANE_CATCHUP=false
export BULK_GPU_PARALLEL="${NIGHT_CATCHUP_GPU_PARALLEL:-8}"
export BULK_CPU_PARALLEL="${NIGHT_CATCHUP_CPU_PARALLEL:-2}"
export UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS="${NIGHT_CATCHUP_BUDGET_SECONDS:-14400}"
export UNIFIED_INTAKE_EXTRACTION_PARALLEL="${NIGHT_CATCHUP_UNIFIED_PARALLEL:-8}"
export BULK_OLLAMA_TIMEOUT="${NIGHT_CATCHUP_OLLAMA_TIMEOUT:-900}"
nohup bash "$ROOT/scripts/run_remaining_catchup_popos.sh" >>"$LOG" 2>&1 &
echo $! >"$PID_FILE"
echo "   PID $(cat "$PID_FILE")"
echo "   tail -f $LOG"
echo "   Resume API when done: bash $ROOT/scripts/resume_after_extraction_catchup.sh"
echo "   (Also restores cron via data/hyperfocus_state.json if quiesce disabled it)"
