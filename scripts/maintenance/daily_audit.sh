#!/bin/bash

# Daily Audit Script for News Intelligence System v3.0
# Runs automated daily maintenance checks and cleanup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/daily_audit_$(date +%Y%m%d).log"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1${NC}" | tee -a "$LOG_FILE"
}

# Start audit
log "Starting daily audit for News Intelligence System v3.0"
log "Project root: $PROJECT_ROOT"
log "Log file: $LOG_FILE"

# Change to project directory
cd "$PROJECT_ROOT"

# 1. Check disk usage
log "Checking disk usage..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 85 ]; then
    error "Disk usage critical: ${DISK_USAGE}%"
elif [ "$DISK_USAGE" -gt 75 ]; then
    warning "Disk usage warning: ${DISK_USAGE}%"
else
    success "Disk usage OK: ${DISK_USAGE}%"
fi

# 2. Check file counts
log "Checking file counts..."
FILE_COUNT=$(find . -type f | wc -l)
if [ "$FILE_COUNT" -gt 20000 ]; then
    error "File count critical: $FILE_COUNT files"
elif [ "$FILE_COUNT" -gt 10000 ]; then
    warning "File count warning: $FILE_COUNT files"
else
    success "File count OK: $FILE_COUNT files"
fi

# 3. Check log file sizes
log "Checking log file sizes..."
LARGE_LOGS=$(find logs/ -name "*.log" -size +100M 2>/dev/null | wc -l)
if [ "$LARGE_LOGS" -gt 0 ]; then
    warning "Found $LARGE_LOGS large log files (>100MB)"
    find logs/ -name "*.log" -size +100M -exec ls -lh {} \; | tee -a "$LOG_FILE"
else
    success "No large log files found"
fi

# 4. Check node_modules size
log "Checking node_modules size..."
if [ -d "web/node_modules" ]; then
    NODE_SIZE=$(du -sh web/node_modules | cut -f1)
    NODE_SIZE_MB=$(du -sm web/node_modules | cut -f1)
    if [ "$NODE_SIZE_MB" -gt 2000 ]; then
        error "Node modules size critical: $NODE_SIZE"
    elif [ "$NODE_SIZE_MB" -gt 1000 ]; then
        warning "Node modules size warning: $NODE_SIZE"
    else
        success "Node modules size OK: $NODE_SIZE"
    fi
else
    success "No node_modules directory found"
fi

# 5. Clean Python cache files
log "Cleaning Python cache files..."
PYCACHE_COUNT=$(find . -name "__pycache__" -type d | wc -l)
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    success "Cleaned $PYCACHE_COUNT __pycache__ directories"
else
    success "No Python cache files found"
fi

# 6. Clean .pyc files
log "Cleaning .pyc files..."
PYC_COUNT=$(find . -name "*.pyc" | wc -l)
if [ "$PYC_COUNT" -gt 0 ]; then
    find . -name "*.pyc" -delete 2>/dev/null || true
    success "Cleaned $PYC_COUNT .pyc files"
else
    success "No .pyc files found"
fi

# 7. Clean empty files
log "Cleaning empty files..."
EMPTY_COUNT=$(find . -type f -empty | wc -l)
if [ "$EMPTY_COUNT" -gt 0 ]; then
    find . -type f -empty -not -path "./.venv/*" -not -path "./web/node_modules/*" -delete 2>/dev/null || true
    success "Cleaned $EMPTY_COUNT empty files"
else
    success "No empty files found"
fi

# 8. Check Docker resources
log "Checking Docker resources..."
if command -v docker &> /dev/null; then
    DOCKER_IMAGES=$(docker images -q | wc -l)
    DOCKER_CONTAINERS=$(docker ps -aq | wc -l)
    success "Docker: $DOCKER_IMAGES images, $DOCKER_CONTAINERS containers"
    
    # Check for unused Docker resources
    UNUSED_IMAGES=$(docker images -f "dangling=true" -q | wc -l)
    if [ "$UNUSED_IMAGES" -gt 0 ]; then
        warning "Found $UNUSED_IMAGES unused Docker images"
    fi
else
    warning "Docker not available"
fi

# 9. Check for hardcoded paths
log "Checking for hardcoded paths..."
HARDCODED_PATHS=$(grep -r "/home/petes/news-system" . --include="*.py" --include="*.sh" 2>/dev/null | wc -l)
if [ "$HARDCODED_PATHS" -gt 0 ]; then
    error "Found $HARDCODED_PATHS hardcoded path references"
    grep -r "/home/petes/news-system" . --include="*.py" --include="*.sh" 2>/dev/null | tee -a "$LOG_FILE"
else
    success "No hardcoded path references found"
fi

# 10. Check import consistency
log "Checking Python import consistency..."
cd "$PROJECT_ROOT"
if python3 -c "import sys; sys.path.append('api'); from services.maintenance_monitor import MaintenanceMonitor; print('Import test passed')" 2>/dev/null; then
    success "Python imports working correctly"
else
    error "Python import issues detected"
fi

# 11. Generate summary
log "Generating audit summary..."
AUDIT_SUMMARY="
Daily Audit Summary - $(date)
================================
Disk Usage: ${DISK_USAGE}%
File Count: $FILE_COUNT
Large Logs: $LARGE_LOGS
Node Modules: ${NODE_SIZE:-"N/A"}
Python Cache: $PYCACHE_COUNT directories cleaned
Empty Files: $EMPTY_COUNT files cleaned
Docker Images: ${DOCKER_IMAGES:-"N/A"}
Docker Containers: ${DOCKER_CONTAINERS:-"N/A"}
Hardcoded Paths: $HARDCODED_PATHS
Import Test: $(if python3 -c "import sys; sys.path.append('api'); from services.maintenance_monitor import MaintenanceMonitor" 2>/dev/null; then echo "PASSED"; else echo "FAILED"; fi)
"

echo "$AUDIT_SUMMARY" | tee -a "$LOG_FILE"

# 12. Run maintenance monitor if available
log "Running maintenance monitor..."
if [ -f "api/services/maintenance_monitor.py" ]; then
    if python3 -c "import sys; sys.path.append('api'); from services.maintenance_monitor import MaintenanceMonitor; m = MaintenanceMonitor(); result = m.run_full_monitoring(); print(f'Monitoring complete: {result[\"alert_count\"]} alerts')" 2>/dev/null; then
        success "Maintenance monitor completed successfully"
    else
        warning "Maintenance monitor had issues"
    fi
else
    warning "Maintenance monitor not available"
fi

# 13. Cleanup old log files (keep last 30 days)
log "Cleaning up old log files..."
find logs/ -name "daily_audit_*.log" -mtime +30 -delete 2>/dev/null || true
success "Old log files cleaned up"

# Final status
log "Daily audit completed successfully"
success "All daily maintenance tasks completed"

# Exit with appropriate code
if [ "$HARDCODED_PATHS" -gt 0 ] || [ "$DISK_USAGE" -gt 85 ]; then
    error "Audit completed with critical issues"
    exit 1
elif [ "$DISK_USAGE" -gt 75 ] || [ "$FILE_COUNT" -gt 10000 ]; then
    warning "Audit completed with warnings"
    exit 2
else
    success "Audit completed successfully"
    exit 0
fi
