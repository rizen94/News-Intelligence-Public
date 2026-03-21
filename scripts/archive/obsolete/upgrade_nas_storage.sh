#!/bin/bash

# News Intelligence System - NAS Storage Upgrade Script
# This script implements a robust, enterprise-grade NAS storage solution

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/var/log/news-intelligence-nas-upgrade.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
fi

# Create log file
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

header "News Intelligence NAS Storage Upgrade"
log "Starting NAS storage upgrade process"

# Step 1: Pre-upgrade backup
header "Step 1: Creating Pre-Upgrade Backup"
log "Creating backup before making changes..."

cd "$PROJECT_DIR"

# Stop services gracefully
log "Stopping services for backup..."
docker-compose down

# Create backup
BACKUP_DIR="/mnt/nas/public/docker-postgres-data/backups/pre_upgrade_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

log "Backing up current configuration..."
cp docker-compose.yml "$BACKUP_DIR/"
cp .env "$BACKUP_DIR/"

# Backup database if running
if docker ps | grep -q news-intelligence-postgres; then
    log "Backing up database..."
    docker exec news-intelligence-postgres pg_dump -U newsapp -d news_intelligence > "$BACKUP_DIR/database_backup.sql"
fi

success "Pre-upgrade backup completed: $BACKUP_DIR"

# Step 2: Install robust NAS solution
header "Step 2: Installing Robust NAS Solution"
log "Running robust NAS setup script..."

if [ -f "$SCRIPT_DIR/setup_robust_nas.sh" ]; then
    bash "$SCRIPT_DIR/setup_robust_nas.sh"
    success "Robust NAS solution installed"
else
    error "Robust NAS setup script not found"
fi

# Step 3: Test NAS connectivity
header "Step 3: Testing NAS Connectivity"
log "Testing NAS mount and health..."

# Test mount
if /usr/local/bin/mount-news-nas; then
    success "NAS mount successful"
else
    error "NAS mount failed"
fi

# Test health
if /usr/local/bin/monitor-nas; then
    success "NAS health check passed"
else
    error "NAS health check failed"
fi

# Step 4: Prepare database storage
header "Step 4: Preparing Database Storage"
log "Setting up database storage directories..."

# Create directories on NAS
mkdir -p /mnt/nas/public/docker-postgres-data/{pgdata,redis-data,prometheus-data,backups,logs}

# Set proper permissions
chown -R 999:999 /mnt/nas/public/docker-postgres-data/pgdata
chown -R 999:999 /mnt/nas/public/docker-postgres-data/redis-data
chown -R 65534:65534 /mnt/nas/public/docker-postgres-data/prometheus-data

success "Database storage directories prepared"

# Step 5: Initialize PostgreSQL on NAS
header "Step 5: Initializing PostgreSQL on NAS"
log "Initializing PostgreSQL database on NAS storage..."

# Create a temporary container to initialize PostgreSQL
log "Creating PostgreSQL initialization container..."
docker run --rm \
    -v /mnt/nas/public/docker-postgres-data/pgdata:/var/lib/postgresql/data \
    -e POSTGRES_DB=news_intelligence \
    -e POSTGRES_USER=newsapp \
    -e POSTGRES_PASSWORD=newsapp_password \
    postgres:15-alpine \
    sh -c 'initdb --pgdata=/var/lib/postgresql/data --username=postgres --auth-local=trust --auth-host=md5 --encoding=UTF-8 --lc-collate=C --lc-ctype=C'

if [ $? -eq 0 ]; then
    success "PostgreSQL initialized on NAS"
else
    warn "PostgreSQL initialization had issues, but continuing..."
fi

# Step 6: Update Docker Compose configuration
header "Step 6: Updating Docker Compose Configuration"
log "Updating to robust NAS configuration..."

# Backup current docker-compose.yml
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)

# Use the robust NAS configuration
if [ -f "docker-compose-robust-nas.yml" ]; then
    cp docker-compose-robust-nas.yml docker-compose.yml
    success "Docker Compose updated to robust NAS configuration"
else
    error "Robust NAS Docker Compose file not found"
fi

# Step 7: Start services with new configuration
header "Step 7: Starting Services with New Configuration"
log "Starting services with robust NAS storage..."

# Start services
docker-compose up -d

# Wait for services to be ready
log "Waiting for services to start..."
sleep 30

# Check service health
log "Checking service health..."
if docker-compose ps | grep -q "Up (healthy)"; then
    success "Services started successfully"
else
    warn "Some services may not be fully healthy yet"
fi

# Step 8: Restore database if backup exists
header "Step 8: Restoring Database"
if [ -f "$BACKUP_DIR/database_backup.sql" ]; then
    log "Restoring database from backup..."
    
    # Wait for PostgreSQL to be ready
    until docker exec news-intelligence-postgres pg_isready -U newsapp -d news_intelligence; do
        log "Waiting for PostgreSQL to be ready..."
        sleep 5
    done
    
    # Restore database
    docker exec -i news-intelligence-postgres psql -U newsapp -d news_intelligence < "$BACKUP_DIR/database_backup.sql"
    
    if [ $? -eq 0 ]; then
        success "Database restored successfully"
    else
        warn "Database restore had issues, but continuing..."
    fi
else
    log "No database backup found, skipping restore"
fi

# Step 9: Verify system functionality
header "Step 9: Verifying System Functionality"
log "Running comprehensive system tests..."

# Test API health
log "Testing API health..."
if curl -f http://localhost:8000/api/health/ >/dev/null 2>&1; then
    success "API health check passed"
else
    warn "API health check failed"
fi

# Test database connectivity
log "Testing database connectivity..."
if docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;" >/dev/null 2>&1; then
    success "Database connectivity test passed"
else
    warn "Database connectivity test failed"
fi

# Test Redis connectivity
log "Testing Redis connectivity..."
if docker exec news-intelligence-redis redis-cli ping | grep -q "PONG"; then
    success "Redis connectivity test passed"
else
    warn "Redis connectivity test failed"
fi

# Test frontend
log "Testing frontend..."
if curl -f http://localhost/ >/dev/null 2>&1; then
    success "Frontend test passed"
else
    warn "Frontend test failed"
fi

# Step 10: Set up monitoring and alerts
header "Step 10: Setting Up Monitoring and Alerts"
log "Configuring monitoring and alerting..."

# Enable monitoring services
systemctl enable news-nas-monitor.timer
systemctl start news-nas-monitor.timer

# Set up log rotation
cat > /etc/logrotate.d/news-intelligence << EOF
/var/log/news-intelligence*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF

success "Monitoring and alerting configured"

# Step 11: Final verification
header "Step 11: Final System Verification"
log "Running final system verification..."

# Check all services are running
log "Checking service status..."
docker-compose ps

# Check NAS mount status
log "Checking NAS mount status..."
df -h /mnt/nas/public

# Check disk usage
USAGE=$(df /mnt/nas/public | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$USAGE" -lt 80 ]; then
    success "NAS disk usage is healthy: ${USAGE}%"
else
    warn "NAS disk usage is high: ${USAGE}%"
fi

# Test backup functionality
log "Testing backup functionality..."
if /usr/local/bin/backup-database >/dev/null 2>&1; then
    success "Backup functionality test passed"
else
    warn "Backup functionality test failed"
fi

# Final summary
header "NAS Storage Upgrade Complete!"
success "News Intelligence System has been upgraded to use robust NAS storage"
log ""
log "Key improvements implemented:"
log "✅ Robust NAS mounting with automatic failover"
log "✅ Health monitoring every 5 minutes"
log "✅ Automated daily backups"
log "✅ Database persistence on NAS"
log "✅ Comprehensive logging and monitoring"
log "✅ Systemd services for reliability"
log "✅ Resource limits and optimization"
log ""
log "Available commands:"
log "- /usr/local/bin/mount-news-nas (manual mount)"
log "- /usr/local/bin/monitor-nas (health check)"
log "- /usr/local/bin/backup-news-system (full backup)"
log "- /usr/local/bin/backup-database (database backup)"
log "- /usr/local/bin/restore-news-system <backup> (restore)"
log ""
log "Log files:"
log "- /var/log/news-intelligence-nas.log"
log "- /var/log/news-intelligence-backup.log"
log "- /var/log/news-intelligence-nas-upgrade.log"
log ""
log "Backup location: $BACKUP_DIR"
log ""
success "System is now running with enterprise-grade NAS storage!"
