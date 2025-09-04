#!/bin/bash

# Setup Docker Cleanup Service
# Installs systemd service and timer to run cleanup every 6 hours

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                DOCKER CLEANUP SETUP                        ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Create log directory
print_status "Creating log directory..."
mkdir -p /var/log
touch /var/log/docker-cleanup.log
chmod 644 /var/log/docker-cleanup.log

# Copy service files
print_status "Installing systemd service files..."
cp "$SCRIPT_DIR/docker-cleanup.service" /etc/systemd/system/
cp "$SCRIPT_DIR/docker-cleanup.timer" /etc/systemd/system/

# Reload systemd
print_status "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start the timer
print_status "Enabling and starting Docker cleanup timer..."
systemctl enable docker-cleanup.timer
systemctl start docker-cleanup.timer

# Check status
print_status "Checking service status..."
systemctl status docker-cleanup.timer --no-pager

print_status "Docker cleanup service installed successfully!"
print_warning "The cleanup will run every 6 hours starting 1 hour after boot"
print_status "Logs will be written to: /var/log/docker-cleanup.log"

echo ""
echo -e "${BLUE}Manual commands:${NC}"
echo -e "  ${YELLOW}Check timer status:${NC} systemctl status docker-cleanup.timer"
echo -e "  ${YELLOW}Run cleanup now:${NC} systemctl start docker-cleanup.service"
echo -e "  ${YELLOW}View logs:${NC} journalctl -u docker-cleanup.service -f"
echo -e "  ${YELLOW}Disable cleanup:${NC} systemctl disable docker-cleanup.timer"


