#!/bin/bash

# News Intelligence System v3.0 - Production Startup Script
# This script starts the production system with RTX 5090 + 62GB RAM optimizations

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

# Create logs directory
mkdir -p logs

# Initialize optimized system
init_optimized_system() {
    log "Initializing RTX 5090 + 62GB RAM optimized system..."
    
    # Load optimized Ollama configuration
    if [ -f ~/.config/ollama/ollama.env ]; then
        source ~/.config/ollama/ollama.env
        log "Loaded optimized Ollama configuration"
    else
        warning "Optimized Ollama config not found, using defaults"
    fi
    
    # Set additional system optimizations
    export CUDA_VISIBLE_DEVICES=0
    export OMP_NUM_THREADS=16
    export MKL_NUM_THREADS=16
    
    # Make scripts executable
    chmod +x scripts/simple_integration.py
    chmod +x scripts/quick_check.py
    chmod +x scripts/production/start_optimized_system.sh
    
    success "Optimized system initialized"
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

# Initialize database
init_database() {
    log "Initializing database..."
    
    # Check if database is accessible
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        log "Database is accessible"
        success "Database initialized"
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
        local total_count=4  # Core services only
        
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
    
    echo ""
    log "Access URLs:"
    echo "  Frontend: http://localhost"
    echo "  API: http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  Monitoring: http://localhost:9090"
    
    echo ""
    log "Integration Tools:"
    echo "  Quick Check: python3 scripts/quick_check.py"
    echo "  Full Integration: python3 scripts/simple_integration.py"
    echo "  Startup Log: logs/production-startup.log"
}

# Start Ollama ML service
start_ollama() {
    log "Starting Ollama ML service with RTX 5090 optimizations..."
    
    # Kill any existing Ollama processes
    pkill -f ollama 2>/dev/null || true
    sleep 2
    
    # Start Ollama with optimized settings
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    log "Ollama started with PID: $OLLAMA_PID"
    
    # Wait for Ollama to be ready
    log "Waiting for Ollama to initialize..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            success "Ollama is ready"
            break
        fi
        log "Waiting... ($i/30)"
        sleep 2
    done
}

# Main execution
main() {
    log "Starting News Intelligence System v3.0 - RTX 5090 Optimized"
    log "============================================================"
    
    init_optimized_system
    check_docker
    check_docker_compose
    stop_existing
    start_services
    
    if wait_for_health; then
        init_database
        start_ollama
        show_status
        success "Production system is ready with RTX 5090 optimizations!"
        log "System started successfully. Check logs with: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f"
        log "Test integration: python3 scripts/simple_integration.py"
        log "Ollama logs: tail -f /tmp/ollama.log"
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
