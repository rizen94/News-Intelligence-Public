#!/bin/bash

# News Intelligence System v8.0 - Stop Script
# Stops API Server and Frontend

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
API_UVICORN_PGREP='uvicorn.*(main|main_v4):app'

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Logging functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}News Intelligence System v8.0 - Stopping${NC}"
echo -e "${BLUE}==============================================${NC}"

# Stop API server
if is_running "$API_UVICORN_PGREP"; then
    API_PID=$(pgrep -f "$API_UVICORN_PGREP" | head -1)
    log "Stopping API Server (PID: $API_PID)..."
    pkill -f "$API_UVICORN_PGREP" || true
    sleep 2
    if is_running "$API_UVICORN_PGREP"; then
        warning "API Server still running, sending SIGKILL..."
        pkill -9 -f "$API_UVICORN_PGREP" || true
    fi
    success "API Server stopped"
else
    log "API Server is not running"
fi

# Stop Frontend
FRONTEND_PATTERN='node.*react-scripts\|vite.*start\|webpack.*serve'
if is_running "$FRONTEND_PATTERN"; then
    FRONTEND_PID=$(pgrep -f "$FRONTEND_PATTERN" | head -1)
    log "Stopping Frontend (PID: $FRONTEND_PID)..."
    pkill -f "$FRONTEND_PATTERN" || true
    sleep 2
    if is_running "$FRONTEND_PATTERN"; then
        warning "Frontend still running, sending SIGKILL..."
        pkill -9 -f "$FRONTEND_PATTERN" || true
    fi
    success "Frontend stopped"
else
    log "Frontend is not running"
fi

# Stop Redis container if running
if command -v docker &> /dev/null; then
    REDIS_CONTAINER="news-intelligence-redis"
    if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        log "Stopping Redis container..."
        docker stop "$REDIS_CONTAINER" || true
        docker rm "$REDIS_CONTAINER" || true
        success "Redis container stopped and removed"
    fi
fi

echo -e "${BLUE}==============================================${NC}"
success "All services stopped!"
echo -e "${BLUE}==============================================${NC}"