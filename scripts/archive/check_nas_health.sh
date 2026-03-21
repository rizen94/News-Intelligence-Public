#!/bin/bash
# NAS Health Check Script
# Checks SSH connectivity, mount status, and database connectivity

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_MOUNT_PATH="/mnt/nas"

echo "🔍 NAS Health Check"
echo "==================="
echo ""

# Check SSH
echo "1. SSH Connectivity:"
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "echo 'connected'" > /dev/null 2>&1; then
    echo "   ✅ SSH connection: OK"
else
    echo "   ❌ SSH connection: FAILED"
fi

# Check Mount
echo ""
echo "2. NAS Mount:"
if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
    echo "   ✅ Mount status: MOUNTED"
    echo "   Mount point: $NAS_MOUNT_PATH"
    df -h "$NAS_MOUNT_PATH" 2>/dev/null | tail -1
else
    echo "   ❌ Mount status: NOT MOUNTED"
fi

# Check Database
echo ""
echo "3. Database Connectivity:"
if python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host='$NAS_HOST',
        port=5432,
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password',
        connect_timeout=5
    )
    conn.close()
    print('   ✅ Database connection: OK')
except Exception as e:
    print(f'   ❌ Database connection: FAILED ({str(e)[:50]})')
" 2>&1; then
    :
else
    echo "   ⚠️  Database check failed"
fi

echo ""
echo "✅ Health check complete"
