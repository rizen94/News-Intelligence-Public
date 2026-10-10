#!/usr/bin/env bash
# Widow API health watchdog — recycle hung uvicorn without host reboot.
# Timer: widow-api-health-watchdog.timer (every 2 min).
#
# On 2 consecutive health failures (5s curl timeout):
#   stop secondary → restart (or SIGKILL) API → wait healthy → start secondary
# 30-minute cooldown after a recovery to avoid flap.

set -euo pipefail

API_UNIT="${API_UNIT:-news-intelligence-api-public.service}"
SECONDARY_UNIT="${SECONDARY_UNIT:-newsplatform-secondary.service}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/system_monitoring/health}"
CURL_MAX_SEC="${CURL_MAX_SEC:-5}"
FAIL_STREAK_NEED="${FAIL_STREAK_NEED:-2}"
COOLDOWN_SEC="${COOLDOWN_SEC:-1800}"
READY_WAIT_SEC="${READY_WAIT_SEC:-180}"

RUN_DIR="${DISK_IO_PRESSURE_RUN_DIR:-/run/news-intelligence}"
STREAK_FILE="${RUN_DIR}/api_health_fail_streak"
COOLDOWN_FILE="${RUN_DIR}/api_health_watchdog_cooldown"
LOG_DIR="${LOG_DIR:-/var/log/news-intelligence}"
LOG_FILE="${LOG_DIR}/api-health-watchdog.log"

mkdir -p "$RUN_DIR" "$LOG_DIR"

log() {
  local msg="[$(date -Iseconds)] $*"
  echo "$msg" | tee -a "$LOG_FILE" >/dev/null
  echo "$msg"
}

_read_streak() {
  if [[ -f "$STREAK_FILE" ]]; then
    cat "$STREAK_FILE" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

_write_streak() {
  echo "$1" >"$STREAK_FILE"
}

_in_cooldown() {
  [[ -f "$COOLDOWN_FILE" ]] || return 1
  local age
  age=$(( $(date +%s) - $(stat -c %Y "$COOLDOWN_FILE" 2>/dev/null || echo 0) ))
  [[ "$age" -lt "$COOLDOWN_SEC" ]]
}

_health_ok() {
  local code
  code=$(curl -sS --max-time "$CURL_MAX_SEC" -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
  [[ "$code" == "200" ]]
}

_wait_health() {
  local deadline=$(( $(date +%s) + READY_WAIT_SEC ))
  while (( $(date +%s) < deadline )); do
    if _health_ok; then
      return 0
    fi
    sleep 5
  done
  return 1
}

_recycle_api() {
  log "RECOVERY: stopping ${SECONDARY_UNIT}"
  systemctl stop "$SECONDARY_UNIT" 2>/dev/null || true

  log "RECOVERY: restarting ${API_UNIT}"
  if ! systemctl restart "$API_UNIT"; then
    log "RECOVERY: restart failed; SIGKILL + start"
    systemctl kill -s SIGKILL "$API_UNIT" 2>/dev/null || true
    sleep 2
    systemctl reset-failed "$API_UNIT" 2>/dev/null || true
    systemctl start "$API_UNIT" || true
  fi

  # If restart returned but process is still wedged, escalate after wait
  if ! _wait_health; then
    log "RECOVERY: health still down after ${READY_WAIT_SEC}s — SIGKILL + start"
    systemctl kill -s SIGKILL "$API_UNIT" 2>/dev/null || true
    sleep 2
    systemctl reset-failed "$API_UNIT" 2>/dev/null || true
    systemctl start "$API_UNIT" || true
    if ! _wait_health; then
      log "RECOVERY: FAILED — API still unhealthy; leaving secondary stopped"
      touch "$COOLDOWN_FILE"
      _write_streak 0
      return 1
    fi
  fi

  log "RECOVERY: API healthy — starting ${SECONDARY_UNIT}"
  systemctl start "$SECONDARY_UNIT" 2>/dev/null || true
  touch "$COOLDOWN_FILE"
  _write_streak 0
  log "RECOVERY: complete (cooldown ${COOLDOWN_SEC}s)"
  return 0
}

# --- main ---
if _in_cooldown; then
  # Still probe so we clear streak on recoveries outside this script
  if _health_ok; then
    _write_streak 0
  fi
  exit 0
fi

if _health_ok; then
  _write_streak 0
  exit 0
fi

streak=$(_read_streak)
# sanitize
[[ "$streak" =~ ^[0-9]+$ ]] || streak=0
streak=$((streak + 1))
_write_streak "$streak"
log "health FAIL streak=${streak}/${FAIL_STREAK_NEED}"

if (( streak >= FAIL_STREAK_NEED )); then
  _recycle_api || true
fi

exit 0
