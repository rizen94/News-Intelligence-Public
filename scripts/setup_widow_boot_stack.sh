#!/bin/bash
# News Intelligence — install full Widow boot stack (systemd + cron).
# Run ON Widow: cd /opt/news-intelligence && ./scripts/setup_widow_boot_stack.sh
# Or: ssh widow "cd /opt/news-intelligence && ./scripts/setup_widow_boot_stack.sh"
#
# Idempotent: safe to re-run after pulling repo updates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

WIDOW_USER="${WIDOW_USER:-$(whoami)}"
DEPLOY_DIR="${DEPLOY_DIR:-$PROJECT_DIR}"

echo "=== News Intelligence Widow boot stack setup ==="
echo "Deploy dir: $DEPLOY_DIR"
echo "User:       $WIDOW_USER"
echo ""

install_unit() {
  local src="$1"
  local dest_name="$2"
  if [ ! -f "$src" ]; then
    echo "⚠️  Missing $src — skipping"
    return
  fi
  sed "s|/opt/news-intelligence|$DEPLOY_DIR|g; s|WIDOW_USER|$WIDOW_USER|g" "$src" \
    | sudo tee "/etc/systemd/system/$dest_name" > /dev/null
  echo "✅ Installed /etc/systemd/system/$dest_name"
}

install_cron() {
  local src="$1"
  local dest_name="$2"
  if [ ! -f "$src" ]; then
    echo "⚠️  Missing $src — skipping cron"
    return
  fi
  # cron.d requires a trailing newline or the entire file is ignored
  {
    sed "s|/opt/news-intelligence|$DEPLOY_DIR|g; s|WIDOW_USER|$WIDOW_USER|g" "$src"
    printf '\n'
  } | sudo tee "/etc/cron.d/$dest_name" > /dev/null
  sudo chmod 644 "/etc/cron.d/$dest_name"
  echo "✅ Installed /etc/cron.d/$dest_name"
}

# Executable helper scripts
chmod +x "$SCRIPT_DIR/systemd_db_probe.py" \
         "$SCRIPT_DIR/systemd_wait_readiness.sh" \
         "$SCRIPT_DIR/verify_widow_boot.sh" \
         "$SCRIPT_DIR/archive_logs_to_nas.sh" \
         "$SCRIPT_DIR/db_backup_weekly_retained.sh" \
         "$SCRIPT_DIR/db_backup_single_latest.sh" \
         "$SCRIPT_DIR/widow_missed_nightly_recovery.sh" \
         "$SCRIPT_DIR/widow_graceful_reboot.sh" \
         "$SCRIPT_DIR/widow_disk_io_governor.sh" \
         "$SCRIPT_DIR/widow_daily_upgrade.sh" \
         "$SCRIPT_DIR/widow_api_health_watchdog.sh" 2>/dev/null || true
mkdir -p "$DEPLOY_DIR/logs"

# Host helpers for disk IO governor + gated apt (USB root)
sudo install -m 755 "$SCRIPT_DIR/widow_disk_io_governor.sh" /usr/local/sbin/widow_disk_io_governor.sh
sudo install -m 755 "$SCRIPT_DIR/widow_daily_upgrade.sh" /usr/local/sbin/widow-daily-upgrade.sh
sudo install -m 755 "$SCRIPT_DIR/widow_api_health_watchdog.sh" /usr/local/sbin/widow_api_health_watchdog.sh
echo "✅ Installed /usr/local/sbin/widow_disk_io_governor.sh + widow-daily-upgrade.sh + widow_api_health_watchdog.sh"

# Hardware RuntimeWatchdog (SP5100 /dev/watchdog) — reboot if kernel stops petting
if [ -f "$PROJECT_DIR/infrastructure/systemd/99-widow-runtime-watchdog.conf" ]; then
  sudo mkdir -p /etc/systemd/system.conf.d
  sudo cp "$PROJECT_DIR/infrastructure/systemd/99-widow-runtime-watchdog.conf" \
    /etc/systemd/system.conf.d/99-widow-runtime-watchdog.conf
  echo "✅ Installed /etc/systemd/system.conf.d/99-widow-runtime-watchdog.conf"
fi

# journald caps — reduce USB root write storms from log floods
if [ -f "$PROJECT_DIR/infrastructure/journald-widow-usb-root.conf" ]; then
  sudo mkdir -p /etc/systemd/journald.conf.d
  sudo cp "$PROJECT_DIR/infrastructure/journald-widow-usb-root.conf" \
    /etc/systemd/journald.conf.d/99-widow-usb-root.conf
  sudo systemctl restart systemd-journald 2>/dev/null || true
  echo "✅ Installed journald USB-root limits"
fi

# Systemd units
install_unit "$PROJECT_DIR/infrastructure/news-intelligence-api-public.service" "news-intelligence-api-public.service"
install_unit "$PROJECT_DIR/infrastructure/newsplatform-secondary.service" "newsplatform-secondary.service"
install_unit "$PROJECT_DIR/infrastructure/news-intelligence.target" "news-intelligence.target"
install_unit "$PROJECT_DIR/infrastructure/news-intelligence-boot-check.service" "news-intelligence-boot-check.service"
install_unit "$PROJECT_DIR/infrastructure/systemd/widow-missed-nightly-recovery.service" "widow-missed-nightly-recovery.service"
install_unit "$PROJECT_DIR/infrastructure/systemd/widow-missed-nightly-recovery.timer" "widow-missed-nightly-recovery.timer"
install_unit "$PROJECT_DIR/infrastructure/widow-disk-io-governor.service" "widow-disk-io-governor.service"
install_unit "$PROJECT_DIR/infrastructure/widow-disk-io-governor.timer" "widow-disk-io-governor.timer"
install_unit "$PROJECT_DIR/infrastructure/widow-api-health-watchdog.service" "widow-api-health-watchdog.service"
install_unit "$PROJECT_DIR/infrastructure/widow-api-health-watchdog.timer" "widow-api-health-watchdog.timer"

# API memory cgroup drop-in (MemoryHigh / MemoryMax)
DROPIN_SRC="$PROJECT_DIR/infrastructure/news-intelligence-api-public.service.d"
DROPIN_DEST="/etc/systemd/system/news-intelligence-api-public.service.d"
if [ -d "$DROPIN_SRC" ]; then
  sudo mkdir -p "$DROPIN_DEST"
  sudo cp -a "$DROPIN_SRC/." "$DROPIN_DEST/"
  # Remove one-off overnight skip drop-in if present (replaced by nonblocking-readiness.conf)
  sudo rm -f "$DROPIN_DEST/skip-readiness-tonight.conf" 2>/dev/null || true
  echo "✅ Installed $DROPIN_DEST (memory.conf, nonblocking-readiness.conf)"
fi

sudo systemctl daemon-reload
# Apply RuntimeWatchdogSec without full reboot
sudo systemctl daemon-reexec 2>/dev/null || true

# Cron jobs
install_cron "$PROJECT_DIR/infrastructure/widow-db-adjacent.cron" "news-intelligence-widow-db"
install_cron "$PROJECT_DIR/infrastructure/newsplatform-backup.cron" "newsplatform-backup"
install_cron "$PROJECT_DIR/infrastructure/news-intelligence-log-archive.cron" "news-intelligence-log-archive"
install_cron "$PROJECT_DIR/infrastructure/news-intelligence-weekly-backup.cron" "news-intelligence-weekly-backup"
install_cron "$PROJECT_DIR/infrastructure/cron.d/widow-daily-upgrade" "widow-daily-upgrade"

# Enable infrastructure services (ignore if not installed on this host)
for svc in postgresql pgbouncer ollama nginx; do
  if systemctl list-unit-files "$svc.service" &>/dev/null; then
    sudo systemctl enable "$svc" 2>/dev/null && echo "✅ Enabled $svc" || echo "⚠️  Could not enable $svc"
  fi
done

# Enable News Intelligence stack
sudo systemctl enable news-intelligence.target
sudo systemctl enable news-intelligence-api-public
sudo systemctl enable newsplatform-secondary
sudo systemctl enable news-intelligence-boot-check 2>/dev/null || true
sudo systemctl enable --now widow-missed-nightly-recovery.timer 2>/dev/null && \
  echo "✅ Enabled widow-missed-nightly-recovery.timer" || \
  echo "⚠️  Could not enable widow-missed-nightly-recovery.timer"

# Disk IO governor (USB root write pressure → /run + DB advisory)
sudo systemctl enable --now widow-disk-io-governor.timer 2>/dev/null && \
  echo "✅ Enabled widow-disk-io-governor.timer" || \
  echo "⚠️  Could not enable widow-disk-io-governor.timer"
# API hang recovery (health probe → recycle API + secondary)
sudo systemctl enable --now widow-api-health-watchdog.timer 2>/dev/null && \
  echo "✅ Enabled widow-api-health-watchdog.timer" || \
  echo "⚠️  Could not enable widow-api-health-watchdog.timer"
# Debian unattended upgrade races our gated script — disable timer (keep apt-daily update)
sudo systemctl disable --now apt-daily-upgrade.timer 2>/dev/null && \
  echo "✅ Disabled apt-daily-upgrade.timer (use gated widow-daily-upgrade)" || true

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start (stops conflicting manual uvicorn on :8000 first):"
echo "  sudo fuser -k 8000/tcp 2>/dev/null || true"
echo "  sudo systemctl start news-intelligence.target"
echo ""
echo "Verify:"
echo "  $SCRIPT_DIR/verify_widow_boot.sh"
echo "  systemctl status news-intelligence-api-public newsplatform-secondary"
echo ""
echo "NAS mount (optional, for backups): see infrastructure/mnt-nas.mount.example"
