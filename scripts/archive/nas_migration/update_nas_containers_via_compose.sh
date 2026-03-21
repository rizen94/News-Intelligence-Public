#!/bin/bash
# Update Docker Containers on NAS via docker-compose
# Assumes docker-compose.yml is available on NAS

set -e

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
PROJECT_NAME="news-intelligence"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "🐳 Updating Docker Containers on NAS via docker-compose"
echo "======================================================"
echo ""

# Function to execute command on NAS
nas_exec() {
    ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "$1"
}

# Function to find docker-compose on NAS
find_docker_compose() {
    echo -e "${CYAN}Searching for docker-compose on NAS...${NC}"
    
    # Try common locations
    COMPOSE_PATHS=(
        "/usr/bin/docker-compose"
        "/usr/local/bin/docker-compose"
        "/opt/bin/docker-compose"
        "$(nas_exec 'which docker-compose' 2>/dev/null || echo '')"
    )
    
    # Also try docker compose (v2)
    DOCKER_COMPOSE_CMD=""
    for path in "${COMPOSE_PATHS[@]}"; do
        if [ -n "$path" ] && nas_exec "test -x '$path' 2>/dev/null && echo 'found'" 2>/dev/null | grep -q "found"; then
            DOCKER_COMPOSE_CMD="$path"
            echo -e "${GREEN}  ✅ Found: $path${NC}"
            break
        fi
    done
    
    # Try docker compose (v2 syntax)
    if [ -z "$DOCKER_COMPOSE_CMD" ]; then
        echo -e "${CYAN}  Trying docker compose (v2)...${NC}"
        if nas_exec "docker compose version 2>/dev/null" > /dev/null 2>&1; then
            DOCKER_COMPOSE_CMD="docker compose"
            echo -e "${GREEN}  ✅ Found: docker compose (v2)${NC}"
        fi
    fi
    
    if [ -z "$DOCKER_COMPOSE_CMD" ]; then
        echo -e "${RED}  ❌ docker-compose not found${NC}"
        return 1
    fi
    
    echo "$DOCKER_COMPOSE_CMD"
}

# Function to find docker-compose.yml on NAS
find_compose_file() {
    echo -e "${CYAN}Searching for docker-compose.yml on NAS...${NC}"
    
    # Common locations
    COMPOSE_LOCATIONS=(
        "/volume1/docker/news-intelligence"
        "/volume1/docker"
        "/share/docker"
        "/mnt/HD/HD_a2/docker"
        "/home/docker"
        "$(nas_exec 'find /volume1 -name docker-compose.yml -type f 2>/dev/null | head -1' 2>/dev/null || echo '')"
    )
    
    for location in "${COMPOSE_LOCATIONS[@]}"; do
        if [ -n "$location" ] && nas_exec "test -f '$location/docker-compose.yml' 2>/dev/null && echo 'found'" 2>/dev/null | grep -q "found"; then
            echo -e "${GREEN}  ✅ Found: $location/docker-compose.yml${NC}"
            echo "$location"
            return 0
        fi
    done
    
    echo -e "${YELLOW}  ⚠️  docker-compose.yml not found${NC}"
    return 1
}

# Main execution
main() {
    # Step 1: Find docker-compose command
    echo "Step 1: Locating docker-compose..."
    echo ""
    DOCKER_COMPOSE_CMD=$(find_docker_compose)
    
    if [ -z "$DOCKER_COMPOSE_CMD" ]; then
        echo -e "${RED}❌ Cannot find docker-compose on NAS${NC}"
        echo ""
        echo "Options:"
        echo "  1. Install docker-compose on NAS"
        echo "  2. Use Container Station web interface"
        echo "  3. Manually update containers"
        return 1
    fi
    
    echo ""
    
    # Step 2: Find docker-compose.yml
    echo "Step 2: Locating docker-compose.yml..."
    echo ""
    COMPOSE_DIR=$(find_compose_file)
    
    if [ -z "$COMPOSE_DIR" ]; then
        echo -e "${YELLOW}⚠️  docker-compose.yml not found on NAS${NC}"
        echo ""
        echo "Would you like to:"
        echo "  1. Copy docker-compose.yml to NAS?"
        echo "  2. Create a new docker-compose.yml on NAS?"
        echo "  3. Update containers manually?"
        echo ""
        read -p "Choice (1/2/3): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[1]$ ]]; then
            echo -e "${CYAN}Copying docker-compose.yml to NAS...${NC}"
            # Determine target location
            TARGET_DIR="/volume1/docker/news-intelligence"
            nas_exec "mkdir -p $TARGET_DIR" 2>/dev/null || true
            scp -P "$NAS_SSH_PORT" docker-compose.yml "$NAS_USER@$NAS_HOST:$TARGET_DIR/" 2>&1
            COMPOSE_DIR="$TARGET_DIR"
            echo -e "${GREEN}✅ Copied to $COMPOSE_DIR${NC}"
        elif [[ $REPLY =~ ^[2]$ ]]; then
            echo -e "${CYAN}Please create docker-compose.yml on NAS manually${NC}"
            return 1
        else
            echo -e "${YELLOW}Skipping docker-compose update${NC}"
            return 0
        fi
    fi
    
    echo ""
    
    # Step 3: List current containers
    echo "Step 3: Current containers..."
    echo ""
    nas_exec "cd $COMPOSE_DIR && $DOCKER_COMPOSE_CMD ps" 2>&1 || echo "No containers running"
    echo ""
    
    # Step 4: Pull latest images
    echo "Step 4: Pulling latest images..."
    echo ""
    if nas_exec "cd $COMPOSE_DIR && $DOCKER_COMPOSE_CMD pull" 2>&1; then
        echo -e "${GREEN}✅ Images pulled successfully${NC}"
    else
        echo -e "${RED}❌ Failed to pull images${NC}"
        return 1
    fi
    
    echo ""
    
    # Step 5: Recreate containers
    echo "Step 5: Recreating containers with updated images..."
    echo ""
    if nas_exec "cd $COMPOSE_DIR && $DOCKER_COMPOSE_CMD up -d" 2>&1; then
        echo -e "${GREEN}✅ Containers recreated successfully${NC}"
    else
        echo -e "${RED}❌ Failed to recreate containers${NC}"
        return 1
    fi
    
    echo ""
    
    # Step 6: Verify
    echo "Step 6: Verifying updated containers..."
    echo ""
    nas_exec "cd $COMPOSE_DIR && $DOCKER_COMPOSE_CMD ps" 2>&1
    
    echo ""
    echo -e "${GREEN}✅ Container update complete!${NC}"
    echo ""
    echo "Updated containers are running with latest images."
}

main "$@"

