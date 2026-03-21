#!/bin/bash
# Check Container Credentials
# Compares credentials in scripts vs actual container configuration

set -e

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
DOCKER_PATH="/usr/local/bin/docker"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "🔐 Container Credentials Check"
echo "=============================="
echo ""

# Function to execute command on NAS
nas_exec() {
    ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "$1"
}

echo "1. Credentials in start_system.sh:"
echo "----------------------------------"
echo -e "${CYAN}Database Configuration:${NC}"
grep -E "DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD" "$PROJECT_ROOT/start_system.sh" | grep -v "^#" | head -5 | sed 's/^/  /'
echo ""

echo "2. Credentials in docker-compose.yml:"
echo "--------------------------------------"
echo -e "${CYAN}PostgreSQL Service:${NC}"
grep -A 5 "postgres:" "$PROJECT_ROOT/docker-compose.yml" | grep -E "POSTGRES|environment:" | sed 's/^/  /' || echo "  No postgres service found"
echo ""

echo "3. Actual Container Configuration on NAS:"
echo "------------------------------------------"
echo ""

# Check for postgres container
POSTGRES_CONTAINER=$(nas_exec "$DOCKER_PATH ps -a --format '{{.Names}}' | grep -iE 'postgres|news' | head -1" 2>&1)

if [ -n "$POSTGRES_CONTAINER" ] && [ "$POSTGRES_CONTAINER" != "postgres" ]; then
    echo -e "${CYAN}Found container: $POSTGRES_CONTAINER${NC}"
    echo ""
    echo "Environment Variables:"
    nas_exec "$DOCKER_PATH inspect $POSTGRES_CONTAINER --format '{{range .Config.Env}}{{println .}}{{end}}'" 2>&1 | grep -iE 'POSTGRES|DB|PASSWORD|USER' | sed 's/^/  /' || echo "  No relevant env vars found"
    echo ""
    echo "Port Mappings:"
    nas_exec "$DOCKER_PATH inspect $POSTGRES_CONTAINER --format '{{range \$p, \$conf := .NetworkSettings.Ports}}{{\$p}} -> {{(index \$conf 0).HostPort}}{{end}}'" 2>&1 | sed 's/^/  /' || echo "  No port mappings"
    echo ""
else
    echo -e "${YELLOW}⚠️  No postgres container found on NAS${NC}"
    echo ""
    echo "Checking all containers:"
    nas_exec "$DOCKER_PATH ps -a --format 'table {{.Names}}\t{{.Image}}'" 2>&1 | head -10
    echo ""
fi

echo "4. Credential Comparison:"
echo "-------------------------"
echo ""

# Extract credentials from start_system.sh
DB_HOST=$(grep "export DB_HOST" "$PROJECT_ROOT/start_system.sh" | head -1 | sed "s/.*DB_HOST.*=//" | tr -d '${}"' | cut -d: -f1)
DB_PORT=$(grep "export DB_PORT" "$PROJECT_ROOT/start_system.sh" | head -1 | sed "s/.*DB_PORT.*=//" | tr -d '${}"' | cut -d: -f1)
DB_NAME=$(grep "export DB_NAME" "$PROJECT_ROOT/start_system.sh" | head -1 | sed "s/.*DB_NAME.*=//" | tr -d '${}"' | cut -d: -f1)
DB_USER=$(grep "export DB_USER" "$PROJECT_ROOT/start_system.sh" | head -1 | sed "s/.*DB_USER.*=//" | tr -d '${}"' | cut -d: -f1)
DB_PASSWORD=$(grep "export DB_PASSWORD" "$PROJECT_ROOT/start_system.sh" | head -1 | sed "s/.*DB_PASSWORD.*=//" | tr -d '${}"' | cut -d: -f1)

echo -e "${CYAN}Script Configuration:${NC}"
echo "  DB_HOST: ${DB_HOST:-192.168.93.100}"
echo "  DB_PORT: ${DB_PORT:-5432}"
echo "  DB_NAME: ${DB_NAME:-news_intelligence}"
echo "  DB_USER: ${DB_USER:-newsapp}"
echo "  DB_PASSWORD: ${DB_PASSWORD:-newsapp_password}"
echo ""

# Extract from docker-compose.yml if exists
if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    COMPOSE_DB=$(grep -A 3 "POSTGRES_DB:" "$PROJECT_ROOT/docker-compose.yml" | head -1 | sed 's/.*POSTGRES_DB: *//' | tr -d ' ')
    COMPOSE_USER=$(grep -A 3 "POSTGRES_USER:" "$PROJECT_ROOT/docker-compose.yml" | head -1 | sed 's/.*POSTGRES_USER: *//' | tr -d ' ')
    COMPOSE_PASS=$(grep -A 3 "POSTGRES_PASSWORD:" "$PROJECT_ROOT/docker-compose.yml" | head -1 | sed 's/.*POSTGRES_PASSWORD: *//' | tr -d ' ')
    
    echo -e "${CYAN}Docker Compose Configuration:${NC}"
    echo "  POSTGRES_DB: ${COMPOSE_DB:-not set}"
    echo "  POSTGRES_USER: ${COMPOSE_USER:-not set}"
    echo "  POSTGRES_PASSWORD: ${COMPOSE_PASS:-not set}"
    echo ""
fi

# Check actual container if it exists
if [ -n "$POSTGRES_CONTAINER" ]; then
    echo -e "${CYAN}Actual Container Configuration:${NC}"
    CONTAINER_ENV=$(nas_exec "$DOCKER_PATH inspect $POSTGRES_CONTAINER --format '{{range .Config.Env}}{{println .}}{{end}}'" 2>&1)
    
    CONTAINER_DB=$(echo "$CONTAINER_ENV" | grep "POSTGRES_DB=" | cut -d= -f2)
    CONTAINER_USER=$(echo "$CONTAINER_ENV" | grep "POSTGRES_USER=" | cut -d= -f2)
    CONTAINER_PASS=$(echo "$CONTAINER_ENV" | grep "POSTGRES_PASSWORD=" | cut -d= -f2)
    
    echo "  POSTGRES_DB: ${CONTAINER_DB:-not set}"
    echo "  POSTGRES_USER: ${CONTAINER_USER:-not set}"
    echo "  POSTGRES_PASSWORD: ${CONTAINER_PASS:-not set}"
    echo ""
    
    # Compare
    echo -e "${CYAN}Comparison:${NC}"
    if [ "$DB_NAME" = "$CONTAINER_DB" ] || [ -z "$CONTAINER_DB" ]; then
        echo -e "  ${GREEN}✅ Database name matches${NC}"
    else
        echo -e "  ${RED}❌ Database name mismatch: script=$DB_NAME, container=$CONTAINER_DB${NC}"
    fi
    
    if [ "$DB_USER" = "$CONTAINER_USER" ] || [ -z "$CONTAINER_USER" ]; then
        echo -e "  ${GREEN}✅ Username matches${NC}"
    else
        echo -e "  ${RED}❌ Username mismatch: script=$DB_USER, container=$CONTAINER_USER${NC}"
    fi
    
    if [ "$DB_PASSWORD" = "$CONTAINER_PASS" ] || [ -z "$CONTAINER_PASS" ]; then
        echo -e "  ${GREEN}✅ Password matches${NC}"
    else
        echo -e "  ${RED}❌ Password mismatch${NC}"
    fi
fi

echo ""
echo "5. Recommended Credentials for Containers:"
echo "-------------------------------------------"
echo "Based on start_system.sh configuration:"
echo "  POSTGRES_DB: ${DB_NAME:-news_intelligence}"
echo "  POSTGRES_USER: ${DB_USER:-newsapp}"
echo "  POSTGRES_PASSWORD: ${DB_PASSWORD:-newsapp_password}"
echo "  Port: ${DB_PORT:-5432}"
echo ""

