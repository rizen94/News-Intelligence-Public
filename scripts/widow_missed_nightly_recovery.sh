#!/usr/bin/env bash
# After an abrupt host death, the 00:45 graceful reboot is skipped (timer Persistent=false).
# On boot, detect a missed nightly window and ensure the NI stack is up for heavy (01:00+).
#
# Install: scripts/setup_widow_boot_stack.sh (or enable widow-missed-nightly-recovery.service)
set -euo pipefail

MARKER="${WIDOW_REBOOT_MARKER:-/var/tmp/widow-nightly-reboot.requested}"
LOG_DIR="${WIDOW_REBOOT_LOG_DIR:-/var/log/news-intelligence}"
LOG="${LOG_DIR}/widow-missed-nightly-recovery.log"
MAX_MARKER_AGE_SEC="${WIDOW_MISSED_REBOOT_MAX_AGE_SEC:-90000}"  # 25h

mkdir -p "$LOG_DIR" 2>/dev/null || sudo mkdir -p "$LOG_DIR" 2>/dev/null || true

log() {
  local line="[$(date -Is)] $*"
  echo "$line" | tee -a "$LOG" 2>/dev/null || echo "$line"
  logger -t widow-missed-nightly "$*" 2>/dev/null || true
}

# Local hour (US/Eastern expected on Widow)
hour=$(date +%H)
# Only act once we are past the scheduled reboot window
if [ "$hour" -lt 1 ]; then
  log "skip: before 01:00 local (hour=${hour}) — nightly reboot may still run"
  exit 0
fi

# Idempotency for same calendar day (timer + boot can both fire)
STAMP_DIR="${WIDOW_RECOVERY_STAMP_DIR:-/var/tmp}"
STAMP="${STAMP_DIR}/widow-missed-nightly-recovery.$(date +%F)"
if [ -f "$STAMP" ]; then
  log "skip: already recovered today (${STAMP})"
  exit 0
fi

missed=0
if [ ! -f "$MARKER" ]; then
  missed=1
  log "WARN: no nightly reboot marker at ${MARKER}"
else
  now=$(date +%s)
  mtime=$(stat -c %Y "$MARKER" 2>/dev/null || echo 0)
  age=$((now - mtime))
  if [ "$age" -gt "$MAX_MARKER_AGE_SEC" ]; then
    missed=1
    log "WARN: nightly reboot marker stale age=${age}s (max ${MAX_MARKER_AGE_SEC}s) — abrupt halt likely skipped 00:45"
  else
    log "ok: nightly reboot marker age=${age}s"
  fi
fi

if [ "$missed" -eq 0 ]; then
  exit 0
fi

log "MISSED_NIGHTLY_REBOOT: ensuring core stack is active for heavy window"
ensure() {
  local u="$1"
  if systemctl cat "$u" &>/dev/null && ! systemctl is-active --quiet "$u"; then
    log "starting ${u}"
    sudo systemctl start "$u" || log "WARN: failed to start ${u}"
  fi
}

ensure postgresql
ensure postgresql@16-main
ensure pgbouncer
ensure nginx
ensure news-intelligence.target
ensure news-intelligence-api-public
ensure newsplatform-secondary

# Record recovery so we do not spam the same day / leave marker forever-stale
echo "$(date -Is) recovered_after_missed_nightly" | sudo tee "$MARKER" >/dev/null || \
  echo "$(date -Is) recovered_after_missed_nightly" >"$MARKER"
date -Is >"$STAMP" 2>/dev/null || sudo tee "$STAMP" >/dev/null <<<"$(date -Is)"
log "recovery complete — marker refreshed; stack ensured"
