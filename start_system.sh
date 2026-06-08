#!/bin/bash

# News Intelligence System v8.0 - Comprehensive Startup Script (Widow Edition)
# DEV ONLY — Production Widow uses systemd: news-intelligence-api-public.service
# Do NOT run this if the systemd API is already running (duplicate AutomationManager).
# See: docs/WIDOW_BOOT_RESILIENCE.md

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
API_DIR="$SCRIPT_DIR/api"
WEB_DIR="$SCRIPT_DIR/web"
API_LOG="$LOG_DIR/api_server.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
REDIS_CONTAINER="news-intelligence-redis"

# Database configuration for Widow server
# Widow uses local PostgreSQL at 192.168.93.101:5432
export DB_HOST="${DB_HOST:-192.168.93.101}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-news_intel}"
export DB_USER="${DB_USER:-newsapp}"

# Create logs directory
mkdir -p "$LOG_DIR"

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_DIR/startup.log"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_DIR/startup.log"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_DIR/startup.log"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_DIR/startup.log"
}

info() {
    echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_DIR/startup.log"
}

# Check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Check if a port is in use
is_port_in_use() {
    lsof -i ":$1" > /dev/null 2>&1
}

# Stop existing processes
stop_existing() {
    log "Stopping existing processes..."

    # Stop API server
    if is_running "uvicorn.*(main|main_v4):app"; then
        log "Stopping existing API server..."
        pkill -f "uvicorn.*(main|main_v4):app" || true
        sleep 2
    fi

    # Stop frontend
    if is_running "node.*react-scripts\|vite\|webpack"; then
        log "Stopping existing frontend..."
        pkill -f "react-scripts\|vite.*start\|webpack.*serve" || true
        sleep 2
    fi

    success "Existing processes stopped"
}

# Check PostgreSQL (Widow local database)
check_postgresql() {
    log "Checking PostgreSQL database..."

    # Widow uses local PostgreSQL at 192.168.93.101:5432
    info "Connecting to local PostgreSQL at ${DB_HOST}:${DB_PORT}"

    # First try direct connection with psycopg2
    if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME}', user='${DB_USER}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT}, connect_timeout=5)" > /dev/null 2>&1; then
        success "PostgreSQL (Widow): Running and accepting connections at ${DB_HOST}:${DB_PORT}"
        return 0
    fi

    # Fallback to pg_isready if available
    if command -v pg_isready &> /dev/null; then
        if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" > /dev/null 2>&1; then
            success "PostgreSQL (Widow): Running and accepting connections"
            return 0
        fi
    fi

    # Try to start PostgreSQL service
    warning "PostgreSQL not responding, attempting to start service..."

    if systemctl --user is-active --quiet postgresql 2>/dev/null || \
       systemctl is-active --quiet postgresql 2>/dev/null || \
       systemctl is-active --quiet postgresql@* 2>/dev/null; then
        success "PostgreSQL service is active"
        sleep 2
        if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME}', user='${DB_USER}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT}, connect_timeout=2)" > /dev/null 2>&1; then
            success "PostgreSQL (Widow): Ready"
            return 0
        fi
    else
        warning "PostgreSQL service not active. Attempting to start..."
        if systemctl --user start postgresql 2>/dev/null || \
           systemctl start postgresql 2>/dev/null || \
           systemctl start postgresql@* 2>/dev/null; then
            sleep 3
            if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME}', user='${DB_USER}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT}, connect_timeout=2)" > /dev/null 2>&1; then
                success "PostgreSQL (Widow): Started and ready"
                return 0
            fi
        fi
    fi

    error "PostgreSQL is not running and could not be started"
    error "Please start PostgreSQL manually: sudo systemctl start postgresql"
    return 1
}

# Start Redis container
start_redis() {
    log "Checking Redis container..."

    if ! command -v docker &> /dev/null; then
        warning "Docker not installed, skipping Redis"
        return 0
    fi

    if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        success "Redis container is already running"
        return 0
    fi

    if docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        log "Starting existing Redis container..."
        docker start "$REDIS_CONTAINER" || {
            warning "Failed to start Redis container"
            return 1
        }
        success "Redis container started"
        return 0
    fi

    log "Creating and starting Redis container..."
    docker run -d --name "$REDIS_CONTAINER" --restart unless-stopped redis:7-alpine \
        --appendonly yes --requirepass "${REDIS_PASSWORD:-newsredis123}" || {
        warning "Failed to create Redis container"
        return 1
    }
    sleep 2
    success "Redis container created and started"
}

# Start API Server
start_api() {
    log "Starting API Server..."

    # Check if .env file exists
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            warning ".env file not found, copying from .env.example"
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        else
            warning ".env file not found and no .env.example available"
        fi
    fi

    # Check if virtual environment exists
    if [ ! -d "$SCRIPT_DIR/.venv" ]; then
        log "Creating virtual environment..."
        python3 -m venv "$SCRIPT_DIR/.venv"
        source "$SCRIPT_DIR/.venv/bin/activate"
        log "Installing dependencies..."
        pip install --upgrade pip
        pip install -r "$API_DIR/requirements.txt"
        success "Virtual environment created and dependencies installed"
    fi

    # Activate virtual environment
    source "$SCRIPT_DIR/.venv/bin/activate"

    # Start uvicorn server
    cd "$API_DIR"
    echo -e "${GREEN}Starting API Server on http://localhost:8000${NC}"
    nohup "$SCRIPT_DIR/.venv/bin/python" -m uvicorn main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 2 \
        --access-log >> "$API_LOG" \
        --error-log >> "$API_LOG" \
        --capture-handled-exceptions \
        2>&1 &
    
    API_PID=$!
    echo $API_PID > "$LOG_DIR/api.pid"
    log "API Server started with PID: $API_PID"

    # Wait for API to be ready
    log "Waiting for API Server to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/api/system_monitoring/health > /dev/null 2>&1; then
            success "API Server is ready"
            return 0
        fi
        log "Waiting for API Server... (attempt $i/30)"
        sleep 1
    done

    error "API Server failed to become ready"
    return 1
}

# Start Frontend
start_frontend() {
    log "Starting Frontend..."

    if [ ! -d "$WEB_DIR" ]; then
        warning "Web directory not found, skipping frontend"
        return 0
    fi

    # Check if node_modules exists
    if [ ! -d "$WEB_DIR/node_modules" ]; then
        log "Installing frontend dependencies..."
        cd "$WEB_DIR"
        npm install || {
            warning "Failed to install frontend dependencies"
            return 1
        }
        success "Frontend dependencies installed"
    fi

    # Start frontend dev server
    cd "$WEB_DIR"
    echo -e "${GREEN}Starting Frontend on http://localhost:3000${NC}"
    nohup "$SCRIPT_DIR/.venv/bin/node" "$(which npx)/node_modules/.bin/react-scripts" start \
        > "$FRONTEND_LOG" 2>&1 &
    
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
    log "Frontend started with PID: $FRONTEND_PID"

    # Wait for frontend to be ready
    log "Waiting for Frontend to be ready..."
    for i in {1..60}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            success "Frontend is ready"
            return 0
        fi
        if [ $((i % 10)) -eq 0 ]; then
            log "Waiting for Frontend... (attempt $i/60)"
        fi
        sleep 1
    done

    warning "Frontend may not be ready yet, but starting in background"
}

# Start background services
start_background_services() {
    log "Starting background services..."

    # Check if automation manager is running
    if ! is_running "AutomationManager"; then
        log "Starting AutomationManager..."
        cd "$API_DIR"
        nohup "$SCRIPT_DIR/.venv/bin/python" -c "
from services.automation_manager import AutomationManager
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
manager = AutomationManager()
manager.run()
" >> "$LOG_DIR/automation.log" 2>&1 &
        echo $! > "$LOG_DIR/automation.pid"
        success "AutomationManager started"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  News Intelligence System v8.0 - Starting${NC}"
    echo -e "${BLUE}============================================${NC}"

    # Stop existing processes first
    stop_existing

    # Check PostgreSQL
    if ! check_postgresql; then
        error "Failed to connect to PostgreSQL"
        exit 1
    fi

    # Start Redis
    start_redis

    # Start API Server
    if ! start_api; then
        error "Failed to start API Server"
        exit 1
    fi

    # Start Frontend (optional)
    start_frontend || warning "Frontend failed to start"

    # Start background services
    start_background_services

    echo -e "${BLUE}============================================${NC}"
    success "System startup complete!"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    echo -e "${GREEN}API Server:     ${CYAN}http://localhost:8000${NC}"
    echo -e "${GREEN}Frontend:       ${CYAN}http://localhost:3000${NC}"
    echo -e "${GREEN}Redis:          ${CYAN}localhost:6379${NC}"
    echo -e "${GREEN}Database:       ${CYAN}${DB_HOST}:${DB_PORT}/${DB_NAME}${NC}"
    echo ""
    echo -e "${CYAN}Logs:${NC}"
    echo -e "  API:      tail -f $API_LOG"
    echo -e "  Frontend: tail -f $FRONTEND_LOG"
    echo -e "  Startup:  tail -f $LOG_DIR/startup.log"
    echo ""
}

# Run main function
main "$@"