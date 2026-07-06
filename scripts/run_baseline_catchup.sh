#!/usr/bin/env bash
# Targeted baseline catch-up: top three backlog phases (dependency order).
#
#   1. unified_intake_extraction  — spine upstream (largest intake debt)
#   2. claim_extraction           — starved downstream (0 runs / 5k+ pending)
#   3. entity_profile_build     — largest profile wall (hybrid fast path)
#
# Usage:
#   ./scripts/run_baseline_catchup.sh dry-run
#   ./scripts/run_baseline_catchup.sh run          # foreground
#   ./scripts/run_baseline_catchup.sh run-bg       # background (recommended)
#   ./scripts/run_baseline_catchup.sh status
#   ./scripts/run_baseline_catchup.sh stop
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/baseline_catchup.log"
PID_FILE="$ROOT/data/baseline_catchup.pid"
STATE="$ROOT/data/baseline_catchup_state.json"

cd "$ROOT"
mkdir -p "$LOG_DIR" "$ROOT/data"

_load_env() {
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  if [[ -f "$ROOT/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "$ROOT/.db_password_widow")"
  fi
  set +a
  export PYTHONPATH=api
  export DB_HOST="${DB_HOST:-127.0.0.1}"
  export DB_PORT="${DB_PORT:-6432}"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/catchup_env.sh"
}

_export_baseline_env() {
  export BULK_CATCHUP_ACTIVE=1
  export BACKLOG_SPRINT_ACTIVE=1
  export BASELINE_CATCHUP_FLOOR="${BASELINE_CATCHUP_FLOOR:-500}"
  export BASELINE_CATCHUP_LOOPS="${BASELINE_CATCHUP_LOOPS:-25}"
  export BASELINE_CATCHUP_STALL="${BASELINE_CATCHUP_STALL:-5}"

  # Unified intake — throughput tuning (forced baseline defaults; .env cannot override)
  export UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS="${UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS:-3600}"
  export UNIFIED_INTAKE_EXTRACTION_PARALLEL="${BASELINE_CATCHUP_UNIFIED_PARALLEL:-8}"
  export UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE="${BASELINE_CATCHUP_UNIFIED_BATCH_SIZE:-3}"
  export OLLAMA_EXTRACTION_NUM_PREDICT="${BASELINE_CATCHUP_OLLAMA_EXTRACTION_NUM_PREDICT:-4096}"
  export BULK_GPU_PARALLEL="${BASELINE_CATCHUP_GPU_PARALLEL:-6}"
  export BULK_CPU_PARALLEL="${BASELINE_CATCHUP_CPU_PARALLEL:-3}"
  export BULK_EXTRACTION_MODEL="${BASELINE_CATCHUP_EXTRACTION_MODEL:-qwen2.5:32b-instruct}"
  export UNIFIED_INTAKE_DEFER_CONTEXT_SYNC="${BASELINE_CATCHUP_DEFER_CONTEXT_SYNC:-1}"
  export AUTOMATION_BULK_CATCHUP_PAUSE=1
  export OLLAMA_GPU_CONCURRENCY="${BASELINE_CATCHUP_GPU_PARALLEL:-6}"

  # Claims — full drain, was starved overnight
  export CLAIM_EXTRACTION_DRAIN=true
  export BULK_CLAIM_LIMIT="${BULK_CLAIM_LIMIT:-5000}"
  export CLAIM_EXTRACTION_PARALLEL="${CLAIM_EXTRACTION_PARALLEL:-32}"

  # Entity profiles — hybrid fast path + parallel drain
  export ENTITY_PROFILE_BUILD_ANYTIME=true
  export ENTITY_PROFILE_BUILD_DRAIN=true
  export ENTITY_PROFILE_BUILD_PARALLEL="${ENTITY_PROFILE_BUILD_PARALLEL:-4}"
  export MAJOR_CATCHUP_BUILD_BATCH_INITIAL="${MAJOR_CATCHUP_BUILD_BATCH_INITIAL:-200}"
  export MAJOR_CATCHUP_BUILD_BATCH_MAX="${MAJOR_CATCHUP_BUILD_BATCH_MAX:-250}"
  export MAJOR_CATCHUP_FLOOR="${MAJOR_CATCHUP_FLOOR:-$BASELINE_CATCHUP_FLOOR}"
  export MAJOR_CATCHUP_LOOPS="${MAJOR_CATCHUP_LOOPS:-$BASELINE_CATCHUP_LOOPS}"
  export MAJOR_CATCHUP_GPU_PARALLEL="${MAJOR_CATCHUP_GPU_PARALLEL:-4}"
}

_kill_baseline() {
  pkill -f "run_baseline_catchup.sh run" 2>/dev/null || true
  pkill -f "bulk_catchup.py --force --phase unified_intake" 2>/dev/null || true
  pkill -f "bulk_catchup.py --force --phase claim_extraction" 2>/dev/null || true
  pkill -f "run_major_backlog_catchup.py --force --phases entity_profile_build" 2>/dev/null || true
  sleep 1
}

cmd_stop() {
  echo "=== Stopping baseline catch-up ==="
  _kill_baseline
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
  "$ROOT/scripts/resume_after_hyperfocus.sh" 2>/dev/null || true
  echo "Done."
}

_run_phases() {
  local floor="$BASELINE_CATCHUP_FLOOR"
  local loops="$BASELINE_CATCHUP_LOOPS"
  local stall="$BASELINE_CATCHUP_STALL"
  local py="$ROOT/.venv/bin/python3"

  echo "=== Baseline catch-up $(date -u -Iseconds) floor=$floor loops=$loops ===" | tee -a "$LOG_FILE"
  echo "Phases: unified_intake_extraction → claim_extraction → entity_profile_build" | tee -a "$LOG_FILE"

  if [[ ! -f "$ROOT/data/bulk_catchup_competition_pause.json" ]]; then
    "$ROOT/scripts/pause_for_bulk_catchup.sh" 2>&1 | tail -3 | tee -a "$LOG_FILE" || true
  fi

  echo "--- Phase 1/3: unified_intake_extraction ---" | tee -a "$LOG_FILE"
  "$py" api/scripts/bulk_catchup.py --force \
    --phase unified_intake_extraction \
    --loops "$loops" \
    --floor "$floor" \
    --stall-loops "$stall" 2>&1 | tee -a "$LOG_FILE"

  echo "--- Phase 2/3: claim_extraction ---" | tee -a "$LOG_FILE"
  "$py" api/scripts/bulk_catchup.py --force \
    --phase claim_extraction \
    --loops "$loops" \
    --floor "$floor" \
    --claim-limit "${BULK_CLAIM_LIMIT:-5000}" \
    --stall-loops "$stall" 2>&1 | tee -a "$LOG_FILE"

  echo "--- Phase 3/3: entity_profile_build ---" | tee -a "$LOG_FILE"
  "$py" api/scripts/run_major_backlog_catchup.py --force \
    --phases entity_profile_build \
    --loops "$loops" \
    --floor "$floor" \
    --stall-loops "$stall" 2>&1 | tee -a "$LOG_FILE"

  echo "=== Baseline catch-up finished $(date -u -Iseconds) ===" | tee -a "$LOG_FILE"
  "$py" api/scripts/bulk_catchup_status.py 2>&1 | tee -a "$LOG_FILE" || true
  "$ROOT/scripts/resume_after_hyperfocus.sh" 2>&1 | tee -a "$LOG_FILE" || true
  rm -f "$PID_FILE"
}

cmd_dry_run() {
  _load_env
  _export_baseline_env
  local py="$ROOT/.venv/bin/python3"
  echo "=== Baseline catch-up dry-run ==="
  echo "floor=$BASELINE_CATCHUP_FLOOR loops=$BASELINE_CATCHUP_LOOPS"
  "$py" api/scripts/bulk_catchup.py --dry-run --force --phase unified_intake_extraction --floor "$BASELINE_CATCHUP_FLOOR"
  "$py" api/scripts/bulk_catchup.py --dry-run --force --phase claim_extraction --floor "$BASELINE_CATCHUP_FLOOR"
  "$py" api/scripts/run_major_backlog_catchup.py --dry-run --force --phases entity_profile_build --floor "$BASELINE_CATCHUP_FLOOR"
}

cmd_run() {
  _load_env
  _export_baseline_env
  _run_phases
}

cmd_run_bg() {
  _load_env
  _export_baseline_env
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Baseline catch-up already running pid=$(cat "$PID_FILE")" >&2
    exit 1
  fi
  nohup bash "$ROOT/scripts/run_baseline_catchup.sh" run >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "Baseline catch-up pid=$(cat "$PID_FILE") log=$LOG_FILE"
}

cmd_status() {
  _load_env
  echo "=== Baseline catch-up status $(date -u -Iseconds) ==="
  [[ -f "$PID_FILE" ]] && echo "pid: $(cat "$PID_FILE")" || echo "pid: (none)"
  [[ -f "$STATE" ]] && python3 -c "import json; print(json.dumps(json.load(open('$STATE')), indent=2))" 2>/dev/null || true
  echo "--- pending (top) ---"
  .venv/bin/python3 api/scripts/bulk_catchup_status.py 2>/dev/null | head -20 || true
  echo "--- log tail ---"
  tail -15 "$LOG_FILE" 2>/dev/null || echo "(no log)"
  pgrep -af "run_baseline_catchup|bulk_catchup.py --force --phase|run_major_backlog_catchup.py --force --phases entity_profile" || echo "(no active phase)"
}

main() {
  local cmd="${1:-status}"
  shift || true
  case "$cmd" in
    stop) cmd_stop ;;
    dry-run) cmd_dry_run ;;
    run) cmd_run ;;
    run-bg) cmd_run_bg ;;
    status) cmd_status ;;
    *)
      echo "Usage: $0 {dry-run|run|run-bg|status|stop}" >&2
      exit 1
      ;;
  esac
}

main "$@"
