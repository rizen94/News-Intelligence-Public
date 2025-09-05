#!/bin/bash

# System Recovery Optimization Script for News Intelligence System v3.0
# Features: Fast startup, health checks, graceful shutdown, resource optimization

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="news-intelligence-system"
RECOVERY_START_TIME=$(date +%s)
LOG_FILE="recovery-optimization.log"
HEALTH_CHECK_TIMEOUT=60
MAX_RETRIES=3

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a $LOG_FILE
}

# Error handling
error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a $LOG_FILE
    exit 1
}

# Success message
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a $LOG_FILE
}

# Warning message
warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a $LOG_FILE
}

# Health check function
health_check() {
    local service=$1
    local url=$2
    local retries=0
    
    log "Checking health of $service..."
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            success "$service is healthy"
            return 0
        else
            retries=$((retries + 1))
            log "Health check attempt $retries/$MAX_RETRIES failed for $service"
            sleep 5
        fi
    done
    
    error "Health check failed for $service after $MAX_RETRIES attempts"
}

# Graceful shutdown function
graceful_shutdown() {
    log "Initiating graceful shutdown..."
    
    # Stop services in reverse order
    docker compose -f docker-compose.optimized.yml down --timeout 30
    
    # Clean up any orphaned containers
    docker container prune -f
    
    success "Graceful shutdown completed"
}

# Fast startup function
fast_startup() {
    log "Starting fast startup sequence..."
    
    # Start core services first
    log "Starting database and cache..."
    docker compose -f docker-compose.optimized.yml up -d news-system-postgres news-system-redis
    
    # Wait for core services to be healthy
    log "Waiting for core services to be ready..."
    sleep 10
    
    # Start backend
    log "Starting backend service..."
    docker compose -f docker-compose.optimized.yml up -d news-system-app
    
    # Wait for backend to be healthy
    health_check "Backend API" "http://localhost:8000/api/health/"
    
    # Start frontend
    log "Starting frontend service..."
    docker compose -f docker-compose.optimized.yml up -d news-frontend news-nginx
    
    # Wait for frontend to be healthy
    health_check "Frontend" "http://localhost:3001/"
    
    # Start monitoring (optional)
    if [ "$1" = "with-monitoring" ]; then
        log "Starting monitoring services..."
        docker compose -f docker-compose.optimized.yml up -d news-system-prometheus news-system-grafana
    fi
    
    success "Fast startup completed"
}

# Resource optimization
optimize_resources() {
    log "Optimizing system resources..."
    
    # Set Docker memory limits
    docker update --memory="512m" --memory-swap="1g" news-system-postgres 2>/dev/null || true
    docker update --memory="256m" --memory-swap="512m" news-system-redis 2>/dev/null || true
    docker update --memory="1g" --memory-swap="2g" news-system-app 2>/dev/null || true
    docker update --memory="256m" --memory-swap="512m" news-frontend 2>/dev/null || true
    docker update --memory="128m" --memory-swap="256m" news-nginx 2>/dev/null || true
    
    # Optimize PostgreSQL
    docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "
        ALTER SYSTEM SET shared_buffers = '128MB';
        ALTER SYSTEM SET effective_cache_size = '256MB';
        ALTER SYSTEM SET maintenance_work_mem = '64MB';
        ALTER SYSTEM SET checkpoint_completion_target = 0.9;
        ALTER SYSTEM SET wal_buffers = '16MB';
        ALTER SYSTEM SET default_statistics_target = 100;
        SELECT pg_reload_conf();
    " 2>/dev/null || warning "PostgreSQL optimization failed"
    
    success "Resource optimization completed"
}

# System monitoring
system_monitoring() {
    local total_time=$(($(date +%s) - RECOVERY_START_TIME))
    
    log "=== SYSTEM RECOVERY REPORT ==="
    echo "Total recovery time: ${total_time}s" | tee -a $LOG_FILE
    echo "Recovery completed at: $(date)" | tee -a $LOG_FILE
    
    # Service status
    echo "=== SERVICE STATUS ===" | tee -a $LOG_FILE
    docker compose -f docker-compose.optimized.yml ps | tee -a $LOG_FILE
    
    # Resource usage
    echo "=== RESOURCE USAGE ===" | tee -a $LOG_FILE
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | tee -a $LOG_FILE
    
    # Health status
    echo "=== HEALTH STATUS ===" | tee -a $LOG_FILE
    curl -s http://localhost:8000/api/health/ | jq '.' | tee -a $LOG_FILE
    
    success "System monitoring completed"
}

# Database optimization
optimize_database() {
    log "Optimizing database performance..."
    
    # Create indexes for better performance
    docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "
        -- Articles table indexes
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_created_at ON articles(created_at);
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_source ON articles(source);
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_category ON articles(category);
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_quality_score ON articles(quality_score);
        
        -- Story expectations table indexes
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_story_expectations_is_active ON story_expectations(is_active);
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_story_expectations_created_at ON story_expectations(created_at);
        
        -- ML task queue indexes
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_task_queue_status ON ml_task_queue(status);
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_task_queue_created_at ON ml_task_queue(created_at);
        
        -- Analyze tables for better query planning
        ANALYZE articles;
        ANALYZE story_expectations;
        ANALYZE ml_task_queue;
    " 2>/dev/null || warning "Database optimization failed"
    
    success "Database optimization completed"
}

# Main recovery function
main() {
    log "Starting system recovery optimization for $PROJECT_NAME v3.0"
    
    # Graceful shutdown if running
    if docker compose -f docker-compose.optimized.yml ps | grep -q "Up"; then
        graceful_shutdown
    fi
    
    # Fast startup
    fast_startup "$1"
    
    # Optimize resources
    optimize_resources
    
    # Optimize database
    optimize_database
    
    # System monitoring
    system_monitoring
    
    success "System recovery optimization completed!"
    log "Recovery log saved to: $LOG_FILE"
}

# Script execution
case "$1" in
    "start")
        main "without-monitoring"
        ;;
    "start-with-monitoring")
        main "with-monitoring"
        ;;
    "shutdown")
        graceful_shutdown
        ;;
    "optimize")
        optimize_resources
        optimize_database
        ;;
    "status")
        system_monitoring
        ;;
    *)
        echo "Usage: $0 {start|start-with-monitoring|shutdown|optimize|status}"
        echo "  start                 - Start system with core services only"
        echo "  start-with-monitoring - Start system with monitoring"
        echo "  shutdown              - Graceful shutdown"
        echo "  optimize              - Optimize resources and database"
        echo "  status                - Show system status"
        exit 1
        ;;
esac


