#!/bin/bash
# Check system status

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}News Intelligence System v3.0 - Status Check${NC}"
echo "============================================="

# Check version
VERSION=$(cat .version)
echo "Current Version: $VERSION"

echo ""
echo "Development Environment:"
if [ -d ".venv" ]; then
    echo -e "  Virtual Environment: ${GREEN}✅ Active${NC}"
else
    echo -e "  Virtual Environment: ${RED}❌ Not found${NC}"
fi

echo ""
echo "Development Services:"
if pg_isready -h localhost -p 5432 -U newsapp > /dev/null 2>&1; then
    echo -e "  PostgreSQL (dev): ${GREEN}✅ Running${NC}"
else
    echo -e "  PostgreSQL (dev): ${RED}❌ Not running${NC}"
fi

if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo -e "  Redis (dev): ${GREEN}✅ Running${NC}"
else
    echo -e "  Redis (dev): ${RED}❌ Not running${NC}"
fi

if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
    echo -e "  API (dev): ${GREEN}✅ Running${NC}"
else
    echo -e "  API (dev): ${RED}❌ Not running${NC}"
fi

echo ""
echo "Production Services:"
if docker ps | grep -q news-intelligence-postgres-prod; then
    echo -e "  PostgreSQL (prod): ${GREEN}✅ Running${NC}"
else
    echo -e "  PostgreSQL (prod): ${RED}❌ Not running${NC}"
fi

if docker ps | grep -q news-intelligence-redis-prod; then
    echo -e "  Redis (prod): ${GREEN}✅ Running${NC}"
else
    echo -e "  Redis (prod): ${RED}❌ Not running${NC}"
fi

if curl -s http://localhost:8001/api/health/ > /dev/null 2>&1; then
    echo -e "  API (prod): ${GREEN}✅ Running${NC}"
else
    echo -e "  API (prod): ${RED}❌ Not running${NC}"
fi

echo ""
echo "Docker Images:"
if docker images | grep -q news-intelligence-api; then
    echo -e "  Production Image: ${GREEN}✅ Available${NC}"
else
    echo -e "  Production Image: ${RED}❌ Not built${NC}"
fi

echo ""
echo "Access URLs:"
echo "  Development:"
echo "    API: http://localhost:8000"
echo "    Docs: http://localhost:8000/docs"
echo "  Production:"
echo "    API: http://localhost:8001"
echo "    Docs: http://localhost:8001/docs"
