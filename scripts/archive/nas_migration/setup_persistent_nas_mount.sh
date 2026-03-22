#!/bin/bash
# Setup Persistent NAS Mount for News Intelligence System
# Creates auto-mount on boot and persistent connection

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
NAS_HOST="192.168.93.100"
NAS_SHARE="public"
NAS_USER="Admin"
NAS_PASSWORD="<NAS_PASSWORD_PLACEHOLDER>"
NAS_DOMAIN="LAKEHOUSE"
MOUNT_POINT="/mnt/nas"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

# Create mount point
create_mount_point() {
    header "Creating Mount Point"
    log "Creating mount point: $MOUNT_POINT"
    
    sudo mkdir -p "$MOUNT_POINT"
    sudo chown $(id -u):$(id -g) "$MOUNT_POINT"
    sudo chmod 755 "$MOUNT_POINT"
    
    success "Mount point created: $MOUNT_POINT"
}

# Create credentials file
create_credentials_file() {
    header "Creating Credentials File"
    log "Creating secure credentials file..."
    
    CREDS_FILE="/etc/nas-credentials"
    
    # Create credentials file with restricted permissions
    echo "username=$NAS_USER" | sudo tee "$CREDS_FILE" > /dev/null
    echo "password=$NAS_PASSWORD" | sudo tee -a "$CREDS_FILE" > /dev/null
    echo "domain=$NAS_DOMAIN" | sudo tee -a "$CREDS_FILE" > /dev/null
    
    # Secure the credentials file
    sudo chmod 600 "$CREDS_FILE"
    sudo chown root:root "$CREDS_FILE"
    
    success "Credentials file created: $CREDS_FILE (secured)"
}

# Add to fstab for auto-mount
add_to_fstab() {
    header "Configuring Auto-Mount (fstab)"
    log "Adding NAS mount to /etc/fstab for auto-mount on boot..."
    
    # Check if entry already exists
    if grep -q "$MOUNT_POINT" /etc/fstab 2>/dev/null; then
        warning "Mount entry already exists in /etc/fstab"
        read -p "Update existing entry? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Skipping fstab update"
            return 0
        fi
        # Remove old entry
        sudo sed -i "\|$MOUNT_POINT|d" /etc/fstab
    fi
    
    # Create fstab entry
    FSTAB_ENTRY="//${NAS_HOST}/${NAS_SHARE} $MOUNT_POINT cifs credentials=/etc/nas-credentials,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,_netdev,auto,user,noauto 0 0"
    
    echo "$FSTAB_ENTRY" | sudo tee -a /etc/fstab > /dev/null
    
    success "Added to /etc/fstab for auto-mount"
    log "Mount will be available on boot (use 'mount $MOUNT_POINT' to mount)"
}

# Create systemd service for auto-mount and monitoring
create_systemd_service() {
    header "Creating Systemd Service"
    log "Creating systemd service for persistent NAS connection..."
    
    SERVICE_FILE="/etc/systemd/system/nas-mount.service"
    MOUNT_SCRIPT="$PROJECT_ROOT/scripts/mount_nas.sh"
    
    # Create mount script
    cat > "$MOUNT_SCRIPT" << 'MOUNT_SCRIPT_EOF'
#!/bin/bash
# NAS Mount Script with Retry Logic

NAS_MOUNT="/mnt/nas"
MAX_RETRIES=5
RETRY_DELAY=5

for i in $(seq 1 $MAX_RETRIES); do
    if mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        echo "NAS already mounted at $NAS_MOUNT"
        exit 0
    fi
    
    echo "Attempting to mount NAS (attempt $i/$MAX_RETRIES)..."
    mount "$NAS_MOUNT" 2>&1
    
    if mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        echo "NAS mounted successfully"
        exit 0
    fi
    
    if [ $i -lt $MAX_RETRIES ]; then
        echo "Mount failed, retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
    fi
done

echo "Failed to mount NAS after $MAX_RETRIES attempts"
exit 1
MOUNT_SCRIPT_EOF
    
    chmod +x "$MOUNT_SCRIPT"
    
    # Create systemd service
    sudo tee "$SERVICE_FILE" > /dev/null << SERVICE_EOF
[Unit]
Description=Mount NAS Storage for News Intelligence System
After=network-online.target
Wants=network-online.target
Requires=network.target

[Service]
Type=oneshot
ExecStart=$MOUNT_SCRIPT
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

# Retry on failure
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
SERVICE_EOF
    
    # Create monitoring service to check mount health
    MONITOR_SERVICE="/etc/systemd/system/nas-mount-monitor.service"
    MONITOR_SCRIPT="$PROJECT_ROOT/scripts/monitor_nas_mount.sh"
    
    cat > "$MONITOR_SCRIPT" << 'MONITOR_SCRIPT_EOF'
#!/bin/bash
# NAS Mount Health Monitor

NAS_MOUNT="/mnt/nas"
CHECK_INTERVAL=60

while true; do
    if ! mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        echo "$(date): NAS mount lost, attempting to remount..."
        mount "$NAS_MOUNT" 2>&1 || echo "$(date): Remount failed"
    fi
    sleep $CHECK_INTERVAL
done
MONITOR_SCRIPT_EOF
    
    chmod +x "$MONITOR_SCRIPT"
    
    sudo tee "$MONITOR_SERVICE" > /dev/null << MONITOR_SERVICE_EOF
[Unit]
Description=NAS Mount Health Monitor
After=nas-mount.service
Requires=nas-mount.service

[Service]
Type=simple
ExecStart=$MONITOR_SCRIPT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
MONITOR_SERVICE_EOF
    
    # Reload systemd and enable services
    sudo systemctl daemon-reload
    sudo systemctl enable nas-mount.service
    sudo systemctl enable nas-mount-monitor.service
    
    success "Systemd services created and enabled"
    log "Services: nas-mount.service, nas-mount-monitor.service"
}

# Test mount
test_mount() {
    header "Testing Mount"
    log "Testing NAS mount..."
    
    # Try to mount
    sudo mount "$MOUNT_POINT" 2>&1 || {
        error "Initial mount test failed"
        return 1
    }
    
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        success "Mount test successful!"
        log "Mount point: $MOUNT_POINT"
        log "Available space:"
        df -h "$MOUNT_POINT" | tail -1 | awk '{print "   Total: " $2 " | Used: " $3 " | Available: " $4 " | Usage: " $5}'
        
        # Test write access
        TEST_FILE="$MOUNT_POINT/.nas_test_$(date +%s)"
        if touch "$TEST_FILE" 2>/dev/null; then
            rm "$TEST_FILE"
            success "Write access confirmed"
        else
            warning "Write access test failed"
        fi
        return 0
    else
        error "Mount test failed"
        return 1
    fi
}

# Create directory structure on NAS
create_nas_directories() {
    header "Creating Directory Structure on NAS"
    log "Creating directories for News Intelligence System..."
    
    if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        warning "NAS not mounted, skipping directory creation"
        return 1
    fi
    
    DIRS=(
        "news-intelligence/postgres-data"
        "news-intelligence/logs"
        "news-intelligence/backups"
        "news-intelligence/ml-models"
        "news-intelligence/data-archives"
    )
    
    for dir in "${DIRS[@]}"; do
        FULL_PATH="$MOUNT_POINT/$dir"
        mkdir -p "$FULL_PATH"
        chmod 755 "$FULL_PATH"
        success "Created: $dir"
    done
    
    success "Directory structure created on NAS"
}

# Main execution
main() {
    header "Persistent NAS Mount Setup"
    echo ""
    log "Setting up persistent NAS connection for News Intelligence System"
    echo ""
    
    create_mount_point
    create_credentials_file
    add_to_fstab
    create_systemd_service
    
    echo ""
    log "Testing mount..."
    if test_mount; then
        create_nas_directories
    fi
    
    echo ""
    header "Setup Complete"
    success "Persistent NAS mount configured!"
    echo ""
    echo "📋 Configuration:"
    echo "   • Mount point: $MOUNT_POINT"
    echo "   • Auto-mount: Enabled (via fstab)"
    echo "   • Systemd service: nas-mount.service (enabled)"
    echo "   • Health monitor: nas-mount-monitor.service (enabled)"
    echo ""
    echo "🚀 Services:"
    echo "   • Start: sudo systemctl start nas-mount.service"
    echo "   • Status: sudo systemctl status nas-mount.service"
    echo "   • Stop: sudo systemctl stop nas-mount.service"
    echo ""
    echo "📝 Manual mount: sudo mount $MOUNT_POINT"
    echo "📝 Manual unmount: sudo umount $MOUNT_POINT"
    echo ""
    echo "✅ NAS will auto-mount on boot and reconnect if connection drops"
}

main "$@"

