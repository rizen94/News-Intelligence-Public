#!/bin/bash
# News Intelligence — enable auto-start on boot
#
# What this does:
#   1. Enables "linger" for your user so systemd user services start at boot
#      (not just on login). Requires sudo once.
#   2. Creates the logs directory.
#   3. Enables both services (API + frontend).
#
# After running this, the system will auto-start on every reboot.
# You can still use start_system.sh for manual restarts.
#
# Usage:  bash scripts/setup_autostart.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${CYAN}[1/4]${NC} Creating logs directory..."
mkdir -p "$SCRIPT_DIR/logs"

echo -e "${CYAN}[2/4]${NC} Enabling linger for user '$USER' (starts services at boot, not just login)..."
echo "      This requires sudo — you may be prompted for your password."
sudo loginctl enable-linger "$USER"

echo -e "${CYAN}[3/4]${NC} Reloading systemd user daemon..."
systemctl --user daemon-reload

echo -e "${CYAN}[4/4]${NC} Enabling services..."
systemctl --user enable news-intel-api.service
systemctl --user enable news-intel-web.service

echo ""
echo -e "${GREEN}Done.${NC} Both services are enabled and will start on next boot."
echo ""
echo "Useful commands:"
echo "  systemctl --user status news-intel-api    # API status"
echo "  systemctl --user status news-intel-web    # Frontend status"
echo "  systemctl --user restart news-intel-api   # Restart API"
echo "  systemctl --user restart news-intel-web   # Restart frontend"
echo "  systemctl --user stop news-intel-api      # Stop API"
echo "  journalctl --user -u news-intel-api -f    # Tail API logs"
echo "  journalctl --user -u news-intel-web -f    # Tail frontend logs"
echo ""
echo "To start the services NOW (without rebooting):"
echo "  systemctl --user start news-intel-api"
echo "  systemctl --user start news-intel-web"
echo ""
echo "To disable auto-start later:"
echo "  systemctl --user disable news-intel-api news-intel-web"
