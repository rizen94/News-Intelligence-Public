#!/usr/bin/env bash
set -euo pipefail

DEV_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_FILE="${PROD_ROOT}/logs/entity_profile_build_catchup.log"
TRIGGER_DONE="${PROD_ROOT}/data/entity_profile_build_watcher.done"
PID_FILE="${PROD_ROOT}/data/entity_profile_build_watcher.pid"

# Ensure single instance
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Watcher already running (PID=$(cat "$PID_FILE")). Exiting."
    exit 0
fi
echo "$$" > "$PID_FILE"
trap 'rm -f "$PID_FILE" "$TRIGGER_DONE"' EXIT

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

_start_next_phase() {
  if [[ -f "$TRIGGER_DONE" ]]; then
    return  # already triggered
  fi
  _load_env
  echo "[$(date -u -Iseconds)] Triggering entity_dossier_compile (pending <= 500 detected)..."
  # Run the next phase in background, using the same pattern as the catchup launcher
  nohup "${DEV_ROOT}/scripts/run_entity_profile_build_catchup.sh" run-bg --phases entity_dossier_compile >>"${PROD_ROOT}/logs/entity_dossier_compile_watcher.log" 2>&1 &
  echo $! >"${PROD_ROOT}/data/entity_dossier_compile_watcher.pid"
  touch "$TRIGGER_DONE"
  echo "[$(date -u -Iseconds)] entity_dossier_compile started."
  # After triggering, we can exit
  exit 0
}

main() {
  _load_env
  echo "[$(date -u -Iseconds)] Starting entity_profile_build watcher (checking every 30s for pending <= 500)..."
  while true; do
    # If log doesn't exist yet, wait a bit
    if [[ ! -f "$LOG_FILE" ]]; then
      sleep 5
      continue
    fi
    # Get the most recent line that contains the pending info
    # We'll look for lines like: "2026-07-09 11:26:43,674 INFO entity_profile_build loop 2/200 pending=833 batch=250"
    # Also could be: "Phase entity_profile_build: pending=833 batch=250"
    pending=$(grep -E 'entity_profile_build.*pending=[0-9]+.*batch=' "$LOG_FILE" | tail -1 | sed -nE 's/.*pending=([0-9]+).*batch=.*/\1/p')
    # If the above didn't match, try the Phase line
    if [[ -z "$pending" ]]; then
      pending=$(grep -E 'Phase entity_profile_build: pending=[0-9]+' "$LOG_FILE" | tail -1 | sed -nE 's/.*Phase entity_profile_build: pending=([0-9]+).*/\1/p')
    fi
    if [[ -n "$pending" ]] && (( pending <= 500 )); then
      echo "[$(date -u -Iseconds)] Detected pending=$pending <=500. Triggering next phase."
      _start_next_phase
      break
    fi
    # Also check for explicit completion
    if grep -q "=== Complete ===" "$LOG_FILE"; then
      echo "[$(date -u -Iseconds)] Found completion marker. Triggering next phase."
      _start_next_phase
      break
    fi
    sleep 30
  done
}
main "$@" &
