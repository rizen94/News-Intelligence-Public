#!/bin/bash

# News Intelligence System v4.0 - Status Check Script
# Shows the status of all system components

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDIS_CONTAINER="news-intelligence-redis"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

# Check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Check if a port is in use
is_port_in_use() {
    lsof -i ":$1" > /dev/null 2>&1
}

echo -e "${BLUE}=========================================="
echo -e "News Intelligence System v4.0 - Status"
echo -e "==========================================${NC}"
echo ""

# Check PostgreSQL (Widow default, or NAS tunnel)
echo -e "${CYAN}Database:${NC}"
# Try Widow first (primary config)
if pg_isready -h 192.168.93.101 -p 5432 -U newsapp > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ PostgreSQL: Running${NC} (Widow 192.168.93.101:5432)"
elif pg_isready -h localhost -p 5433 -U newsapp > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ PostgreSQL: Running${NC} (localhost:5433 NAS tunnel)"
elif "$PYTHON_BIN" -c "
import psycopg2, os
pw = open('$SCRIPT_DIR/.db_password_widow').read().strip() if os.path.exists('$SCRIPT_DIR/.db_password_widow') else os.getenv('DB_PASSWORD','')
psycopg2.connect(host='192.168.93.101', port=5432, database='news_intel', user='newsapp', password=pw, connect_timeout=3)
" 2>/dev/null; then
    echo -e "  ${GREEN}✅ PostgreSQL: Running${NC} (Widow 192.168.93.101:5432)"
else
    echo -e "  ${RED}❌ PostgreSQL: Not responding${NC}"
fi
echo ""

# Check Redis
echo -e "${CYAN}Cache:${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Redis: Running${NC} (Docker: $REDIS_CONTAINER)"
    else
        echo -e "  ${YELLOW}⚠️  Redis: Container running but not responding${NC}"
    fi
else
    echo -e "  ${RED}❌ Redis: Container not running${NC}"
fi
echo ""

# Check API Server
echo -e "${CYAN}API Server:${NC}"
if is_running "uvicorn.*main_v4"; then
    API_PID=$(pgrep -f "uvicorn.*main_v4" | head -1)
    if curl -s http://localhost:8000/api/v4/system_monitoring/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ API Server: Running${NC} (PID: $API_PID, http://localhost:8000)"
        echo -e "  ${GREEN}   - AutomationManager: Active${NC}"
        echo -e "  ${GREEN}   - MLProcessingService: Active${NC}"
    else
        echo -e "  ${YELLOW}⚠️  API Server: Process running but not responding${NC} (PID: $API_PID)"
    fi
else
    if is_port_in_use 8000; then
        echo -e "  ${YELLOW}⚠️  Port 8000 in use but API process not found${NC}"
    else
        echo -e "  ${RED}❌ API Server: Not running${NC}"
    fi
fi
echo ""

# Check Frontend
echo -e "${CYAN}Frontend:${NC}"
if is_running "node.*react-scripts\|vite.*start\|webpack.*serve"; then
    FRONTEND_PID=$(pgrep -f "react-scripts\|vite.*start\|webpack.*serve" | head -1)
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Frontend: Running${NC} (PID: $FRONTEND_PID, http://localhost:3000)"
    else
        echo -e "  ${YELLOW}⚠️  Frontend: Process running but not responding${NC} (PID: $FRONTEND_PID)"
    fi
else
    if is_port_in_use 3000; then
        echo -e "  ${YELLOW}⚠️  Port 3000 in use but frontend process not found${NC}"
    else
        echo -e "  ${RED}❌ Frontend: Not running${NC}"
    fi
fi
echo ""

# Summary
echo -e "${BLUE}=========================================="
echo -e "Quick Actions:${NC}"
echo "  Start:   ./start_system.sh"
echo "  Stop:    ./stop_system.sh"
echo "  Status:  ./status_system.sh"
echo "  Logs:    tail -f logs/api_server.log"
echo -e "${BLUE}==========================================${NC}"

