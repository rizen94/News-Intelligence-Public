#!/bin/bash

# News Intelligence System v3.0 - Port Conflict Resolution Script
# Fixes all port conflicts and standardizes port usage

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Port Configuration
REACT_PORT=3000
HTML_FALLBACK_PORT=3001
GRAFANA_PORT=3002
# CODING_ASSISTANT_PORT=3003  # REMOVED - Project scrapped
OLLAMA_PORT=11434

# Create logs directory
mkdir -p logs

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a logs/port-fix.log
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a logs/port-fix.log
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a logs/port-fix.log
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a logs/port-fix.log
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --fix-all       Fix all port conflicts"
    echo "  --check-only    Check for conflicts without fixing"
    echo "  --react         Fix React port conflicts only"
    echo "  --grafana       Fix Grafana port conflicts only"
    echo "  --ollama        Fix Ollama port conflicts only"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --check-only    # Check for conflicts"
    echo "  $0 --fix-all       # Fix all conflicts"
    echo "  $0 --react         # Fix React conflicts only"
}

# Check for port conflicts
check_conflicts() {
    log "Checking for port conflicts..."
    
    local conflicts_found=false
    
    # Check for port 3000 conflicts
    if grep -r "localhost:3002" . --include="*.sh" --include="*.js" --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" > /dev/null 2>&1; then
        local react_count=$(grep -r "localhost:3002" . --include="*.sh" --include="*.js" --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | wc -l)
        local grafana_count=$(grep -r "localhost:3002" . --include="*.sh" --include="*.js" --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -i grafana | wc -l)
        
        if [ "$react_count" -gt 0 ] && [ "$grafana_count" -gt 0 ]; then
            error "Port 3000 conflict: React ($react_count) + Grafana ($grafana_count)"
            conflicts_found=true
        else
            success "Port 3000: No conflicts detected"
        fi
    fi
    
    # Check for port 3001 conflicts
    if grep -r "localhost:3002" . --include="*.sh" --include="*.js" --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" > /dev/null 2>&1; then
        local html_count=$(grep -r "localhost:3002" . --include="*.sh" --include="*.js" --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -i html | wc -l)
        local grafana_count=$(grep -r "localhost:3002" . --include="*.sh" --include="*.js" --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -i grafana | wc -l)
        
        if [ "$html_count" -gt 0 ] && [ "$grafana_count" -gt 0 ]; then
            error "Port 3001 conflict: HTML Fallback ($html_count) + Grafana ($grafana_count)"
            conflicts_found=true
        else
            success "Port 3001: No conflicts detected"
        fi
    fi
    
    # Check for Ollama port inconsistencies
    local localhost_count=$(grep -r "localhost:11434" . --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | wc -l)
    local custom_ip_count=$(grep -r "192.168.93.92:11434" . --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | wc -l)
    
    if [ "$localhost_count" -gt 0 ] && [ "$custom_ip_count" -gt 0 ]; then
        warning "Ollama port inconsistency: localhost ($localhost_count) + custom IP ($custom_ip_count)"
        conflicts_found=true
    else
        success "Ollama ports: Consistent usage"
    fi
    
    if [ "$conflicts_found" = true ]; then
        error "Port conflicts detected!"
        return 1
    else
        success "No port conflicts detected"
        return 0
    fi
}

# Fix React port conflicts
fix_react_conflicts() {
    log "Fixing React port conflicts..."
    
    # Update web/start-frontend.sh
    if [ -f "web/start-frontend.sh" ]; then
        sed -i "s/localhost:3002/localhost:$REACT_PORT/g" web/start-frontend.sh
        success "Updated web/start-frontend.sh"
    fi
    
    # Update web/build-react.sh
    if [ -f "web/build-react.sh" ]; then
        sed -i "s/localhost:3002/localhost:$REACT_PORT/g" web/build-react.sh
        success "Updated web/build-react.sh"
    fi
    
    # Update any other React references
    find . -name "*.sh" -o -name "*.js" -o -name "*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:3002" | while read file; do
        if [[ "$file" != *"web/start-frontend.sh" ]] && [[ "$file" != *"web/build-react.sh" ]]; then
            sed -i "s/localhost:3002/localhost:$REACT_PORT/g" "$file"
            log "Updated $file"
        fi
    done
    
    success "React port conflicts fixed"
}

# Fix Grafana port conflicts
fix_grafana_conflicts() {
    log "Fixing Grafana port conflicts..."
    
    # Update scripts that reference Grafana on port 3000
    find . -name "*.sh" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:3002" | while read file; do
        if grep -q -i "grafana" "$file"; then
            sed -i "s/localhost:3002/localhost:$GRAFANA_PORT/g" "$file"
            log "Updated Grafana port in $file"
        fi
    done
    
    # Update scripts that reference Grafana on port 3001
    find . -name "*.sh" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:3002" | while read file; do
        if grep -q -i "grafana" "$file"; then
            sed -i "s/localhost:3002/localhost:$GRAFANA_PORT/g" "$file"
            log "Updated Grafana port in $file"
        fi
    done
    
    success "Grafana port conflicts fixed"
}

# Fix Ollama port inconsistencies
fix_ollama_conflicts() {
    log "Fixing Ollama port inconsistencies..."
    
    # Standardize all Ollama URLs to use localhost:11434
    find . -name "*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "192.168.93.92:11434" | while read file; do
        sed -i "s/192.168.93.92:11434/localhost:11434/g" "$file"
        log "Updated Ollama URL in $file"
    done
    
    # Update any other custom IP references
    find . -name "*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "host.docker.internal:11434" | while read file; do
        sed -i "s/host.docker.internal:11434/localhost:11434/g" "$file"
        log "Updated Ollama URL in $file"
    done
    
    success "Ollama port inconsistencies fixed"
}

# Fix HTML fallback port conflicts
fix_html_conflicts() {
    log "Fixing HTML fallback port conflicts..."
    
    # Update web/start-frontend.sh
    if [ -f "web/start-frontend.sh" ]; then
        sed -i "s/localhost:3002/localhost:$HTML_FALLBACK_PORT/g" web/start-frontend.sh
        success "Updated HTML fallback port in web/start-frontend.sh"
    fi
    
    # Update web/build-react.sh
    if [ -f "web/build-react.sh" ]; then
        sed -i "s/localhost:3002/localhost:$HTML_FALLBACK_PORT/g" web/build-react.sh
        success "Updated HTML fallback port in web/build-react.sh"
    fi
    
    success "HTML fallback port conflicts fixed"
}

# Fix coding assistant port conflicts - REMOVED (Project scrapped)
# fix_coding_assistant_conflicts() {
#     log "Fixing coding assistant port conflicts..."
#     success "Coding assistant port conflicts fixed"
# }

# Create port configuration file
create_port_config() {
    log "Creating port configuration file..."
    
    cat > .env.ports << EOF
# News Intelligence System v3.0 - Port Configuration
# This file defines all port mappings to prevent conflicts

# Development Ports
REACT_PORT=$REACT_PORT
HTML_FALLBACK_PORT=$HTML_FALLBACK_PORT
GRAFANA_PORT=$GRAFANA_PORT
# CODING_ASSISTANT_PORT=$CODING_ASSISTANT_PORT  # REMOVED - Project scrapped

# External Service Ports
OLLAMA_PORT=$OLLAMA_PORT

# Production Ports (Docker)
POSTGRES_PORT=5432
REDIS_PORT=6379
API_PORT=8000
FRONTEND_PORT=80
PROMETHEUS_PORT=9090
EOF
    
    success "Port configuration file created: .env.ports"
}

# Fix all port conflicts
fix_all_conflicts() {
    log "Fixing all port conflicts..."
    
    fix_react_conflicts
    fix_grafana_conflicts
    fix_ollama_conflicts
    fix_html_conflicts
    # fix_coding_assistant_conflicts  # REMOVED - Project scrapped
    create_port_config
    
    success "All port conflicts fixed!"
}

# Main execution
main() {
    case "${1:-}" in
        --fix-all)
            fix_all_conflicts
            ;;
        --check-only)
            check_conflicts
            ;;
        --react)
            fix_react_conflicts
            ;;
        --grafana)
            fix_grafana_conflicts
            ;;
        --ollama)
            fix_ollama_conflicts
            ;;
        --help)
            show_usage
            ;;
        *)
            error "Invalid option: ${1:-}"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
