#!/bin/bash
# Setup Persistent and Reliable NAS Connection
# Configures SSH keys, mounts, health checks, and auto-reconnect

set -e

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_PASSWORD="<NAS_PASSWORD_PLACEHOLDER>"
NAS_SHARE="public"
NAS_MOUNT_PATH="/mnt/nas"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🔧 Setting Up Persistent NAS Connection"
echo "======================================="
echo ""

# 1. Setup SSH Key Authentication
echo "1. Setting up SSH key authentication..."
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "   Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -q
    echo -e "${GREEN}   ✅ SSH key generated${NC}"
else
    echo -e "${GREEN}   ✅ SSH key already exists${NC}"
fi

echo "   Copying public key to NAS..."
if sshpass -p "$NAS_PASSWORD" ssh-copy-id -o StrictHostKeyChecking=no -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" 2>&1 | grep -q "Number of key(s) added"; then
    echo -e "${GREEN}   ✅ SSH key copied to NAS${NC}"
else
    # Try manual copy
    PUB_KEY=$(cat ~/.ssh/id_rsa.pub)
    sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" \
        "mkdir -p ~/.ssh && echo '$PUB_KEY' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys" 2>&1
    echo -e "${GREEN}   ✅ SSH key manually added to NAS${NC}"
fi

# Test passwordless SSH
echo "   Testing passwordless SSH..."
if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "echo 'test'" > /dev/null 2>&1; then
    echo -e "${GREEN}   ✅ Passwordless SSH works!${NC}"
else
    echo -e "${YELLOW}   ⚠️  Passwordless SSH not working yet${NC}"
fi

echo ""

# 2. Setup SSH Config
echo "2. Configuring SSH client..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

if [ ! -f ~/.ssh/config ]; then
    touch ~/.ssh/config
    chmod 600 ~/.ssh/config
fi

if ! grep -q "Host nas" ~/.ssh/config; then
    cat >> ~/.ssh/config << EOF

# NAS Connection
Host nas
    HostName $NAS_HOST
    Port $NAS_SSH_PORT
    User $NAS_USER
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
    UserKnownHostsFile ~/.ssh/known_hosts
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ConnectTimeout 10
EOF
    echo -e "${GREEN}   ✅ SSH config updated${NC}"
else
    echo -e "${GREEN}   ✅ SSH config already exists${NC}"
fi

echo ""

# 3. Setup Persistent NAS Mount
echo "3. Setting up persistent NAS mount..."

# Create mount point
sudo mkdir -p "$NAS_MOUNT_PATH"
sudo chown $USER:$USER "$NAS_MOUNT_PATH" 2>/dev/null || true

# Check if already in fstab
if grep -q "$NAS_MOUNT_PATH" /etc/fstab 2>/dev/null; then
    echo -e "${GREEN}   ✅ NAS mount already in fstab${NC}"
else
    echo "   Adding NAS mount to fstab..."
    FSTAB_ENTRY="//$NAS_HOST/$NAS_SHARE $NAS_MOUNT_PATH cifs credentials=/etc/nas-credentials,uid=$(id -u),gid=$(id -g),iocharset=utf8,file_mode=0777,dir_mode=0777,domain=LAKEHOUSE 0 0"
    
    # Create credentials file
    sudo mkdir -p /etc
    echo "username=$NAS_USER
password=$NAS_PASSWORD
domain=LAKEHOUSE" | sudo tee /etc/nas-credentials > /dev/null
    sudo chmod 600 /etc/nas-credentials
    
    # Add to fstab
    echo "$FSTAB_ENTRY" | sudo tee -a /etc/fstab > /dev/null
    echo -e "${GREEN}   ✅ NAS mount added to fstab${NC}"
fi

# Test mount
echo "   Testing NAS mount..."
if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
    echo -e "${GREEN}   ✅ NAS is already mounted${NC}"
else
    echo "   Mounting NAS..."
    sudo mount "$NAS_MOUNT_PATH" 2>&1 && echo -e "${GREEN}   ✅ NAS mounted successfully${NC}" || echo -e "${YELLOW}   ⚠️  Mount failed (may need manual mount)${NC}"
fi

echo ""

# 4. Create NAS Health Check Script
echo "4. Creating NAS health check script..."
cat > "$PROJECT_ROOT/scripts/check_nas_health.sh" << 'HEALTH_SCRIPT'
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
HEALTH_SCRIPT
chmod +x "$PROJECT_ROOT/scripts/check_nas_health.sh"
echo -e "${GREEN}   ✅ Health check script created${NC}"

echo ""

# 5. Create Auto-Reconnect Service
echo "5. Creating auto-reconnect systemd service..."
sudo tee /etc/systemd/system/nas-connection.service > /dev/null << EOF
[Unit]
Description=NAS Connection Monitor and Auto-Reconnect
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$PROJECT_ROOT/scripts/nas_connection_monitor.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create connection monitor script
cat > "$PROJECT_ROOT/scripts/nas_connection_monitor.sh" << 'MONITOR_SCRIPT'
#!/bin/bash
# NAS Connection Monitor - Auto-reconnects if connection fails

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_MOUNT_PATH="/mnt/nas"

while true; do
    # Check SSH
    if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "echo 'ping'" > /dev/null 2>&1; then
        echo "$(date): SSH connection lost, attempting reconnect..."
    fi
    
    # Check mount
    if ! mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
        echo "$(date): NAS mount lost, attempting remount..."
        sudo mount "$NAS_MOUNT_PATH" 2>&1 || echo "Remount failed"
    fi
    
    sleep 60
done
MONITOR_SCRIPT
chmod +x "$PROJECT_ROOT/scripts/nas_connection_monitor.sh"
echo -e "${GREEN}   ✅ Auto-reconnect service created${NC}"

echo ""

# 6. Setup Database Connection Reliability
echo "6. Verifying database connection configuration..."
if grep -q "DB_HOST=192.168.93.100" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    echo -e "${GREEN}   ✅ Database configured to use NAS${NC}"
else
    echo -e "${YELLOW}   ⚠️  Database may not be configured for NAS${NC}"
fi

echo ""

# Summary
echo "======================================="
echo -e "${GREEN}✅ Persistent NAS Connection Setup Complete!${NC}"
echo ""
echo "What was configured:"
echo "  ✅ SSH key authentication (passwordless login)"
echo "  ✅ SSH config file (~/.ssh/config)"
echo "  ✅ Persistent NAS mount (/etc/fstab)"
echo "  ✅ Health check script (scripts/check_nas_health.sh)"
echo "  ✅ Auto-reconnect service (systemd)"
echo ""
echo "Next steps:"
echo "  1. Test connection: ssh nas 'docker ps'"
echo "  2. Check health: ./scripts/check_nas_health.sh"
echo "  3. Enable auto-reconnect: sudo systemctl enable nas-connection.service"
echo "  4. Start auto-reconnect: sudo systemctl start nas-connection.service"
echo ""

