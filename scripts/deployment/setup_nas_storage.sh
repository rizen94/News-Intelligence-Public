#!/bin/bash

# News Intelligence System - NAS Storage Setup Script
# This script sets up the TerraMaster NAS for storing all system data

set -e

echo "🚀 NEWS INTELLIGENCE SYSTEM - NAS STORAGE SETUP"
echo "================================================"

# Configuration
NAS_MOUNT="/mnt/terramaster-nas"
NAS_IP="192.168.93.100"
BASE_PATH="/mnt/terramaster-nas/docker-postgres-data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

# Function to check if NAS is accessible
check_nas_access() {
    print_status "Checking NAS accessibility..."
    
    if ping -c 1 -W 5 $NAS_IP > /dev/null 2>&1; then
        print_success "NAS is reachable at $NAS_IP"
    else
        print_error "Cannot reach NAS at $NAS_IP"
        exit 1
    fi
}

# Function to mount NAS
mount_nas() {
    print_status "Mounting TerraMaster NAS..."
    
    # Create mount point if it doesn't exist
    sudo mkdir -p $NAS_MOUNT
    
    # Check if already mounted
    if mountpoint -q $NAS_MOUNT; then
        print_warning "NAS is already mounted at $NAS_MOUNT"
        return 0
    fi
    
    # Mount the NAS
    if sudo mount -t cifs //$NAS_IP/public $NAS_MOUNT -o guest,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,sec=none; then
        print_success "NAS mounted successfully at $NAS_MOUNT"
    else
        print_error "Failed to mount NAS"
        exit 1
    fi
}

# Function to create directory structure
create_directory_structure() {
    print_status "Creating directory structure on NAS..."
    
    # Create main directories
    local dirs=(
        "logs"
        "backups"
        "ml-models"
        "data-archives"
        "prometheus-data"
        "grafana-data"
        "temp"
        "data"
    )
    
    for dir in "${dirs[@]}"; do
        local full_path="$BASE_PATH/$dir"
        if sudo mkdir -p "$full_path" 2>/dev/null; then
            print_success "Created directory: $dir"
        else
            print_warning "Could not create directory: $dir (may already exist or permission issue)"
        fi
    done
    
    # Set permissions
    if sudo chown -R $(id -u):$(id -g) "$BASE_PATH" 2>/dev/null; then
        print_success "Set ownership for NAS directories"
    else
        print_warning "Could not set ownership (permission issue)"
    fi
}

# Function to check PostgreSQL data
check_postgres_data() {
    print_status "Checking existing PostgreSQL data..."
    
    if [[ -d "$BASE_PATH/pgdata" ]]; then
        print_success "Found existing PostgreSQL data directory"
        
        # Check if it's a valid PostgreSQL cluster
        if [[ -f "$BASE_PATH/pgdata/PG_VERSION" ]]; then
            local version=$(cat "$BASE_PATH/pgdata/PG_VERSION")
            print_success "PostgreSQL version: $version"
        else
            print_warning "PostgreSQL data directory exists but may not be valid"
        fi
        
        # Check for existing databases
        if [[ -d "$BASE_PATH/pgdata/base" ]]; then
            local db_count=$(find "$BASE_PATH/pgdata/base" -maxdepth 1 -type d | wc -l)
            print_success "Found $db_count database directories"
        fi
    else
        print_warning "No existing PostgreSQL data found - will create new cluster"
    fi
}

# Function to create environment file
create_env_file() {
    print_status "Creating environment configuration file..."
    
    local env_file=".env.nas"
    
    cat > "$env_file" << EOF
# News Intelligence System - NAS Configuration
# Generated on $(date)

# Database Configuration
DB_PASSWORD=secure_password_123
DB_HOST=postgres
DB_NAME=news_system
DB_USER=newsapp

# PostgreSQL Performance Tuning
POSTGRES_SHARED_BUFFERS=256MB
POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
POSTGRES_WORK_MEM=4MB
POSTGRES_MAINTENANCE_WORK_MEM=64MB
POSTGRES_AUTOVACUUM_MAX_WORKERS=3
POSTGRES_AUTOVACUUM_NAPTIME=1min
POSTGRES_LOG_ROTATION_AGE=1d
POSTGRES_LOG_ROTATION_SIZE=100MB

# Application Configuration
RSS_INTERVAL_MINUTES=60
PRUNING_INTERVAL_HOURS=12
MAX_RUNTIME_HOURS=24
LOG_LEVEL=INFO
CLEANUP_INTERVAL_HOURS=6
MAX_LOG_SIZE_MB=100
MAX_TEMP_FILES=1000

# Monitoring Configuration
GRAFANA_PASSWORD=admin123

# NAS Storage Paths
NAS_MOUNT_PATH=$NAS_MOUNT
NAS_BASE_PATH=$BASE_PATH
NAS_POSTGRES_DATA=$BASE_PATH/pgdata
NAS_LOGS=$BASE_PATH/logs
NAS_BACKUPS=$BASE_PATH/backups
NAS_ML_MODELS=$BASE_PATH/ml-models
NAS_DATA_ARCHIVES=$BASE_PATH/data-archives
NAS_PROMETHEUS_DATA=$BASE_PATH/prometheus-data
NAS_GRAFANA_DATA=$BASE_PATH/grafana-data
NAS_TEMP=$BASE_PATH/temp
NAS_DATA=$BASE_PATH/data

# Security Settings
PYTHONHASHSEED=random
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
EOF

    print_success "Created environment file: $env_file"
    print_status "Please review and modify the password in $env_file before deployment"
}

# Function to create deployment script
create_deployment_script() {
    print_status "Creating NAS deployment script..."
    
    local deploy_script="deploy_nas.sh"
    
    cat > "$deploy_script" << 'EOF'
#!/bin/bash

# News Intelligence System - NAS Deployment Script

set -e

echo "🚀 Deploying News Intelligence System on NAS..."

# Check if .env.nas exists
if [[ ! -f ".env.nas" ]]; then
    echo "❌ Environment file .env.nas not found. Run setup_nas_storage.sh first."
    exit 1
fi

# Load environment variables
export $(cat .env.nas | grep -v '^#' | xargs)

# Check NAS mount
if ! mountpoint -q /mnt/terramaster-nas; then
    echo "❌ NAS not mounted. Mounting now..."
    sudo mount -t cifs //192.168.93.100/public /mnt/terramaster-nas -o guest,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,sec=none
fi

# Build and start services
echo "🔨 Building and starting services..."
docker-compose -f docker-compose.nas.yml --env-file .env.nas up --build -d

echo "✅ Deployment complete!"
echo ""
echo "📊 Services available:"
echo "   - News System: http://localhost:8000"
echo "   - Grafana: http://localhost:3002 (admin/admin123)"
echo "   - Prometheus: http://localhost:9090"
echo ""
echo "🗄️  Data stored on NAS at: $NAS_BASE_PATH"
echo "📁 PostgreSQL data: $NAS_POSTGRES_DATA"
echo "📊 Monitoring data: $NAS_PROMETHEUS_DATA"
echo "📈 Grafana data: $NAS_GRAFANA_DATA"
EOF

    chmod +x "$deploy_script"
    print_success "Created deployment script: $deploy_script"
}

# Function to display storage information
display_storage_info() {
    print_status "Storage Information:"
    echo ""
    
    if mountpoint -q $NAS_MOUNT; then
        echo "📁 NAS Mount: $NAS_MOUNT"
        echo "💾 Total Space: $(df -h $NAS_MOUNT | awk 'NR==2 {print $2}')"
        echo "📊 Used Space: $(df -h $NAS_MOUNT | awk 'NR==2 {print $3}')"
        echo "🆓 Available Space: $(df -h $NAS_MOUNT | awk 'NR==2 {print $4}')"
        echo "📈 Usage: $(df -h $NAS_MOUNT | awk 'NR==2 {print $5}')"
        echo ""
        echo "🗂️  Directory Structure:"
        echo "   $BASE_PATH/"
        echo "   ├── pgdata/           (PostgreSQL databases)"
        echo "   ├── logs/             (Application logs)"
        echo "   ├── backups/          (Database backups)"
        echo "   ├── ml-models/        (ML model storage)"
        echo "   ├── data-archives/    (Historical data)"
        echo "   ├── prometheus-data/  (Monitoring data)"
        echo "   ├── grafana-data/     (Dashboard data)"
        echo "   ├── temp/             (Temporary files)"
        echo "   └── data/             (Application data)"
    else
        print_error "NAS not mounted"
    fi
}

# Function to create backup script
create_backup_script() {
    print_status "Creating backup script..."
    
    local backup_script="backup_nas_data.sh"
    
    cat > "$backup_script" << 'EOF'
#!/bin/bash

# News Intelligence System - NAS Data Backup Script

set -e

BACKUP_DIR="/mnt/terramaster-nas/docker-postgres-data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="news_system_backup_$TIMESTAMP"

echo "🔄 Creating backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL data
if docker ps | grep -q news-system-postgres-nas; then
    echo "📊 Backing up PostgreSQL database..."
    docker exec news-system-postgres-nas pg_dumpall -U newsapp > "$BACKUP_DIR/${BACKUP_NAME}_postgres.sql"
    echo "✅ PostgreSQL backup complete: ${BACKUP_NAME}_postgres.sql"
else
    echo "⚠️  PostgreSQL container not running, skipping database backup"
fi

# Backup application data
echo "📁 Backing up application data..."
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_app_data.tar.gz" \
    -C /mnt/terramaster-nas/docker-postgres-data \
    logs data ml-models data-archives 2>/dev/null || true

echo "✅ Application data backup complete: ${BACKUP_NAME}_app_data.tar.gz"

# Clean up old backups (keep last 7 days)
echo "🧹 Cleaning up old backups..."
find "$BACKUP_DIR" -name "news_system_backup_*" -mtime +7 -delete

echo "🎉 Backup complete! Files saved to: $BACKUP_DIR"
echo "📊 Backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
EOF

    chmod +x "$backup_script"
    print_success "Created backup script: $backup_script"
}

# Main execution
main() {
    echo "Starting NAS storage setup..."
    echo ""
    
    check_nas_access
    mount_nas
    create_directory_structure
    check_postgres_data
    create_env_file
    create_deployment_script
    create_backup_script
    
    echo ""
    print_success "NAS storage setup complete!"
    echo ""
    display_storage_info
    echo ""
    echo "📋 Next steps:"
    echo "   1. Review and modify .env.nas file"
    echo "   2. Run ./deploy_nas.sh to deploy the system"
    echo "   3. Use ./backup_nas_data.sh for regular backups"
    echo ""
    echo "🔧 To unmount NAS: sudo umount $NAS_MOUNT"
    echo "🔧 To remount NAS: sudo mount -t cifs //$NAS_IP/public $NAS_MOUNT -o guest,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,sec=none"
}

# Run main function
main "$@"

