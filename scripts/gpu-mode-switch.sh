#!/bin/bash

# GPU Mode Switch for News Intelligence System
# Switches between Development (Coding Assistant GPU) and Production (News App GPU) modes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
NEWS_APP_DIR="/home/pete/Documents/Projects/News Intelligence"
CODING_ASSISTANT_DIR="/home/pete/Documents/Projects/Coding Assistant"
BACKUP_DIR="$NEWS_APP_DIR/backups/gpu-configs"

print_header() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║                    GPU MODE SWITCH                        ║${NC}"
    echo -e "${PURPLE}║              News Intelligence System v2.9.0              ║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
}

# Backup current configurations
backup_configs() {
    print_status "Creating backup of current configurations..."
    
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_path="$BACKUP_DIR/config_backup_$timestamp"
    
    mkdir -p "$backup_path"
    
    # Backup News Intelligence docker compose.yml
    if [ -f "$NEWS_APP_DIR/docker compose.yml" ]; then
        cp "$NEWS_APP_DIR/docker compose.yml" "$backup_path/news-docker compose.yml"
    fi
    
    # Backup Coding Assistant docker compose.yml
    if [ -f "$CODING_ASSISTANT_DIR/docker compose.yml" ]; then
        cp "$CODING_ASSISTANT_DIR/docker compose.yml" "$backup_path/coding-docker compose.yml"
    fi
    
    print_success "Configurations backed up to $backup_path"
}

# Switch to Development Mode (Coding Assistant gets GPU)
switch_to_development() {
    print_status "Switching to DEVELOPMENT mode..."
    print_status "Coding Assistant will get GPU priority for fast development"
    
    # Stop both systems
    print_status "Stopping both systems..."
    cd "$NEWS_APP_DIR"
    docker compose down 2>/dev/null || true
    
    cd "$CODING_ASSISTANT_DIR"
    docker compose down 2>/dev/null || true
    
    # Configure News Intelligence for CPU/swap mode
    print_status "Configuring News Intelligence for CPU/swap mode..."
    cd "$NEWS_APP_DIR"
    
    # Create CPU-optimized docker compose override
    cat > docker-compose.override.yml << 'EOF'
# Development Mode Override - CPU/Swap Priority
services:
  news-system-api:
    environment:
      - CUDA_VISIBLE_DEVICES=""  # Disable GPU for News Intelligence
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G
    # Remove GPU requirements
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  # Disable GPU monitoring in development
  nvidia-gpu-exporter:
    profiles:
      - disabled
EOF
    
    # Configure Coding Assistant for GPU mode
    print_status "Configuring Coding Assistant for GPU mode..."
    cd "$CODING_ASSISTANT_DIR"
    
    # Ensure GPU is enabled
    sed -i 's/CUDA_VISIBLE_DEVICES=""/CUDA_VISIBLE_DEVICES=0/' docker-compose.yml
    
    # Start systems
    print_status "Starting systems in development mode..."
    
    # Start News Intelligence (CPU mode)
    cd "$NEWS_APP_DIR"
    docker compose up -d
    
    # Start Coding Assistant (GPU mode)
    cd "$CODING_ASSISTANT_DIR"
    docker compose up -d
    
    print_success "Development mode activated!"
    print_status "Coding Assistant: GPU accelerated (fast responses)"
    print_status "News Intelligence: CPU/swap mode (slower but functional)"
    print_status "Access Coding Assistant: http://localhost:3002"
    print_status "Access News Intelligence: https://newsintel.local"
}

# Switch to Production Mode (News Intelligence gets GPU)
switch_to_production() {
    print_status "Switching to PRODUCTION mode..."
    print_status "News Intelligence will get GPU priority for full performance"
    
    # Stop both systems
    print_status "Stopping both systems..."
    cd "$NEWS_APP_DIR"
    docker compose down 2>/dev/null || true
    
    cd "$CODING_ASSISTANT_DIR"
    docker compose down 2>/dev/null || true
    
    # Remove development overrides
    print_status "Removing development overrides..."
    cd "$NEWS_APP_DIR"
    rm -f docker-compose.override.yml
    
    # Configure Coding Assistant for CPU mode
    print_status "Configuring Coding Assistant for CPU mode..."
    cd "$CODING_ASSISTANT_DIR"
    
    # Disable GPU for coding assistant
    sed -i 's/CUDA_VISIBLE_DEVICES=0/CUDA_VISIBLE_DEVICES=""/' docker-compose.yml
    
    # Comment out GPU resources
    sed -i 's/^    deploy:/    # deploy:/' docker-compose.yml
    sed -i 's/^      resources:/    #   resources:/' docker-compose.yml
    sed -i 's/^        reservations:/    #     reservations:/' docker-compose.yml
    sed -i 's/^          devices:/    #       devices:/' docker-compose.yml
    sed -i 's/^            - driver: nvidia/    #         - driver: nvidia/' docker-compose.yml
    sed -i 's/^              count: 1/    #           count: 1/' docker-compose.yml
    sed -i 's/^              capabilities: \[gpu\]/    #           capabilities: [gpu]/' docker-compose.yml
    
    # Start systems
    print_status "Starting systems in production mode..."
    
    # Start News Intelligence (GPU mode)
    cd "$NEWS_APP_DIR"
    docker compose up -d
    
    # Start Coding Assistant (CPU mode)
    cd "$CODING_ASSISTANT_DIR"
    docker compose up -d
    
    print_success "Production mode activated!"
    print_status "News Intelligence: GPU accelerated (full performance)"
    print_status "Coding Assistant: CPU mode (slower but functional)"
    print_status "Access News Intelligence: https://newsintel.local"
    print_status "Access Coding Assistant: http://localhost:3002"
}

# Show current status
show_status() {
    print_status "Current GPU Mode Status:"
    echo ""
    
    # Check News Intelligence GPU config
    cd "$NEWS_APP_DIR"
    if [ -f "docker-compose.override.yml" ]; then
        echo -e "${YELLOW}News Intelligence:${NC} CPU/Swap mode (Development)"
    else
        echo -e "${GREEN}News Intelligence:${NC} GPU mode (Production)"
    fi
    
    # Check Coding Assistant GPU config
    cd "$CODING_ASSISTANT_DIR"
    if grep -q 'CUDA_VISIBLE_DEVICES=0' docker compose.yml; then
        echo -e "${GREEN}Coding Assistant:${NC} GPU mode (Development)"
    else
        echo -e "${YELLOW}Coding Assistant:${NC} CPU mode (Production)"
    fi
    
    echo ""
    print_status "Container Status:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(news-system|coding-assistant)"
    
    echo ""
    print_status "GPU Usage:"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo "No GPU detected"
}

# Main function
main() {
    print_header
    
    case "${1:-status}" in
        "development"|"dev")
            create_backup_dir
            backup_configs
            switch_to_development
            ;;
        "production"|"prod")
            create_backup_dir
            backup_configs
            switch_to_production
            ;;
        "status")
            show_status
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 {development|production|status|help}"
            echo ""
            echo "Commands:"
            echo "  development, dev  - Switch to development mode (Coding Assistant gets GPU)"
            echo "  production, prod  - Switch to production mode (News Intelligence gets GPU)"
            echo "  status           - Show current mode and system status"
            echo "  help             - Show this help message"
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
