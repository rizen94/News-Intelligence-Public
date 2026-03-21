#!/bin/bash

# News Intelligence System - Auto-Start Setup Script
# This script sets up the system to automatically start on boot

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
CURRENT_DIR="$(pwd)"

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

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        error "This script should not be run as root. Please run as your regular user."
        exit 1
    fi
}

# Create user systemd directory
create_user_systemd_dir() {
    log "Creating user systemd directory..."
    mkdir -p "$SYSTEMD_USER_DIR"
    success "User systemd directory created"
}

# Check if Docker is installed and running
check_docker() {
    log "Checking Docker installation..."
    
    if ! command -v docker > /dev/null 2>&1; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    success "Docker is installed and running"
}

# Check if Docker Compose is available
check_docker_compose() {
    log "Checking Docker Compose..."
    
    if ! command -v docker-compose > /dev/null 2>&1; then
        error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    success "Docker Compose is available"
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
    
    # Enable lingering for the user (allows services to start without login)
    sudo loginctl enable-linger "$USER"
    
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

# Show service management commands
show_commands() {
    log "Service Management Commands:"
    echo "========================"
    echo "Start service:     systemctl --user start $SERVICE_NAME"
    echo "Stop service:      systemctl --user stop $SERVICE_NAME"
    echo "Restart service:   systemctl --user restart $SERVICE_NAME"
    echo "Check status:      systemctl --user status $SERVICE_NAME"
    echo "View logs:         journalctl --user -u $SERVICE_NAME -f"
    echo "Disable service:   systemctl --user disable $SERVICE_NAME"
    echo ""
    echo "Or use the management script:"
    echo "  ./scripts/production/manage-service.sh start"
    echo "  ./scripts/production/manage-service.sh status"
    echo "  ./scripts/production/manage-service.sh logs"
    echo ""
    echo "The service will automatically start on boot."
    echo "To test it now, run: systemctl --user start $SERVICE_NAME"
}

# Uninstall the service
uninstall_service() {
    log "Uninstalling user systemd service..."
    
    # Stop and disable the service
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    
    # Remove service file
    rm -f "$SYSTEMD_USER_DIR/$SERVICE_FILE"
    
    # Reload user systemd daemon
    systemctl --user daemon-reload
    
    success "User systemd service uninstalled"
}

# Main function
main() {
    log "Setting up News Intelligence System Auto-Start"
    log "=============================================="
    
    # Check if we're in the right directory
    if [ ! -f "start.sh" ] || [ ! -f "$SERVICE_FILE" ]; then
        error "Please run this script from the News Intelligence project directory"
        exit 1
    fi
    
    # Check if uninstall was requested
    if [ "$1" = "--uninstall" ]; then
        uninstall_service
        exit 0
    fi
    
    check_root
    create_user_systemd_dir
    check_docker
    check_docker_compose
    install_service
    test_service
    show_commands
    
    success "Auto-start setup completed!"
    log "The News Intelligence System will now start automatically on boot."
}

# Handle script interruption
trap 'error "Script interrupted"; exit 1' INT TERM

# Run main function
main "$@"
