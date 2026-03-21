#!/bin/bash
# Check NAS Docker Containers Status
# This script connects to NAS and checks if PostgreSQL and other containers are running

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_PASSWORD="Pooter@STORAGE2024"

echo "🔍 Checking NAS Docker Containers"
echo "================================="
echo ""
echo "Host: ${NAS_USER}@${NAS_HOST}:${NAS_SSH_PORT}"
echo ""

# Check if sshpass is available
if ! command -v sshpass &> /dev/null; then
    echo "⚠️  sshpass not installed. Installing..."
    echo "   Run: sudo apt-get install sshpass"
    echo ""
    echo "   Or connect manually:"
    echo "   ssh -p ${NAS_SSH_PORT} ${NAS_USER}@${NAS_HOST}"
    echo ""
    exit 1
fi

# Test connection
echo "1. Testing SSH connection..."
if ! sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
    "${NAS_USER}@${NAS_HOST}" "echo 'Connection successful!'" > /dev/null 2>&1; then
    echo "   ❌ SSH connection failed"
    echo "   Please verify:"
    echo "     - NAS is accessible"
    echo "     - SSH port ${NAS_SSH_PORT} is open"
    echo "     - Credentials are correct"
    exit 1
fi
echo "   ✅ SSH connection successful"
echo ""

# Check all running containers
echo "2. Running Docker Containers:"
echo "=============================="
sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
    "${NAS_USER}@${NAS_HOST}" "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo ""

# Check PostgreSQL containers specifically
echo "3. PostgreSQL Containers (all states):"
echo "======================================="
sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
    "${NAS_USER}@${NAS_HOST}" "docker ps -a --filter 'name=postgres' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'"
echo ""

# Check if PostgreSQL container is running
echo "4. PostgreSQL Container Status:"
echo "================================"
POSTGRES_STATUS=$(sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
    "${NAS_USER}@${NAS_HOST}" "docker ps --filter 'name=postgres' --format '{{.Names}}'")

if [ -z "$POSTGRES_STATUS" ]; then
    echo "   ❌ No PostgreSQL container is running"
    echo ""
    echo "   Checking stopped containers..."
    STOPPED=$(sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "docker ps -a --filter 'name=postgres' --filter 'status=exited' --format '{{.Names}}'")
    
    if [ -n "$STOPPED" ]; then
        echo "   ⚠️  Found stopped PostgreSQL container(s): $STOPPED"
        echo "   To start: ssh -p ${NAS_SSH_PORT} ${NAS_USER}@${NAS_HOST} 'docker start $STOPPED'"
    else
        echo "   ⚠️  No PostgreSQL container found at all"
        echo "   PostgreSQL container needs to be created on NAS"
    fi
else
    echo "   ✅ PostgreSQL container is running: $POSTGRES_STATUS"
    echo ""
    echo "5. Testing PostgreSQL connection from inside container:"
    echo "======================================================="
    sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "for container in \$(docker ps --filter 'name=postgres' --format '{{.Names}}'); do
            echo \"Container: \$container\"
            docker exec \$container pg_isready -U postgres 2>&1 || echo '  pg_isready failed'
            docker exec \$container psql -U postgres -c 'SELECT version();' 2>&1 | head -2
            echo ''
        done"
fi

echo ""
echo "6. Checking Docker Compose Services:"
echo "======================================"
sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
    "${NAS_USER}@${NAS_HOST}" "if [ -f docker-compose.yml ]; then
        cd ~ && docker-compose ps 2>&1
    elif [ -f /mnt/nas/docker-compose.yml ]; then
        cd /mnt/nas && docker-compose ps 2>&1
    else
        echo 'No docker-compose.yml found in common locations'
    fi"
echo ""

echo "✅ Container check complete!"

