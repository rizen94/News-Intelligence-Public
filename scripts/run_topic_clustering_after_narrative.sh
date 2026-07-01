#!/usr/bin/env bash
# Wait for entity_dossier_narrative catch-up, then drain topic_clustering at full speed.
#
# Usage:
#   ./scripts/run_topic_clustering_after_narrative.sh              # wait + run (foreground)
#   ./scripts/run_topic_clustering_after_narrative.sh --bg         # background orchestrator
#   ./scripts/run_topic_clustering_after_narrative.sh --skip-wait  # topic clustering only
#   ./scripts/run_topic_clustering_after_narrative.sh --status
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/topic_clustering_after_narrative.log"
ORCH_PID_FILE="$ROOT/data/topic_clustering_after_narrative.pid"
TC_PID_FILE="$ROOT/data/topic_clustering_catchup.pid"
NARRATIVE_PATTERN='run_major_backlog_catchup.py --phases entity_dossier_narrative'
POLL_SECONDS="${NARRATIVE_POLL_SECONDS:-120}"

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

_export_topic_full_speed() {
  export BULK_CATCHUP_ACTIVE=1
  export OLLAMA_DUAL_HOST_ROUTING_ENABLED=true
  export OLLAMA_GPU_HOST="${OLLAMA_GPU_HOST:-${OLLAMA_POP_OS_HOST:-http://192.168.93.99:11434}}"
  export OLLAMA_GPU_CONCURRENCY="${TOPIC_CATCHUP_GPU_CONCURRENCY:-12}"
  export OLLAMA_TIMEOUT="${TOPIC_CATCHUP_OLLAMA_TIMEOUT:-900}"
  export OLLAMA_GPU_TIMEOUT="${TOPIC_CATCHUP_OLLAMA_TIMEOUT:-900}"
  export TOPIC_CLUSTERING_BATCH_SIZE="${TOPIC_CATCHUP_BATCH_SIZE:-200}"
  export TOPIC_CLUSTERING_CONCURRENCY="${TOPIC_CATCHUP_CONCURRENCY:-20}"
  export TOPIC_FAST_MATCH_MIN_SCORE="${TOPIC_FAST_MATCH_MIN_SCORE:-0.62}"
  export WORKER_DB_POOL_MAX="${TOPIC_CATCHUP_WORKER_DB_POOL_MAX:-32}"
}

_narrative_running() {
  pgrep -f "$NARRATIVE_PATTERN" >/dev/null 2>&1
}

_pending_narrative() {
  _load_env
  .venv/bin/python3 - <<'PY'
from services.dossier_compiler_service import count_dossier_narrative_pending
print(count_dossier_narrative_pending())
PY
}

_pending_topic() {
  _load_env
  .venv/bin/python3 - <<'PY'
from services.backlog_metrics import get_all_pending_counts
print(get_all_pending_counts().get("topic_clustering", 0))
PY
}

_wait_for_narrative() {
  echo "=== Waiting for entity_dossier_narrative to finish $(date -u -Iseconds) ===" | tee -a "$LOG_FILE"
  while _narrative_running; do
    pending="$(_pending_narrative 2>/dev/null || echo "?")"
    echo "$(date -u -Iseconds) narrative still running pending=$pending" | tee -a "$LOG_FILE"
    sleep "$POLL_SECONDS"
  done
  echo "$(date -u -Iseconds) narrative process exited" | tee -a "$LOG_FILE"
}

_ensure_competition_pause() {
  if [[ ! -f "$ROOT/data/bulk_catchup_competition_pause.json" ]]; then
    PYTHONPATH=api .venv/bin/python3 - <<'PY'
from shared.bulk_catchup_pause import write_pause_marker
write_pause_marker(reason="run_topic_clustering_after_narrative.sh", by="operator")
print("Wrote competition pause marker")
PY
  fi
}

_run_topic_clustering() {
  _load_env
  _export_topic_full_speed
  _ensure_competition_pause

  local batch="${TOPIC_CLUSTERING_BATCH_SIZE}"
  local concurrency="${TOPIC_CLUSTERING_CONCURRENCY}"
  local max_batches="${TOPIC_CATCHUP_MAX_BATCHES:-5000}"
  local pending="$(_pending_topic 2>/dev/null || echo "?")"

  echo "=== Topic clustering full-speed catch-up $(date -u -Iseconds) ===" | tee -a "$LOG_FILE"
  echo "pending=$pending batch=$batch concurrency=$concurrency max_batches=$max_batches gpu=$OLLAMA_GPU_HOST" | tee -a "$LOG_FILE"

  .venv/bin/python3 api/scripts/catchup_topic_clustering.py \
    --batch-size "$batch" \
    --concurrency "$concurrency" \
    --max-batches "$max_batches" \
    2>&1 | tee -a "$LOG_FILE"

  local after="$(_pending_topic 2>/dev/null || echo "?")"
  echo "=== Topic clustering catch-up finished $(date -u -Iseconds) pending=$after ===" | tee -a "$LOG_FILE"
}

cmd_status() {
  echo "=== topic_clustering_after_narrative status $(date -u -Iseconds) ==="
  [[ -f "$ORCH_PID_FILE" ]] && echo "orchestrator_pid: $(cat "$ORCH_PID_FILE")" || echo "orchestrator_pid: (none)"
  [[ -f "$TC_PID_FILE" ]] && echo "topic_catchup_pid: $(cat "$TC_PID_FILE")" || echo "topic_catchup_pid: (none)"
  echo "narrative_running: $(_narrative_running && echo yes || echo no)"
  _load_env 2>/dev/null || true
  echo "narrative_pending: $(_pending_narrative 2>/dev/null || echo "?")"
  echo "topic_pending: $(_pending_topic 2>/dev/null || echo "?")"
  echo "--- processes ---"
  pgrep -af "$NARRATIVE_PATTERN" || echo "(no narrative)"
  pgrep -af "catchup_topic_clustering.py" || echo "(no topic catchup)"
  echo "--- log tail ---"
  tail -12 "$LOG_FILE" 2>/dev/null || echo "(no log yet)"
}

cmd_main() {
  local skip_wait=false
  for arg in "$@"; do
    case "$arg" in
      --skip-wait) skip_wait=true ;;
      --status) cmd_status; return 0 ;;
      --bg) echo "Use: nohup $0 >>$LOG_FILE 2>&1 &"; return 1 ;;
    esac
  done

  if [[ "$skip_wait" != true ]]; then
    _wait_for_narrative
  fi
  _run_topic_clustering
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cmd_main "$@"
fi
