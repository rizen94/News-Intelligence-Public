#!/bin/bash

# News Intelligence System v8.0 - Comprehensive Startup Script
# Starts: SSH Tunnel, API Server, Frontend, and all background services (Redis removed)

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

# Load .env if present. Store DB_PASSWORD here (and NEWS_API_KEY, FRED_API_KEY).
# Required for DB: DB_PASSWORD must be set in .env for PostgreSQL authentication.
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    while IFS= read -r line; do
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ "$line" =~ ^(DB_|DATABASE|NEWS_API_KEY|FRED_API_KEY)= ]] || continue
        key="${line%%=*}"; val="${line#*=}"; val="${val%\"}"; val="${val#\"}"
        export "$key"="$val"
    done < <(grep -E '^(DB_|DATABASE|NEWS_API_KEY|FRED_API_KEY)=' "$SCRIPT_DIR/.env" 2>/dev/null || true)
fi

# ============================================================================
# DATABASE: Widow (direct) or NAS (SSH tunnel rollback)
# Widow: DB_HOST=192.168.93.101, DB_PORT=5432, DB_NAME=news_intel
# NAS rollback: DB_HOST=localhost, DB_PORT=5433 + setup_nas_ssh_tunnel.sh
# Set DB_PASSWORD in .env (project root); it is loaded above and passed to the API.
# ============================================================================
export DB_HOST="${DB_HOST:-192.168.93.101}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-news_intel}"
export DB_USER="${DB_USER:-newsapp}"
export DB_PASSWORD="${DB_PASSWORD:-}"

# Require DB password so the API never starts without credentials (avoids 503s on all DB routes)
if [[ -z "${DB_PASSWORD}" ]]; then
    if [[ "${DB_HOST}" == "192.168.93.101" ]] && [[ -f "$SCRIPT_DIR/.db_password_widow" ]]; then
        export DB_PASSWORD="$(cat "$SCRIPT_DIR/.db_password_widow" | head -1 | tr -d '\n\r')"
        echo -e "${CYAN}[INFO]${NC} Using DB password from .db_password_widow"
    fi
fi
if [[ -z "${DB_PASSWORD}" ]]; then
    echo -e "${RED}[ERROR]${NC} DB_PASSWORD is not set. The API will return 503 for all database routes without it." >&2
    echo -e "  Set it in project-root .env:" >&2
    echo -e "    DB_PASSWORD=your_newsapp_password" >&2
    echo -e "  Or (Widow only) create .db_password_widow with the password on the first line." >&2
    echo -e "  Then run this script again." >&2
    exit 1
fi

if [[ "${DB_HOST}" == "192.168.93.101" ]]; then
    echo -e "${CYAN}[INFO]${NC} Using Widow database (direct) at ${DB_HOST}:${DB_PORT}"
elif [[ "${DB_HOST}" == "localhost" ]] || [[ "${DB_HOST}" == "127.0.0.1" ]]; then
    if [[ "${DB_PORT}" != "5433" ]]; then
        echo -e "${RED}[ERROR]${NC} NAS rollback requires DB_PORT=5433 (SSH tunnel)" >&2
        exit 1
    fi
    echo -e "${CYAN}[INFO]${NC} Using NAS database via SSH tunnel (localhost:5433 -> 192.168.93.100:5432)"
    if ! pgrep -f "ssh -L 5433:localhost:5432.*192.168.93.100" > /dev/null 2>&1; then
        echo -e "${YELLOW}[WARNING]${NC} SSH tunnel not detected. Starting tunnel..."
        if [ -f "$SCRIPT_DIR/scripts/setup_nas_ssh_tunnel.sh" ]; then
            bash "$SCRIPT_DIR/scripts/setup_nas_ssh_tunnel.sh" || {
                echo -e "${RED}[ERROR]${NC} Failed to establish SSH tunnel." >&2
                exit 1
            }
        fi
    fi
    echo -e "${GREEN}[SUCCESS]${NC} SSH tunnel verified"
else
    echo -e "${RED}[ERROR]${NC} Unknown DB_HOST='${DB_HOST}'. Use 192.168.93.101 (Widow) or localhost (NAS rollback)" >&2
    exit 1
fi
LOG_DIR="$SCRIPT_DIR/logs"
API_DIR="$SCRIPT_DIR/api"
WEB_DIR="$SCRIPT_DIR/web"
API_LOG="$LOG_DIR/api_server.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
# Create logs directory
mkdir -p "$LOG_DIR"

# Uvicorn command line: `main:app` (api/main.py) or legacy `main_v4:app` — both must match for stop/restart
API_UVICORN_PGREP='uvicorn.*(main|main_v4):app'

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

# Check if a port is in use (only if something is LISTENing on it)
is_port_in_use() {
    ss -tlnp 2>/dev/null | grep -q ":$1 " && return 0
    # Fallback: netstat or lsof (listeners only)
    netstat -tlnp 2>/dev/null | grep -q ":$1 " && return 0
    return 1
}

# Free a TCP port when pgrep missed the process (e.g. odd uvicorn argv)
free_port() {
    local port=$1
    if command -v fuser &>/dev/null; then
        fuser -k "${port}/tcp" 2>/dev/null || true
    elif command -v lsof &>/dev/null; then
        lsof -ti ":${port}" 2>/dev/null | xargs -r kill 2>/dev/null || true
    fi
    sleep 1
}

# Stop existing processes
stop_existing() {
    log "Stopping existing processes..."
    
    # Stop API server: pkill then wait for process and port to clear (avoids "already running" + health fail)
    if is_running "$API_UVICORN_PGREP"; then
        log "Stopping existing API server..."
        pkill -f "$API_UVICORN_PGREP" || true
        local wait_count=0
        while is_running "$API_UVICORN_PGREP" && [ $wait_count -lt 10 ]; do
            sleep 1
            wait_count=$((wait_count + 1))
        done
        if is_running "$API_UVICORN_PGREP"; then
            warning "API process still present, sending SIGKILL..."
            pkill -9 -f "$API_UVICORN_PGREP" || true
            sleep 2
        fi
    fi
    if is_port_in_use 8000; then
        log "Freeing port 8000..."
        free_port 8000
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
    
    # For Widow (secondary) - direct connection
    if [[ "${DB_HOST}" == "192.168.93.101" ]]; then
        info "Verifying Widow database connection at ${DB_HOST}:${DB_PORT}..."
        if python3 -c "
import psycopg2, os
pw = os.environ.get('DB_PASSWORD') or (open('${SCRIPT_DIR}/.db_password_widow').read().strip() if os.path.exists('${SCRIPT_DIR}/.db_password_widow') else '')
conn = psycopg2.connect(host='${DB_HOST}', port=${DB_PORT}, database='${DB_NAME}', user='${DB_USER}', password=pw, connect_timeout=5)
conn.close()
" 2>/dev/null; then
            success "PostgreSQL (Widow): Running at ${DB_HOST}:${DB_PORT}"
            return 0
        fi
        if command -v pg_isready &> /dev/null; then
            if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" > /dev/null 2>&1; then
                success "PostgreSQL (Widow): Running"
                return 0
            fi
        fi
        error "Cannot connect to Widow database at ${DB_HOST}:${DB_PORT}"
        return 1
    fi
    
    # For NAS database (direct, legacy) - verify connectivity only
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

# Start API Server
start_api() {
    log "Starting API server..."
    
    # If we think API is already running, verify it responds; otherwise force-kill and start
    if is_running "$API_UVICORN_PGREP"; then
        if curl -sf http://localhost:8000/api/system_monitoring/health > /dev/null 2>&1; then
            success "API server already running and healthy"
            return 0
        fi
        warning "API process present but not responding to health check; restarting..."
        pkill -9 -f "$API_UVICORN_PGREP" || true
        sleep 3
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
    nohup env DB_HOST="${DB_HOST}" DB_PORT="${DB_PORT}" DB_NAME="${DB_NAME}" DB_USER="${DB_USER}" DB_PASSWORD="${DB_PASSWORD}" \
        NEWS_API_KEY="${NEWS_API_KEY:-}" FRED_API_KEY="${FRED_API_KEY:-}" \
        "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$API_LOG" 2>&1 &
    API_PID=$!
    
    # Wait for API to be ready
    log "Waiting for API server to start..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/api/system_monitoring/health > /dev/null 2>&1; then
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
    
    # Check API
    if curl -s --connect-timeout 5 --max-time 15 http://localhost:8000/api/system_monitoring/health > /dev/null 2>&1; then
        success "✅ API Server: Running (http://localhost:8000)"
        info "   - AutomationManager: Active (background tasks)"
        info "   - MLProcessingService: Active"
    else
        error "❌ API Server: Not responding"
        all_healthy=false
    fi
    
    # Check Frontend
    if curl -s --connect-timeout 5 --max-time 10 http://localhost:3000 > /dev/null 2>&1; then
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
            echo "  API PID:      $(cat "$LOG_DIR/api.pid")"
        fi
        if [ -f "$LOG_DIR/frontend.pid" ]; then
            echo "  Frontend PID: $(cat "$LOG_DIR/frontend.pid")"
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
    log "News Intelligence System v8.0 - Startup"
    log "=========================================="
    log "Started at: $(date)"
    echo ""
    
    # Pre-flight checks
    info "Running pre-flight checks..."
    
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
    
    # 2. API Server (includes AutomationManager and MLProcessingService)
    if ! start_api; then
        error "API server startup failed"
        return 1
    fi
    
    # 3. Frontend
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

