#!/bin/bash

# News Intelligence System - Simple Auto-Start Setup
# This script sets up the system to automatically start on boot (user-level)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="news-intelligence-system"
SERVICE_FILE="news-intelligence-system.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Create user systemd directory
create_user_systemd_dir() {
    log "Creating user systemd directory..."
    mkdir -p "$SYSTEMD_USER_DIR"
    success "User systemd directory created"
}

# Install the systemd service
install_service() {
    log "Installing user systemd service..."
    
    # Copy service file to user systemd directory
    cp "$SERVICE_FILE" "$SYSTEMD_USER_DIR/"
    
    # Reload user systemd daemon
    systemctl --user daemon-reload
    
    # Enable the service
    systemctl --user enable "$SERVICE_NAME"
    
    success "User systemd service installed and enabled"
}

# Test the service
test_service() {
    log "Testing the service..."
    
    # Check service status
    if systemctl --user is-enabled "$SERVICE_NAME" > /dev/null 2>&1; then
        success "Service is enabled"
    else
        error "Service is not enabled"
        return 1
    fi
    
    # Check if service file exists
    if [ -f "$SYSTEMD_USER_DIR/$SERVICE_FILE" ]; then
        success "Service file is installed"
    else
        error "Service file is not installed"
        return 1
    fi
}

# Show setup instructions
show_instructions() {
    log "Setup Instructions:"
    echo "==================="
    echo ""
    echo "The service is now installed but requires one manual step:"
    echo ""
    echo "1. Enable lingering for your user (allows services to start without login):"
    echo "   sudo loginctl enable-linger $USER"
    echo ""
    echo "2. Or add this to your ~/.bashrc or ~/.profile:"
    echo "   systemctl --user start $SERVICE_NAME"
    echo ""
    echo "Service Management Commands:"
    echo "============================"
    echo "Start service:     systemctl --user start $SERVICE_NAME"
    echo "Stop service:      systemctl --user stop $SERVICE_NAME"
    echo "Restart service:   systemctl --user restart $SERVICE_NAME"
    echo "Check status:      systemctl --user status $SERVICE_NAME"
    echo "View logs:         journalctl --user -u $SERVICE_NAME -f"
    echo ""
    echo "Or use the management script:"
    echo "  ./scripts/production/manage-service.sh start"
    echo "  ./scripts/production/manage-service.sh status"
    echo "  ./scripts/production/manage-service.sh logs"
    echo ""
    echo "To test the service now:"
    echo "  systemctl --user start $SERVICE_NAME"
}

# Main function
main() {
    log "Setting up News Intelligence System Auto-Start (Simple)"
    log "======================================================"
    
    # Check if we're in the right directory
    if [ ! -f "start.sh" ] || [ ! -f "$SERVICE_FILE" ]; then
        error "Please run this script from the News Intelligence project directory"
        exit 1
    fi
    
    create_user_systemd_dir
    install_service
    test_service
    show_instructions
    
    success "Auto-start setup completed!"
    log "The News Intelligence System service is now installed."
    log "Follow the instructions above to complete the setup."
}

# Run main function
main "$@"
