#!/bin/bash
# Setup persistent SSH tunnel to NAS PostgreSQL database
# This allows the application to connect to NAS database via localhost:5433

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
LOCAL_PORT="5433"
NAS_DB_PORT="5432"
SSH_KEY_PATH="$HOME/.ssh/id_rsa"

echo -e "${GREEN}🔧 Setting up persistent SSH tunnel to NAS database${NC}"
echo ""

# Check if tunnel already exists
if ps aux | grep -q "[s]sh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}"; then
    echo -e "${YELLOW}⚠️  SSH tunnel already running on port ${LOCAL_PORT}${NC}"
    echo "   PID: $(ps aux | grep "[s]sh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}" | awk '{print $2}')"
    echo ""
    read -p "Kill existing tunnel and create new one? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "ssh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}" || true
        sleep 1
    else
        echo "Keeping existing tunnel."
        exit 0
    fi
fi

# Check SSH key
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo -e "${YELLOW}⚠️  SSH key not found at $SSH_KEY_PATH${NC}"
    echo "   Generating new SSH key..."
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_PATH" -N "" -q
    echo -e "${GREEN}✅ SSH key generated${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  You need to copy this key to the NAS:${NC}"
    echo "   ssh-copy-id -p ${NAS_SSH_PORT} ${NAS_USER}@${NAS_HOST}"
    echo ""
    read -p "Copy key to NAS now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ssh-copy-id -p "${NAS_SSH_PORT}" "${NAS_USER}@${NAS_HOST}" || {
            echo -e "${RED}❌ Failed to copy SSH key. Please do it manually.${NC}"
            exit 1
        }
    fi
fi

# Create SSH tunnel
echo -e "${GREEN}🔌 Creating SSH tunnel: localhost:${LOCAL_PORT} -> ${NAS_HOST}:${NAS_DB_PORT}${NC}"
ssh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT} -N -f -p ${NAS_SSH_PORT} -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 ${NAS_USER}@${NAS_HOST}

sleep 2

# Verify tunnel
if ps aux | grep -q "[s]sh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}"; then
    echo -e "${GREEN}✅ SSH tunnel established successfully${NC}"
    echo "   Local port: ${LOCAL_PORT}"
    echo "   Remote: ${NAS_HOST}:${NAS_DB_PORT}"
    echo "   PID: $(ps aux | grep "[s]sh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}" | awk '{print $2}')"
    echo ""
    
    # Test database connection
    echo -e "${GREEN}🧪 Testing database connection through tunnel...${NC}"
    if python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        port=${LOCAL_PORT},
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password',
        connect_timeout=5
    )
    cursor = conn.cursor()
    cursor.execute('SELECT version();')
    version = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    if 'aarch64' in version:
        print('✅ Connected to NAS database (ARM)')
        exit(0)
    else:
        print('⚠️  Connected but may not be NAS')
        exit(0)
except Exception as e:
    print(f'❌ Connection failed: {e}')
    exit(1)
" 2>&1; then
        echo -e "${GREEN}✅ Database connection successful!${NC}"
        echo ""
        echo -e "${GREEN}📝 Configuration:${NC}"
        echo "   Set these environment variables:"
        echo "   export DB_HOST=localhost"
        echo "   export DB_PORT=${LOCAL_PORT}"
        echo ""
        echo "   Or update configs/.env:"
        echo "   DB_HOST=localhost"
        echo "   DB_PORT=${LOCAL_PORT}"
    else
        echo -e "${RED}❌ Database connection failed${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Failed to establish SSH tunnel${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ SSH tunnel setup complete!${NC}"

