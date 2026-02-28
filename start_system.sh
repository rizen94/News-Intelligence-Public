#!/bin/bash

# News Intelligence System v4.0 - Comprehensive Startup Script
# Starts: SSH Tunnel, Redis, API Server, Frontend, and all background services

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

# ============================================================================
# NAS DATABASE via SSH TUNNEL (HARD REQUIREMENT)
# Connection: localhost:5433 -> SSH -> 192.168.93.100:5432
# ============================================================================
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5433}"
export DB_NAME="${DB_NAME:-news_intelligence}"
export DB_USER="${DB_USER:-newsapp}"
export DB_PASSWORD="${DB_PASSWORD:-newsapp_password}"

if [[ "${DB_HOST}" != "localhost" ]] && [[ "${DB_HOST}" != "127.0.0.1" ]]; then
    echo -e "${RED}[ERROR]${NC} DIRECT CONNECTION BLOCKED: DB_HOST='${DB_HOST}' is not allowed" >&2
    echo -e "${RED}[ERROR]${NC} System MUST use SSH tunnel (localhost:5433)" >&2
    exit 1
fi

if [[ "${DB_PORT}" != "5433" ]]; then
    echo -e "${RED}[ERROR]${NC} INVALID PORT: DB_PORT='${DB_PORT}' - must be 5433 (SSH tunnel)" >&2
    exit 1
fi

echo -e "${CYAN}[INFO]${NC} Using SSH tunnel to NAS database (localhost:5433 -> 192.168.93.100:5432)"

if ! ps aux | grep -q "[s]sh -L 5433:localhost:5432.*192.168.93.100"; then
    echo -e "${YELLOW}[WARNING]${NC} SSH tunnel not detected. Attempting to create tunnel..."
    if [ -f "$SCRIPT_DIR/scripts/setup_nas_ssh_tunnel.sh" ]; then
        bash "$SCRIPT_DIR/scripts/setup_nas_ssh_tunnel.sh" || {
            echo -e "${RED}[ERROR]${NC} Failed to establish SSH tunnel. Start manually:" >&2
            echo -e "${RED}[ERROR]${NC}   ssh -L 5433:localhost:5432 -N -f -p 9222 Admin@192.168.93.100" >&2
            exit 1
        }
    else
        echo -e "${YELLOW}[WARNING]${NC} Tunnel script not found. Creating tunnel directly..."
        ssh -L 5433:localhost:5432 -N -f -p 9222 Admin@192.168.93.100 || {
            echo -e "${RED}[ERROR]${NC} Failed to create SSH tunnel. Please run manually:" >&2
            echo -e "${RED}[ERROR]${NC}   ssh -L 5433:localhost:5432 -N -f -p 9222 Admin@192.168.93.100" >&2
            exit 1
        }
    fi
fi

echo -e "${GREEN}[SUCCESS]${NC} SSH tunnel verified and running"
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

# Check PostgreSQL
check_postgresql() {
    log "Checking PostgreSQL database..."
    
    # For NAS database (REQUIRED) - verify connectivity only, do NOT try to start
    if [[ "${DB_HOST}" == "192.168.93.100" ]]; then
        log "Verifying NAS database connection..."
        
        # Test connection with longer timeout for network
        if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME:-news_intelligence}', user='${DB_USER:-newsapp}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT:-5432}, connect_timeout=5)" > /dev/null 2>&1; then
            success "PostgreSQL (NAS): Running and accepting connections at ${DB_HOST}:${DB_PORT}"
            return 0
        fi
        
        # Fallback to pg_isready if available
        if command -v pg_isready &> /dev/null; then
            if pg_isready -h "${DB_HOST}" -p "${DB_PORT:-5432}" -U "${DB_USER:-newsapp}" > /dev/null 2>&1; then
                success "PostgreSQL (NAS): Running and accepting connections"
                return 0
            fi
        fi
        
        # NAS database is not accessible - FAIL (do not fallback to local)
        error "Cannot connect to NAS database at ${DB_HOST}:${DB_PORT}"
        error "System REQUIRES NAS database - local storage is BLOCKED"
        error "Please ensure:"
        error "  1. NAS is accessible (ping 192.168.93.100)"
        error "  2. PostgreSQL is running on NAS"
        error "  3. Database credentials are correct"
        error "  4. Network connectivity is working"
        return 1
    fi
    
    # For localhost - this is the SSH tunnel case (localhost:5433 -> NAS:5432)
    if [[ "${DB_HOST}" == "localhost" ]] || [[ "${DB_HOST}" == "127.0.0.1" ]]; then
        info "Connecting to NAS database via SSH tunnel (localhost:${DB_PORT})"
        
        # First try direct connection through tunnel
        if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME:-news_intelligence}', user='${DB_USER:-newsapp}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT:-5432}, connect_timeout=5)" > /dev/null 2>&1; then
            success "PostgreSQL (NAS via SSH tunnel): Running and accepting connections"
            return 0
        fi
        
        # Fallback to pg_isready if available
        if command -v pg_isready &> /dev/null; then
            if pg_isready -h "${DB_HOST}" -p "${DB_PORT:-5432}" -U "${DB_USER:-newsapp}" > /dev/null 2>&1; then
                success "PostgreSQL (local): Running and accepting connections"
                return 0
            fi
        fi
        
        # Try to start PostgreSQL service (local only)
        warning "PostgreSQL not responding, attempting to start local service..."
        
        if systemctl --user is-active --quiet postgresql 2>/dev/null || \
           systemctl is-active --quiet postgresql 2>/dev/null || \
           systemctl is-active --quiet postgresql@* 2>/dev/null; then
            success "PostgreSQL service is active"
            sleep 2
            if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME:-news_intelligence}', user='${DB_USER:-newsapp}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT:-5432}, connect_timeout=2)" > /dev/null 2>&1; then
                success "PostgreSQL (local): Ready"
                return 0
            fi
        else
            warning "PostgreSQL service not active. Attempting to start..."
            if systemctl --user start postgresql 2>/dev/null || \
               systemctl start postgresql 2>/dev/null || \
               systemctl start postgresql@* 2>/dev/null; then
                sleep 3
                if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME:-news_intelligence}', user='${DB_USER:-newsapp}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT:-5432}, connect_timeout=2)" > /dev/null 2>&1; then
                    success "PostgreSQL (local): Started and ready"
                    return 0
                fi
            fi
        fi
        
        error "PostgreSQL (local) is not running and could not be started"
        error "Please start PostgreSQL manually: sudo systemctl start postgresql"
        return 1
    fi
    
    # For other remote databases - just verify connectivity
    log "Verifying database connection to ${DB_HOST}..."
    if python3 -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', database='${DB_NAME:-news_intelligence}', user='${DB_USER:-newsapp}', password='${DB_PASSWORD:-newsapp_password}', port=${DB_PORT:-5432}, connect_timeout=5)" > /dev/null 2>&1; then
        success "PostgreSQL: Running and accepting connections at ${DB_HOST}:${DB_PORT}"
        return 0
    else
        error "Cannot connect to PostgreSQL at ${DB_HOST}:${DB_PORT}"
        return 1
    fi
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
            warning "Redis container not found. Creating new container..."
            docker run -d --name "$REDIS_CONTAINER" -p 6379:6379 redis:latest > /dev/null 2>&1 || {
                error "Failed to create Redis container"
                return 1
            }
            sleep 3
            if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
                success "Redis container created and ready"
            else
                warning "Redis container created but may not be ready yet"
            fi
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
    
    # Check if port 8000 is in use
    if is_port_in_use 8000; then
        error "Port 8000 is already in use. Please free the port or stop the existing service."
        return 1
    fi
    
    cd "$API_DIR"
    
    # Use venv Python when available (explicit path for nohup/subprocess reliability)
    PYTHON_BIN="python3"
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
        info "Using virtual environment: .venv"
    elif [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        PYTHON_BIN="python3"
        info "Using virtual environment: venv"
    else
        warning "No virtual environment found. Using system Python."
    fi
    
    # Start API server in background with SSH tunnel environment variables
    # Note: The API server automatically starts:
    # - AutomationManager (RSS processing, article processing, ML processing, topic clustering)
    # - MLProcessingService
    log "Starting API server (includes AutomationManager and ML Processing Service)..."
    log "Using SSH tunnel: DB_HOST=${DB_HOST} DB_PORT=${DB_PORT}"
    nohup env DB_HOST="${DB_HOST}" DB_PORT="${DB_PORT}" DB_NAME="${DB_NAME}" DB_USER="${DB_USER}" DB_PASSWORD="${DB_PASSWORD}" "$PYTHON_BIN" -m uvicorn main_v4:app --host 0.0.0.0 --port 8000 --reload > "$API_LOG" 2>&1 &
    API_PID=$!
    
    # Wait for API to be ready
    log "Waiting for API server to start..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/api/v4/system_monitoring/health > /dev/null 2>&1; then
            success "API server started (PID: $API_PID)"
            info "  - AutomationManager: Auto-started (RSS, Articles, ML, Topic Clustering)"
            info "  - MLProcessingService: Auto-started"
            echo "$API_PID" > "$LOG_DIR/api.pid"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    error "API server failed to start within timeout"
    error "Check logs at: $API_LOG"
    return 1
}

# Start Frontend
start_frontend() {
    log "Starting frontend..."
    
    if is_running "node.*react-scripts\|vite.*start\|webpack.*serve"; then
        warning "Frontend already running"
        return 0
    fi
    
    # Check if port 3000 is in use
    if is_port_in_use 3000; then
        error "Port 3000 is already in use. Please free the port or stop the existing service."
        return 1
    fi
    
    cd "$WEB_DIR"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        warning "node_modules not found. Installing dependencies..."
        npm install
    fi
    
    # Start frontend in background
    log "Starting React development server..."
    CHOKIDAR_USEPOLLING=true nohup npm start > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    
    # Wait for frontend to be ready
    log "Waiting for frontend to start (this may take 30-60 seconds)..."
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
    log ""
    log "=========================================="
    log "Service Status Verification"
    log "=========================================="
    
    local all_healthy=true
    
    # Check PostgreSQL (via SSH tunnel) — pg_isready or psycopg2 fallback
    _py="$SCRIPT_DIR/.venv/bin/python"
    [ -x "$_py" ] || _py="python3"
    if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER:-newsapp}" > /dev/null 2>&1; then
        success "✅ PostgreSQL: Running (NAS via SSH tunnel: ${DB_HOST}:${DB_PORT})"
    elif "$_py" -c "import psycopg2; psycopg2.connect(host='${DB_HOST}', port=${DB_PORT}, database='${DB_NAME:-news_intelligence}', user='${DB_USER:-newsapp}', password='${DB_PASSWORD:-newsapp_password}', connect_timeout=3)" > /dev/null 2>&1; then
        success "✅ PostgreSQL: Running (NAS via SSH tunnel: ${DB_HOST}:${DB_PORT})"
    else
        error "❌ PostgreSQL: Not responding at ${DB_HOST}:${DB_PORT}"
        all_healthy=false
    fi
    
    # Check Redis
    if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
        success "✅ Redis: Running (Docker container: $REDIS_CONTAINER)"
    else
        error "❌ Redis: Not responding"
        all_healthy=false
    fi
    
    # Check API
    if curl -s http://localhost:8000/api/v4/system_monitoring/health > /dev/null 2>&1; then
        success "✅ API Server: Running (http://localhost:8000)"
        info "   - AutomationManager: Active (background tasks)"
        info "   - MLProcessingService: Active"
    else
        error "❌ API Server: Not responding"
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
        log ""
        log "Access URLs:"
        echo "  🌐 Frontend:    http://localhost:3000"
        echo "  🔧 API:        http://localhost:8000"
        echo "  📚 API Docs:   http://localhost:8000/docs"
        echo ""
        log "Background Services (Auto-started by API):"
        echo "  🔄 AutomationManager: RSS processing, Article processing, ML processing, Topic clustering"
        echo "  🤖 MLProcessingService: ML model processing"
        echo ""
        log "Logs:"
        echo "  📄 API:        $API_LOG"
        echo "  📄 Frontend:   $FRONTEND_LOG"
        echo "  📄 Startup:    $LOG_DIR/startup.log"
        echo ""
        log "Process IDs:"
        if [ -f "$LOG_DIR/api.pid" ]; then
            echo "  API PID:      $(cat $LOG_DIR/api.pid)"
        fi
        if [ -f "$LOG_DIR/frontend.pid" ]; then
            echo "  Frontend PID: $(cat $LOG_DIR/frontend.pid)"
        fi
    else
        warning "Some services may not be fully ready. Check logs above."
        error "Please review the errors and ensure all dependencies are installed."
    fi
    log "=========================================="
}

# Main execution
main() {
    log "=========================================="
    log "News Intelligence System v4.0 - Startup"
    log "=========================================="
    log "Started at: $(date)"
    echo ""
    
    # Pre-flight checks
    info "Running pre-flight checks..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
        return 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        error "Node.js is not installed or not in PATH"
        return 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed or not in PATH"
        return 1
    fi
    
    success "Pre-flight checks passed"
    echo ""
    
    # Stop existing processes
    stop_existing
    
    # Start services in order
    log "Starting services..."
    echo ""
    
    # 1. PostgreSQL (database)
    if ! check_postgresql; then
        error "PostgreSQL check failed. Please start PostgreSQL manually and try again."
        return 1
    fi
    
    # 2. Redis (cache)
    if ! start_redis; then
        error "Redis startup failed"
        return 1
    fi
    
    # 3. API Server (includes AutomationManager and MLProcessingService)
    if ! start_api; then
        error "API server startup failed"
        return 1
    fi
    
    # 4. Frontend
    if ! start_frontend; then
        warning "Frontend startup had issues, but continuing..."
    fi
    
    # Wait a moment for everything to settle
    log "Waiting for services to stabilize..."
    sleep 5
    
    # Verify
    verify_services
    
    log ""
    success "Startup complete!"
    log "=========================================="
}

# Handle script interruption
cleanup() {
    log "Cleaning up on exit..."
    # Note: We don't stop services on cleanup for persistence
    exit 0
}

trap cleanup EXIT INT TERM

# Run main function
main "$@"

