#!/bin/bash

# Production Deployment Script for News Intelligence System v3.0
# Optimized for production deployment with monitoring and scaling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="news-intelligence-system"
VERSION="3.0.0"
ENVIRONMENT="production"
DEPLOYMENT_START_TIME=$(date +%s)
LOG_FILE="production-deployment.log"

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

# Pre-deployment checks
pre_deployment_checks() {
    log "Starting pre-deployment checks..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running. Please start Docker and try again."
    fi
    
    # Check if required files exist
    if [ ! -f "docker-compose.yml" ]; then
        error "docker-compose.yml not found. Please run from project root."
    fi
    
    # Check disk space
    AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
    if [ $AVAILABLE_SPACE -lt 5242880 ]; then # 5GB in KB
        warning "Low disk space detected. Consider cleaning up before deployment."
    fi
    
    # Check memory
    AVAILABLE_MEMORY=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    if [ $AVAILABLE_MEMORY -lt 2048 ]; then # 2GB
        warning "Low memory detected. Consider increasing system memory."
    fi
    
    success "Pre-deployment checks completed"
}

# Backup current deployment
backup_current_deployment() {
    log "Creating backup of current deployment..."
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    
    # Backup database
    if docker ps | grep -q news-system-postgres; then
        log "Backing up database..."
        docker exec news-system-postgres pg_dump -U newsapp newsintelligence > $BACKUP_DIR/database.sql
    fi
    
    # Backup configuration
    cp -r configs/ $BACKUP_DIR/ 2>/dev/null || true
    cp docker-compose.yml $BACKUP_DIR/ 2>/dev/null || true
    
    # Backup logs
    mkdir -p $BACKUP_DIR/logs
    docker logs news-system-app > $BACKUP_DIR/logs/backend.log 2>/dev/null || true
    docker logs news-frontend > $BACKUP_DIR/logs/frontend.log 2>/dev/null || true
    
    success "Backup created at $BACKUP_DIR"
}

# Build production images
build_production_images() {
    log "Building production images..."
    
    # Enable BuildKit for better caching
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # Build with production optimizations
    docker compose build \
        --no-cache \
        --parallel \
        --progress=plain \
        2>&1 | tee -a $LOG_FILE
    
    if [ $? -eq 0 ]; then
        success "Production images built successfully"
    else
        error "Failed to build production images"
    fi
}

# Deploy to production
deploy_production() {
    log "Deploying to production..."
    
    # Stop existing services gracefully
    log "Stopping existing services..."
    docker compose down --timeout 30
    
    # Start production services
    log "Starting production services..."
    docker compose up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_service_health
    
    success "Production deployment completed"
}

# Check service health
check_service_health() {
    log "Checking service health..."
    
    # Check backend API
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
            success "Backend API is healthy"
            break
        else
            log "Waiting for backend API... (attempt $attempt/$max_attempts)"
            sleep 10
            attempt=$((attempt + 1))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        error "Backend API failed to start within expected time"
    fi
    
    # Check frontend
    if curl -f -s http://localhost:3001/ > /dev/null 2>&1; then
        success "Frontend is healthy"
    else
        warning "Frontend may not be fully ready yet"
    fi
    
    # Check database
    if docker exec news-system-postgres pg_isready -U newsapp > /dev/null 2>&1; then
        success "Database is healthy"
    else
        error "Database is not healthy"
    fi
}

# Setup monitoring
setup_monitoring() {
    log "Setting up production monitoring..."
    
    # Start monitoring services
    docker compose -f configs/docker-compose.monitoring.yml up -d
    
    # Wait for monitoring to be ready
    sleep 20
    
    # Check monitoring services
    if curl -f -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        success "Prometheus is running"
    else
        warning "Prometheus may not be fully ready"
    fi
    
    if curl -f -s http://localhost:3002/api/health > /dev/null 2>&1; then
        success "Grafana is running"
    else
        warning "Grafana may not be fully ready"
    fi
}

# Optimize production settings
optimize_production() {
    log "Optimizing production settings..."
    
    # Set production environment variables
    docker exec news-system-app sh -c 'echo "ENVIRONMENT=production" >> /app/.env'
    
    # Optimize database settings
    docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "
        ALTER SYSTEM SET shared_buffers = '256MB';
        ALTER SYSTEM SET effective_cache_size = '1GB';
        ALTER SYSTEM SET maintenance_work_mem = '128MB';
        ALTER SYSTEM SET checkpoint_completion_target = 0.9;
        ALTER SYSTEM SET wal_buffers = '32MB';
        ALTER SYSTEM SET default_statistics_target = 100;
        ALTER SYSTEM SET random_page_cost = 1.1;
        ALTER SYSTEM SET effective_io_concurrency = 200;
        SELECT pg_reload_conf();
    " 2>/dev/null || warning "Database optimization failed"
    
    # Set memory limits for containers
    docker update --memory="2g" --memory-swap="4g" news-system-app 2>/dev/null || true
    docker update --memory="1g" --memory-swap="2g" news-system-postgres 2>/dev/null || true
    docker update --memory="512m" --memory-swap="1g" news-system-redis 2>/dev/null || true
    
    success "Production optimization completed"
}

# Run post-deployment tests
run_post_deployment_tests() {
    log "Running post-deployment tests..."
    
    # Test API endpoints
    local api_tests=(
        "http://localhost:8000/api/health/"
        "http://localhost:8000/api/articles/?per_page=5"
        "http://localhost:8000/api/dashboard/stats"
    )
    
    for url in "${api_tests[@]}"; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            success "API test passed: $url"
        else
            error "API test failed: $url"
        fi
    done
    
    # Test frontend
    if curl -f -s http://localhost:3001/ > /dev/null 2>&1; then
        success "Frontend test passed"
    else
        error "Frontend test failed"
    fi
    
    success "Post-deployment tests completed"
}

# Generate deployment report
generate_deployment_report() {
    local total_time=$(($(date +%s) - DEPLOYMENT_START_TIME))
    
    log "=== PRODUCTION DEPLOYMENT REPORT ==="
    echo "Deployment completed at: $(date)" | tee -a $LOG_FILE
    echo "Total deployment time: ${total_time}s" | tee -a $LOG_FILE
    echo "Version: $VERSION" | tee -a $LOG_FILE
    echo "Environment: $ENVIRONMENT" | tee -a $LOG_FILE
    
    # Service status
    echo "=== SERVICE STATUS ===" | tee -a $LOG_FILE
    docker compose ps | tee -a $LOG_FILE
    
    # Resource usage
    echo "=== RESOURCE USAGE ===" | tee -a $LOG_FILE
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | tee -a $LOG_FILE
    
    # Health status
    echo "=== HEALTH STATUS ===" | tee -a $LOG_FILE
    curl -s http://localhost:8000/api/health/ | jq '.' | tee -a $LOG_FILE
    
    success "Deployment report generated"
}

# Cleanup function
cleanup() {
    log "Cleaning up temporary files..."
    docker system prune -f --volumes
    success "Cleanup completed"
}

# Main deployment function
main() {
    log "Starting production deployment for $PROJECT_NAME v$VERSION"
    
    # Pre-deployment checks
    pre_deployment_checks
    
    # Backup current deployment
    backup_current_deployment
    
    # Build production images
    build_production_images
    
    # Deploy to production
    deploy_production
    
    # Setup monitoring
    setup_monitoring
    
    # Optimize production settings
    optimize_production
    
    # Run post-deployment tests
    run_post_deployment_tests
    
    # Generate deployment report
    generate_deployment_report
    
    # Cleanup
    cleanup
    
    success "Production deployment completed successfully!"
    log "Deployment log saved to: $LOG_FILE"
    
    echo ""
    echo "🚀 Production deployment complete!"
    echo "Frontend: http://localhost:3001"
    echo "API: http://localhost:8000"
    echo "API Docs: http://localhost:8000/docs"
    echo "Monitoring: http://localhost:3002"
    echo ""
}

# Script execution
case "$1" in
    "deploy")
        main
        ;;
    "health")
        check_service_health
        ;;
    "backup")
        backup_current_deployment
        ;;
    "optimize")
        optimize_production
        ;;
    "test")
        run_post_deployment_tests
        ;;
    *)
        echo "Usage: $0 {deploy|health|backup|optimize|test}"
        echo "  deploy   - Full production deployment"
        echo "  health   - Check service health"
        echo "  backup   - Create backup of current deployment"
        echo "  optimize - Optimize production settings"
        echo "  test     - Run post-deployment tests"
        exit 1
        ;;
esac


