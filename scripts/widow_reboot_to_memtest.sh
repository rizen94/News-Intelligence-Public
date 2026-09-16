#!/usr/bin/env bash
# One-shot: stop NI app plane, set next GRUB boot to memtest86+, reboot Widow.
# Invoked by: widow-reboot-to-memtest.service (calendar one-shot; does NOT persist DEFAULT).
# Does not change GRUB_DEFAULT permanently — only grub next_entry (next boot).
#
# Widow boot topology (critical):
#   - Live root + /boot is USB Toshiba (sdc1, UUID 435f4509-…).
#   - BIOS loads GRUB from the PNY SSD (sdb, UUID a12a2d5c-…); that GRUB's
#     default is "Widow USB Toshiba root" and its $prefix/grubenv is on PNY.
#   - Plain `grub-reboot` only writes the live USB grubenv, which BIOS GRUB
#     does not load — so we MUST also set next_entry on the PNY grubenv.
#
# Live path on Widow: /opt/news-intelligence/scripts/widow_reboot_to_memtest.sh
# Symlink: /usr/local/sbin/widow-reboot-to-memtest.sh
# Repo: News Intelligence scripts/widow_reboot_to_memtest.sh
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
# Filesystem UUID of the disk whose GRUB BIOS actually loads (PNY SSD).
BIOS_GRUB_FS_UUID="${WIDOW_BIOS_GRUB_FS_UUID:-a12a2d5c-0f35-4934-924f-02a89db9fd30}"
# USB root UUID — memtest binary + live /boot live here.
USB_ROOT_FS_UUID="${WIDOW_USB_ROOT_FS_UUID:-435f4509-f615-45ec-b2ed-7b77ea8a70f9}"
BIOS_GRUB_MNT="${WIDOW_BIOS_GRUB_MNT:-/mnt/widow-bios-grub}"

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

cfg_has_memtest_title() {
  local cfg="$1"
  sudo -n grep -Fq "menuentry \"${MEMTEST_TITLE}\"" "$cfg" \
    || sudo -n grep -Fq "menuentry '${MEMTEST_TITLE}'" "$cfg"
}

ensure_memtest_on_bios_grub_cfg() {
  # Inject memtest menuentries into the BIOS-loaded grub.cfg if missing.
  local cfg="$1"
  if cfg_has_memtest_title "$cfg"; then
    log "BIOS GRUB cfg already has entry: ${MEMTEST_TITLE}"
    return 0
  fi
  log "injecting memtest menuentries into BIOS GRUB cfg: $cfg"
  sudo -n tee -a "$cfg" >/dev/null <<EOF

### BEGIN widow memtest one-shot (BIOS GRUB on PNY; binary on USB root) ###
menuentry "${MEMTEST_TITLE}" {
	insmod part_msdos
	insmod ext2
	search --no-floppy --fs-uuid --set=root ${USB_ROOT_FS_UUID}
	linux   /boot/memtest86+x64.bin
}
menuentry "${MEMTEST_TITLE}, serial console" {
	insmod part_msdos
	insmod ext2
	search --no-floppy --fs-uuid --set=root ${USB_ROOT_FS_UUID}
	linux	/boot/memtest86+x64.bin console=ttyS0,115200
}
### END widow memtest one-shot ###
EOF
}

set_next_entry_on_grubenv() {
  local envfile="$1"
  sudo -n grub-editenv "$envfile" set "next_entry=${MEMTEST_TITLE}"
  local got
  got="$(sudo -n grub-editenv "$envfile" list 2>/dev/null | sed -n 's/^next_entry=//p' || true)"
  if [ "$got" != "$MEMTEST_TITLE" ]; then
    log "ERROR: failed to set next_entry on $envfile (got='${got}')"
    return 1
  fi
  log "next_entry set on $envfile"
  sudo -n grub-editenv "$envfile" list 2>/dev/null | tee -a "$LOG" || true
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
  "Stopping NI app plane, disabling nightly reboot timer, set BIOS-GRUB next_entry to '${MEMTEST_TITLE}', then reboot. Morning restore is still human."

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

# 4. Resolve memtest GRUB entry on live USB cfg (binary + canonical title live here).
if ! sudo -n test -r "$GRUB_CFG"; then
  log "ERROR: cannot read $GRUB_CFG — aborting, no reboot"
  notify "Widow memtest reboot FAILED" "Cannot read ${GRUB_CFG}. No reboot."
  exit 2
fi

if ! cfg_has_memtest_title "$GRUB_CFG"; then
  log "ERROR: GRUB entry not found on live cfg: ${MEMTEST_TITLE}"
  log "HINT: sudo grep memtest ${GRUB_CFG}"
  notify "Widow memtest reboot FAILED" "GRUB entry missing: ${MEMTEST_TITLE}. No reboot."
  exit 3
fi

if ! sudo -n test -r "/boot/memtest86+x64.bin"; then
  log "ERROR: memtest binary missing: /boot/memtest86+x64.bin"
  notify "Widow memtest reboot FAILED" "memtest86+x64.bin missing on USB /boot. No reboot."
  exit 3
fi

# 5. Set one-shot next_entry on the GRUB env BIOS actually loads (PNY), then
#    also on the live USB env (belt-and-suspenders if prefixes ever unify).
BIOS_MOUNTED=0
cleanup_bios_mnt() {
  if [ "$BIOS_MOUNTED" = "1" ]; then
    sync || true
    sudo -n umount "$BIOS_GRUB_MNT" 2>/dev/null || true
    BIOS_MOUNTED=0
  fi
}
trap cleanup_bios_mnt EXIT

if ! sudo -n test -b "/dev/disk/by-uuid/${BIOS_GRUB_FS_UUID}"; then
  log "ERROR: BIOS GRUB filesystem UUID not present: ${BIOS_GRUB_FS_UUID}"
  notify "Widow memtest reboot FAILED" "PNY BIOS GRUB UUID missing (${BIOS_GRUB_FS_UUID}). No reboot."
  exit 4
fi

sudo -n mkdir -p "$BIOS_GRUB_MNT"
if findmnt -n "$BIOS_GRUB_MNT" >/dev/null 2>&1; then
  log "BIOS GRUB mount already present at $BIOS_GRUB_MNT"
else
  sudo -n mount -o rw "/dev/disk/by-uuid/${BIOS_GRUB_FS_UUID}" "$BIOS_GRUB_MNT"
  BIOS_MOUNTED=1
fi

BIOS_GRUB_CFG="${BIOS_GRUB_MNT}/boot/grub/grub.cfg"
BIOS_GRUB_ENV="${BIOS_GRUB_MNT}/boot/grub/grubenv"
if ! sudo -n test -r "$BIOS_GRUB_CFG" || ! sudo -n test -w "$BIOS_GRUB_ENV"; then
  log "ERROR: BIOS GRUB cfg/env missing under $BIOS_GRUB_MNT"
  notify "Widow memtest reboot FAILED" "PNY /boot/grub missing. No reboot."
  exit 4
fi

ensure_memtest_on_bios_grub_cfg "$BIOS_GRUB_CFG"
if ! cfg_has_memtest_title "$BIOS_GRUB_CFG"; then
  log "ERROR: could not ensure memtest entry on BIOS GRUB cfg"
  notify "Widow memtest reboot FAILED" "PNY grub.cfg missing memtest entry. No reboot."
  exit 4
fi

# Copy binary onto PNY too (entry prefers USB UUID; local copy is fallback inventory).
if ! sudo -n test -r "${BIOS_GRUB_MNT}/boot/memtest86+x64.bin"; then
  log "copying memtest86+x64.bin onto PNY /boot"
  sudo -n cp /boot/memtest86+x64.bin "${BIOS_GRUB_MNT}/boot/memtest86+x64.bin"
fi

log "setting one-shot next_entry on BIOS (PNY) grubenv: ${MEMTEST_TITLE}"
if ! set_next_entry_on_grubenv "$BIOS_GRUB_ENV"; then
  notify "Widow memtest reboot FAILED" "Could not set next_entry on PNY grubenv. No reboot."
  exit 4
fi

log "also setting live USB grubenv via grub-reboot (may be ignored by BIOS GRUB)"
if sudo -n grub-reboot "${MEMTEST_TITLE}"; then
  sudo -n grub-editenv list 2>/dev/null | tee -a "$LOG" || true
else
  log "WARN: grub-reboot (live USB) failed — continuing because BIOS PNY env is set"
fi

cleanup_bios_mnt
trap - EXIT

date -Is > "$MARKER" 2>/dev/null || true
date -Is > "$FLAG_DONE" 2>/dev/null || true
log "marker=${MARKER} done_flag=${FLAG_DONE}"

# 6. Disarm this one-shot timer so it cannot fire again.
if systemctl list-unit-files widow-reboot-to-memtest.timer >/dev/null 2>&1; then
  log "disabling widow-reboot-to-memtest.timer (one-shot complete)"
  sudo -n systemctl disable --now widow-reboot-to-memtest.timer 2>/dev/null || true
fi

sync
log "sync ok; issuing systemctl reboot"
notify "Widow rebooting to memtest86+" \
  "BIOS(PNY) next_entry='${MEMTEST_TITLE}'. Expect host offline overnight. Morning: console PASS/FAIL → Debian → restore NI + re-enable widow-nightly-reboot.timer."

# Small delay so ntfy/log flush before network dies.
sleep 2
exec sudo -n systemctl reboot
