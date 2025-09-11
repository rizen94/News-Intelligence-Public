#!/bin/bash

# News Intelligence System v3.0 - Docker Alignment Verification Script
# Verifies that all Docker configurations are aligned with the manage script

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
LOG_FILE="logs/alignment-verification.log"

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

# Verify compose file exists
verify_compose_file() {
    log "Verifying main compose file..."
    
    if [ -f "$COMPOSE_FILE" ]; then
        success "Main compose file exists: $COMPOSE_FILE"
    else
        error "Main compose file not found: $COMPOSE_FILE"
        return 1
    fi
}

# Verify service names alignment
verify_service_names() {
    log "Verifying service names alignment..."
    
    local compose_services=$(grep "container_name:" "$COMPOSE_FILE" | sed 's/.*container_name: //' | sort)
    local expected_services=("news-intelligence-postgres" "news-intelligence-redis" "news-intelligence-api" "news-intelligence-frontend" "news-intelligence-monitoring")
    
    local all_aligned=true
    
    for service in "${expected_services[@]}"; do
        if echo "$compose_services" | grep -q "$service"; then
            success "Service name aligned: $service"
        else
            error "Service name misaligned: $service"
            all_aligned=false
        fi
    done
    
    if [ "$all_aligned" = true ]; then
        success "All service names are aligned"
    else
        error "Service names are not aligned"
        return 1
    fi
}

# Verify database name alignment
verify_database_name() {
    log "Verifying database name alignment..."
    
    local compose_db=$(grep "POSTGRES_DB:" "$COMPOSE_FILE" | sed 's/.*POSTGRES_DB: //')
    local expected_db="news_intelligence"
    
    if [ "$compose_db" = "$expected_db" ]; then
        success "Database name aligned: $compose_db"
    else
        error "Database name misaligned: expected $expected_db, found $compose_db"
        return 1
    fi
}

# Verify port mappings alignment
verify_port_mappings() {
    log "Verifying port mappings alignment..."
    
    local expected_ports=("5432:5432" "6379:6379" "8000:8000" "80:80" "9090:9090")
    local all_aligned=true
    
    for port in "${expected_ports[@]}"; do
        if grep -A 1 "ports:" "$COMPOSE_FILE" | grep -q "\"$port\""; then
            success "Port mapping aligned: $port"
        else
            error "Port mapping misaligned: $port"
            all_aligned=false
        fi
    done
    
    if [ "$all_aligned" = true ]; then
        success "All port mappings are aligned"
    else
        error "Port mappings are not aligned"
        return 1
    fi
}

# Verify docker-manage.sh script alignment
verify_manage_script() {
    log "Verifying docker-manage.sh script alignment..."
    
    if [ -f "scripts/docker-manage.sh" ]; then
        success "Docker manage script exists"
    else
        error "Docker manage script not found"
        return 1
    fi
    
    # Check if script uses correct project name
    if grep -q "PROJECT_NAME=\"$PROJECT_NAME\"" scripts/docker-manage.sh; then
        success "Docker manage script uses correct project name"
    else
        error "Docker manage script project name misaligned"
        return 1
    fi
    
    # Check if script uses correct database name
    if grep -q "news_intelligence" scripts/docker-manage.sh; then
        success "Docker manage script uses correct database name"
    else
        error "Docker manage script database name misaligned"
        return 1
    fi
}

# Verify no conflicting files exist
verify_no_conflicts() {
    log "Verifying no conflicting files exist..."
    
    local conflicting_files=(
        "configs/docker-compose.backend.yml"
        "configs/docker-compose.frontend.yml"
        "configs/docker-compose.monitoring.yml"
        "configs/docker-compose.override.yml"
        "api/Dockerfile.optimized"
        "web/Dockerfile"
    )
    
    local conflicts_found=false
    
    for file in "${conflicting_files[@]}"; do
        if [ -f "$file" ]; then
            error "Conflicting file still exists: $file"
            conflicts_found=true
        else
            success "No conflict: $file (archived or removed)"
        fi
    done
    
    if [ "$conflicts_found" = false ]; then
        success "No conflicting files found"
    else
        error "Conflicting files still exist"
        return 1
    fi
}

# Verify Dockerfile alignment
verify_dockerfiles() {
    log "Verifying Dockerfile alignment..."
    
    # Check main API Dockerfile
    if [ -f "api/Dockerfile.production" ]; then
        success "Main API Dockerfile exists: api/Dockerfile.production"
    else
        error "Main API Dockerfile not found"
        return 1
    fi
    
    # Check main frontend Dockerfile
    if [ -f "Dockerfile.frontend" ]; then
        success "Main frontend Dockerfile exists: Dockerfile.frontend"
    else
        error "Main frontend Dockerfile not found"
        return 1
    fi
    
    # Check web Dockerfile
    if [ -f "web/Dockerfile.frontend" ]; then
        success "Web Dockerfile exists: web/Dockerfile.frontend"
    else
        warning "Web Dockerfile not found (may be using main Dockerfile.frontend)"
    fi
}

# Run all verification checks
run_verification() {
    log "Starting Docker alignment verification..."
    echo "========================================"
    
    local all_passed=true
    
    verify_compose_file || all_passed=false
    echo ""
    
    verify_service_names || all_passed=false
    echo ""
    
    verify_database_name || all_passed=false
    echo ""
    
    verify_port_mappings || all_passed=false
    echo ""
    
    verify_manage_script || all_passed=false
    echo ""
    
    verify_no_conflicts || all_passed=false
    echo ""
    
    verify_dockerfiles || all_passed=false
    echo ""
    
    if [ "$all_passed" = true ]; then
        success "🎉 All Docker configurations are properly aligned!"
        success "✅ Docker-manage.sh script is fully compatible"
        success "✅ No conflicting files found"
        success "✅ Ready for production deployment"
    else
        error "❌ Docker alignment verification failed"
        error "Please fix the issues above before proceeding"
        return 1
    fi
}

# Main execution
main() {
    case "${1:-}" in
        --help)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  --help    Show this help message"
            echo ""
            echo "This script verifies that all Docker configurations"
            echo "are properly aligned with the docker-manage.sh script."
            ;;
        *)
            run_verification
            ;;
    esac
}

# Run main function
main "$@"
