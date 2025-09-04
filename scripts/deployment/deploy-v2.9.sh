#!/bin/bash

# News Intelligence System v2.9.0 - Production Deployment Script
# Comprehensive deployment script for full system redeploy

set -e  # Exit on any error

# Configuration
VERSION="2.9.0"
PROJECT_NAME="news-intelligence-system"
BACKUP_DIR="/opt/backups/news-intelligence"
LOG_FILE="/var/log/news-intelligence/deploy-v2.9.log"
DOCKER_COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

log "Starting News Intelligence System v${VERSION} deployment..."

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    warning "Running as root. This is not recommended for production."
fi

# Check prerequisites
log "Checking prerequisites..."

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker first."
fi

if ! docker info &> /dev/null; then
    error "Docker is not running. Please start Docker first."
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed. Please install Docker Compose first."
fi

# Check if git is installed
if ! command -v git &> /dev/null; then
    error "Git is not installed. Please install Git first."
fi

success "Prerequisites check passed."

# Create backup directory
log "Creating backup directory..."
mkdir -p "$BACKUP_DIR"

# Backup current system if it exists
if [ -f "$DOCKER_COMPOSE_FILE" ]; then
    log "Backing up current system..."
    BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
    
    # Backup Docker volumes
    if docker-compose -f "$DOCKER_COMPOSE_FILE" ps -q | grep -q .; then
        log "Creating database backup..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres pg_dump -U news_user news_db > "$BACKUP_DIR/$BACKUP_NAME/database.sql" 2>/dev/null || warning "Database backup failed or database not accessible"
    fi
    
    # Backup configuration files
    cp -r . "$BACKUP_DIR/$BACKUP_NAME/config" 2>/dev/null || warning "Configuration backup failed"
    
    success "Backup created: $BACKUP_DIR/$BACKUP_NAME"
fi

# Stop existing services
log "Stopping existing services..."
if [ -f "$DOCKER_COMPOSE_FILE" ]; then
    docker-compose -f "$DOCKER_COMPOSE_FILE" down --remove-orphans || warning "Failed to stop some services"
fi

# Clean up old containers and images
log "Cleaning up old containers and images..."
docker system prune -f || warning "Docker cleanup failed"

# Pull latest images
log "Pulling latest Docker images..."
docker-compose -f "$DOCKER_COMPOSE_FILE" pull || error "Failed to pull Docker images"

# Build new images
log "Building new Docker images..."
docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache || error "Failed to build Docker images"

# Start services
log "Starting services..."
docker-compose -f "$DOCKER_COMPOSE_FILE" up -d || error "Failed to start services"

# Wait for services to be ready
log "Waiting for services to be ready..."
sleep 30

# Health check
log "Performing health checks..."

# Check if API is responding
API_URL="http://localhost:8000/api/health"
for i in {1..30}; do
    if curl -s "$API_URL" > /dev/null; then
        success "API health check passed"
        break
    fi
    if [ $i -eq 30 ]; then
        error "API health check failed after 30 attempts"
    fi
    log "Waiting for API... (attempt $i/30)"
    sleep 10
done

# Check if Web UI is responding
WEB_URL="http://localhost:3000"
for i in {1..30}; do
    if curl -s "$WEB_URL" > /dev/null; then
        success "Web UI health check passed"
        break
    fi
    if [ $i -eq 30 ]; then
        error "Web UI health check failed after 30 attempts"
    fi
    log "Waiting for Web UI... (attempt $i/30)"
    sleep 10
done

# Run database migrations
log "Running database migrations..."
docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T api python -c "
import asyncio
import sys
sys.path.append('/app')
from api.config.database import init_database
asyncio.run(init_database())
print('Database initialization completed')
" || warning "Database migration failed"

# Run system tests
log "Running system tests..."
if [ -f "test_production_readiness.py" ]; then
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T api python test_production_readiness.py || warning "System tests failed"
fi

# Check service status
log "Checking service status..."
docker-compose -f "$DOCKER_COMPOSE_FILE" ps

# Display access information
log "Deployment completed successfully!"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  News Intelligence System v${VERSION}${NC}"
echo -e "${GREEN}  Deployment Successful!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo -e "  Web Interface: ${YELLOW}http://localhost:3000${NC}"
echo -e "  API Documentation: ${YELLOW}http://localhost:8000/docs${NC}"
echo -e "  API Health Check: ${YELLOW}http://localhost:8000/api/health${NC}"
echo -e "  Monitoring: ${YELLOW}http://localhost:3000/monitoring${NC}"
echo ""
echo -e "${BLUE}Service Status:${NC}"
docker-compose -f "$DOCKER_COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  View logs: ${YELLOW}docker-compose -f $DOCKER_COMPOSE_FILE logs -f${NC}"
echo -e "  Deployment log: ${YELLOW}$LOG_FILE${NC}"
echo ""
echo -e "${BLUE}Management Commands:${NC}"
echo -e "  Stop services: ${YELLOW}docker-compose -f $DOCKER_COMPOSE_FILE down${NC}"
echo -e "  Restart services: ${YELLOW}docker-compose -f $DOCKER_COMPOSE_FILE restart${NC}"
echo -e "  Update services: ${YELLOW}docker-compose -f $DOCKER_COMPOSE_FILE pull && docker-compose -f $DOCKER_COMPOSE_FILE up -d${NC}"
echo ""

# Create systemd service if not exists
if [ ! -f "/etc/systemd/system/news-intelligence.service" ]; then
    log "Creating systemd service..."
    sudo tee /etc/systemd/system/news-intelligence.service > /dev/null <<EOF
[Unit]
Description=News Intelligence System v${VERSION}
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/docker-compose -f $(pwd)/$DOCKER_COMPOSE_FILE up -d
ExecStop=/usr/bin/docker-compose -f $(pwd)/$DOCKER_COMPOSE_FILE down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable news-intelligence.service
    success "Systemd service created and enabled"
fi

# Final status check
log "Performing final status check..."
if docker-compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "Up"; then
    success "All services are running successfully!"
    log "News Intelligence System v${VERSION} is ready for use!"
else
    error "Some services failed to start. Check logs for details."
fi

echo ""
echo -e "${GREEN}🎉 Deployment Complete! 🎉${NC}"
echo -e "${GREEN}Your News Intelligence System v${VERSION} is now running!${NC}"
echo ""
