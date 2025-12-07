#!/bin/bash

# Quick setup script for auto-start service
# Installs/updates the systemd service for automatic startup on reboot

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Installing News Intelligence auto-start service...${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/news-intelligence-system.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_DIR"

# Copy service file
echo -e "${BLUE}Copying service file...${NC}"
cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
echo -e "${GREEN}✅ Service file copied${NC}"

# Reload systemd
echo -e "${BLUE}Reloading systemd daemon...${NC}"
systemctl --user daemon-reload
echo -e "${GREEN}✅ Systemd reloaded${NC}"

# Enable service
echo -e "${BLUE}Enabling service for auto-start...${NC}"
systemctl --user enable news-intelligence-system
echo -e "${GREEN}✅ Service enabled${NC}"

# Enable lingering (allows service to run without user login)
echo -e "${BLUE}Enabling lingering (allows service to run without login)...${NC}"
sudo loginctl enable-linger "$USER"
echo -e "${GREEN}✅ Lingering enabled${NC}"

echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo "Service management commands:"
echo "  Start:   systemctl --user start news-intelligence-system"
echo "  Stop:    systemctl --user stop news-intelligence-system"
echo "  Status:  systemctl --user status news-intelligence-system"
echo "  Logs:    journalctl --user -u news-intelligence-system -f"
echo ""
echo -e "${YELLOW}The service will automatically start on next reboot.${NC}"
echo "To start it now, run: systemctl --user start news-intelligence-system"

