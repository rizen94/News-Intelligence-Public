#!/bin/bash

# News Intelligence System v3.0 - Hybrid Development/Production System
# VENV for development + automated production builds + stable version management

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR=".venv"
PROD_IMAGE="news-intelligence-api:production"
DEV_IMAGE="news-intelligence-api:development"
VERSION_FILE=".version"
BUILD_LOG="logs/build.log"
PROD_LOG="logs/production.log"

# Create necessary directories
mkdir -p logs

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$BUILD_LOG"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$BUILD_LOG"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$BUILD_LOG"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$BUILD_LOG"
}

info() {
    echo -e "${PURPLE}[INFO]${NC} $1" | tee -a "$BUILD_LOG"
}

# Initialize version management
init_version() {
    if [ ! -f "$VERSION_FILE" ]; then
        echo "1.0.0" > "$VERSION_FILE"
        log "Initialized version management with v1.0.0"
    else
        CURRENT_VERSION=$(cat "$VERSION_FILE")
        log "Current version: $CURRENT_VERSION"
    fi
}

# Increment version
increment_version() {
    CURRENT_VERSION=$(cat "$VERSION_FILE")
    IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
    MAJOR=${VERSION_PARTS[0]}
    MINOR=${VERSION_PARTS[1]}
    PATCH=${VERSION_PARTS[2]}
    
    # Increment patch version
    NEW_PATCH=$((PATCH + 1))
    NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"
    
    echo "$NEW_VERSION" > "$VERSION_FILE"
    log "Version incremented to: $NEW_VERSION"
    echo "$NEW_VERSION"
}

# Set up development environment
setup_dev_environment() {
    log "Setting up development environment..."
    
    # Check if VENV already exists
    if [ -d "$VENV_DIR" ]; then
        warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            success "Using existing virtual environment"
            return 0
        fi
    fi
    
    # Create virtual environment
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install development dependencies
    if [ -f "requirements-fixed.txt" ]; then
        pip install -r requirements-fixed.txt
    else
        pip install -r api/requirements.txt
    fi
    
    # Install additional development tools
    pip install pytest black flake8 mypy
    
    success "Development environment created"
}

# Create development scripts
create_dev_scripts() {
    log "Creating development scripts..."
    
    # Development start script
    cat > start-dev.sh << 'EOF'
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
EOF

    # Development test script
    cat > test-dev.sh << 'EOF'
#!/bin/bash
# Test development environment

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Testing News Intelligence System v3.0 - Development Environment${NC}"
echo "====================================================================="

# Activate virtual environment
source .venv/bin/activate

# Test imports
echo "Testing imports..."
python -c "import fastapi; print('✅ FastAPI:', fastapi.__version__)"
python -c "import pydantic; print('✅ Pydantic:', pydantic.__version__)"
python -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)"

# Test API creation
echo ""
echo "Testing API creation..."
cd api
python -c "
import sys
sys.path.append('.')
from main import app
print('✅ API app created successfully')
"

# Test route imports
echo "Testing route imports..."
python -c "
from routes.health import router as health_router
from routes.articles import router as articles_router
from routes.pipeline_monitoring import router as pipeline_router
print('✅ All routes imported successfully')
"

echo ""
echo -e "${GREEN}✅ All development tests passed!${NC}"
echo ""
echo "Development environment is ready!"
echo "Run './start-dev.sh' to start the development server"
EOF

    # Production build script
    cat > build-prod.sh << 'EOF'
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
if [ -f "Dockerfile.optimized" ]; then
    echo "Using optimized Dockerfile..."
    docker build -f Dockerfile.optimized -t news-intelligence-api:production -t news-intelligence-api:$VERSION ./api
else
    echo "Using standard Dockerfile..."
    docker build -t news-intelligence-api:production -t news-intelligence-api:$VERSION ./api
fi

echo -e "${GREEN}✅ Production image built successfully!${NC}"
echo "Image: news-intelligence-api:production"
echo "Tagged: news-intelligence-api:$VERSION"
EOF

    # Production deployment script
    cat > deploy-prod.sh << 'EOF'
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
EOF

    # Status check script
    cat > status.sh << 'EOF'
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
EOF

    # Make scripts executable
    chmod +x start-dev.sh test-dev.sh build-prod.sh deploy-prod.sh status.sh
    
    success "Development scripts created"
}

# Set up automated production builds
setup_prod_automation() {
    log "Setting up automated production builds..."
    
    # Create production build automation script
    cat > auto-build-prod.sh << 'EOF'
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
EOF

    # Create systemd service for production automation
    cat > news-intelligence-auto-build.service << 'EOF'
[Unit]
Description=News Intelligence System Auto Build
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=pete
WorkingDirectory=/home/pete/Documents/Projects/News Intelligence
ExecStart=/home/pete/Documents/Projects/News Intelligence/auto-build-prod.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    chmod +x auto-build-prod.sh
    
    success "Production automation setup complete"
}

# Main setup function
main() {
    log "Setting up Hybrid Development/Production System"
    log "=============================================="
    
    # Initialize version management
    init_version
    
    # Set up development environment
    setup_dev_environment
    
    # Create development scripts
    create_dev_scripts
    
    # Set up production automation
    setup_prod_automation
    
    echo ""
    success "Hybrid system setup complete!"
    echo ""
    echo "🎯 Development Environment:"
    echo "  - Virtual environment: .venv/"
    echo "  - Fast iteration: ./start-dev.sh"
    echo "  - Testing: ./test-dev.sh"
    echo "  - API: http://localhost:8000"
    echo ""
    echo "🚀 Production Environment:"
    echo "  - Automated builds: auto-build-prod.sh"
    echo "  - Manual build: ./build-prod.sh"
    echo "  - Manual deploy: ./deploy-prod.sh"
    echo "  - API: http://localhost:8001"
    echo ""
    echo "📊 Monitoring:"
    echo "  - Status check: ./status.sh"
    echo "  - Build logs: logs/build.log"
    echo "  - Production logs: logs/production.log"
    echo ""
    echo "🔄 Version Management:"
    echo "  - Current version: $(cat .version)"
    echo "  - Auto-increment on builds"
    echo "  - Stable production deployments"
    echo ""
    echo "Next steps:"
    echo "1. Run './start-dev.sh' to start development"
    echo "2. Run './deploy-prod.sh' to deploy production"
    echo "3. Run './status.sh' to check system status"
}

# Run main function
main "$@"
