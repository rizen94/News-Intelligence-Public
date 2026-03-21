#!/bin/bash

# News Intelligence System - NAS Admin Setup Script
# This script sets up the TerraMaster NAS with admin credentials

set -e

echo "🔐 NEWS INTELLIGENCE SYSTEM - NAS ADMIN SETUP"
echo "=============================================="

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

# Function to get admin credentials
get_admin_credentials() {
    echo ""
    print_status "Please provide your TerraMaster NAS admin credentials:"
    read -p "Admin Username: " ADMIN_USER
    read -s -p "Admin Password: " ADMIN_PASS
    echo ""
    
    if [[ -z "$ADMIN_USER" || -z "$ADMIN_PASS" ]]; then
        print_error "Username and password cannot be empty"
        exit 1
    fi
    
    print_success "Credentials captured for user: $ADMIN_USER"
}

# Function to mount NAS with admin credentials
mount_nas_admin() {
    print_status "Mounting TerraMaster NAS with admin credentials..."
    
    # Create mount point if it doesn't exist
    sudo mkdir -p $NAS_MOUNT
    
    # Check if already mounted
    if mountpoint -q $NAS_MOUNT; then
        print_warning "NAS is already mounted at $NAS_MOUNT"
        sudo umount $NAS_MOUNT
    fi
    
    # Mount the NAS with admin credentials
    if sudo mount -t cifs //$NAS_IP/public $NAS_MOUNT -o username=$ADMIN_USER,password=$ADMIN_PASS,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0; then
        print_success "NAS mounted successfully with admin credentials at $NAS_MOUNT"
    else
        print_error "Failed to mount NAS with admin credentials"
        exit 1
    fi
}

# Function to create directory structure with proper permissions
create_directory_structure() {
    print_status "Creating directory structure on NAS with admin permissions..."
    
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
            # Set proper permissions
            sudo chmod 777 "$full_path"
            sudo chown $(id -u):$(id -g) "$full_path"
        else
            print_warning "Could not create directory: $dir"
        fi
    done
    
    # Verify directory creation
    echo ""
    print_status "Verifying directory structure..."
    ls -la "$BASE_PATH/"
}

# Function to test write permissions
test_write_permissions() {
    print_status "Testing write permissions on NAS directories..."
    
    local test_file="$BASE_PATH/test_write_permissions.txt"
    local test_content="NAS write test - $(date)"
    
    if echo "$test_content" > "$test_file" 2>/dev/null; then
        print_success "Write test passed - can write to NAS"
        rm "$test_file"
    else
        print_error "Write test failed - cannot write to NAS"
        return 1
    fi
}

# Function to create persistent mount configuration
create_persistent_mount() {
    print_status "Creating persistent mount configuration..."
    
    local fstab_entry="//$NAS_IP/public $NAS_MOUNT cifs username=$ADMIN_USER,password=$ADMIN_PASS,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,auto 0 0"
    
    # Check if entry already exists
    if grep -q "$NAS_MOUNT" /etc/fstab; then
        print_warning "Mount entry already exists in /etc/fstab"
    else
        echo "$fstab_entry" | sudo tee -a /etc/fstab
        print_success "Added persistent mount to /etc/fstab"
    fi
}

# Function to display final configuration
display_final_config() {
    print_status "Final NAS Configuration:"
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
        echo "   ├── pgdata/           (PostgreSQL databases) ✅"
        echo "   ├── logs/             (Application logs) ✅"
        echo "   ├── backups/          (Database backups) ✅"
        echo "   ├── ml-models/        (ML model storage) ✅"
        echo "   ├── data-archives/    (Historical data) ✅"
        echo "   ├── prometheus-data/  (Monitoring data) ✅"
        echo "   ├── grafana-data/     (Dashboard data) ✅"
        echo "   ├── temp/             (Temporary files) ✅"
        echo "   └── data/             (Application data) ✅"
    else
        print_error "NAS not mounted"
    fi
}

# Main execution
main() {
    echo "Starting NAS admin setup..."
    echo ""
    
    get_admin_credentials
    mount_nas_admin
    create_directory_structure
    test_write_permissions
    create_persistent_mount
    
    echo ""
    print_success "NAS admin setup complete!"
    echo ""
    display_final_config
    echo ""
    echo "📋 Next steps:"
    echo "   1. Your system is now configured to save ALL data to the NAS"
    echo "   2. Run ./deploy_nas.sh to deploy the system"
    echo "   3. All databases, logs, ML models, and monitoring data will be stored on NAS"
    echo ""
    echo "🔧 To manually mount: sudo mount -t cifs //$NAS_IP/public $NAS_MOUNT -o username=$ADMIN_USER,password=YOUR_PASSWORD,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0"
    echo "🔧 To unmount: sudo umount $NAS_MOUNT"
}

# Run main function
main "$@"

