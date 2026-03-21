#!/bin/bash

# News Intelligence System - Complete Stack Startup
# Starts: Redis, API Server, Frontend
# Resilient to reboots via systemd

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
API_DIR="$SCRIPT_DIR/api"
WEB_DIR="$SCRIPT_DIR/web"
API_LOG="$LOG_DIR/api_server.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
REDIS_CONTAINER="news-intelligence-redis"

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

# Check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Stop existing processes
stop_existing() {
    log "Stopping existing processes..."
    
    # Stop API server
    if is_running "uvicorn.*main_v4"; then
        log "Stopping existing API server..."
        pkill -f "uvicorn.*main_v4" || true
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

# Start Redis
start_redis() {
    log "Starting Redis..."
    
    # Check if Redis container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        # Start existing container
        if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
            success "Redis container already running"
        else
            docker start "$REDIS_CONTAINER" > /dev/null 2>&1
            sleep 2
            
            # Wait for Redis to be ready
            local max_attempts=10
            local attempt=0
            while [ $attempt -lt $max_attempts ]; do
                if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
                    success "Redis started and ready"
                    return 0
                fi
                attempt=$((attempt + 1))
                sleep 1
            done
            
            error "Redis container started but not responding"
            return 1
        fi
    else
        # Start via docker-compose if available
        if [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
            log "Starting Redis via docker-compose..."
            cd "$SCRIPT_DIR"
            docker-compose up -d redis > /dev/null 2>&1 || true
            sleep 3
            
            if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
                success "Redis started via docker-compose"
            else
                warning "Redis may not be ready yet, but container started"
            fi
        else
            error "Redis container not found and docker-compose.yml not available"
            return 1
        fi
    fi
}

# Start API Server
start_api() {
    log "Starting API server..."
    
    if is_running "uvicorn.*main_v4"; then
        warning "API server already running"
        return 0
    fi
    
    cd "$API_DIR"
    
    # Check if virtual environment exists
    if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    
    # Start API server in background
    nohup python3 -m uvicorn main_v4:app --host 0.0.0.0 --port 8000 --reload > "$API_LOG" 2>&1 &
    API_PID=$!
    
    # Wait for API to be ready
    log "Waiting for API server to start..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/api/v4/system-monitoring/status > /dev/null 2>&1; then
            success "API server started (PID: $API_PID)"
            echo "$API_PID" > "$LOG_DIR/api.pid"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    error "API server failed to start within timeout"
    return 1
}

# Start Frontend
start_frontend() {
    log "Starting frontend..."
    
    if is_running "node.*react-scripts\|vite.*start\|webpack.*serve"; then
        warning "Frontend already running"
        return 0
    fi
    
    cd "$WEB_DIR"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        warning "node_modules not found. Run 'npm install' first if needed."
    fi
    
    # Start frontend in background
    nohup npm start > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    
    # Wait for frontend to be ready
    log "Waiting for frontend to start..."
    local max_attempts=60
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            success "Frontend started (PID: $FRONTEND_PID)"
            echo "$FRONTEND_PID" > "$LOG_DIR/frontend.pid"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    warning "Frontend may still be starting (check logs at $FRONTEND_LOG)"
    echo "$FRONTEND_PID" > "$LOG_DIR/frontend.pid"
    return 0
}

# Verify services
verify_services() {
    log "Verifying services..."
    
    local all_healthy=true
    
    # Check Redis
    if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
        success "✅ Redis: Running"
    else
        error "❌ Redis: Not responding"
        all_healthy=false
    fi
    
    # Check API
    if curl -s http://localhost:8000/api/v4/system-monitoring/status > /dev/null 2>&1; then
        success "✅ API: Running (http://localhost:8000)"
    else
        error "❌ API: Not responding"
        all_healthy=false
    fi
    
    # Check Frontend
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        success "✅ Frontend: Running (http://localhost:3000)"
    else
        warning "⚠️  Frontend: Not responding yet (may still be starting)"
    fi
    
    echo ""
    if [ "$all_healthy" = true ]; then
        success "All critical services are running!"
        log "Access URLs:"
        echo "  Frontend: http://localhost:3000"
        echo "  API: http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        echo ""
        log "Logs:"
        echo "  API: $API_LOG"
        echo "  Frontend: $FRONTEND_LOG"
        echo "  Startup: $LOG_DIR/startup.log"
    else
        warning "Some services may not be fully ready. Check logs above."
    fi
}

# Main execution
main() {
    log "=========================================="
    log "News Intelligence System - Startup"
    log "=========================================="
    log "Started at: $(date)"
    echo ""
    
    stop_existing
    
    # Start services
    start_redis
    start_api
    start_frontend
    
    # Wait a moment for everything to settle
    sleep 3
    
    # Verify
    verify_services
    
    log "Startup complete!"
    log "=========================================="
}

# Handle script interruption
cleanup() {
    log "Cleaning up on exit..."
    # Note: We don't stop services on cleanup for systemd persistence
    exit 0
}

trap cleanup EXIT INT TERM

# Run main function
main "$@"

