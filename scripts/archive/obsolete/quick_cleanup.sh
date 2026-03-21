#!/bin/bash
# Quick Cleanup - Automated Space Saving
# Removes safe-to-delete items without prompts

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

TOTAL_FREED=0

# Clean Python cache (safe, can regenerate)
clean_python_cache() {
    header "Cleaning Python Cache"
    local size_before=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    
    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true
    find "$PROJECT_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    
    local size_after=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    local freed=$((size_before - size_after))
    
    if [ $freed -gt 0 ]; then
        success "Freed $(numfmt --to=iec-i --suffix=B $freed)"
        TOTAL_FREED=$((TOTAL_FREED + freed))
    fi
}

# Clean build artifacts (safe, can rebuild)
clean_build_artifacts() {
    header "Cleaning Build Artifacts"
    local size_before=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    
    rm -rf "$PROJECT_ROOT/web/build" 2>/dev/null || true
    rm -rf "$PROJECT_ROOT/web/dist" 2>/dev/null || true
    rm -rf "$PROJECT_ROOT/api/dist" 2>/dev/null || true
    
    local size_after=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    local freed=$((size_before - size_after))
    
    if [ $freed -gt 0 ]; then
        success "Freed $(numfmt --to=iec-i --suffix=B $freed)"
        TOTAL_FREED=$((TOTAL_FREED + freed))
    fi
}

# Clean old logs (keep last 7 days)
clean_old_logs() {
    header "Cleaning Old Logs"
    local cutoff_date=$(date -d '7 days ago' +%s)
    local freed=0
    
    find "$PROJECT_ROOT" -type f \( -name "*.log" -o -name "*.log.*" \) -mtime +7 2>/dev/null | while read logfile; do
        if [ -f "$logfile" ]; then
            local size=$(stat -c %s "$logfile" 2>/dev/null || echo "0")
            rm -f "$logfile"
            freed=$((freed + size))
        fi
    done
    
    # Truncate large log files (>100MB)
    find "$PROJECT_ROOT" -type f -name "*.log" -size +100M 2>/dev/null | while read logfile; do
        log "Truncating large log: $logfile"
        > "$logfile"
    done
    
    if [ $freed -gt 0 ]; then
        success "Cleaned old logs"
    fi
}

# Remove old backup directories (keep recent)
clean_old_backup_dirs() {
    header "Cleaning Old Backup Directories"
    
    # Remove backups older than 30 days
    find "$PROJECT_ROOT/backups" -type d -mtime +30 -maxdepth 1 2>/dev/null | while read backup_dir; do
        if [ -d "$backup_dir" ] && [ "$backup_dir" != "$PROJECT_ROOT/backups" ]; then
            local size=$(du -sb "$backup_dir" 2>/dev/null | awk '{print $1}')
            log "Removing old backup: $(basename $backup_dir) ($(numfmt --to=iec-i --suffix=B $size))"
            rm -rf "$backup_dir"
            TOTAL_FREED=$((TOTAL_FREED + size))
        fi
    done
}

# Main execution
main() {
    header "Quick Cleanup - Automated"
    log "Cleaning safe-to-delete files..."
    echo ""
    
    local size_before=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    
    clean_python_cache
    clean_build_artifacts
    clean_old_logs
    clean_old_backup_dirs
    
    local size_after=$(du -sb "$PROJECT_ROOT" 2>/dev/null | awk '{print $1}')
    local freed=$((size_before - size_after))
    
    header "Cleanup Complete"
    log "Original size: $(numfmt --to=iec-i --suffix=B $size_before)"
    log "Final size: $(numfmt --to=iec-i --suffix=B $size_after)"
    
    if [ $freed -gt 0 ]; then
        success "Freed: $(numfmt --to=iec-i --suffix=B $freed)"
    else
        log "No space freed (may already be clean)"
    fi
    
    echo ""
    log "💡 For more aggressive cleanup:"
    log "   • Remove .venv: rm -rf .venv (saves 6.8GB)"
    log "   • Remove node_modules: rm -rf web/node_modules (saves 1.2GB)"
    log "   • Move archive to NAS: ./scripts/move_to_nas.sh"
}

main "$@"
