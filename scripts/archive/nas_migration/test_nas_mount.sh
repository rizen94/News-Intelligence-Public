#!/bin/bash
# Test NAS SMB Mount with LAKEHOUSE domain

NAS_HOST="192.168.93.100"
NAS_SHARE="public"
NAS_USER="Admin"
NAS_PASSWORD="<NAS_PASSWORD_PLACEHOLDER>"
NAS_DOMAIN="LAKEHOUSE"
MOUNT_POINT="/mnt/nas"

echo "🔍 Testing NAS SMB Mount"
echo "========================"
echo ""
echo "Configuration:"
echo "  Host: $NAS_HOST"
echo "  Share: $NAS_SHARE"
echo "  User: $NAS_USER"
echo "  Domain: $NAS_DOMAIN"
echo "  Mount Point: $MOUNT_POINT"
echo ""

# Create mount point
sudo mkdir -p "$MOUNT_POINT" 2>/dev/null || mkdir -p "$MOUNT_POINT"

# Check if already mounted
if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    echo "✅ NAS is already mounted at $MOUNT_POINT"
    echo ""
    echo "Testing access..."
    ls -la "$MOUNT_POINT/" | head -5
    echo ""
    echo "Disk space:"
    df -h "$MOUNT_POINT" | tail -1
    echo ""
    echo "✅ Mount is working!"
    exit 0
fi

# Try mounting with domain=LAKEHOUSE
echo "Attempting mount with domain=LAKEHOUSE..."
sudo mount -t cifs "//${NAS_HOST}/${NAS_SHARE}" "$MOUNT_POINT" \
    -o username="$NAS_USER",password="$NAS_PASSWORD",domain="$NAS_DOMAIN",uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0 2>&1

if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    echo "✅ Mount successful with domain=LAKEHOUSE!"
    echo ""
    echo "Testing access..."
    ls -la "$MOUNT_POINT/" | head -5
    echo ""
    echo "Disk space:"
    df -h "$MOUNT_POINT" | tail -1
    echo ""
    echo "✅ LAKEHOUSE domain works for mounting!"
    exit 0
else
    echo "❌ Mount failed with domain=LAKEHOUSE"
    echo ""
    echo "Trying without domain parameter..."
    sudo umount "$MOUNT_POINT" 2>/dev/null
    sudo mount -t cifs "//${NAS_HOST}/${NAS_SHARE}" "$MOUNT_POINT" \
        -o username="$NAS_USER",password="$NAS_PASSWORD",uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0 2>&1
    
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        echo "✅ Mount successful without domain parameter"
        echo "   (LAKEHOUSE domain may not be needed)"
        exit 0
    else
        echo "❌ Mount failed without domain parameter too"
        echo ""
        echo "💡 Troubleshooting:"
        echo "   1. Check NAS is accessible: ping $NAS_HOST"
        echo "   2. Verify credentials in NAS web interface"
        echo "   3. Check SMB/CIFS service is enabled on NAS"
        echo "   4. Try: smbclient -L //$NAS_HOST -U $NAS_USER"
        exit 1
    fi
fi

