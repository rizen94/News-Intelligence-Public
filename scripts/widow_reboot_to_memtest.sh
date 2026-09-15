#!/usr/bin/env bash
# One-shot: stop NI app plane, set next GRUB boot to memtest86+, reboot Widow.
# Invoked by: widow-reboot-to-memtest.service (calendar one-shot; does NOT persist DEFAULT).
# Does not change GRUB_DEFAULT permanently — only grub-reboot (next boot).
set -euo pipefail

LOG_TAG="widow-reboot-to-memtest"
LOG_DIR="${WIDOW_MEMTEST_LOG_DIR:-/var/log/news-intelligence}"
LOG="${LOG_DIR}/widow-reboot-to-memtest.log"
MARKER="${WIDOW_MEMTEST_MARKER:-/var/tmp/widow-reboot-to-memtest.requested}"
FLAG_DONE="${WIDOW_MEMTEST_DONE_FLAG:-/var/tmp/widow-reboot-to-memtest.done}"
# Prefer non-serial entry; override if needed.
MEMTEST_TITLE="${WIDOW_MEMTEST_GRUB_TITLE:-Memory test (memtest86+x64.bin)}"
NTFY_BASE="${WIDOW_NTFY_BASE:-http://192.168.93.99:18586}"
NTFY_TOPIC="${WIDOW_NTFY_TOPIC:-homelab-alerts}"
GRUB_CFG="${WIDOW_GRUB_CFG:-/boot/grub/grub.cfg}"

mkdir -p "$LOG_DIR"

log() {
  local line="[$(date -Is)] $*"
  echo "$line" | tee -a "$LOG"
  logger -t "$LOG_TAG" "$*" 2>/dev/null || true
}

notify() {
  local title="$1"
  local body="$2"
  curl -sS -m 8 \
    -H "Title: ${title}" \
    -H "Priority: high" \
    -H "Tags: warning,computer" \
    -d "$body" \
    "${NTFY_BASE}/${NTFY_TOPIC}" >/dev/null 2>&1 || true
}

# Idempotent: if already fired successfully this window, do nothing.
if [ -f "$FLAG_DONE" ]; then
  log "ABORT: done flag exists ($FLAG_DONE) — refusing second memtest reboot"
  exit 0
fi

# Safety: refuse if uptime < 30 minutes (boot-loop guard; matches nightly reboot).
UPTIME_SECONDS=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 9999)
MIN_UPTIME_SECONDS=1800
if [ "$UPTIME_SECONDS" -lt "$MIN_UPTIME_SECONDS" ]; then
  log "ABORT: uptime ${UPTIME_SECONDS}s < ${MIN_UPTIME_SECONDS}s — refusing reboot"
  notify "Widow memtest reboot ABORTED" "Uptime too low (${UPTIME_SECONDS}s). No reboot."
  exit 1
fi

log "starting memtest reboot sequence (uptime: ${UPTIME_SECONDS}s)"
notify "Widow memtest reboot STARTING" \
  "Stopping NI app plane, disabling nightly reboot timer, grub-reboot to '${MEMTEST_TITLE}', then reboot. Morning restore is still human."

# 1. Prevent 03:00 graceful reboot from interrupting memtest overnight.
if systemctl is-enabled --quiet widow-nightly-reboot.timer 2>/dev/null \
  || systemctl is-active --quiet widow-nightly-reboot.timer 2>/dev/null; then
  log "disabling widow-nightly-reboot.timer for memtest window"
  sudo -n systemctl disable --now widow-nightly-reboot.timer || true
else
  log "widow-nightly-reboot.timer already inactive/disabled"
fi

# 2. Stop application plane (same order as widow_graceful_reboot.sh).
if systemctl is-active --quiet news-intelligence-api-public 2>/dev/null; then
  log "stopping news-intelligence-api-public"
  sudo -n systemctl stop news-intelligence-api-public || true
fi
if systemctl is-active --quiet newsplatform-secondary 2>/dev/null; then
  log "stopping newsplatform-secondary"
  sudo -n systemctl stop newsplatform-secondary || true
fi
sleep 8

# 3. Checkpoint Postgres (leave PG/PgBouncer/nginx for systemd reboot stop).
if sudo -n -u postgres psql -c "CHECKPOINT;" >/dev/null 2>&1; then
  log "postgres CHECKPOINT ok"
else
  log "postgres CHECKPOINT skipped (not available)"
fi

# 4. Resolve memtest GRUB entry (must exist; prefer exact title match).
if ! sudo -n test -r "$GRUB_CFG"; then
  log "ERROR: cannot read $GRUB_CFG — aborting, no reboot"
  notify "Widow memtest reboot FAILED" "Cannot read ${GRUB_CFG}. No reboot."
  exit 2
fi

if ! sudo -n grep -Fq "menuentry \"${MEMTEST_TITLE}\"" "$GRUB_CFG" \
  && ! sudo -n grep -Fq "menuentry '${MEMTEST_TITLE}'" "$GRUB_CFG"; then
  log "ERROR: GRUB entry not found: ${MEMTEST_TITLE}"
  log "HINT: sudo grep memtest ${GRUB_CFG}"
  notify "Widow memtest reboot FAILED" "GRUB entry missing: ${MEMTEST_TITLE}. No reboot."
  exit 3
fi

log "setting one-shot next boot via grub-reboot: ${MEMTEST_TITLE}"
if ! sudo -n grub-reboot "${MEMTEST_TITLE}"; then
  log "ERROR: grub-reboot failed — aborting, no reboot"
  notify "Widow memtest reboot FAILED" "grub-reboot failed for '${MEMTEST_TITLE}'. No reboot."
  exit 4
fi

# Verify next_entry was set (best-effort).
if sudo -n grub-editenv list 2>/dev/null | tee -a "$LOG" | grep -q .; then
  log "grub-editenv list captured above"
else
  log "WARN: grub-editenv list empty or unavailable (continuing)"
fi

date -Is > "$MARKER" 2>/dev/null || true
date -Is > "$FLAG_DONE" 2>/dev/null || true
log "marker=${MARKER} done_flag=${FLAG_DONE}"

# 5. Disarm this one-shot timer so it cannot fire again.
if systemctl list-unit-files widow-reboot-to-memtest.timer >/dev/null 2>&1; then
  log "disabling widow-reboot-to-memtest.timer (one-shot complete)"
  sudo -n systemctl disable --now widow-reboot-to-memtest.timer 2>/dev/null || true
fi

sync
log "sync ok; issuing systemctl reboot"
notify "Widow rebooting to memtest86+" \
  "grub-reboot set to '${MEMTEST_TITLE}'. Expect host offline overnight. Morning: console PASS/FAIL → Debian → restore NI + re-enable widow-nightly-reboot.timer."

# Small delay so ntfy/log flush before network dies.
sleep 2
exec sudo -n systemctl reboot
