#!/bin/bash
# Check NAS Docker Containers via rsync
# Uses rsync server on NAS (port 873) to transfer and execute check script

NAS_HOST="192.168.93.100"
RSYNC_PORT="873"
RSYNC_USER="rsync"
RSYNC_PASSWORD="Pooter@STORAGE2024"
RSYNC_MODULE=""  # May need to be configured based on NAS setup

echo "🔍 Checking NAS Containers via rsync"
echo "====================================="
echo ""
echo "Host: ${RSYNC_USER}@${NAS_HOST}:${RSYNC_PORT}"
echo ""

# Create temporary check script
CHECK_SCRIPT="/tmp/check_nas_containers_$$.sh"
cat > "$CHECK_SCRIPT" << 'REMOTE_SCRIPT'
#!/bin/bash
echo "=== Docker Containers on NAS ==="
echo ""
echo "1. Running containers:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo ""
echo "2. PostgreSQL containers (all states):"
docker ps -a --filter 'name=postgres' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
echo ""
echo "3. PostgreSQL container status:"
POSTGRES_CONTAINER=$(docker ps --filter 'name=postgres' --format '{{.Names}}' | head -1)
if [ -n "$POSTGRES_CONTAINER" ]; then
    echo "   ✅ Container found: $POSTGRES_CONTAINER"
    echo "   Testing PostgreSQL..."
    docker exec $POSTGRES_CONTAINER pg_isready -U postgres 2>&1
    docker exec $POSTGRES_CONTAINER psql -U postgres -c 'SELECT version();' 2>&1 | head -2
    echo ""
    echo "   Checking if news_intelligence database exists:"
    docker exec $POSTGRES_CONTAINER psql -U postgres -c "SELECT datname FROM pg_database WHERE datname = 'news_intelligence';" 2>&1
    echo ""
    echo "   Checking if newsapp user exists:"
    docker exec $POSTGRES_CONTAINER psql -U postgres -c "SELECT usename FROM pg_user WHERE usename = 'newsapp';" 2>&1
else
    echo "   ❌ No running PostgreSQL container found"
    STOPPED=$(docker ps -a --filter 'name=postgres' --filter 'status=exited' --format '{{.Names}}' | head -1)
    if [ -n "$STOPPED" ]; then
        echo "   ⚠️  Found stopped container: $STOPPED"
        echo "   To start: docker start $STOPPED"
    else
        echo "   ⚠️  No PostgreSQL container found at all"
    fi
fi
echo ""
echo "4. All containers:"
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
REMOTE_SCRIPT

chmod +x "$CHECK_SCRIPT"

# Try to transfer script via rsync
echo "Transferring check script to NAS..."
export RSYNC_PASSWORD="$RSYNC_PASSWORD"

# Try different rsync module paths
for module in "" "backup" "data" "tmp" "/"; do
    echo "Trying module: ${module:-'default'}"
    
    if [ -z "$module" ]; then
        RSYNC_TARGET="rsync://${RSYNC_USER}@${NAS_HOST}:${RSYNC_PORT}/"
    else
        RSYNC_TARGET="rsync://${RSYNC_USER}@${NAS_HOST}:${RSYNC_PORT}/${module}/"
    fi
    
    if rsync --port="$RSYNC_PORT" "$CHECK_SCRIPT" "${RSYNC_TARGET}check_containers.sh" 2>&1 | head -5; then
        echo "✅ Script transferred successfully"
        break
    fi
done

# Clean up
rm -f "$CHECK_SCRIPT"

echo ""
echo "Note: rsync is primarily for file transfer."
echo "To execute the script on NAS, you'll need to SSH in and run it:"
echo "  ssh -p 9222 Admin@192.168.93.100"
echo "  /tmp/check_containers.sh"
echo ""
echo "Or use SSH to execute directly:"
echo "  ssh -p 9222 Admin@192.168.93.100 'bash -s' < $CHECK_SCRIPT"

