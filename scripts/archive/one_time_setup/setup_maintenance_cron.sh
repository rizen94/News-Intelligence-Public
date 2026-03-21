#!/bin/bash

# Setup Maintenance Cron Jobs for News Intelligence System v3.0
# Configures automated maintenance tasks

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

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

log "Setting up maintenance cron jobs for News Intelligence System v3.0"
log "Project root: $PROJECT_ROOT"

# Create cron job entries
CRON_JOBS="
# News Intelligence System v3.0 - Maintenance Jobs
# Daily audit at 6:00 AM
0 6 * * * $PROJECT_ROOT/scripts/daily_audit.sh >> $PROJECT_ROOT/logs/cron_daily_audit.log 2>&1

# Weekly deep cleanup at 2:00 AM on Sunday
0 2 * * 0 $PROJECT_ROOT/scripts/docker-manage.sh cleanup >> $PROJECT_ROOT/logs/cron_weekly_cleanup.log 2>&1

# Monthly full audit at 9:00 AM on 1st of month
0 9 1 * * $PROJECT_ROOT/scripts/weekly_audit.sh >> $PROJECT_ROOT/logs/cron_monthly_audit.log 2>&1

# Hourly Python cache cleanup
0 * * * * find $PROJECT_ROOT -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# Daily log rotation (keep last 30 days)
0 1 * * * find $PROJECT_ROOT/logs -name '*.log' -mtime +30 -delete 2>/dev/null || true
"

# Create temporary cron file
TEMP_CRON="/tmp/news_intelligence_cron_$$"
echo "$CRON_JOBS" > "$TEMP_CRON"

# Check if cron jobs already exist
if crontab -l 2>/dev/null | grep -q "News Intelligence System v3.0"; then
    warning "Maintenance cron jobs already exist"
    log "Current cron jobs:"
    crontab -l 2>/dev/null | grep -A 10 -B 2 "News Intelligence System v3.0" || true
    
    read -p "Do you want to replace existing cron jobs? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Removing existing cron jobs..."
        crontab -l 2>/dev/null | grep -v "News Intelligence System v3.0" | crontab -
        success "Existing cron jobs removed"
    else
        log "Keeping existing cron jobs"
        rm -f "$TEMP_CRON"
        exit 0
    fi
fi

# Add new cron jobs
log "Adding new cron jobs..."
(crontab -l 2>/dev/null; cat "$TEMP_CRON") | crontab -

# Verify cron jobs were added
if crontab -l 2>/dev/null | grep -q "News Intelligence System v3.0"; then
    success "Maintenance cron jobs added successfully"
    log "Scheduled maintenance tasks:"
    echo "  - Daily audit: 6:00 AM"
    echo "  - Weekly cleanup: 2:00 AM (Sunday)"
    echo "  - Monthly audit: 9:00 AM (1st of month)"
    echo "  - Hourly Python cache cleanup"
    echo "  - Daily log rotation"
else
    error "Failed to add cron jobs"
    exit 1
fi

# Clean up temporary file
rm -f "$TEMP_CRON"

# Create log directories
mkdir -p "$PROJECT_ROOT/logs"

# Test daily audit script
log "Testing daily audit script..."
if [ -f "$PROJECT_ROOT/scripts/daily_audit.sh" ]; then
    if bash "$PROJECT_ROOT/scripts/daily_audit.sh" --help 2>/dev/null; then
        success "Daily audit script is working"
    else
        warning "Daily audit script may have issues"
    fi
else
    error "Daily audit script not found"
fi

# Create maintenance status script
cat > "$PROJECT_ROOT/scripts/maintenance_status.sh" << 'EOF'
#!/bin/bash
# Maintenance Status Check for News Intelligence System v3.0

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

echo "News Intelligence System v3.0 - Maintenance Status"
echo "=================================================="
echo "Project Root: $PROJECT_ROOT"
echo "Log Directory: $LOG_DIR"
echo ""

# Check cron jobs
echo "Cron Jobs:"
if crontab -l 2>/dev/null | grep -q "News Intelligence System v3.0"; then
    echo "  ✅ Maintenance cron jobs are active"
    crontab -l 2>/dev/null | grep "News Intelligence System v3.0" | head -1
else
    echo "  ❌ No maintenance cron jobs found"
fi
echo ""

# Check recent audit logs
echo "Recent Audit Logs:"
if [ -d "$LOG_DIR" ]; then
    ls -la "$LOG_DIR"/*audit*.log 2>/dev/null | tail -5 || echo "  No audit logs found"
else
    echo "  Log directory not found"
fi
echo ""

# Check disk usage
echo "Disk Usage:"
df -h / | awk 'NR==2 {print "  Root: " $5 " used (" $3 "/" $2 ")"}'
echo ""

# Check file counts
echo "File Counts:"
echo "  Total files: $(find "$PROJECT_ROOT" -type f | wc -l)"
echo "  Python files: $(find "$PROJECT_ROOT" -name "*.py" | wc -l)"
echo "  Log files: $(find "$PROJECT_ROOT/logs" -name "*.log" 2>/dev/null | wc -l)"
echo ""

# Check for issues
echo "Issue Check:"
HARDCODED=$(grep -r "/home/petes/news-system" "$PROJECT_ROOT" --include="*.py" --include="*.sh" 2>/dev/null | wc -l)
if [ "$HARDCODED" -eq 0 ]; then
    echo "  ✅ No hardcoded paths found"
else
    echo "  ❌ $HARDCODED hardcoded path references found"
fi

EMPTY_FILES=$(find "$PROJECT_ROOT" -type f -empty 2>/dev/null | wc -l)
if [ "$EMPTY_FILES" -eq 0 ]; then
    echo "  ✅ No empty files found"
else
    echo "  ⚠️  $EMPTY_FILES empty files found"
fi

echo ""
echo "Maintenance Status Check Complete"
EOF

chmod +x "$PROJECT_ROOT/scripts/maintenance_status.sh"
success "Maintenance status script created"

# Create maintenance runbook
cat > "$PROJECT_ROOT/MAINTENANCE_RUNBOOK.md" << 'EOF'
# 🛠️ Maintenance Runbook - News Intelligence System v3.0

## Quick Commands

### Check Status
```bash
./scripts/maintenance_status.sh
```

### Run Daily Audit
```bash
./scripts/daily_audit.sh
```

### Manual Cleanup
```bash
# Clean Python cache
find . -name "__pycache__" -type d -exec rm -rf {} +

# Clean .pyc files
find . -name "*.pyc" -delete

# Clean empty files
find . -type f -empty -delete

# Clean Docker resources
./scripts/docker-manage.sh cleanup
```

### Emergency Cleanup
```bash
# Check disk usage
df -h

# Find large files
find . -size +100M -exec ls -lh {} \;

# Clean logs
find logs/ -name "*.log" -mtime +7 -delete

# Clean node_modules
rm -rf web/node_modules
cd web && npm install
```

## Monitoring

### Check Cron Jobs
```bash
crontab -l | grep "News Intelligence System"
```

### View Logs
```bash
tail -f logs/daily_audit_$(date +%Y%m%d).log
```

### Check Alerts
```bash
python3 -c "import sys; sys.path.append('api'); from services.maintenance_monitor import MaintenanceMonitor; m = MaintenanceMonitor(); result = m.run_full_monitoring(); print(f'Alerts: {result[\"alert_count\"]}')"
```

## Troubleshooting

### Common Issues
1. **Disk space full** → Run emergency cleanup
2. **Import errors** → Check path configuration
3. **Docker issues** → Clean Docker resources
4. **Log files large** → Rotate logs

### Contact
- Check logs in `logs/` directory
- Review maintenance reports
- Run status check script
EOF

success "Maintenance runbook created"

log "Maintenance cron setup completed successfully"
success "All maintenance systems are now configured"

echo ""
echo "Next Steps:"
echo "1. Check status: ./scripts/maintenance_status.sh"
echo "2. Run test audit: ./scripts/daily_audit.sh"
echo "3. Review runbook: cat MAINTENANCE_RUNBOOK.md"
echo "4. Monitor logs: tail -f logs/daily_audit_$(date +%Y%m%d).log"
echo ""
echo "Maintenance system is now active and will run automatically!"
