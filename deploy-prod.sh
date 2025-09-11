#!/bin/bash
# Deploy production system

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Deploying News Intelligence System v3.0 - Production${NC}"
echo "======================================================="

# Get current version
VERSION=$(cat .version)
echo "Deploying version: $VERSION"

# Stop existing production containers
echo "Stopping existing production containers..."
docker stop news-intelligence-postgres-prod news-intelligence-redis-prod news-intelligence-api-prod 2>/dev/null || true
docker rm news-intelligence-postgres-prod news-intelligence-redis-prod news-intelligence-api-prod 2>/dev/null || true

# Start PostgreSQL
echo "Starting PostgreSQL..."
docker run -d \
    --name news-intelligence-postgres-prod \
    -e POSTGRES_DB=news_intelligence \
    -e POSTGRES_USER=newsapp \
    -e POSTGRES_PASSWORD=newsapp_password \
    -p 5433:5432 \
    -v postgres_prod_data:/var/lib/postgresql/data \
    postgres:15-alpine

# Start Redis
echo "Starting Redis..."
docker run -d \
    --name news-intelligence-redis-prod \
    -p 6380:6379 \
    redis:7-alpine

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Start API
echo "Starting API..."
docker run -d \
    --name news-intelligence-api-prod \
    --link news-intelligence-postgres-prod:postgres \
    --link news-intelligence-redis-prod:redis \
    -e DATABASE_URL=postgresql://newsapp:newsapp_password@postgres:5432/news_intelligence \
    -e REDIS_URL=redis://redis:6379/0 \
    -e ENVIRONMENT=production \
    -p 8001:8000 \
    news-intelligence-api:production

# Wait for API
echo "Waiting for API to start..."
sleep 15

# Test API
if curl -s http://localhost:8001/api/health/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Production deployment successful!${NC}"
    echo ""
    echo "Production URLs:"
    echo "  API: http://localhost:8001"
    echo "  Docs: http://localhost:8001/docs"
    echo "  Pipeline Monitoring: http://localhost:8001/api/pipeline-monitoring"
    echo ""
    echo "Development URLs:"
    echo "  API: http://localhost:8000"
    echo "  Docs: http://localhost:8000/docs"
else
    echo -e "${RED}❌ Production deployment failed!${NC}"
    echo "API logs:"
    docker logs news-intelligence-api-prod
    exit 1
fi
