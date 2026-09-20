#!/usr/bin/env bash
# Entity profile build catch-up — batched LLM + auto-tune (dev code via PYTHONPATH).
set -euo pipefail

DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_DIR="${ENTITY_PROFILE_CATCHUP_LOG_DIR:-$DEV_ROOT/logs}"
DATA_DIR="${ENTITY_PROFILE_CATCHUP_DATA_DIR:-$DEV_ROOT/data}"
LOG_FILE="$LOG_DIR/entity_profile_build_catchup.log"
PID_FILE="$DATA_DIR/entity_profile_build_catchup.pid"

mkdir -p "$LOG_DIR" "$DATA_DIR"

_load_env() {
  set -a
  if [[ -f "$PROD_ROOT/.env" ]]; then
    # shellcheck source=/dev/null
    source "$PROD_ROOT/.env"
  elif [[ -f "$DEV_ROOT/.env" ]]; then
    # shellcheck source=/dev/null
    source "$DEV_ROOT/.env"
  else
    echo "No .env in $PROD_ROOT or $DEV_ROOT" >&2
    exit 1
  fi
  if [[ -f "$PROD_ROOT/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "$PROD_ROOT/.db_password_widow")"
  elif [[ -f "$DEV_ROOT/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "$DEV_ROOT/.db_password_widow")"
  fi
  set +a
  export PYTHONPATH="$DEV_ROOT/api"
  export DB_HOST="${DB_HOST:-127.0.0.1}"
  export DB_PORT="${DB_PORT:-6432}"
  # shellcheck source=/dev/null
  source "$DEV_ROOT/scripts/catchup_env.sh"
}

_export_profile_env() {
  export BULK_CATCHUP_ACTIVE=1
  export BACKLOG_SPRINT_ACTIVE=1
  export ENTITY_PROFILE_BUILD_ANYTIME=true
  export ENTITY_PROFILE_BUILD_DRAIN=true
  export ENTITY_PROFILE_BUILD_PARALLEL="${ENTITY_PROFILE_BUILD_PARALLEL:-8}"
  export ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE="${ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE:-30}"
  export MAJOR_CATCHUP_GPU_PARALLEL="${MAJOR_CATCHUP_GPU_PARALLEL:-8}"
  export MAJOR_CATCHUP_BUILD_BATCH_INITIAL="${MAJOR_CATCHUP_BUILD_BATCH_INITIAL:-200}"
  export MAJOR_CATCHUP_BUILD_BATCH_MAX="${MAJOR_CATCHUP_BUILD_BATCH_MAX:-250}"
  export MAJOR_CATCHUP_FLOOR="${MAJOR_CATCHUP_FLOOR:-500}"
  export MAJOR_CATCHUP_LOOPS="${MAJOR_CATCHUP_LOOPS:-200}"
  export MAJOR_CATCHUP_STALL_LOOPS="${MAJOR_CATCHUP_STALL_LOOPS:-8}"
  export MAJOR_CATCHUP_GPU_METRICS_SSH="${MAJOR_CATCHUP_GPU_METRICS_SSH:-pete@192.168.93.99}"
  export AUTOMATION_BULK_CATCHUP_PAUSE=1
}

_stop() {
  pkill -f "run_major_backlog_catchup.py.*entity_profile_build" 2>/dev/null || true
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
  sleep 1
}

cmd_stop() {
  echo "Stopping entity profile build catch-up"
  _stop
  echo "Done."
}

cmd_status() {
  _load_env
  echo "=== entity_profile_build catch-up $(date -u -Iseconds) ==="
  echo "dev_code: $DEV_ROOT/api"
  [[ -f "$PID_FILE" ]] && echo "pid: $(cat "$PID_FILE")" || echo "pid: (none)"
  pgrep -af "run_major_backlog_catchup.py.*entity_profile_build" || echo "(no process)"
  echo "--- log tail ---"
  tail -20 "$LOG_FILE" 2>/dev/null || echo "(no log)"
}

cmd_run_bg() {
  _stop
  _load_env
  _export_profile_env
  cd "$DEV_ROOT"
  mkdir -p "$DEV_ROOT/logs" "$LOG_DIR"
  PY="${PROD_ROOT}/.venv/bin/python3"
  if [[ ! -x "$PY" ]]; then
    PY="${DEV_ROOT}/.venv/bin/python3"
  fi
  if [[ ! -x "$PY" ]]; then
    PY="$(command -v python3)"
  fi
  echo "=== entity_profile_build catch-up $(date -u -Iseconds) ===" | tee -a "$LOG_FILE"
  echo "PYTHONPATH=$PYTHONPATH chunk=$ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE parallel=$ENTITY_PROFILE_BUILD_PARALLEL" | tee -a "$LOG_FILE"
  nohup "$PY" "$DEV_ROOT/api/scripts/run_major_backlog_catchup.py" --force \
    --phases entity_profile_build \
    --loops "$MAJOR_CATCHUP_LOOPS" \
    --floor "$MAJOR_CATCHUP_FLOOR" \
    --stall-loops "$MAJOR_CATCHUP_STALL_LOOPS" \
    >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "Started pid=$(cat "$PID_FILE") log=$LOG_FILE"
}

main() {
  local cmd="${1:-status}"
  case "$cmd" in
    stop) cmd_stop ;;
    status) cmd_status ;;
    run-bg) cmd_run_bg ;;
    *)
      echo "Usage: $0 {run-bg|status|stop}" >&2
      exit 1
      ;;
  esac
}

main "$@"
