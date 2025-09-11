#!/bin/bash

# News Intelligence System v3.0 - Production Startup Script with Pipeline Logging
# This script starts the production system with comprehensive pipeline tracking and monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="news-intelligence"
HEALTH_CHECK_TIMEOUT=300
LOG_FILE="logs/production-startup.log"
PIPELINE_LOG_FILE="logs/pipeline_trace.log"

# Create logs directory
mkdir -p logs

# Initialize pipeline logging system
init_pipeline_logging() {
    log "Initializing pipeline logging system..."
    
    # Create pipeline log file
    touch "$PIPELINE_LOG_FILE"
    
    # Set up log rotation for pipeline logs
    if ! crontab -l 2>/dev/null | grep -q "pipeline_trace.log"; then
        log "Setting up log rotation for pipeline logs..."
        (crontab -l 2>/dev/null; echo "0 2 * * * find $(pwd)/logs -name 'pipeline_trace.log*' -mtime +7 -delete") | crontab -
    fi
    
    success "Pipeline logging system initialized"
}

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

# Initialize database with pipeline tracking tables
init_database() {
    log "Initializing database with pipeline tracking tables..."
    
    # Check if database is accessible
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        log "Database is accessible, checking for pipeline tracking tables..."
        
        # Run database migrations for pipeline tracking
        log "Applying pipeline tracking database migrations..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres psql -U newsapp -d news_intelligence -f /docker-entrypoint-initdb.d/011_pipeline_tracking_tables.sql 2>/dev/null || {
            warning "Pipeline tracking tables may already exist or migration failed"
        }
        success "Pipeline tracking database schema initialized"
    else
        warning "Database not accessible yet, will initialize after startup"
    fi
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

# Check if Docker Compose is available
check_docker_compose() {
    log "Checking Docker Compose..."
    if ! command -v docker-compose > /dev/null 2>&1; then
        error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
    success "Docker Compose is available"
}

# Stop existing containers
stop_existing() {
    log "Stopping existing containers..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --remove-orphans 2>/dev/null || true
    success "Existing containers stopped"
}

# Start services
start_services() {
    log "Starting production services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
    success "Services started"
}

# Wait for service health
wait_for_health() {
    log "Waiting for services to become healthy..."
    
    local timeout=$HEALTH_CHECK_TIMEOUT
    local start_time=$(date +%s)
    
    while [ $(($(date +%s) - start_time)) -lt $timeout ]; do
        local healthy_count=0
        local total_count=5  # Added pipeline monitoring
        
        # Check PostgreSQL
        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
            ((healthy_count++))
        fi
        
        # Check Redis
        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis redis-cli ping > /dev/null 2>&1; then
            ((healthy_count++))
        fi
        
        # Check API
        if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
            ((healthy_count++))
        fi
        
        # Check Frontend
        if curl -s http://localhost/ > /dev/null 2>&1; then
            ((healthy_count++))
        fi
        
        # Check Pipeline Monitoring API
        if curl -s http://localhost:8000/api/pipeline-monitoring/health > /dev/null 2>&1; then
            ((healthy_count++))
        fi
        
        if [ $healthy_count -eq $total_count ]; then
            success "All services are healthy!"
            return 0
        fi
        
        log "Health check: $healthy_count/$total_count services healthy"
        sleep 10
    done
    
    error "Health check timeout. Some services may not be ready."
    return 1
}

# Display service status
show_status() {
    log "Service Status:"
    echo "=================="
    
    # PostgreSQL
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        success "PostgreSQL: Running"
    else
        error "PostgreSQL: Not responding"
    fi
    
    # Redis
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis redis-cli ping > /dev/null 2>&1; then
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
    echo "  Monitoring: http://localhost:9090"
    
    echo ""
    log "Pipeline Logging:"
    echo "  Pipeline Log: logs/pipeline_trace.log"
    echo "  Startup Log: logs/production-startup.log"
}

# Main execution
main() {
    log "Starting News Intelligence System v3.0 with Pipeline Logging"
    log "============================================================"
    
    init_pipeline_logging
    check_docker
    check_docker_compose
    stop_existing
    start_services
    
    if wait_for_health; then
        init_database
        show_status
        success "Production system with pipeline logging is ready!"
        log "System started successfully. Check logs with: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f"
        log "Pipeline logs: tail -f logs/pipeline_trace.log"
    else
        error "Production system failed to start properly."
        log "Check logs with: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs"
        exit 1
    fi
}

# Handle script interruption
trap 'error "Script interrupted. Stopping services..."; docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down; exit 1' INT TERM

# Run main function
main "$@"
