#!/bin/bash
# Simple NAS container check - run this after installing sshpass
# Or connect manually: ssh -p 9222 Admin@192.168.93.100

NAS_HOST="192.168.93.100"
SSH_PORT="9222"
SSH_USER="Admin"
SSH_PASSWORD="Pooter@STORAGE2024"

if ! command -v sshpass &> /dev/null; then
    echo "⚠️  sshpass not installed."
    echo "Install with: sudo apt-get install sshpass"
    echo ""
    echo "Or connect manually:"
    echo "  ssh -p $SSH_PORT $SSH_USER@$NAS_HOST"
    echo "  Password: $SSH_PASSWORD"
    exit 1
fi

echo "🔍 Checking NAS Docker Containers..."
echo ""

sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" \
    "${SSH_USER}@${NAS_HOST}" << 'REMOTE'
echo "=== Running Containers ==="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo ""
echo "=== PostgreSQL Containers ==="
docker ps -a --filter 'name=postgres' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
echo ""
POSTGRES=$(docker ps --filter 'name=postgres' --format '{{.Names}}' | head -1)
if [ -n "$POSTGRES" ]; then
    echo "✅ PostgreSQL container running: $POSTGRES"
    docker exec $POSTGRES pg_isready -U postgres
    docker exec $POSTGRES psql -U postgres -c "SELECT datname FROM pg_database WHERE datname = 'news_intelligence';" 2>&1
    docker exec $POSTGRES psql -U postgres -c "SELECT usename FROM pg_user WHERE usename = 'newsapp';" 2>&1
else
    echo "❌ No PostgreSQL container running"
    STOPPED=$(docker ps -a --filter 'name=postgres' --filter 'status=exited' --format '{{.Names}}' | head -1)
    [ -n "$STOPPED" ] && echo "⚠️  Stopped container: $STOPPED"
fi
REMOTE
