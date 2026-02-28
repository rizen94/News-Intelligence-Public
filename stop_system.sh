#!/bin/bash

# News Intelligence System v4.0 - Stop Script
# Stops: API Server, Frontend (keeps PostgreSQL and Redis running)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Stop API server
stop_api() {
    if is_running "uvicorn.*main_v4"; then
        log "Stopping API server..."
        pkill -f "uvicorn.*main_v4" || true
        sleep 2
        if is_running "uvicorn.*main_v4"; then
            warning "API server did not stop gracefully, forcing..."
            pkill -9 -f "uvicorn.*main_v4" || true
        fi
        success "API server stopped"
    else
        warning "API server not running"
    fi
}

# Stop Frontend
stop_frontend() {
    if is_running "node.*react-scripts\|vite.*start\|webpack.*serve"; then
        log "Stopping frontend..."
        pkill -f "react-scripts\|vite.*start\|webpack.*serve" || true
        sleep 2
        if is_running "node.*react-scripts\|vite.*start\|webpack.*serve"; then
            warning "Frontend did not stop gracefully, forcing..."
            pkill -9 -f "react-scripts\|vite.*start\|webpack.*serve" || true
        fi
        success "Frontend stopped"
    else
        warning "Frontend not running"
    fi
}

# Main execution
main() {
    log "=========================================="
    log "News Intelligence System v4.0 - Stop"
    log "=========================================="
    log "Stopping services..."
    echo ""
    
    stop_api
    stop_frontend
    
    # Clean up PID files
    if [ -f "$LOG_DIR/api.pid" ]; then
        rm "$LOG_DIR/api.pid"
    fi
    if [ -f "$LOG_DIR/frontend.pid" ]; then
        rm "$LOG_DIR/frontend.pid"
    fi
    
    log ""
    success "Services stopped"
    warning "Note: PostgreSQL and Redis are still running"
    log "=========================================="
}

main "$@"

