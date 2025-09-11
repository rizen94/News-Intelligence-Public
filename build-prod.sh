#!/bin/bash
# Build production Docker image

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Building News Intelligence System v3.0 - Production Image${NC}"
echo "=============================================================="

# Get current version
VERSION=$(cat .version)
echo "Building version: $VERSION"

# Build production image
if [ -f "Dockerfile.simple" ]; then
    echo "Using simple Dockerfile..."
    docker build -f Dockerfile.simple -t news-intelligence-api:production -t news-intelligence-api:$VERSION ./api
elif [ -f "Dockerfile.optimized" ]; then
    echo "Using optimized Dockerfile..."
    docker build -f Dockerfile.optimized -t news-intelligence-api:production -t news-intelligence-api:$VERSION ./api
else
    echo "Using standard Dockerfile..."
    docker build -t news-intelligence-api:production -t news-intelligence-api:$VERSION ./api
fi

echo -e "${GREEN}✅ Production image built successfully!${NC}"
echo "Image: news-intelligence-api:production"
echo "Tagged: news-intelligence-api:$VERSION"
