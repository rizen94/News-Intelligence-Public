#!/bin/bash

# News Intelligence System v3.0 - Docker Management Script
# Unified Docker operations for microservice architecture

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
LOG_FILE="logs/docker-manage.log"

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

# Show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start           Start all services"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services"
    echo "  status          Show service status"
    echo "  logs            Show service logs"
    echo "  clean           Clean up containers and images"
    echo "  build           Build all services"
    echo "  pull            Pull latest images"
    echo "  health          Check service health"
    echo "  shell           Open shell in service container"
    echo "  backup          Backup service data"
    echo "  restore         Restore service data"
    echo ""
    echo "Options:"
    echo "  --service NAME  Target specific service"
    echo "  --follow        Follow logs (for logs command)"
    echo "  --tail N        Show last N lines (for logs command)"
    echo "  --force         Force operation (for clean command)"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start all services"
    echo "  $0 logs --follow            # Follow all logs"
    echo "  $0 logs --service api       # Show API logs"
    echo "  $0 clean --force            # Force clean all"
    echo "  $0 shell --service postgres # Open postgres shell"
}

# Check Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Start services
start_services() {
    local service="${1:-}"
    log "Starting services${service:+: $service}..."
    
    if [ -n "$service" ]; then
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d "$service"
    else
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
    fi
    
    success "Services started"
}

# Stop services
stop_services() {
    local service="${1:-}"
    log "Stopping services${service:+: $service}..."
    
    if [ -n "$service" ]; then
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" stop "$service"
    else
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
    fi
    
    success "Services stopped"
}

# Restart services
restart_services() {
    local service="${1:-}"
    log "Restarting services${service:+: $service}..."
    
    if [ -n "$service" ]; then
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" restart "$service"
    else
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
    fi
    
    success "Services restarted"
}

# Show service status
show_status() {
    log "Service Status:"
    echo "=================="
    
    # Show running containers
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
    
    echo ""
    log "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
}

# Show service logs
show_logs() {
    local service="${1:-}"
    local follow="${2:-}"
    local tail_lines="${3:-100}"
    
    log "Showing logs${service:+ for $service}..."
    
    if [ "$follow" = "true" ]; then
        if [ -n "$service" ]; then
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f --tail="$tail_lines" "$service"
        else
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f --tail="$tail_lines"
        fi
    else
        if [ -n "$service" ]; then
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs --tail="$tail_lines" "$service"
        else
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs --tail="$tail_lines"
        fi
    fi
}

# Clean up containers and images
clean_containers() {
    local force="${1:-false}"
    
    log "Cleaning up Docker resources..."
    
    if [ "$force" = "true" ]; then
        warning "Force cleaning - this will remove ALL containers and images!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker system prune -a --volumes -f
            success "Force clean completed"
        else
            log "Clean cancelled"
        fi
    else
        # Safe clean - only remove unused resources
        docker system prune -f
        docker volume prune -f
        success "Safe clean completed"
    fi
}

# Build services
build_services() {
    local service="${1:-}"
    log "Building services${service:+: $service}..."
    
    if [ -n "$service" ]; then
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build "$service"
    else
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build
    fi
    
    success "Services built"
}

# Pull latest images
pull_images() {
    log "Pulling latest images..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" pull
    success "Images pulled"
}

# Check service health
check_health() {
    log "Checking service health..."
    
    local healthy_count=0
    local total_count=0
    
    # Check PostgreSQL
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        success "PostgreSQL: Healthy"
        ((healthy_count++))
    else
        error "PostgreSQL: Unhealthy"
    fi
    ((total_count++))
    
    # Check Redis
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis redis-cli ping > /dev/null 2>&1; then
        success "Redis: Healthy"
        ((healthy_count++))
    else
        error "Redis: Unhealthy"
    fi
    ((total_count++))
    
    # Check API
    if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
        success "API: Healthy"
        ((healthy_count++))
    else
        error "API: Unhealthy"
    fi
    ((total_count++))
    
    # Check Frontend
    if curl -s http://localhost/ > /dev/null 2>&1; then
        success "Frontend: Healthy"
        ((healthy_count++))
    else
        error "Frontend: Unhealthy"
    fi
    ((total_count++))
    
    echo ""
    if [ $healthy_count -eq $total_count ]; then
        success "All services are healthy! ($healthy_count/$total_count)"
    else
        warning "Some services are unhealthy ($healthy_count/$total_count)"
    fi
}

# Open shell in service container
open_shell() {
    local service="${1:-}"
    
    if [ -z "$service" ]; then
        error "Service name required for shell command"
        exit 1
    fi
    
    log "Opening shell in $service container..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec "$service" /bin/bash
}

# Backup service data
backup_data() {
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    log "Backing up service data to $backup_dir..."
    
    # Backup PostgreSQL data
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_dump -U newsapp news_intelligence > "$backup_dir/postgres_backup.sql"
    success "PostgreSQL data backed up"
    
    # Backup Redis data
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis redis-cli --rdb "$backup_dir/redis_backup.rdb"
    success "Redis data backed up"
    
    # Backup application data
    cp -r data "$backup_dir/" 2>/dev/null || warning "No application data to backup"
    cp -r logs "$backup_dir/" 2>/dev/null || warning "No logs to backup"
    
    success "Backup completed: $backup_dir"
}

# Restore service data
restore_data() {
    local backup_dir="${1:-}"
    
    if [ -z "$backup_dir" ]; then
        error "Backup directory required for restore command"
        exit 1
    fi
    
    if [ ! -d "$backup_dir" ]; then
        error "Backup directory not found: $backup_dir"
        exit 1
    fi
    
    log "Restoring service data from $backup_dir..."
    
    # Restore PostgreSQL data
    if [ -f "$backup_dir/postgres_backup.sql" ]; then
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres psql -U newsapp -d news_intelligence < "$backup_dir/postgres_backup.sql"
        success "PostgreSQL data restored"
    fi
    
    # Restore Redis data
    if [ -f "$backup_dir/redis_backup.rdb" ]; then
        docker cp "$backup_dir/redis_backup.rdb" "$PROJECT_NAME-redis-1:/data/dump.rdb"
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" restart redis
        success "Redis data restored"
    fi
    
    success "Restore completed"
}

# Main execution
main() {
    check_docker
    
    case "${1:-}" in
        start)
            start_services "${2:-}"
            ;;
        stop)
            stop_services "${2:-}"
            ;;
        restart)
            restart_services "${2:-}"
            ;;
        status)
            show_status
            ;;
        logs)
            local follow="false"
            local tail_lines="100"
            local service=""
            
            # Parse options
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --follow)
                        follow="true"
                        shift
                        ;;
                    --tail)
                        tail_lines="$2"
                        shift 2
                        ;;
                    --service)
                        service="$2"
                        shift 2
                        ;;
                    *)
                        error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done
            
            show_logs "$service" "$follow" "$tail_lines"
            ;;
        clean)
            local force="false"
            
            # Parse options
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --force)
                        force="true"
                        shift
                        ;;
                    *)
                        error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done
            
            clean_containers "$force"
            ;;
        build)
            build_services "${2:-}"
            ;;
        pull)
            pull_images
            ;;
        health)
            check_health
            ;;
        shell)
            open_shell "${2:-}"
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data "${2:-}"
            ;;
        --help)
            show_usage
            ;;
        *)
            error "Invalid command: ${1:-}"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
