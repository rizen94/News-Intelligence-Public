#!/bin/bash
# News Intelligence System v3.3.0 - Comprehensive Startup Script with Disaster Recovery
# Handles all startup activities and disaster recovery conditions

set -euo pipefail  # Exit on any error, undefined vars, pipe failures

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
LOG_DIR="$PROJECT_DIR/logs"
BACKUP_DIR="$PROJECT_DIR/backups"
PID_FILE="$PROJECT_DIR/.system.pid"
LOCK_FILE="$PROJECT_DIR/.system.lock"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/startup.log"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/startup.log"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/startup.log"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/startup.log"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$PROJECT_DIR/data/cache"
    mkdir -p "$PROJECT_DIR/data/models"
    log_success "Directories created successfully"
}

# Check if system is already running
check_system_status() {
    log_info "Checking system status..."
    
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            log_warning "System appears to be running (PID: $pid)"
            read -p "Do you want to stop the existing system and restart? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "Stopping existing system..."
                kill -TERM "$pid" 2>/dev/null || true
                sleep 5
                if ps -p "$pid" > /dev/null 2>&1; then
                    log_warning "Force killing process $pid"
                    kill -KILL "$pid" 2>/dev/null || true
                fi
                rm -f "$PID_FILE"
            else
                log_info "Exiting without changes"
                exit 0
            fi
        else
            log_warning "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi
    
    if [ -f "$LOCK_FILE" ]; then
        log_warning "Lock file found, removing..."
        rm -f "$LOCK_FILE"
    fi
    
    log_success "System status check completed"
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    
    # Check Node.js (for frontend)
    if ! command -v node &> /dev/null; then
        log_warning "Node.js is not installed - frontend will not be available"
    fi
    
    # Check available memory
    local mem_gb=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$mem_gb" -lt 4 ]; then
        log_warning "System has less than 4GB RAM ($mem_gb GB) - performance may be affected"
    fi
    
    # Check available disk space
    local disk_gb=$(df -BG "$PROJECT_DIR" | awk 'NR==2{print $4}' | sed 's/G//')
    if [ "$disk_gb" -lt 10 ]; then
        log_warning "Less than 10GB disk space available ($disk_gb GB) - may cause issues"
    fi
    
    log_success "System requirements check completed"
}

# Start Docker services
start_docker_services() {
    log_info "Starting Docker services..."
    
    # Start Docker daemon if not running
    if ! docker info &> /dev/null; then
        log_info "Starting Docker daemon..."
        sudo systemctl start docker
        sleep 5
    fi
    
    # Check if containers are already running
    if docker-compose ps | grep -q "Up"; then
        log_warning "Some containers are already running"
        read -p "Do you want to restart all containers? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Stopping existing containers..."
            docker-compose down
        fi
    fi
    
    # Start containers
    log_info "Starting containers with docker-compose..."
    cd "$PROJECT_DIR"
    docker-compose up -d --build
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose ps | grep -q "Up" && \
           docker exec news-system-postgres pg_isready -U newsapp &> /dev/null; then
            log_success "Docker services are ready"
            break
        fi
        
        attempt=$((attempt + 1))
        log_info "Waiting for services... (attempt $attempt/$max_attempts)"
        sleep 10
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Services failed to start within expected time"
        docker-compose logs
        exit 1
    fi
}

# Initialize database
initialize_database() {
    log_info "Initializing database..."
    
    # Wait for PostgreSQL to be ready
    local max_attempts=20
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec news-system-postgres pg_isready -U newsapp &> /dev/null; then
            break
        fi
        attempt=$((attempt + 1))
        sleep 5
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "PostgreSQL failed to start"
        exit 1
    fi
    
    # Run database migrations
    log_info "Running database migrations..."
    if [ -f "$PROJECT_DIR/api/docker/postgres/init/01_base_schema.sql" ]; then
        docker exec -i news-system-postgres psql -U newsapp -d newsintelligence < "$PROJECT_DIR/api/docker/postgres/init/01_base_schema.sql"
        log_success "Base schema applied"
    fi
    
    # Apply any additional migrations
    for migration_file in "$PROJECT_DIR/api/database/migrations"/*.sql; do
        if [ -f "$migration_file" ]; then
            log_info "Applying migration: $(basename "$migration_file")"
            docker exec -i news-system-postgres psql -U newsapp -d newsintelligence < "$migration_file"
        fi
    done
    
    log_success "Database initialization completed"
}

# Install Python dependencies
install_python_dependencies() {
    log_info "Installing Python dependencies..."
    
    cd "$PROJECT_DIR"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    if [ -f "api/requirements.txt" ]; then
        log_info "Installing requirements from api/requirements.txt..."
        pip install -r api/requirements.txt
    fi
    
    # Install additional dependencies if needed
    pip install psycopg2-binary feedparser nltk scikit-learn joblib threadpoolctl sgmllib3k
    
    log_success "Python dependencies installed"
}

# Install Node.js dependencies (if available)
install_node_dependencies() {
    if command -v node &> /dev/null; then
        log_info "Installing Node.js dependencies..."
        cd "$PROJECT_DIR/web"
        
        if [ -f "package.json" ]; then
            # Check Node.js version
            local node_version=$(node --version | sed 's/v//' | cut -d. -f1)
            if [ "$node_version" -lt 14 ]; then
                log_warning "Node.js version $node_version is too old for React 18+. Frontend may not work properly."
            fi
            
            # Install dependencies
            npm install
            log_success "Node.js dependencies installed"
        else
            log_warning "No package.json found in web directory"
        fi
    else
        log_warning "Node.js not available - skipping frontend setup"
    fi
}

# Start API server
start_api_server() {
    log_info "Starting API server..."
    
    cd "$PROJECT_DIR"
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Start API server in background
    nohup python3 -c "
import sys
sys.path.append('api')
from api.main import app
import uvicorn
print('Starting News Intelligence System v3.3.0 with automation enabled...')
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
" > "$LOG_DIR/api.log" 2>&1 &
    
    local api_pid=$!
    echo $api_pid > "$PID_FILE"
    
    # Wait for API to be ready
    log_info "Waiting for API server to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/api/health/ &> /dev/null; then
            log_success "API server is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "API server failed to start"
        cat "$LOG_DIR/api.log"
        exit 1
    fi
}

# Start frontend (if available)
start_frontend() {
    if command -v node &> /dev/null && [ -d "$PROJECT_DIR/web" ]; then
        log_info "Starting frontend..."
        cd "$PROJECT_DIR/web"
        
        # Start frontend in background
        nohup npm start > "$LOG_DIR/frontend.log" 2>&1 &
        local frontend_pid=$!
        echo $frontend_pid >> "$PID_FILE"
        
        log_success "Frontend started (PID: $frontend_pid)"
    else
        log_warning "Frontend not available or not configured"
    fi
}

# Run system health check
run_health_check() {
    log_info "Running system health check..."
    
    # Check API health
    local api_health=$(curl -s http://localhost:8000/api/health/ | jq -r '.data.status' 2>/dev/null || echo "unknown")
    if [ "$api_health" = "healthy" ]; then
        log_success "API health check passed"
    else
        log_error "API health check failed: $api_health"
        return 1
    fi
    
    # Check database connectivity
    if docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "SELECT 1;" &> /dev/null; then
        log_success "Database connectivity check passed"
    else
        log_error "Database connectivity check failed"
        return 1
    fi
    
    # Check Redis connectivity
    if docker exec news-system-redis redis-cli ping &> /dev/null; then
        log_success "Redis connectivity check passed"
    else
        log_error "Redis connectivity check failed"
        return 1
    fi
    
    log_success "All health checks passed"
}

# Create system monitoring script
create_monitoring_script() {
    log_info "Creating system monitoring script..."
    
    cat > "$PROJECT_DIR/monitor_system.sh" << 'EOF'
#!/bin/bash
# System monitoring script

LOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/logs"
PID_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.system.pid"

check_system() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "✅ System is running (PID: $pid)"
            
            # Check API
            if curl -s http://localhost:8000/api/health/ &> /dev/null; then
                echo "✅ API is responding"
            else
                echo "❌ API is not responding"
            fi
            
            # Check database
            if docker exec news-system-postgres pg_isready -U newsapp &> /dev/null; then
                echo "✅ Database is ready"
            else
                echo "❌ Database is not ready"
            fi
            
            # Check Redis
            if docker exec news-system-redis redis-cli ping &> /dev/null; then
                echo "✅ Redis is ready"
            else
                echo "❌ Redis is not ready"
            fi
        else
            echo "❌ System is not running (stale PID file)"
        fi
    else
        echo "❌ System is not running (no PID file)"
    fi
}

check_system
EOF
    
    chmod +x "$PROJECT_DIR/monitor_system.sh"
    log_success "Monitoring script created: $PROJECT_DIR/monitor_system.sh"
}

# Create disaster recovery script
create_recovery_script() {
    log_info "Creating disaster recovery script..."
    
    cat > "$PROJECT_DIR/disaster_recovery.sh" << 'EOF'
#!/bin/bash
# Disaster recovery script for News Intelligence System

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
BACKUP_DIR="$PROJECT_DIR/backups"

echo "🚨 DISASTER RECOVERY MODE 🚨"
echo "This script will attempt to recover the system from various failure states"
echo

# Function to stop all services
stop_all_services() {
    echo "🛑 Stopping all services..."
    
    # Stop API server
    if [ -f "$PROJECT_DIR/.system.pid" ]; then
        local pid=$(cat "$PROJECT_DIR/.system.pid")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill -TERM "$pid" 2>/dev/null || true
            sleep 5
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -KILL "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PROJECT_DIR/.system.pid"
    fi
    
    # Stop Docker containers
    cd "$PROJECT_DIR"
    docker-compose down 2>/dev/null || true
    
    # Clean up lock files
    rm -f "$PROJECT_DIR/.system.lock"
    
    echo "✅ All services stopped"
}

# Function to clean up Docker
cleanup_docker() {
    echo "🧹 Cleaning up Docker..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    # Remove unused networks
    docker network prune -f
    
    echo "✅ Docker cleanup completed"
}

# Function to restore from backup
restore_from_backup() {
    echo "📦 Checking for backups..."
    
    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A "$BACKUP_DIR")" ]; then
        echo "Found backups in $BACKUP_DIR"
        ls -la "$BACKUP_DIR"
        
        read -p "Do you want to restore from the latest backup? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            local latest_backup=$(ls -t "$BACKUP_DIR"/*.sql 2>/dev/null | head -n1)
            if [ -n "$latest_backup" ]; then
                echo "Restoring from: $latest_backup"
                # Start PostgreSQL first
                docker-compose up -d news-system-postgres
                sleep 10
                # Restore database
                docker exec -i news-system-postgres psql -U newsapp -d newsintelligence < "$latest_backup"
                echo "✅ Database restored from backup"
            else
                echo "❌ No SQL backup files found"
            fi
        fi
    else
        echo "❌ No backups found"
    fi
}

# Function to reset system
reset_system() {
    echo "🔄 Resetting system to clean state..."
    
    stop_all_services
    cleanup_docker
    
    # Remove data directories
    rm -rf "$PROJECT_DIR/data/cache"/*
    rm -rf "$PROJECT_DIR/logs"/*
    
    echo "✅ System reset completed"
}

# Main recovery menu
echo "Select recovery option:"
echo "1) Stop all services and cleanup"
echo "2) Clean up Docker resources"
echo "3) Restore from backup"
echo "4) Reset system to clean state"
echo "5) Full recovery (stop, cleanup, restore, restart)"
echo "6) Exit"

read -p "Enter choice (1-6): " choice

case $choice in
    1)
        stop_all_services
        ;;
    2)
        cleanup_docker
        ;;
    3)
        restore_from_backup
        ;;
    4)
        reset_system
        ;;
    5)
        stop_all_services
        cleanup_docker
        restore_from_backup
        echo "🔄 Restarting system..."
        "$PROJECT_DIR/startup_with_recovery.sh"
        ;;
    6)
        echo "Exiting recovery mode"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo "Recovery operation completed"
EOF
    
    chmod +x "$PROJECT_DIR/disaster_recovery.sh"
    log_success "Disaster recovery script created: $PROJECT_DIR/disaster_recovery.sh"
}

# Create systemd service file
create_systemd_service() {
    log_info "Creating systemd service file..."
    
    sudo tee /etc/systemd/system/news-intelligence.service > /dev/null << EOF
[Unit]
Description=News Intelligence System v3.3.0
After=docker.service
Requires=docker.service

[Service]
Type=forking
User=pete
Group=pete
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/startup_with_recovery.sh
ExecStop=$PROJECT_DIR/disaster_recovery.sh
Restart=on-failure
RestartSec=30
TimeoutStartSec=300
TimeoutStopSec=300

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    log_success "Systemd service created: news-intelligence.service"
    log_info "To enable auto-start: sudo systemctl enable news-intelligence.service"
}

# Main startup sequence
main() {
    log_info "🚀 Starting News Intelligence System v3.3.0 with Disaster Recovery"
    log_info "Project directory: $PROJECT_DIR"
    
    # Create lock file
    touch "$LOCK_FILE"
    
    # Run startup sequence
    create_directories
    check_system_status
    check_requirements
    start_docker_services
    initialize_database
    install_python_dependencies
    install_node_dependencies
    start_api_server
    start_frontend
    run_health_check
    create_monitoring_script
    create_recovery_script
    create_systemd_service
    
    # Remove lock file
    rm -f "$LOCK_FILE"
    
    log_success "🎉 News Intelligence System v3.3.0 started successfully!"
    log_info "📊 System Status:"
    log_info "   - API Server: http://localhost:8000"
    log_info "   - API Docs: http://localhost:8000/docs"
    log_info "   - Frontend: http://localhost:3000 (if available)"
    log_info "   - Logs: $LOG_DIR"
    log_info "   - Monitor: $PROJECT_DIR/monitor_system.sh"
    log_info "   - Recovery: $PROJECT_DIR/disaster_recovery.sh"
    log_info "   - PID File: $PID_FILE"
    
    # Show monitoring info
    log_info "📈 To monitor the system: $PROJECT_DIR/monitor_system.sh"
    log_info "🚨 For disaster recovery: $PROJECT_DIR/disaster_recovery.sh"
    log_info "🔄 To restart: $PROJECT_DIR/startup_with_recovery.sh"
}

# Handle script interruption
trap 'log_error "Startup interrupted"; rm -f "$LOCK_FILE"; exit 1' INT TERM

# Run main function
main "$@"

