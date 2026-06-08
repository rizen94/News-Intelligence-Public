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
  sed "s|/opt/news-intelligence|$DEPLOY_DIR|g; s|WIDOW_USER|$WIDOW_USER|g" "$src" \
    | sudo tee "/etc/cron.d/$dest_name" > /dev/null
  sudo chmod 644 "/etc/cron.d/$dest_name"
  echo "✅ Installed /etc/cron.d/$dest_name"
}

# Executable helper scripts
chmod +x "$SCRIPT_DIR/systemd_db_probe.py" \
         "$SCRIPT_DIR/systemd_wait_readiness.sh" \
         "$SCRIPT_DIR/verify_widow_boot.sh" \
         "$SCRIPT_DIR/archive_logs_to_nas.sh" \
         "$SCRIPT_DIR/db_backup_weekly_retained.sh" \
         "$SCRIPT_DIR/db_backup_single_latest.sh" 2>/dev/null || true
mkdir -p "$DEPLOY_DIR/logs"

# Systemd units
install_unit "$PROJECT_DIR/infrastructure/news-intelligence-api-public.service" "news-intelligence-api-public.service"
install_unit "$PROJECT_DIR/infrastructure/newsplatform-secondary.service" "newsplatform-secondary.service"
install_unit "$PROJECT_DIR/infrastructure/news-intelligence.target" "news-intelligence.target"
install_unit "$PROJECT_DIR/infrastructure/news-intelligence-boot-check.service" "news-intelligence-boot-check.service"

sudo systemctl daemon-reload

# Cron jobs
install_cron "$PROJECT_DIR/infrastructure/widow-db-adjacent.cron" "news-intelligence-widow-db"
install_cron "$PROJECT_DIR/infrastructure/newsplatform-backup.cron" "newsplatform-backup"
install_cron "$PROJECT_DIR/infrastructure/news-intelligence-log-archive.cron" "news-intelligence-log-archive"
install_cron "$PROJECT_DIR/infrastructure/news-intelligence-weekly-backup.cron" "news-intelligence-weekly-backup"

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
