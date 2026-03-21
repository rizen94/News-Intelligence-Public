#!/bin/bash
# Update Docker Containers on NAS
# Uses full Docker path and provides commands for manual execution

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
DOCKER_PATH="/usr/local/bin/docker"

echo "🐳 Updating Docker Containers on NAS"
echo "===================================="
echo ""

# Images to update
IMAGES=(
    "postgres:15-alpine"
    "redis:7-alpine"
    "nginx:alpine"
)

echo "Step 1: Current containers on NAS"
echo "----------------------------------"
ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "$DOCKER_PATH ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>&1 | head -20 || echo "Note: May need sudo or docker group membership"
echo ""

echo "Step 2: Commands to run on NAS"
echo "------------------------------"
echo ""
echo "SSH into NAS and run these commands:"
echo ""
echo "# Pull latest images:"
for image in "${IMAGES[@]}"; do
    echo "  $DOCKER_PATH pull $image"
done
echo ""
echo "# Restart containers if using docker-compose:"
echo "  cd /path/to/docker-compose.yml"
echo "  $DOCKER_PATH-compose pull"
echo "  $DOCKER_PATH-compose up -d"
echo ""
echo "# Or restart individual containers:"
echo "  $DOCKER_PATH restart news-intelligence-postgres"
echo "  $DOCKER_PATH restart news-intelligence-redis"
echo "  $DOCKER_PATH restart news-intelligence-api"
echo "  $DOCKER_PATH restart news-intelligence-web"
echo ""

echo "Step 3: Automated update if permissions allow"
echo "-----------------------------------------------"
echo ""

# Try to pull images
for image in "${IMAGES[@]}"; do
    echo "Pulling $image..."
    if ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "$DOCKER_PATH pull $image" 2>&1; then
        echo "✅ $image updated"
    else
        echo "⚠️  $image - permission denied or not found"
    fi
    echo ""
done

echo "✅ Update process complete!"
echo ""
echo "Note: If permission errors occurred, use the manual commands above"
echo "      or add user to docker group: sudo usermod -aG docker $NAS_USER"
