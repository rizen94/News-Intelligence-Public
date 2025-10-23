#!/bin/bash

# News Intelligence System v3.0 - Manual Startup Script
# Bypasses docker-compose issues by starting services manually

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LOG_FILE="logs/manual-startup.log"
PIPELINE_LOG_FILE="logs/pipeline_trace.log"

# Create logs directory
mkdir -p logs

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Initialize pipeline logging system
init_pipeline_logging() {
    log "Initializing pipeline logging system..."
    
    # Create pipeline log file
    touch "$PIPELINE_LOG_FILE"
    
    success "Pipeline logging system initialized"
}

# Check if Docker is running
check_docker() {
    log "Checking Docker status..."
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    success "Docker is running"
}

# Stop existing containers
stop_existing() {
    log "Stopping existing containers..."
    
    # Stop and remove existing containers
    docker stop news-intelligence-postgres news-intelligence-redis news-intelligence-api news-intelligence-frontend 2>/dev/null || true
    docker rm news-intelligence-postgres news-intelligence-redis news-intelligence-api news-intelligence-frontend 2>/dev/null || true
    
    success "Existing containers stopped"
}

# Start PostgreSQL
start_postgres() {
    log "Starting PostgreSQL database..."
    
    # Create network if it doesn't exist
    docker network create news-network 2>/dev/null || true
    
    # Start PostgreSQL
    docker run -d \
        --name news-intelligence-postgres \
        --network news-network \
        -e POSTGRES_DB=news_intelligence \
        -e POSTGRES_USER=newsapp \
        -e POSTGRES_PASSWORD=newsapp_password \
        -p 5432:5432 \
        -v postgres_data:/var/lib/postgresql/data \
        -v "$(pwd)/api/database/init.sql:/docker-entrypoint-initdb.d/init.sql" \
        -v "$(pwd)/api/database/migrations/011_pipeline_tracking_tables.sql:/docker-entrypoint-initdb.d/011_pipeline_tracking_tables.sql" \
        postgres:15-alpine
    
    # Wait for PostgreSQL to be ready
    log "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec news-intelligence-postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
            success "PostgreSQL is ready"
            return 0
        fi
        sleep 2
    done
    
    error "PostgreSQL failed to start"
    return 1
}

# Start Redis
start_redis() {
    log "Starting Redis cache..."
    
    docker run -d \
        --name news-intelligence-redis \
        --network news-network \
        -p 6379:6379 \
        -v redis_data:/data \
        redis:7-alpine redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    
    # Wait for Redis to be ready
    log "Waiting for Redis to be ready..."
    for i in {1..15}; do
        if docker exec news-intelligence-redis redis-cli ping > /dev/null 2>&1; then
            success "Redis is ready"
            return 0
        fi
        sleep 2
    done
    
    error "Redis failed to start"
    return 1
}

# Start API
start_api() {
    log "Starting API service..."
    
    # Build API image if it doesn't exist
    if ! docker images | grep -q news-intelligence-api; then
        log "Building API image..."
        docker build -t news-intelligence-api -f api/Dockerfile.production ./api
    fi
    
    docker run -d \
        --name news-intelligence-api \
        --network news-network \
        -e DATABASE_URL=postgresql://newsapp:newsapp_password@news-intelligence-postgres:5432/news_intelligence \
        -e REDIS_URL=redis://news-intelligence-redis:6379/0 \
        -e ENVIRONMENT=production \
        -e LOG_LEVEL=info \
        -p 8000:8000 \
        -v "$(pwd)/api/logs:/app/logs" \
        news-intelligence-api
    
    # Wait for API to be ready
    log "Waiting for API to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
            success "API is ready"
            return 0
        fi
        sleep 3
    done
    
    error "API failed to start"
    return 1
}

# Start Frontend
start_frontend() {
    log "Starting Frontend service..."
    
    # Build frontend image if it doesn't exist
    if ! docker images | grep -q news-intelligence-frontend; then
        log "Building frontend image..."
        docker build -t news-intelligence-frontend -f Dockerfile.frontend ./web
    fi
    
    docker run -d \
        --name news-intelligence-frontend \
        --network news-network \
        -p 80:80 \
        news-intelligence-frontend
    
    # Wait for frontend to be ready
    log "Waiting for frontend to be ready..."
    for i in {1..20}; do
        if curl -s http://localhost/ > /dev/null 2>&1; then
            success "Frontend is ready"
            return 0
        fi
        sleep 3
    done
    
    error "Frontend failed to start"
    return 1
}

# Initialize database
init_database() {
    log "Initializing database with pipeline tracking tables..."
    
    # Apply pipeline tracking migration
    docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -f /docker-entrypoint-initdb.d/011_pipeline_tracking_tables.sql 2>/dev/null || {
        warning "Pipeline tracking tables may already exist or migration failed"
    }
    
    success "Database initialized with pipeline tracking"
}

# Display service status
show_status() {
    log "Service Status:"
    echo "=================="
    
    # PostgreSQL
    if docker exec news-intelligence-postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        success "PostgreSQL: Running"
    else
        error "PostgreSQL: Not responding"
    fi
    
    # Redis
    if docker exec news-intelligence-redis redis-cli ping > /dev/null 2>&1; then
        success "Redis: Running"
    else
        error "Redis: Not responding"
    fi
    
    # API
    if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
        success "API: Running (http://localhost:8000)"
    else
        error "API: Not responding"
    fi
    
    # Frontend
    if curl -s http://localhost/ > /dev/null 2>&1; then
        success "Frontend: Running (http://localhost)"
    else
        error "Frontend: Not responding"
    fi
    
    # Pipeline Monitoring
    if curl -s http://localhost:8000/api/pipeline-monitoring/health > /dev/null 2>&1; then
        success "Pipeline Monitoring: Running (http://localhost:8000/api/pipeline-monitoring)"
    else
        error "Pipeline Monitoring: Not responding"
    fi
    
    echo ""
    log "Access URLs:"
    echo "  Frontend: http://localhost"
    echo "  API: http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  Pipeline Monitoring: http://localhost:8000/api/pipeline-monitoring"
    
    echo ""
    log "Pipeline Logging:"
    echo "  Pipeline Log: logs/pipeline_trace.log"
    echo "  Startup Log: logs/manual-startup.log"
}

# Main execution
main() {
    log "Starting News Intelligence System v3.0 with Pipeline Logging (Manual Mode)"
    log "============================================================================"
    
    init_pipeline_logging
    check_docker
    stop_existing
    
    if start_postgres && start_redis && start_api && start_frontend; then
        init_database
        show_status
        success "Production system with pipeline logging is ready!"
        log "System started successfully. Check logs with: docker logs news-intelligence-api"
        log "Pipeline logs: tail -f logs/pipeline_trace.log"
    else
        error "Production system failed to start properly."
        log "Check logs with: docker logs news-intelligence-api"
        exit 1
    fi
}

# Handle script interruption
trap 'error "Script interrupted. Stopping services..."; docker stop news-intelligence-postgres news-intelligence-redis news-intelligence-api news-intelligence-frontend; exit 1' INT TERM

# Run main function
main "$@"
