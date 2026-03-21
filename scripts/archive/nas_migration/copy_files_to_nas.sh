#!/bin/bash
# Copy PostgreSQL Migration Files to NAS via SMB

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

NAS_HOST="192.168.93.100"
NAS_SHARE="public"
NAS_USER="Admin"
NAS_PASSWORD="Pooter@STORAGE2024"
NAS_DOMAIN="LAKEHOUSE"
MOUNT_POINT="/mnt/nas"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LATEST_BACKUP=$(ls -td "$PROJECT_ROOT/backups/nas_migration_*" 2>/dev/null | head -1)

echo "📁 Copying Files to NAS"
echo "========================"
echo ""

# Check if backup directory exists
if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No migration backup directory found"
    echo "   Run: ./scripts/nas_postgres_setup_manual.sh first"
    exit 1
fi

echo "📋 Source: $LATEST_BACKUP"
echo ""

# Create mount point
echo "1. Creating mount point..."
sudo mkdir -p "$MOUNT_POINT" 2>/dev/null || mkdir -p "$MOUNT_POINT"

# Check if already mounted
if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    echo "✅ NAS already mounted at $MOUNT_POINT"
else
    echo "2. Mounting NAS..."
    sudo mount -t cifs "//${NAS_HOST}/${NAS_SHARE}" "$MOUNT_POINT" \
        -o username="$NAS_USER",password="$NAS_PASSWORD",domain="$NAS_DOMAIN",uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0
    
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        echo "✅ NAS mounted successfully"
    else
        echo "❌ Failed to mount NAS"
        exit 1
    fi
fi

# Copy files
echo ""
echo "3. Copying files to NAS..."
cp "$LATEST_BACKUP"/*.sh "$LATEST_BACKUP"/*.yml "$LATEST_BACKUP"/*.tar.gz "$LATEST_BACKUP"/*.md "$MOUNT_POINT/" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Files copied successfully!"
    echo ""
    echo "📋 Files on NAS:"
    ls -lh "$MOUNT_POINT"/*.{sh,yml,tar.gz,md} 2>/dev/null | awk '{print "   • " $9 " (" $5 ")"}'
    echo ""
    echo "✅ Ready for next steps!"
    echo ""
    echo "📖 Next: Follow instructions in QUICK_START.md"
    echo "   Files are at: $MOUNT_POINT/"
else
    echo "❌ Failed to copy files"
    exit 1
fi

