#!/bin/bash

# Optimized Build Script for News Intelligence System v3.0
# Features: Parallel builds, layer caching, performance monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="news-intelligence-system"
BUILD_START_TIME=$(date +%s)
LOG_FILE="build-optimization.log"

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

# Cleanup function
cleanup() {
    log "Cleaning up temporary files..."
    docker system prune -f --volumes
    success "Cleanup completed"
}

# Build performance monitoring
monitor_build() {
    local service=$1
    local start_time=$2
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo "Build time for $service: ${duration}s" >> $LOG_FILE
    
    # Monitor resource usage
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" >> $LOG_FILE
}

# Pre-build optimization
pre_build_optimization() {
    log "Starting pre-build optimization..."
    
    # Clean up old images and containers
    log "Cleaning up old Docker resources..."
    docker system prune -f --volumes
    
    # Enable BuildKit for better caching
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # Create build cache directories
    mkdir -p .docker-cache/{backend,frontend}
    
    success "Pre-build optimization completed"
}

# Build backend with optimization
build_backend() {
    log "Building backend with optimization..."
    local start_time=$(date +%s)
    
    # Build with cache
    docker build \
        --file api/Dockerfile.optimized \
        --tag newsintelligence-backend:latest \
        --tag newsintelligence-backend:$(date +%Y%m%d-%H%M%S) \
        --cache-from newsintelligence-backend:latest \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --progress=plain \
        . 2>&1 | tee -a $LOG_FILE
    
    if [ $? -eq 0 ]; then
        success "Backend build completed"
        monitor_build "backend" $start_time
    else
        error "Backend build failed"
    fi
}

# Build frontend with optimization
build_frontend() {
    log "Building frontend with optimization..."
    local start_time=$(date +%s)
    
    # Build with cache
    docker build \
        --file web/Dockerfile.optimized \
        --tag newsintelligence-frontend:latest \
        --tag newsintelligence-frontend:$(date +%Y%m%d-%H%M%S) \
        --cache-from newsintelligence-frontend:latest \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --build-arg NODE_ENV=production \
        --progress=plain \
        ./web 2>&1 | tee -a $LOG_FILE
    
    if [ $? -eq 0 ]; then
        success "Frontend build completed"
        monitor_build "frontend" $start_time
    else
        error "Frontend build failed"
    fi
}

# Parallel build function
parallel_build() {
    log "Starting parallel build process..."
    
    # Start backend build in background
    build_backend &
    BACKEND_PID=$!
    
    # Start frontend build in background
    build_frontend &
    FRONTEND_PID=$!
    
    # Wait for both builds to complete
    wait $BACKEND_PID
    BACKEND_EXIT_CODE=$?
    
    wait $FRONTEND_PID
    FRONTEND_EXIT_CODE=$?
    
    # Check results
    if [ $BACKEND_EXIT_CODE -eq 0 ] && [ $FRONTEND_EXIT_CODE -eq 0 ]; then
        success "Parallel build completed successfully"
    else
        error "Parallel build failed - Backend: $BACKEND_EXIT_CODE, Frontend: $FRONTEND_EXIT_CODE"
    fi
}

# Build monitoring and reporting
build_monitoring() {
    local total_time=$(($(date +%s) - BUILD_START_TIME))
    
    log "=== BUILD PERFORMANCE REPORT ==="
    echo "Total build time: ${total_time}s" | tee -a $LOG_FILE
    echo "Build completed at: $(date)" | tee -a $LOG_FILE
    
    # Docker image sizes
    echo "=== IMAGE SIZES ===" | tee -a $LOG_FILE
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep newsintelligence | tee -a $LOG_FILE
    
    # System resources
    echo "=== SYSTEM RESOURCES ===" | tee -a $LOG_FILE
    docker system df | tee -a $LOG_FILE
    
    success "Build monitoring completed"
}

# Main build function
main() {
    log "Starting optimized build for $PROJECT_NAME v3.0"
    
    # Pre-build optimization
    pre_build_optimization
    
    # Choose build strategy
    if [ "$1" = "parallel" ]; then
        parallel_build
    else
        build_backend
        build_frontend
    fi
    
    # Build monitoring
    build_monitoring
    
    # Cleanup
    cleanup
    
    success "Build process completed successfully!"
    log "Build log saved to: $LOG_FILE"
}

# Script execution
case "$1" in
    "parallel")
        main "parallel"
        ;;
    "sequential")
        main "sequential"
        ;;
    "clean")
        cleanup
        ;;
    *)
        echo "Usage: $0 {parallel|sequential|clean}"
        echo "  parallel   - Build backend and frontend in parallel"
        echo "  sequential - Build backend then frontend"
        echo "  clean      - Clean up Docker resources"
        exit 1
        ;;
esac


