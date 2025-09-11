#!/bin/bash
# Start development server with VENV

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting News Intelligence System v3.0 - Development Mode${NC}"
echo "=============================================================="

# Activate virtual environment
source .venv/bin/activate

# Set development environment variables
export DATABASE_URL="postgresql://newsapp:newsapp_password@localhost:5432/news_intelligence"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"
export LOG_LEVEL="debug"
export DEBUG="true"

# Check if PostgreSQL and Redis are running
echo "Checking dependencies..."

# Check PostgreSQL
if ! pg_isready -h localhost -p 5432 -U newsapp > /dev/null 2>&1; then
    echo "PostgreSQL not running. Starting with Docker..."
    docker run -d --name dev-postgres \
        -e POSTGRES_DB=news_intelligence \
        -e POSTGRES_USER=newsapp \
        -e POSTGRES_PASSWORD=newsapp_password \
        -p 5432:5432 \
        postgres:15-alpine
    sleep 5
fi

# Check Redis
if ! redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo "Redis not running. Starting with Docker..."
    docker run -d --name dev-redis \
        -p 6379:6379 \
        redis:7-alpine
    sleep 3
fi

echo -e "${GREEN}Dependencies ready!${NC}"
echo ""
echo "Starting API server..."
echo "API: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo "Pipeline Monitoring: http://localhost:8000/api/pipeline-monitoring"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the API
cd api
python main.py
