#!/bin/bash
# Mount Widow server's News Intelligence project via SSHFS
# Usage: ./scripts/mount_widow_project.sh [mount|unmount|status]

set -e

WIDOW_HOST="192.168.93.101"
WIDOW_USER="pete"
WIDOW_PROJECT_PATH="/home/pete/projects/News Intelligence"
DEFAULT_MOUNT_POINT="$HOME/widow-news-intel"

MOUNT_POINT="${1:-$DEFAULT_MOUNT_POINT}"
ACTION="${2:-mount}"

echo "Widow Project Mount Manager"
echo "================================"
echo "Host: ${WIDOW_USER}@${WIDOW_HOST}"
echo "Project: ${WIDOW_PROJECT_PATH}"
echo "Mount Point: ${MOUNT_POINT}"
echo ""

# Check if SSHFS is installed
if ! command -v sshfs &> /dev/null; then
    echo "❌ SSHFS is not installed. Installing..."
    sudo apt-get update && sudo apt-get install -y sshfs
    echo "✅ SSHFS installed successfully"
fi

case "$ACTION" in
    mount)
        echo "📀 Mounting Widow project..."
        
        # Create mount point if it doesn't exist
        mkdir -p "$MOUNT_POINT"
        
        # Check if already mounted
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            echo "⚠️  Already mounted at ${MOUNT_POINT}"
            echo "Unmounting first..."
            fusermount -u "$MOUNT_POINT" 2>/dev/null || umount "$MOUNT_POINT" 2>/dev/null || true
            sleep 1
        fi
        
        # Mount using SSHFS
        sshfs "pete@192.168.93.101:/home/pete/projects/News Intelligence" "$MOUNT_POINT"
        
        if [ $? -eq 0 ]; then
            echo "✅ Mounted successfully at ${MOUNT_POINT}"
            echo ""
            echo "Quick access:"
            echo "  cd ${MOUNT_POINT}"
            echo ""
            echo "To unmount later:"
            echo "  ${0} unmount"
            exit 0
        else
            echo "❌ Failed to mount"
            exit 1
        fi
        ;;
    
    unmount)
        echo "📀 Unmounting..."
        
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            fusermount -u "$MOUNT_POINT" 2>/dev/null || umount "$MOUNT_POINT" 2>/dev/null
            echo "✅ Unmounted"
        else
            echo "ℹ️  Not mounted"
        fi
        ;;
    
    status)
        if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
            echo "✅ Mounted at ${MOUNT_POINT}"
            df -h "$MOUNT_POINT" | tail -1
        else
            echo "❌ Not mounted"
        fi
        ;;
    
    *)
        echo "Usage: $0 [mount|unmount|status] [mount-point]"
        exit 1
        ;;
esac