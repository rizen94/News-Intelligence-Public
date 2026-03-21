#!/bin/bash
# Cleanup Local Storage Before Migration
# Removes unnecessary files to free up space

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/backups/cleanup_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_ROOT/logs/cleanup.log"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$BACKUP_DIR"

TOTAL_FREED=0

log() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

# Calculate space freed
add_freed_space() {
    local size="$1"
    TOTAL_FREED=$((TOTAL_FREED + size))
}

# Clean Python cache
clean_python_cache() {
    header "Cleaning Python Cache"
    log "Removing Python cache files..."
    
    local size_before=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    
    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    
    local size_after=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    local freed=$((size_before - size_after))
    
    if [ $freed -gt 0 ]; then
        success "Freed $(numfmt --to=iec-i --suffix=B $freed) from Python cache"
    else
        log "No Python cache found"
    fi
}

# Clean Node modules (keep only production)
clean_node_modules() {
    header "Cleaning Node Modules"
    log "Checking node_modules size..."
    
    if [ -d "$PROJECT_ROOT/web/node_modules" ]; then
        local size=$(du -sb "$PROJECT_ROOT/web/node_modules" 2>/dev/null | awk '{print $1}')
        log "node_modules size: $(numfmt --to=iec-i --suffix=B $size)"
        
        read -p "Remove node_modules? (can reinstall with npm install) (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$PROJECT_ROOT/web/node_modules"
            success "Removed node_modules ($(numfmt --to=iec-i --suffix=B $size))"
            log "Reinstall with: cd web && npm install"
        else
            log "Skipping node_modules cleanup"
        fi
    else
        log "No node_modules found"
    fi
}

# Clean build artifacts
clean_build_artifacts() {
    header "Cleaning Build Artifacts"
    log "Removing build directories..."
    
    local dirs=("web/build" "web/dist" "api/dist" "*.egg-info")
    local freed=0
    
    for pattern in "${dirs[@]}"; do
        for dir in $(find "$PROJECT_ROOT" -type d -name "$(basename "$pattern")" 2>/dev/null); do
            if [ -d "$dir" ]; then
                local size=$(du -sb "$dir" 2>/dev/null | awk '{print $1}')
                rm -rf "$dir"
                freed=$((freed + size))
                success "Removed: $dir ($(numfmt --to=iec-i --suffix=B $size))"
            fi
        done
    done
    
    if [ $freed -gt 0 ]; then
        success "Freed $(numfmt --to=iec-i --suffix=B $freed) from build artifacts"
    else
        log "No build artifacts found"
    fi
}

# Clean old logs
clean_old_logs() {
    header "Cleaning Old Logs"
    log "Removing old log files..."
    
    # Keep last 7 days of logs
    local cutoff_date=$(date -d '7 days ago' +%s)
    local freed=0
    
    find "$PROJECT_ROOT" -type f -name "*.log" -o -name "*.log.*" 2>/dev/null | while read logfile; do
        if [ -f "$logfile" ]; then
            local file_date=$(stat -c %Y "$logfile" 2>/dev/null || echo "0")
            if [ $file_date -lt $cutoff_date ]; then
                local size=$(stat -c %s "$logfile" 2>/dev/null || echo "0")
                rm -f "$logfile"
                freed=$((freed + size))
                log "Removed old log: $logfile"
            fi
        fi
    done
    
    # Also clean very large log files
    find "$PROJECT_ROOT" -type f -name "*.log" -size +100M 2>/dev/null | while read logfile; do
        log "Large log file found: $logfile ($(du -h "$logfile" | awk '{print $1}'))"
        read -p "Truncate or remove? (t/r/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Tt]$ ]]; then
            > "$logfile"
            log "Truncated: $logfile"
        elif [[ $REPLY =~ ^[Rr]$ ]]; then
            rm -f "$logfile"
            log "Removed: $logfile"
        fi
    done
}

# Clean backup files (keep recent)
clean_old_backups() {
    header "Cleaning Old Backups"
    log "Checking backup directories..."
    
    # Keep last 30 days of backups
    find "$PROJECT_ROOT/backups" -type f -mtime +30 2>/dev/null | while read backup; do
        if [ -f "$backup" ]; then
            local size=$(stat -c %s "$backup" 2>/dev/null || echo "0")
            log "Old backup: $backup ($(du -h "$backup" | awk '{print $1}'))"
            read -p "Remove? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f "$backup"
                success "Removed: $backup"
            fi
        fi
    done
}

# Clean Docker data (if not needed)
clean_docker_data() {
    header "Cleaning Docker Data"
    log "Checking for Docker volumes/data..."
    
    if docker ps -a 2>/dev/null | grep -q "news-intelligence"; then
        warning "Docker containers found for news-intelligence"
        read -p "Remove stopped containers and unused volumes? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker container prune -f
            docker volume prune -f
            success "Cleaned Docker containers and volumes"
        fi
    else
        log "No Docker containers found"
    fi
}

# Clean archive directories (move to NAS)
suggest_archive_cleanup() {
    header "Archive Directories"
    log "Checking archive directories..."
    
    find "$PROJECT_ROOT" -type d -name "archive" -o -name "archives" 2>/dev/null | while read arch_dir; do
        if [ -d "$arch_dir" ] && [ "$(du -sb "$arch_dir" 2>/dev/null | awk '{print $1}')" -gt 1048576 ]; then
            local size=$(du -sh "$arch_dir" 2>/dev/null | awk '{print $1}')
            log "Large archive found: $arch_dir ($size)"
            echo "   Consider moving to NAS: /mnt/nas/news-intelligence/data-archives/"
        fi
    done
}

# Main execution
main() {
    header "Local Storage Cleanup"
    log "Starting cleanup process..."
    echo ""
    
    # Show current usage
    local total_size=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    log "Current project size: $(numfmt --to=iec-i --suffix=B $total_size)"
    echo ""
    
    # Run cleanup tasks
    clean_python_cache
    clean_build_artifacts
    clean_old_logs
    clean_old_backups
    suggest_archive_cleanup
    
    # Optional cleanups (interactive)
    clean_node_modules
    clean_docker_data
    
    # Final summary
    header "Cleanup Complete"
    local final_size=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    local freed=$((total_size - final_size))
    
    log "Original size: $(numfmt --to=iec-i --suffix=B $total_size)"
    log "Final size: $(numfmt --to=iec-i --suffix=B $final_size)"
    
    if [ $freed -gt 0 ]; then
        success "Freed: $(numfmt --to=iec-i --suffix=B $freed)"
    else
        log "No space freed"
    fi
    
    echo ""
    log "Log file: $LOG_FILE"
}

main "$@"

