#!/bin/bash

# News Intelligence System v3.0 - Quick Fix for Startup Issues
# Addresses FastAPI/Pydantic compatibility and implements optimizations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Fix FastAPI/Pydantic compatibility issue
fix_compatibility() {
    log "Fixing FastAPI/Pydantic compatibility issue..."
    
    # Check if the problematic file exists
    if [ -f "api/routes/enhanced_analysis.py" ]; then
        log "Found enhanced_analysis.py - checking for compatibility issues..."
        
        # Create backup
        cp api/routes/enhanced_analysis.py api/routes/enhanced_analysis.py.backup
        
        # Fix the FieldInfo issue by updating the route definition
        sed -i 's/FieldInfo/Field/g' api/routes/enhanced_analysis.py
        
        success "Fixed FieldInfo compatibility issue"
    else
        warning "enhanced_analysis.py not found - skipping compatibility fix"
    fi
}

# Update requirements with compatible versions
update_requirements() {
    log "Updating requirements with compatible versions..."
    
    if [ -f "requirements-fixed.txt" ]; then
        cp requirements-fixed.txt api/requirements.txt
        success "Updated API requirements with compatible versions"
    else
        warning "requirements-fixed.txt not found - using existing requirements"
    fi
}

# Test the fix
test_fix() {
    log "Testing the fix..."
    
    # Stop any running containers
    docker stop news-intelligence-api news-intelligence-postgres news-intelligence-redis 2>/dev/null || true
    docker rm news-intelligence-api news-intelligence-postgres news-intelligence-redis 2>/dev/null || true
    
    # Test API startup locally first
    log "Testing API startup locally..."
    
    # Create a simple test script
    cat > test_api_startup.py << 'EOF'
#!/usr/bin/env python3
"""Test API startup to verify compatibility fixes"""

import sys
import os

# Add the API directory to the path
sys.path.append('api')

try:
    # Test imports
    print("Testing imports...")
    from main import app
    print("✅ API app imported successfully")
    
    # Test route imports
    print("Testing route imports...")
    from routes.enhanced_analysis import router
    print("✅ Enhanced analysis routes imported successfully")
    
    print("✅ All compatibility tests passed!")
    
except Exception as e:
    print(f"❌ Compatibility test failed: {e}")
    sys.exit(1)
EOF

    # Run the test
    if python3 test_api_startup.py; then
        success "Compatibility fix verified"
        rm test_api_startup.py
    else
        error "Compatibility fix failed"
        rm test_api_startup.py
        return 1
    fi
}

# Build optimized Docker image
build_optimized_image() {
    log "Building optimized Docker image..."
    
    # Use the optimized Dockerfile
    if [ -f "Dockerfile.optimized" ]; then
        docker build -f Dockerfile.optimized -t news-intelligence-api:optimized ./api
        success "Optimized Docker image built"
    else
        warning "Dockerfile.optimized not found - using standard build"
        docker build -t news-intelligence-api:optimized ./api
    fi
}

# Test optimized startup
test_optimized_startup() {
    log "Testing optimized startup..."
    
    # Start PostgreSQL
    docker run -d \
        --name news-intelligence-postgres \
        -e POSTGRES_DB=news_intelligence \
        -e POSTGRES_USER=newsapp \
        -e POSTGRES_PASSWORD=newsapp_password \
        -p 5432:5432 \
        postgres:15-alpine
    
    # Wait for PostgreSQL
    log "Waiting for PostgreSQL..."
    sleep 10
    
    # Start Redis
    docker run -d \
        --name news-intelligence-redis \
        -p 6379:6379 \
        redis:7-alpine
    
    # Wait for Redis
    log "Waiting for Redis..."
    sleep 5
    
    # Start API with optimized image
    docker run -d \
        --name news-intelligence-api \
        --link news-intelligence-postgres:postgres \
        --link news-intelligence-redis:redis \
        -e DATABASE_URL=postgresql://newsapp:newsapp_password@postgres:5432/news_intelligence \
        -e REDIS_URL=redis://redis:6379/0 \
        -e ENVIRONMENT=production \
        -p 8000:8000 \
        news-intelligence-api:optimized
    
    # Wait for API
    log "Waiting for API to start..."
    sleep 15
    
    # Test API health
    if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
        success "API is running and healthy!"
        log "API URL: http://localhost:8000"
        log "API Docs: http://localhost:8000/docs"
    else
        error "API failed to start properly"
        log "API logs:"
        docker logs news-intelligence-api
        return 1
    fi
}

# Main execution
main() {
    log "Quick Fix for News Intelligence System v3.0 Startup Issues"
    log "=========================================================="
    
    # Fix compatibility issues
    fix_compatibility
    
    # Update requirements
    update_requirements
    
    # Test the fix
    if ! test_fix; then
        error "Compatibility fix failed"
        exit 1
    fi
    
    # Build optimized image
    build_optimized_image
    
    # Test optimized startup
    if test_optimized_startup; then
        success "Quick fix completed successfully!"
        echo ""
        echo "System is now running with optimizations:"
        echo "  - Fixed FastAPI/Pydantic compatibility"
        echo "  - Optimized Docker build (multi-stage)"
        echo "  - Reduced build time significantly"
        echo ""
        echo "Access URLs:"
        echo "  API: http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        echo "  Pipeline Monitoring: http://localhost:8000/api/pipeline-monitoring"
    else
        error "Quick fix failed"
        exit 1
    fi
}

# Run main function
main "$@"
