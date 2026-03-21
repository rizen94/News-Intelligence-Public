#!/bin/bash

# News Intelligence System v3.0 - Final Port Configuration
# Clean, conflict-free port allocation

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

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Final Port Allocation
REACT_PORT=3000
HTML_FALLBACK_PORT=3001
GRAFANA_PORT=3002
# CODING_ASSISTANT_PORT=3003  # REMOVED - Project scrapped

log "Applying final port configuration..."

# Fix React port (3000)
log "Setting React port to 3000..."
find . -name "*.sh" -o -name "*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:3000" | while read file; do
    if [[ "$file" != *"fix-port-conflicts.sh" ]] && [[ "$file" != *"port-config-final.sh" ]]; then
        if ! grep -q -i "grafana" "$file"; then
            sed -i "s/localhost:3000/localhost:$REACT_PORT/g" "$file"
            log "Updated React port in $file"
        fi
    fi
done

# Fix HTML Fallback port (3001)
log "Setting HTML Fallback port to 3001..."
find . -name "*.sh" -o -name "*.js" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:3001" | while read file; do
    if [[ "$file" != *"fix-port-conflicts.sh" ]] && [[ "$file" != *"port-config-final.sh" ]]; then
        if ! grep -q -i "grafana" "$file"; then
            sed -i "s/localhost:3001/localhost:$HTML_FALLBACK_PORT/g" "$file"
            log "Updated HTML Fallback port in $file"
        fi
    fi
done

# Fix Grafana port (3002)
log "Setting Grafana port to 3002..."
find . -name "*.sh" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:300[01]" | while read file; do
    if [[ "$file" != *"fix-port-conflicts.sh" ]] && [[ "$file" != *"port-config-final.sh" ]]; then
        if grep -q -i "grafana" "$file"; then
            sed -i "s/localhost:3000/localhost:$GRAFANA_PORT/g" "$file"
            sed -i "s/localhost:3001/localhost:$GRAFANA_PORT/g" "$file"
            log "Updated Grafana port in $file"
        fi
    fi
done

# Fix Coding Assistant port (3003) - REMOVED (Project scrapped)
# log "Setting Coding Assistant port to 3003..."
# find . -name "*.sh" | grep -v node_modules | grep -v archive | grep -v backups | grep -v ".venv" | xargs grep -l "localhost:3002" | while read file; do
#     if [[ "$file" != *"fix-port-conflicts.sh" ]] && [[ "$file" != *"port-config-final.sh" ]]; then
#         if ! grep -q -i "grafana" "$file"; then
#             sed -i "s/localhost:3002/localhost:$CODING_ASSISTANT_PORT/g" "$file"
#             log "Updated Coding Assistant port in $file"
#         fi
#     fi
# done

# Create final port configuration
cat > .env.ports << EOF
# News Intelligence System v3.0 - Final Port Configuration
# CONFLICT-FREE PORT ALLOCATION

# Development Ports
REACT_PORT=$REACT_PORT                    # React Development Server
HTML_FALLBACK_PORT=$HTML_FALLBACK_PORT    # HTML Fallback Interface
GRAFANA_PORT=$GRAFANA_PORT                # Grafana Monitoring Dashboard
CODING_ASSISTANT_PORT=$CODING_ASSISTANT_PORT  # Coding Assistant

# External Service Ports
OLLAMA_PORT=11434                         # Ollama AI Service

# Production Ports (Docker)
POSTGRES_PORT=5432                        # PostgreSQL Database
REDIS_PORT=6379                          # Redis Cache
API_PORT=8000                            # FastAPI Backend
FRONTEND_PORT=80                         # Nginx Frontend
PROMETHEUS_PORT=9090                     # Prometheus Monitoring

# Monitoring Ports
POSTGRES_EXPORTER_PORT=9187              # PostgreSQL Exporter
NODE_EXPORTER_PORT=9100                  # Node Exporter
EOF

success "Final port configuration applied!"
success "Port allocation:"
success "  React: $REACT_PORT"
success "  HTML Fallback: $HTML_FALLBACK_PORT"
success "  Grafana: $GRAFANA_PORT"
# success "  Coding Assistant: $CODING_ASSISTANT_PORT"  # REMOVED - Project scrapped
success "Configuration saved to: .env.ports"
