#!/bin/bash
# Automated production build and deployment

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BUILD_LOG="logs/auto-build.log"
VERSION_FILE=".version"
PROD_IMAGE="news-intelligence-api:production"

# Logging
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$BUILD_LOG"
}

# Check if rebuild is needed
check_rebuild_needed() {
    # Check if source files have changed since last build
    if [ -f "logs/last-build" ]; then
        LAST_BUILD=$(cat logs/last-build)
        if find api -name "*.py" -newer "logs/last-build" | grep -q .; then
            log "Source files changed - rebuild needed"
            return 0
        else
            log "No changes detected - skipping rebuild"
            return 1
        fi
    else
        log "No previous build found - rebuild needed"
        return 0
    fi
}

# Build production image
build_production() {
    log "Building production image..."
    
    # Increment version
    VERSION=$(cat "$VERSION_FILE")
    NEW_VERSION=$(echo "$VERSION" | awk -F. '{$NF = $NF + 1;} 1' | sed 's/ /./g')
    echo "$NEW_VERSION" > "$VERSION_FILE"
    
    # Build image
    if [ -f "Dockerfile.optimized" ]; then
        docker build -f Dockerfile.optimized -t "$PROD_IMAGE" -t "news-intelligence-api:$NEW_VERSION" ./api
    else
        docker build -t "$PROD_IMAGE" -t "news-intelligence-api:$NEW_VERSION" ./api
    fi
    
    # Update last build timestamp
    touch logs/last-build
    
    log "Production image built: $NEW_VERSION"
}

# Deploy to production
deploy_production() {
    log "Deploying to production..."
    
    # Stop existing production API
    docker stop news-intelligence-api-prod 2>/dev/null || true
    docker rm news-intelligence-api-prod 2>/dev/null || true
    
    # Start new production API
    docker run -d \
        --name news-intelligence-api-prod \
        --link news-intelligence-postgres-prod:postgres \
        --link news-intelligence-redis-prod:redis \
        -e DATABASE_URL=postgresql://newsapp:newsapp_password@postgres:5432/news_intelligence \
        -e REDIS_URL=redis://redis:6379/0 \
        -e ENVIRONMENT=production \
        -p 8001:8000 \
        "$PROD_IMAGE"
    
    # Wait for API to start
    sleep 15
    
    # Test API
    if curl -s http://localhost:8001/api/health/ > /dev/null 2>&1; then
        log "✅ Production deployment successful"
    else
        log "❌ Production deployment failed"
        docker logs news-intelligence-api-prod
        return 1
    fi
}

# Main automation loop
main() {
    log "Starting automated production build system..."
    
    while true; do
        if check_rebuild_needed; then
            build_production
            deploy_production
        fi
        
        # Check every 5 minutes
        sleep 300
    done
}

# Run main function
main "$@"
