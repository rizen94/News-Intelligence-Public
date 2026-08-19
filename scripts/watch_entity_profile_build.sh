#!/usr/bin/env bash
# Watch entity_profile_build log and trigger next phase when pending is low.
set -euo pipefail

DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_DIR="${PROD_ROOT}/logs"
LOG_FILE="${LOG_DIR}/entity_profile_build_catchup.log"
# Where to write the trigger flag
TRIGGER_FILE="${PROD_ROOT}/data/entity_profile_build_done.trigger"

# Ensure directories exist
mkdir -p "$LOG_DIR" "$(dirname "$TRIGGER_FILE")"

# Source environment (same as catchup script)
_load_env() {
  set -a
  if [[ -f "${PROD_ROOT}/.env" ]]; then
    source "${PROD_ROOT}/.env"
  elif [[ -f "${DEV_ROOT}/.env" ]]; then
    source "${DEV_ROOT}/.env"
  else
    echo "No .env found in ${PROD_ROOT} or ${DEV_ROOT}" >&2
    exit 1
  fi
  if [[ -f "${PROD_ROOT}/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "${PROD_ROOT}/.db_password_widow")"
  elif [[ -f "${DEV_ROOT}/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "${DEV_ROOT}/.db_password_widow")"
  fi
  set +a
  export PYTHONPATH="${DEV_ROOT}/api"
  export DB_HOST="${DB_HOST:-127.0.0.1}"
  export DB_PORT="${DB_PORT:-6432}"
  source "${DEV_ROOT}/scripts/catchup_env.sh"
}

# Export needed vars for the next phase
_export_next_phase_env() {
  export BULK_CATCHUP_ACTIVE=1
  export BACKLOG_SPRINT_ACTIVE=1
  export ENTITY_DOSSER_COMPILE_ANYTIME=true
  export ENTITY_DOSSER_COMPILE_DRAIN=true
  export ENTITY_DOSSER_COMPILE_PARALLEL="${ENTITY_DOSSER_COMPILE_PARALLEL:-12}"
  export DOSSIER_COMPILE_BATCH_INITIAL="${DOSSIER_COMPILE_BATCH_INITIAL:-500}"
  export DOSSIER_COMPILE_BATCH_MAX="${DOSSIER_COMPILE_BATCH_MAX:-1000}"
  export DOSSIER_COMPILE_FLOOR="${DOSSIER_COMPILE_FLOOR:-100}"
  export DOSSIER_COMPILE_LOOPS="${DOSSIER_COMPILE_LOOPS:-5}"
  export DOSSIER_COMPILE_STALL_LOOPS="${DOSSIER_COMPILE_STALL_LOOPS:-3}"
  export AUTOMATION_BULK_CATCHUP_PAUSE=1
}

_start_next_phase() {
  _load_env
  _export_next_phase_env
  echo "[$(date -u -Iseconds)] Triggering entity_dossier_compile phase..." | tee -a "${LOG_FILE}"
  "${DEV_ROOT}/scripts/run_major_backlog_catchup.sh" run-bg --phases entity_dossier_compile 2>&1 | tee -a "${LOG_FILE}"
  # After starting, we can exit; the watcher's job is done.
  exit 0
}

main() {
  _load_env
  echo "[$(date -u -Iseconds)] Starting watcher for entity_profile_build completion..." | tee -a "${LOG_FILE}"
  # Tail the log and look for completion signals
  # We'll look for either:
  #   - "Phase entity_profile_build: pending=0"
  #   - Or a line with "loop .* batch=" where the pending number shown in the same line is <= 500 (floor)
  # We'll use a simple grep -m 1 to stop at first match.
  # Since the log is being written, we use tail -F.
  tail -F "${LOG_FILE}" | while IFS= read -r line; do
    echo "$line" >> /tmp/watch_entity_profile_build.log 2>/dev/null || true
    if [[ "$line" =~ Phase\ entity_profile_build:\ pending=([0-9]+) ]]; then
      pending="${BASH_REMATCH[1]}"
      if (( pending <= 500 )); then
        echo "[$(date -u -Iseconds)] Detected low pending=${pending} in line: $line" | tee -a "${LOG_FILE}"
        _start_next_phase
      fi
    fi
    # Also watch for explicit completion message
    if [[ "$line" == *"=== Complete ==="* ]]; then
      echo "[$(date -u -Iseconds)] Detected completion marker: $line" | tee -a "${LOG_FILE}"
      _start_next_phase
    fi
    # If we see a line indicating a new loop started with batch and pending low, also trigger
    if [[ "$line" =~ entity_profile_build\ loop\ [0-9]+\/200\ pending=([0-9]+)\ batch= ]]; then
      pending="${BASH_REMATCH[1]}"
      if (( pending <= 500 )); then
        echo "[$(date -u -Iseconds)] Detected low pending in loop line: $line" | tee -a "${LOG_FILE}"
        _start_next_phase
      fi
    fi
  done
}
# Run main in background so we can return
main "$@" &
