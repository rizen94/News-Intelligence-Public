#!/bin/bash

# News Intelligence System v3.0 - Production Stop Script
# This script safely stops the production system

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
LOG_FILE="logs/production-stop.log"

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

# Stop services gracefully
stop_services() {
    log "Stopping production services..."
    
    # Stop with graceful shutdown
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --timeout 30
    
    success "Services stopped"
}

# Clean up orphaned containers
cleanup() {
    log "Cleaning up orphaned containers..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --remove-orphans 2>/dev/null || true
    success "Cleanup completed"
}

# Show final status
show_status() {
    log "Final Status:"
    echo "============="
    
    # Check if any containers are still running
    local running_containers=$(docker ps --filter "name=$PROJECT_NAME" --format "{{.Names}}" | wc -l)
    
    if [ $running_containers -eq 0 ]; then
        success "All containers stopped"
    else
        warning "$running_containers containers still running"
        docker ps --filter "name=$PROJECT_NAME" --format "table {{.Names}}\t{{.Status}}"
    fi
}

# Main execution
main() {
    log "Stopping News Intelligence System v3.0 Production"
    log "=================================================="
    
    stop_services
    cleanup
    show_status
    
    success "Production system stopped successfully!"
}

# Run main function
main "$@"
