#!/bin/bash
# Update Docker Containers on NAS
# Pulls latest images and restarts containers for News Intelligence project

set -e

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "🐳 Updating Docker Containers on NAS"
echo "===================================="
echo ""

# Function to execute command on NAS
nas_exec() {
    ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "$1"
}

# Function to check if container exists
container_exists() {
    nas_exec "docker ps -a --format '{{.Names}}' | grep -q '^$1$'"
}

# Function to check if container is running
container_running() {
    nas_exec "docker ps --format '{{.Names}}' | grep -q '^$1$'"
}

# Function to get container image
get_container_image() {
    nas_exec "docker ps -a --filter 'name=^$1$' --format '{{.Image}}'"
}

# Function to update a container
update_container() {
    local CONTAINER_NAME=$1
    local IMAGE_NAME=$2
    
    echo -e "${CYAN}Updating: $CONTAINER_NAME${NC}"
    
    # Check if container exists
    if ! container_exists "$CONTAINER_NAME"; then
        echo -e "${YELLOW}  ⚠️  Container $CONTAINER_NAME does not exist, skipping...${NC}"
        return 0
    fi
    
    # Get current image
    if [ -z "$IMAGE_NAME" ]; then
        IMAGE_NAME=$(get_container_image "$CONTAINER_NAME")
    fi
    
    if [ -z "$IMAGE_NAME" ]; then
        echo -e "${YELLOW}  ⚠️  Could not determine image for $CONTAINER_NAME, skipping...${NC}"
        return 0
    fi
    
    echo -e "${BLUE}  Image: $IMAGE_NAME${NC}"
    
    # Check if container is running
    local WAS_RUNNING=false
    if container_running "$CONTAINER_NAME"; then
        WAS_RUNNING=true
        echo -e "${BLUE}  Container is running, will restart after update${NC}"
    fi
    
    # Pull latest image
    echo -e "${BLUE}  Pulling latest image...${NC}"
    if nas_exec "docker pull $IMAGE_NAME" 2>&1; then
        echo -e "${GREEN}  ✅ Image pulled successfully${NC}"
    else
        echo -e "${RED}  ❌ Failed to pull image${NC}"
        return 1
    fi
    
    # Stop container if running
    if [ "$WAS_RUNNING" = true ]; then
        echo -e "${BLUE}  Stopping container...${NC}"
        nas_exec "docker stop $CONTAINER_NAME" > /dev/null 2>&1 || true
    fi
    
    # Remove old container
    echo -e "${BLUE}  Removing old container...${NC}"
    nas_exec "docker rm $CONTAINER_NAME" > /dev/null 2>&1 || true
    
    # Get container configuration
    echo -e "${BLUE}  Checking container configuration...${NC}"
    local INSPECT=$(nas_exec "docker inspect $CONTAINER_NAME" 2>/dev/null || echo "")
    
    if [ -z "$INSPECT" ]; then
        echo -e "${YELLOW}  ⚠️  Could not inspect old container, you may need to recreate manually${NC}"
        return 0
    fi
    
    # Extract container configuration
    local CMD=$(nas_exec "docker inspect $CONTAINER_NAME --format '{{.Config.Cmd}}' 2>/dev/null" || echo "")
    local ENV=$(nas_exec "docker inspect $CONTAINER_NAME --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null" || echo "")
    local VOLUMES=$(nas_exec "docker inspect $CONTAINER_NAME --format '{{range .Mounts}}{{println .Source}}:{{println .Destination}}{{end}}' 2>/dev/null" || echo "")
    local PORTS=$(nas_exec "docker inspect $CONTAINER_NAME --format '{{range \$p, \$conf := .NetworkSettings.Ports}}{{\$p}} {{end}}' 2>/dev/null" || echo "")
    
    echo -e "${YELLOW}  ⚠️  Container configuration extraction incomplete.${NC}"
    echo -e "${YELLOW}  ⚠️  Please recreate container manually or use docker-compose.${NC}"
    echo -e "${BLUE}  Image $IMAGE_NAME is updated and ready to use.${NC}"
    
    return 0
}

# Function to update via docker-compose
update_via_compose() {
    local COMPOSE_FILE=$1
    local COMPOSE_DIR=$(dirname "$COMPOSE_FILE")
    
    echo -e "${CYAN}Updating via docker-compose: $COMPOSE_FILE${NC}"
    
    # Pull latest images
    echo -e "${BLUE}  Pulling latest images...${NC}"
    nas_exec "cd $COMPOSE_DIR && docker-compose pull" 2>&1
    
    # Recreate containers
    echo -e "${BLUE}  Recreating containers...${NC}"
    nas_exec "cd $COMPOSE_DIR && docker-compose up -d" 2>&1
    
    echo -e "${GREEN}  ✅ Containers updated via docker-compose${NC}"
}

# Main execution
main() {
    echo "Step 1: Listing all containers on NAS..."
    echo ""
    nas_exec "docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'" | head -20
    echo ""
    
    echo "Step 2: Identifying News Intelligence related containers..."
    echo ""
    
    # Common container names to check
    CONTAINERS=(
        "postgres"
        "postgresql"
        "news-intelligence-postgres"
        "news_intelligence_postgres"
        "news-postgres"
        "newsapp-postgres"
    )
    
    FOUND_CONTAINERS=()
    
    for container in "${CONTAINERS[@]}"; do
        if container_exists "$container"; then
            FOUND_CONTAINERS+=("$container")
            echo -e "${GREEN}  ✅ Found: $container${NC}"
        fi
    done
    
    # Also check for any container with "news" or "intelligence" in name
    echo ""
    echo "Checking for other related containers..."
    OTHER_CONTAINERS=$(nas_exec "docker ps -a --format '{{.Names}}' | grep -iE 'news|intelligence'" || echo "")
    
    if [ -n "$OTHER_CONTAINERS" ]; then
        while IFS= read -r container; do
            if [ -n "$container" ] && [[ ! " ${FOUND_CONTAINERS[@]} " =~ " ${container} " ]]; then
                FOUND_CONTAINERS+=("$container")
                echo -e "${GREEN}  ✅ Found: $container${NC}"
            fi
        done <<< "$OTHER_CONTAINERS"
    fi
    
    echo ""
    
    if [ ${#FOUND_CONTAINERS[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No News Intelligence containers found.${NC}"
        echo ""
        echo "Checking for docker-compose files..."
        
        COMPOSE_FILES=$(nas_exec "find /volume1 -name 'docker-compose.yml' -o -name 'docker-compose.yaml' 2>/dev/null | head -5" || echo "")
        
        if [ -n "$COMPOSE_FILES" ]; then
            echo -e "${GREEN}Found docker-compose files:${NC}"
            echo "$COMPOSE_FILES"
            echo ""
            read -p "Update containers via docker-compose? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                while IFS= read -r compose_file; do
                    if [ -n "$compose_file" ]; then
                        update_via_compose "$compose_file"
                    fi
                done <<< "$COMPOSE_FILES"
            fi
        else
            echo -e "${YELLOW}No docker-compose files found.${NC}"
        fi
        
        return 0
    fi
    
    echo "Step 3: Updating containers..."
    echo ""
    
    for container in "${FOUND_CONTAINERS[@]}"; do
        update_container "$container"
        echo ""
    done
    
    echo ""
    echo "Step 4: Verifying updated containers..."
    echo ""
    nas_exec "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -iE 'news|intelligence|postgres' || docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'" | head -10
    
    echo ""
    echo -e "${GREEN}✅ Container update process complete!${NC}"
    echo ""
    echo "Note: If containers were not automatically recreated, you may need to:"
    echo "  1. Check docker-compose.yml on NAS"
    echo "  2. Manually recreate containers with updated images"
    echo "  3. Use: docker-compose up -d"
}

main "$@"

