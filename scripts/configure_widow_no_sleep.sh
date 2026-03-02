#!/bin/bash
# News Intelligence — Disable sleep/suspend on Widow (secondary machine)
# Run ON Widow: sudo ./scripts/configure_widow_no_sleep.sh
# Or from primary: ssh widow "cd /opt/news-intelligence && sudo ./scripts/configure_widow_no_sleep.sh"

set -e

echo "Configuring Widow to stay awake (no suspend/hibernate)..."

sudo mkdir -p /etc/systemd/logind.conf.d/
sudo tee /etc/systemd/logind.conf.d/no-suspend.conf << 'EOF'
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
EOF

echo "Restarting systemd-logind..."
sudo systemctl restart systemd-logind

echo "Done. Widow should no longer suspend. Reboot to be sure."
