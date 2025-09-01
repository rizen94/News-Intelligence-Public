#!/bin/bash

# 🚀 News Intelligence System v3.0 - New Hardware Deployment Script
# Run this script on the new hardware to deploy the system

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo -e "${BLUE}🚀 Deploying News Intelligence System v3.0${NC}"
echo ""

# Check prerequisites
print_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_warning "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    print_warning "Please log out and back in, then run this script again"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_warning "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

print_status "Prerequisites check passed"

# Extract migration package
print_info "Extracting migration package..."
tar -xzf news_system_migration_*.tar.gz
print_status "Migration package extracted"

# Set up environment
print_info "Setting up environment..."
if [ -f "env_backup_*" ]; then
    cp env_backup_* .env
    print_warning "Please review and update .env file with new hardware settings"
else
    print_warning "No environment backup found. Please create .env file manually"
fi

# Import database
print_info "Starting PostgreSQL container..."
docker-compose up -d postgres
sleep 15

print_info "Creating database..."
docker exec news-system-postgres createdb -U newsapp news_system || true

print_info "Importing database..."
if [ -f "database_backup_*.sql" ]; then
    docker exec -i news-system-postgres psql -U newsapp -d news_system < database_backup_*.sql
    print_status "Database imported successfully"
else
    print_warning "No database backup found"
fi

# Start all services
print_info "Starting all services..."
docker-compose up -d

print_info "Waiting for services to start..."
sleep 20

# Verify deployment
print_info "Verifying deployment..."

# Check if frontend is accessible
if curl -s http://localhost:8000/ | grep -q "React App"; then
    print_status "Frontend is accessible"
else
    print_warning "Frontend may not be fully loaded yet"
fi

# Check API endpoints
if curl -s http://localhost:8000/api/articles?page=1&per_page=1 | grep -q "articles"; then
    print_status "API endpoints are working"
else
    print_warning "API endpoints may not be fully loaded yet"
fi

print_status "Deployment completed!"
echo ""
echo -e "${BLUE}🌐 Access your system at: http://localhost:8000${NC}"
echo -e "${BLUE}📊 API available at: http://localhost:8000/api/${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review and update .env file with new hardware settings"
echo "2. Configure RSS feeds in api/config/rss_sources.json"
echo "3. Set up monitoring and backup strategies"
echo "4. Review DEPLOYMENT.md for additional configuration options"
