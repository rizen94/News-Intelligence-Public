#!/bin/bash
# Check NAS containers - uses rsync info but executes via SSH
# rsync server is on port 873, but we still need SSH for command execution

NAS_HOST="192.168.93.100"
SSH_PORT="9222"
SSH_USER="Admin"
SSH_PASSWORD="<NAS_PASSWORD_PLACEHOLDER>"
RSYNC_USER="rsync"
RSYNC_PASSWORD="<NAS_PASSWORD_PLACEHOLDER>"

echo "🔍 Checking NAS Docker Containers"
echo "================================="
echo ""

# Check if sshpass is available
if ! command -v sshpass &> /dev/null; then
    echo "⚠️  sshpass not installed. Installing..."
    sudo apt-get install -y sshpass > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ Could not install sshpass. Please install manually:"
        echo "   sudo apt-get install sshpass"
        exit 1
    fi
fi

echo "Connecting to NAS and checking containers..."
echo ""

# Execute container check commands via SSH
sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$SSH_PORT" \
    "${SSH_USER}@${NAS_HOST}" << 'REMOTE_COMMANDS'
echo "=== Running Docker Containers ==="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo ""
echo "=== PostgreSQL Containers (All States) ==="
docker ps -a --filter 'name=postgres' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
echo ""
echo "=== PostgreSQL Container Details ==="
POSTGRES_CONTAINER=$(docker ps --filter 'name=postgres' --format '{{.Names}}' | head -1)
if [ -n "$POSTGRES_CONTAINER" ]; then
    echo "✅ Container running: $POSTGRES_CONTAINER"
    echo ""
    echo "Testing PostgreSQL connection:"
    docker exec $POSTGRES_CONTAINER pg_isready -U postgres 2>&1
    echo ""
    echo "PostgreSQL version:"
    docker exec $POSTGRES_CONTAINER psql -U postgres -c 'SELECT version();' 2>&1 | head -2
    echo ""
    echo "Checking databases:"
    docker exec $POSTGRES_CONTAINER psql -U postgres -c '\l' 2>&1 | grep -E "news_intelligence|Name"
    echo ""
    echo "Checking users:"
    docker exec $POSTGRES_CONTAINER psql -U postgres -c '\du' 2>&1 | grep -E "newsapp|Name"
else
    echo "❌ No running PostgreSQL container found"
    STOPPED=$(docker ps -a --filter 'name=postgres' --filter 'status=exited' --format '{{.Names}}' | head -1)
    if [ -n "$STOPPED" ]; then
        echo "⚠️  Found stopped container: $STOPPED"
        echo "   To start: docker start $STOPPED"
    else
        echo "⚠️  No PostgreSQL container found"
    fi
fi
echo ""
echo "=== All Containers ==="
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
REMOTE_COMMANDS

echo ""
echo "✅ Container check complete!"
