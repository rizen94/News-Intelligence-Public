#!/bin/bash
# Move Large Files/Directories to NAS
# Helps free up local storage by moving data to NAS

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NAS_MOUNT="/mnt/nas"

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

# Check NAS mount
check_nas() {
    if ! mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        error "NAS not mounted at $NAS_MOUNT"
        return 1
    fi
    return 0
}

# Move archive to NAS
move_archive() {
    header "Moving Archive to NAS"
    
    if [ ! -d "$PROJECT_ROOT/archive" ]; then
        log "No archive directory found"
        return 0
    fi
    
    local size=$(du -sh "$PROJECT_ROOT/archive" 2>/dev/null | awk '{print $1}')
    log "Archive size: $size"
    
    read -p "Move archive/ to NAS? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        check_nas || return 1
        
        local nas_archive="$NAS_MOUNT/news-intelligence/data-archives/archive-$(date +%Y%m%d)"
        mkdir -p "$nas_archive"
        
        log "Moving archive to NAS..."
        mv "$PROJECT_ROOT/archive" "$nas_archive/" && \
        ln -s "$nas_archive/archive" "$PROJECT_ROOT/archive"
        
        success "Archive moved to: $nas_archive"
        log "Symlink created: $PROJECT_ROOT/archive -> $nas_archive/archive"
    fi
}

# Move ollama data to NAS
move_ollama_data() {
    header "Moving Ollama Data to NAS"
    
    if [ ! -d "$PROJECT_ROOT/ollama_data" ]; then
        log "No ollama_data directory found"
        return 0
    fi
    
    local size=$(du -sh "$PROJECT_ROOT/ollama_data" 2>/dev/null | awk '{print $1}')
    log "Ollama data size: $size"
    
    read -p "Move ollama_data/ to NAS? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        check_nas || return 1
        
        local nas_ollama="$NAS_MOUNT/news-intelligence/ml-models/ollama_data"
        mkdir -p "$nas_ollama"
        
        log "Moving ollama_data to NAS..."
        mv "$PROJECT_ROOT/ollama_data" "$nas_ollama/" && \
        ln -s "$nas_ollama/ollama_data" "$PROJECT_ROOT/ollama_data"
        
        success "Ollama data moved to: $nas_ollama"
    fi
}

# Move old backups to NAS
move_old_backups() {
    header "Moving Old Backups to NAS"
    
    if [ ! -d "$PROJECT_ROOT/backups" ]; then
        log "No backups directory found"
        return 0
    fi
    
    check_nas || return 1
    
    local nas_backups="$NAS_MOUNT/news-intelligence/backups"
    mkdir -p "$nas_backups"
    
    # Find backups older than 7 days
    find "$PROJECT_ROOT/backups" -type f -mtime +7 2>/dev/null | while read backup; do
        local size=$(du -h "$backup" 2>/dev/null | awk '{print $1}')
        log "Old backup: $backup ($size)"
        read -p "Move to NAS? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mv "$backup" "$nas_backups/"
            success "Moved: $(basename $backup)"
        fi
    done
}

# Main execution
main() {
    header "Move Large Files to NAS"
    log "Helping free up local storage..."
    echo ""
    
    check_nas || exit 1
    
    move_archive
    move_ollama_data
    move_old_backups
    
    header "Complete"
    success "Files moved to NAS!"
    log "Check NAS at: $NAS_MOUNT/news-intelligence/"
}

main "$@"

