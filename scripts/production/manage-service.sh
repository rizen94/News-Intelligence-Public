#!/bin/bash

# News Intelligence System - Service Management Script
# Easy commands to manage the auto-start service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="news-intelligence-system"

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

# Show usage
show_usage() {
    echo "News Intelligence System - Service Management"
    echo "============================================="
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     - Start the service"
    echo "  stop      - Stop the service"
    echo "  restart   - Restart the service"
    echo "  status    - Show service status"
    echo "  logs      - Show service logs"
    echo "  enable    - Enable auto-start on boot"
    echo "  disable   - Disable auto-start on boot"
    echo "  install   - Install the service"
    echo "  uninstall - Uninstall the service"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 logs"
}

# Start the service
start_service() {
    log "Starting News Intelligence System..."
    systemctl --user start "$SERVICE_NAME"
    success "Service started"
}

# Stop the service
stop_service() {
    log "Stopping News Intelligence System..."
    systemctl --user stop "$SERVICE_NAME"
    success "Service stopped"
}

# Restart the service
restart_service() {
    log "Restarting News Intelligence System..."
    systemctl --user restart "$SERVICE_NAME"
    success "Service restarted"
}

# Show service status
show_status() {
    log "Service Status:"
    echo "==============="
    systemctl --user status "$SERVICE_NAME" --no-pager
}

# Show service logs
show_logs() {
    log "Service Logs (Press Ctrl+C to exit):"
    echo "===================================="
    journalctl --user -u "$SERVICE_NAME" -f
}

# Enable auto-start
enable_service() {
    log "Enabling auto-start on boot..."
    systemctl --user enable "$SERVICE_NAME"
    success "Auto-start enabled"
}

# Disable auto-start
disable_service() {
    log "Disabling auto-start on boot..."
    systemctl --user disable "$SERVICE_NAME"
    success "Auto-start disabled"
}

# Install the service
install_service() {
    log "Installing the service..."
    ./scripts/production/setup-autostart.sh
}

# Uninstall the service
uninstall_service() {
    log "Uninstalling the service..."
    ./scripts/production/setup-autostart.sh --uninstall
}

# Main function
main() {
    case "${1:-}" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        enable)
            enable_service
            ;;
        disable)
            disable_service
            ;;
        install)
            install_service
            ;;
        uninstall)
            uninstall_service
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
