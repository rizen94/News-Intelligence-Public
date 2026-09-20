#!/usr/bin/env bash
# One-off full-pipeline backlog burndown on PopOS GPU (GPU-only, large batches).
#
# Usage:
#   ./scripts/run_backlog_gpu_sprint.sh stop
#   ./scripts/run_backlog_gpu_sprint.sh dry-run
#   ./scripts/run_backlog_gpu_sprint.sh run          # foreground
#   ./scripts/run_backlog_gpu_sprint.sh run-bg
#   ./scripts/run_backlog_gpu_sprint.sh status
#   ./scripts/run_backlog_gpu_sprint.sh resume
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/backlog_gpu_sprint.log"
PID_FILE="$ROOT/data/backlog_gpu_sprint.pid"
STATE="$ROOT/data/backlog_gpu_sprint_state.json"

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

_export_sprint_env() {
  export BACKLOG_SPRINT_GPU_HOST="${BACKLOG_SPRINT_GPU_HOST:-${OLLAMA_GPU_HOST:-http://192.168.93.99:11434}}"
  export BACKLOG_SPRINT_GPU_MODEL_EXTRACTION="${BACKLOG_SPRINT_GPU_MODEL_EXTRACTION:-qwen2.5:32b-instruct}"
  export BACKLOG_SPRINT_GPU_MODEL_FAST="${BACKLOG_SPRINT_GPU_MODEL_FAST:-llama3.1:8b}"
  export BACKLOG_SPRINT_GPU_PARALLEL_HEAVY="${BACKLOG_SPRINT_GPU_PARALLEL_HEAVY:-3}"
  export BACKLOG_SPRINT_GPU_PARALLEL_FAST="${BACKLOG_SPRINT_GPU_PARALLEL_FAST:-8}"
  export BACKLOG_SPRINT_DUAL_LANE=false
  export BACKLOG_SPRINT_FLOOR="${BACKLOG_SPRINT_FLOOR:-200}"
  export BACKLOG_SPRINT_MAX_LOOPS="${BACKLOG_SPRINT_MAX_LOOPS:-50}"
  export BACKLOG_SPRINT_BATCH_EVENT="${BACKLOG_SPRINT_BATCH_EVENT:-500}"
  export BACKLOG_SPRINT_BATCH_ENTITY_PER_DOMAIN="${BACKLOG_SPRINT_BATCH_ENTITY_PER_DOMAIN:-500}"
  export BACKLOG_SPRINT_BATCH_CLAIM="${BACKLOG_SPRINT_BATCH_CLAIM:-5000}"
  export BACKLOG_SPRINT_OLLAMA_TIMEOUT="${BACKLOG_SPRINT_OLLAMA_TIMEOUT:-900}"
  export PYTHONPATH=api
}

_kill_competitors() {
  for pattern in \
    "run_backlog_gpu_sprint.py" \
    "run_major_backlog_catchup.py" \
    "run_hyperfocus_backlog" \
    "bulk_catchup.py" \
    "catchup_topic_clustering.py"; do
    pkill -f "$pattern" 2>/dev/null || true
  done
  sleep 2
}

cmd_stop() {
  echo "=== Stopping backlog competitors ==="
  _kill_competitors
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
  "$ROOT/scripts/quiesce_for_hyperfocus.sh"
  echo "Done. API should be inactive; pause marker set."
}

cmd_dry_run() {
  _load_env
  _export_sprint_env
  .venv/bin/python3 api/scripts/run_backlog_gpu_sprint.py --dry-run
}

cmd_run() {
  _kill_competitors
  if [[ ! -f "$ROOT/data/bulk_catchup_competition_pause.json" ]]; then
    "$ROOT/scripts/pause_for_bulk_catchup.sh" 2>&1 | tail -3
  fi
  systemctl is-active --quiet news-intelligence-api-public 2>/dev/null && \
    echo "WARN: API still active — run './scripts/run_backlog_gpu_sprint.sh stop' first" >&2
  _load_env
  _export_sprint_env
  echo "=== Backlog GPU sprint $(date -u -Iseconds) log=$LOG_FILE ==="
  .venv/bin/python3 api/scripts/run_backlog_gpu_sprint.py --force "$@" 2>&1 | tee -a "$LOG_FILE"
}

cmd_run_bg() {
  _kill_competitors
  if systemctl is-active --quiet news-intelligence-api-public 2>/dev/null; then
    echo "API still active — run './scripts/run_backlog_gpu_sprint.sh stop' first" >&2
    exit 1
  fi
  if [[ ! -f "$ROOT/data/bulk_catchup_competition_pause.json" ]]; then
    "$ROOT/scripts/pause_for_bulk_catchup.sh" 2>&1 | tail -2
  fi
  _load_env
  _export_sprint_env
  nohup .venv/bin/python3 api/scripts/run_backlog_gpu_sprint.py --force "$@" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "Sprint pid=$(cat "$PID_FILE") log=$LOG_FILE"
}

cmd_status() {
  _load_env
  echo "=== Backlog GPU sprint status $(date -u -Iseconds) ==="
  [[ -f "$PID_FILE" ]] && echo "pid_file: $(cat "$PID_FILE")" || echo "pid_file: (none)"
  [[ -f "$STATE" ]] && python3 -c "import json; print(json.dumps(json.load(open('$STATE')), indent=2))" || echo "(no state)"
  echo "--- pending ---"
  .venv/bin/python3 api/scripts/bulk_catchup_status.py 2>/dev/null | head -40 || true
  echo "--- processes ---"
  pgrep -af "run_backlog_gpu_sprint|run_major_backlog|bulk_catchup|hyperfocus" || echo "(none)"
  echo "--- log tail ---"
  tail -8 "$LOG_FILE" 2>/dev/null || echo "(no log yet)"
}

cmd_resume() {
  "$ROOT/scripts/resume_after_hyperfocus.sh"
  rm -f "$PID_FILE"
  echo "Sprint resume complete. Monitor: PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup_status.py --watch 60"
}

main() {
  local cmd="${1:-status}"
  shift || true
  case "$cmd" in
    stop) cmd_stop ;;
    dry-run) cmd_dry_run ;;
    run) cmd_run "$@" ;;
    run-bg) cmd_run_bg "$@" ;;
    status) cmd_status ;;
    resume) cmd_resume ;;
    *)
      echo "Usage: $0 {stop|dry-run|run|run-bg|status|resume}" >&2
      exit 1
      ;;
  esac
}

main "$@"
