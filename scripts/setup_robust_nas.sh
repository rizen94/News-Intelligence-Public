#!/bin/bash

# News Intelligence System - Robust NAS Storage Setup
# This script implements a multi-layer storage solution for maximum reliability

set -e

# Configuration
NAS_HOST="192.168.93.100"
NAS_SHARE="public"
NAS_USER="Admin"
NAS_WORKGROUP="LAKEHOUSE"
NAS_PASSWORD="Pooter@STORAGE2024"
NAS_MOUNT_PATH="/mnt/nas"
LOCAL_CACHE_PATH="/opt/news-intelligence/cache"
BACKUP_PATH="/mnt/nas/public/docker-postgres-data/backups"
LOG_FILE="/var/log/news-intelligence-nas.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
fi

log "Starting News Intelligence Robust NAS Storage Setup"

# 1. Install required packages
log "Installing required packages..."
apt-get update -y
apt-get install -y \
    nfs-common \
    cifs-utils \
    rsync \
    inotify-tools \
    lsof \
    hdparm \
    iotop \
    nfs-utils \
    autofs \
    systemd-resolved

# 2. Create directory structure
log "Creating directory structure..."
mkdir -p "$NAS_MOUNT_PATH"/{public,private,backups}
mkdir -p "$LOCAL_CACHE_PATH"/{postgres,redis,prometheus,logs}
mkdir -p /etc/news-intelligence/nas
mkdir -p /var/log/news-intelligence

# 3. Set up NFS mount (preferred over CIFS for databases)
log "Setting up NFS mount..."
cat > /etc/news-intelligence/nas/nfs-mount.conf << EOF
# NFS Mount Configuration for News Intelligence
# NFS is more reliable for database workloads than CIFS

# Check if NFS is available on NAS
if rpcinfo -p "$NAS_HOST" | grep -q nfs; then
    log "NFS service detected on NAS, using NFS mount"
    echo "$NAS_HOST:/public $NAS_MOUNT_PATH/public nfs defaults,rsize=65536,wsize=65536,hard,intr,timeo=600,retrans=2 0 0" >> /etc/fstab
else
    warn "NFS not available, falling back to CIFS with optimizations"
    echo "//$NAS_HOST/$NAS_SHARE $NAS_MOUNT_PATH/public cifs username=$NAS_USER,password=$NAS_PASSWORD,workgroup=$NAS_WORKGROUP,uid=0,gid=0,iocharset=utf8,file_mode=0777,dir_mode=0777,rsize=65536,wsize=65536,cache=strict,vers=3.0,sec=ntlmssp,hard,intr,timeo=600,retrans=2 0 0" >> /etc/fstab
fi
EOF

# 4. Create robust mount script
log "Creating robust mount script..."
cat > /usr/local/bin/mount-news-nas << 'EOF'
#!/bin/bash

# Robust NAS mounting script with automatic failover and health checks

NAS_MOUNT_PATH="/mnt/nas"
LOG_FILE="/var/log/news-intelligence-nas.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

is_mounted() {
    mountpoint -q "$1" 2>/dev/null
}

is_healthy() {
    local mount_point="$1"
    # Test write access
    if touch "$mount_point"/.health_check 2>/dev/null; then
        rm -f "$mount_point"/.health_check
        return 0
    fi
    return 1
}

mount_nas() {
    log "Attempting to mount NAS storage..."
    
    # Try NFS first
    if rpcinfo -p 192.168.93.100 | grep -q nfs; then
        log "Using NFS mount"
        mount -t nfs 192.168.93.100:/public "$NAS_MOUNT_PATH/public" -o rsize=65536,wsize=65536,hard,intr,timeo=600,retrans=2
    else
        log "Using CIFS mount with optimizations"
        mount -t cifs //192.168.93.100/public "$NAS_MOUNT_PATH/public" -o username=Admin,password=Pooter@STORAGE2024,workgroup=LAKEHOUSE,uid=0,gid=0,iocharset=utf8,file_mode=0777,dir_mode=0777,rsize=65536,wsize=65536,cache=strict,vers=3.0,sec=ntlmssp,hard,intr,timeo=600,retrans=2
    fi
    
    if is_healthy "$NAS_MOUNT_PATH/public"; then
        log "NAS mounted successfully and healthy"
        return 0
    else
        log "NAS mount failed health check"
        return 1
    fi
}

# Main execution
if is_mounted "$NAS_MOUNT_PATH/public"; then
    if is_healthy "$NAS_MOUNT_PATH/public"; then
        log "NAS already mounted and healthy"
        exit 0
    else
        log "NAS mounted but unhealthy, attempting remount..."
        umount "$NAS_MOUNT_PATH/public" 2>/dev/null || true
    fi
fi

if mount_nas; then
    log "NAS mount successful"
    exit 0
else
    log "NAS mount failed"
    exit 1
fi
EOF

chmod +x /usr/local/bin/mount-news-nas

# 5. Create database storage solution
log "Setting up database storage solution..."
cat > /usr/local/bin/setup-db-storage << 'EOF'
#!/bin/bash

# Database storage setup with local caching and NAS persistence

NAS_DB_PATH="/mnt/nas/public/docker-postgres-data"
LOCAL_CACHE_PATH="/opt/news-intelligence/cache/postgres"
BACKUP_PATH="/mnt/nas/public/docker-postgres-data/backups"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Create directories with proper permissions
mkdir -p "$NAS_DB_PATH"/{pgdata,backups,logs}
mkdir -p "$LOCAL_CACHE_PATH"
mkdir -p "$BACKUP_PATH"

# Set ownership for PostgreSQL
chown -R 999:999 "$LOCAL_CACHE_PATH"
chmod -R 755 "$LOCAL_CACHE_PATH"

# Create backup script
cat > /usr/local/bin/backup-database << 'BACKUP_EOF'
#!/bin/bash
# Database backup script with NAS persistence

BACKUP_DIR="/mnt/nas/public/docker-postgres-data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="postgres_backup_${TIMESTAMP}.sql"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Create backup
log "Creating database backup: $BACKUP_FILE"
docker exec news-intelligence-postgres pg_dump -U newsapp -d news_intelligence > "$BACKUP_DIR/$BACKUP_FILE"

if [ $? -eq 0 ]; then
    log "Backup created successfully: $BACKUP_FILE"
    # Compress backup
    gzip "$BACKUP_DIR/$BACKUP_FILE"
    log "Backup compressed: ${BACKUP_FILE}.gz"
    
    # Clean old backups (keep last 30 days)
    find "$BACKUP_DIR" -name "postgres_backup_*.sql.gz" -mtime +30 -delete
    log "Old backups cleaned up"
else
    log "Backup failed"
    exit 1
fi
BACKUP_EOF

chmod +x /usr/local/bin/backup-database

log "Database storage setup complete"
EOF

chmod +x /usr/local/bin/setup-db-storage

# 6. Create monitoring script
log "Creating NAS monitoring script..."
cat > /usr/local/bin/monitor-nas << 'EOF'
#!/bin/bash

# NAS monitoring and health check script

NAS_MOUNT_PATH="/mnt/nas/public"
LOG_FILE="/var/log/news-intelligence-nas.log"
ALERT_EMAIL="admin@newsintelligence.local"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_nas_health() {
    local mount_point="$1"
    
    # Check if mounted
    if ! mountpoint -q "$mount_point"; then
        log "ERROR: NAS not mounted at $mount_point"
        return 1
    fi
    
    # Check disk space
    local usage=$(df "$mount_point" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$usage" -gt 90 ]; then
        log "WARNING: NAS disk usage is ${usage}%"
    fi
    
    # Check write access
    if ! touch "$mount_point"/.health_check 2>/dev/null; then
        log "ERROR: Cannot write to NAS"
        return 1
    fi
    rm -f "$mount_point"/.health_check
    
    # Check read access
    if ! ls "$mount_point" >/dev/null 2>&1; then
        log "ERROR: Cannot read from NAS"
        return 1
    fi
    
    log "NAS health check passed"
    return 0
}

# Run health check
if check_nas_health "$NAS_MOUNT_PATH"; then
    log "NAS monitoring: OK"
    exit 0
else
    log "NAS monitoring: FAILED"
    # Attempt to remount
    /usr/local/bin/mount-news-nas
    exit 1
fi
EOF

chmod +x /usr/local/bin/monitor-nas

# 7. Set up systemd services
log "Setting up systemd services..."

# NAS mount service
cat > /etc/systemd/system/news-nas-mount.service << EOF
[Unit]
Description=News Intelligence NAS Mount
Before=docker.service
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mount-news-nas
RemainAfterExit=yes
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOF

# NAS monitoring service
cat > /etc/systemd/system/news-nas-monitor.service << EOF
[Unit]
Description=News Intelligence NAS Monitor
After=news-nas-mount.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/monitor-nas
User=root

[Install]
WantedBy=multi-user.target
EOF

# NAS monitoring timer
cat > /etc/systemd/system/news-nas-monitor.timer << EOF
[Unit]
Description=News Intelligence NAS Monitor Timer
Requires=news-nas-monitor.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

# 8. Enable services
log "Enabling services..."
systemctl daemon-reload
systemctl enable news-nas-mount.service
systemctl enable news-nas-monitor.timer
systemctl start news-nas-mount.service
systemctl start news-nas-monitor.timer

# 9. Update Docker Compose for robust storage
log "Updating Docker Compose configuration..."
cat > /tmp/docker-compose-nas-update.yml << 'EOF'
# Updated volumes section for robust NAS storage
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nas/public/docker-postgres-data/pgdata
  redis_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nas/public/docker-postgres-data/redis-data
  prometheus_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/nas/public/docker-postgres-data/prometheus-data
EOF

# 10. Create backup and restore scripts
log "Creating backup and restore scripts..."

# Backup script
cat > /usr/local/bin/backup-news-system << 'EOF'
#!/bin/bash
# Complete system backup script

BACKUP_DIR="/mnt/nas/public/docker-postgres-data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="news_system_backup_${TIMESTAMP}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting complete system backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# Backup database
log "Backing up database..."
docker exec news-intelligence-postgres pg_dump -U newsapp -d news_intelligence > "$BACKUP_DIR/$BACKUP_NAME/database.sql"

# Backup Redis data
log "Backing up Redis data..."
docker exec news-intelligence-redis redis-cli BGSAVE
docker cp news-intelligence-redis:/data/dump.rdb "$BACKUP_DIR/$BACKUP_NAME/redis.rdb"

# Backup configuration files
log "Backing up configuration files..."
cp -r /home/pete/Documents/projects/Projects/News\ Intelligence/docker-compose.yml "$BACKUP_DIR/$BACKUP_NAME/"
cp -r /home/pete/Documents/projects/Projects/News\ Intelligence/.env "$BACKUP_DIR/$BACKUP_NAME/"

# Create backup manifest
cat > "$BACKUP_DIR/$BACKUP_NAME/manifest.txt" << MANIFEST_EOF
News Intelligence System Backup
Created: $(date)
Backup Name: $BACKUP_NAME
Components:
- Database: database.sql
- Redis: redis.rdb
- Configuration: docker-compose.yml, .env
MANIFEST_EOF

# Compress backup
log "Compressing backup..."
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

log "Backup completed: ${BACKUP_NAME}.tar.gz"
EOF

chmod +x /usr/local/bin/backup-news-system

# Restore script
cat > /usr/local/bin/restore-news-system << 'EOF'
#!/bin/bash
# System restore script

BACKUP_DIR="/mnt/nas/public/docker-postgres-data/backups"

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_name.tar.gz>"
    echo "Available backups:"
    ls -la "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$BACKUP_DIR/$1"
RESTORE_DIR="/tmp/news_restore_$$"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

if [ ! -f "$BACKUP_FILE" ]; then
    log "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

log "Starting system restore from: $1"

# Extract backup
mkdir -p "$RESTORE_DIR"
cd "$RESTORE_DIR"
tar -xzf "$BACKUP_FILE"

# Stop services
log "Stopping services..."
docker-compose down

# Restore database
log "Restoring database..."
docker-compose up -d postgres
sleep 10
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker exec -i news-intelligence-postgres psql -U newsapp -d news_intelligence < database.sql

# Restore Redis
log "Restoring Redis..."
docker-compose up -d redis
sleep 5
docker cp redis.rdb news-intelligence-redis:/data/dump.rdb
docker restart news-intelligence-redis

# Start all services
log "Starting all services..."
docker-compose up -d

log "System restore completed"
rm -rf "$RESTORE_DIR"
EOF

chmod +x /usr/local/bin/restore-news-system

# 11. Set up automated backups
log "Setting up automated backups..."
cat > /etc/cron.d/news-intelligence-backup << EOF
# News Intelligence System Automated Backups
# Daily backup at 2 AM
0 2 * * * root /usr/local/bin/backup-news-system >> /var/log/news-intelligence-backup.log 2>&1

# Weekly full system backup on Sunday at 3 AM
0 3 * * 0 root /usr/local/bin/backup-news-system && /usr/local/bin/backup-database >> /var/log/news-intelligence-backup.log 2>&1
EOF

# 12. Final setup
log "Running final setup..."
/usr/local/bin/setup-db-storage

log "Robust NAS storage setup completed successfully!"
log "Services enabled:"
log "- news-nas-mount.service (auto-mount on boot)"
log "- news-nas-monitor.timer (health checks every 5 minutes)"
log "- Automated backups (daily at 2 AM, weekly full backup on Sunday at 3 AM)"
log ""
log "Available commands:"
log "- /usr/local/bin/mount-news-nas (manual mount)"
log "- /usr/local/bin/monitor-nas (health check)"
log "- /usr/local/bin/backup-news-system (manual backup)"
log "- /usr/local/bin/restore-news-system <backup_file> (restore)"
log ""
log "Log files:"
log "- /var/log/news-intelligence-nas.log"
log "- /var/log/news-intelligence-backup.log"
