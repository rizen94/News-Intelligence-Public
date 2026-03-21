#!/bin/bash

# News Intelligence System v3.0 - Port Verification Script
# Verifies that all port mappings are conflict-free

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check port 3000 usage
check_port_3000() {
    log "Checking port 3000 usage..."
    
    local react_count=$(grep -r "localhost:3000" . --include="*.sh" --include="*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -v "fix-port-conflicts.sh" | grep -v "port-config-final.sh" | wc -l)
    local grafana_count=$(grep -r "localhost:3000" . --include="*.sh" --include="*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -i grafana | wc -l)
    
    if [ "$grafana_count" -gt 0 ]; then
        error "Port 3000: Grafana still using this port ($grafana_count references)"
        return 1
    else
        success "Port 3000: React only ($react_count references)"
        return 0
    fi
}

# Check port 3001 usage
check_port_3001() {
    log "Checking port 3001 usage..."
    
    local html_count=$(grep -r "localhost:3001" . --include="*.sh" --include="*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -v "fix-port-conflicts.sh" | grep -v "port-config-final.sh" | grep -v -i grafana | wc -l)
    local grafana_count=$(grep -r "localhost:3001" . --include="*.sh" --include="*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -i grafana | wc -l)
    
    if [ "$grafana_count" -gt 0 ]; then
        error "Port 3001: Grafana still using this port ($grafana_count references)"
        return 1
    else
        success "Port 3001: HTML Fallback only ($html_count references)"
        return 0
    fi
}

# Check port 3002 usage
check_port_3002() {
    log "Checking port 3002 usage..."
    
    local grafana_count=$(grep -r "localhost:3002" . --include="*.sh" --include="*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -v "fix-port-conflicts.sh" | grep -v "port-config-final.sh" | grep -i grafana | wc -l)
    local other_count=$(grep -r "localhost:3002" . --include="*.sh" --include="*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | grep -v "fix-port-conflicts.sh" | grep -v "port-config-final.sh" | grep -v -i grafana | wc -l)
    
    if [ "$other_count" -gt 0 ]; then
        error "Port 3002: Non-Grafana services using this port ($other_count references)"
        return 1
    else
        success "Port 3002: Grafana only ($grafana_count references)"
        return 0
    fi
}

# Check port 3003 usage - REMOVED (Project scrapped)
# check_port_3003() {
#     log "Checking port 3003 usage..."
#     success "Port 3003: Available (Coding Assistant project scrapped)"
#     return 0
# }

# Check Ollama consistency
check_ollama_consistency() {
    log "Checking Ollama port consistency..."
    
    local localhost_count=$(grep -r "localhost:11434" . --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | wc -l)
    local custom_ip_count=$(grep -r "192.168.93.92:11434" . --include="*.py" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | wc -l)
    
    if [ "$custom_ip_count" -gt 0 ]; then
        warning "Ollama: Still using custom IP ($custom_ip_count references)"
        return 1
    else
        success "Ollama: Consistent localhost usage ($localhost_count references)"
        return 0
    fi
}

# Check Docker compose ports
check_docker_ports() {
    log "Checking Docker compose ports..."
    
    local ports=("5432:5432" "6379:6379" "8000:8000" "80:80" "9090:9090")
    local all_found=true
    
    for port in "${ports[@]}"; do
        if grep -A 1 "ports:" docker-compose.yml | grep -q "\"$port\""; then
            success "Docker port $port: Found"
        else
            error "Docker port $port: Missing"
            all_found=false
        fi
    done
    
    if [ "$all_found" = true ]; then
        success "All Docker ports configured"
        return 0
    else
        error "Some Docker ports missing"
        return 1
    fi
}

# Run all checks
run_verification() {
    log "Starting port verification..."
    echo "=============================="
    
    local all_passed=true
    
    check_port_3000 || all_passed=false
    echo ""
    
    check_port_3001 || all_passed=false
    echo ""
    
    check_port_3002 || all_passed=false
    echo ""
    
    # check_port_3003 || all_passed=false  # REMOVED - Project scrapped
    echo ""
    
    check_ollama_consistency || all_passed=false
    echo ""
    
    check_docker_ports || all_passed=false
    echo ""
    
    if [ "$all_passed" = true ]; then
        success "🎉 All port mappings are conflict-free!"
        success "✅ React: 3000"
        success "✅ HTML Fallback: 3001"
        success "✅ Grafana: 3002"
        # success "✅ Coding Assistant: 3003"  # REMOVED - Project scrapped
        success "✅ Docker ports: Configured"
        success "✅ Ollama: Consistent"
    else
        error "❌ Port conflicts detected"
        error "Please fix the issues above"
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
            echo "This script verifies that all port mappings"
            echo "are conflict-free and properly configured."
            ;;
        *)
            run_verification
            ;;
    esac
}

# Run main function
main "$@"
