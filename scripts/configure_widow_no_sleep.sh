#!/bin/bash
# News Intelligence — Keep server on full time (no suspend/hibernate/power-saver shutdown)
# Run ON the server (Widow or any Linux box you want always-on):
#   sudo ./scripts/configure_widow_no_sleep.sh
# Or from your dev machine (if you have ssh access):
#   ssh your-server "curl -sL https://... | sudo bash"
#   ssh your-server "cd /path/to/News\ Intelligence && sudo ./scripts/configure_widow_no_sleep.sh"

set -e

echo "=========================================="
echo "Configure server to stay on (no sleep/suspend)"
echo "=========================================="

# 1. systemd-logind: block user- and system-triggered suspend/hibernate
echo "[1/4] Configuring logind (no suspend/hibernate)..."
sudo mkdir -p /etc/systemd/logind.conf.d/
sudo tee /etc/systemd/logind.conf.d/no-suspend.conf << 'EOF'
[Login]
# Optional: if this is a laptop, keep it on when lid is closed
HandleLidSwitch=ignore
HandleLidSwitchDocked=ignore

[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
EOF

echo "[2/4] Restarting systemd-logind..."
sudo systemctl restart systemd-logind

# 2. Mask sleep targets so nothing can trigger system sleep
echo "[3/4] Masking systemd sleep targets..."
for t in sleep suspend hibernate hybrid-sleep; do
  sudo systemctl mask "${t}.target" 2>/dev/null || true
done

# 3. Disable automatic suspend via D-Bus (common on desktops/servers with GUI)
echo "[4/4] Disabling org.freedesktop.login1 sleep (if present)..."
if command -v systemctl &>/dev/null && systemctl is-active -q systemd-logind 2>/dev/null; then
  # Already handled by logind config above
  true
fi

echo ""
echo "=========================================="
echo "Done. This machine is configured to stay on:"
echo "  - Suspend/hibernate disabled (logind)"
echo "  - Sleep targets masked (nothing can request system sleep)"
echo "  - Lid switch ignored (if applicable)"
echo ""
echo "Optional: reboot once to apply everywhere:  sudo reboot"
echo "=========================================="
