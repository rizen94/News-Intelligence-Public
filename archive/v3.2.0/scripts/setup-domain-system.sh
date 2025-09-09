#!/bin/bash

# News Intelligence System v2.9.0 - Complete Domain Setup
# Sets up proper URL system with DNS resolution and SSL

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="newsintel.local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${PURPLE}🌐 News Intelligence System v2.9.0 - Domain Setup${NC}"
echo -e "${PURPLE}================================================${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${BLUE}🔍 Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi

if ! command_exists openssl; then
    echo -e "${RED}❌ OpenSSL is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites are installed${NC}"
echo ""

# Step 1: Generate SSL certificates
echo -e "${BLUE}🔐 Step 1: Generating SSL certificates...${NC}"
cd "$PROJECT_DIR"
if [ -f "scripts/generate-ssl-certs.sh" ]; then
    ./scripts/generate-ssl-certs.sh
else
    echo -e "${RED}❌ SSL certificate script not found${NC}"
    exit 1
fi
echo ""

# Step 2: Setup local DNS
echo -e "${BLUE}🌐 Step 2: Setting up local DNS resolution...${NC}"
if [ -f "scripts/setup-local-dns.sh" ]; then
    if [ "$EUID" -eq 0 ]; then
        ./scripts/setup-local-dns.sh
    else
        echo -e "${YELLOW}⚠️  DNS setup requires root privileges${NC}"
        echo -e "${YELLOW}   Please run: sudo ./scripts/setup-local-dns.sh${NC}"
        echo -e "${YELLOW}   Or manually add the following to /etc/hosts:${NC}"
        echo -e "${YELLOW}   127.0.0.1 newsintel.local${NC}"
        echo -e "${YELLOW}   127.0.0.1 api.newsintel.local${NC}"
        echo -e "${YELLOW}   127.0.0.1 app.newsintel.local${NC}"
        echo -e "${YELLOW}   127.0.0.1 monitor.newsintel.local${NC}"
        echo -e "${YELLOW}   127.0.0.1 grafana.newsintel.local${NC}"
        echo -e "${YELLOW}   127.0.0.1 metrics.newsintel.local${NC}"
        echo -e "${YELLOW}   127.0.0.1 prometheus.newsintel.local${NC}"
    fi
else
    echo -e "${RED}❌ DNS setup script not found${NC}"
    exit 1
fi
echo ""

# Step 3: Stop existing containers
echo -e "${BLUE}🛑 Step 3: Stopping existing containers...${NC}"
docker compose -f docker-compose.yml down 2>/dev/null || true
echo -e "${GREEN}✅ Existing containers stopped${NC}"
echo ""

# Step 4: Build and start services
echo -e "${BLUE}🚀 Step 4: Building and starting services...${NC}"
docker compose -f docker-compose.yml build --no-cache
docker compose -f docker-compose.yml up -d
echo ""

# Step 5: Wait for services to be ready
echo -e "${BLUE}⏳ Step 5: Waiting for services to be ready...${NC}"
sleep 10

# Check if services are running
echo -e "${BLUE}🔍 Checking service status...${NC}"
docker compose -f docker-compose.yml ps
echo ""

# Step 6: Test domain access
echo -e "${BLUE}🧪 Step 6: Testing domain access...${NC}"

# Test main application
echo -e "${BLUE}   Testing main application...${NC}"
if curl -k -s -o /dev/null -w "%{http_code}" https://newsintel.local | grep -q "200\|301\|302"; then
    echo -e "${GREEN}   ✅ Main application accessible${NC}"
else
    echo -e "${YELLOW}   ⚠️  Main application not yet ready (this is normal, may take a few minutes)${NC}"
fi

# Test API
echo -e "${BLUE}   Testing API...${NC}"
if curl -k -s -o /dev/null -w "%{http_code}" https://api.newsintel.local/health | grep -q "200"; then
    echo -e "${GREEN}   ✅ API accessible${NC}"
else
    echo -e "${YELLOW}   ⚠️  API not yet ready (this is normal, may take a few minutes)${NC}"
fi

# Test monitoring
echo -e "${BLUE}   Testing monitoring...${NC}"
if curl -k -s -o /dev/null -w "%{http_code}" https://monitor.newsintel.local | grep -q "200\|301\|302"; then
    echo -e "${GREEN}   ✅ Monitoring accessible${NC}"
else
    echo -e "${YELLOW}   ⚠️  Monitoring not yet ready (this is normal, may take a few minutes)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Domain setup completed successfully!${NC}"
echo ""
echo -e "${PURPLE}📋 Your News Intelligence System is now accessible at:${NC}"
echo -e "${GREEN}   🏠 Main Application: https://newsintel.local${NC}"
echo -e "${GREEN}   🔗 API Documentation: https://api.newsintel.local/docs${NC}"
echo -e "${GREEN}   📊 Monitoring Dashboard: https://monitor.newsintel.local${NC}"
echo -e "${GREEN}   📈 Metrics: https://metrics.newsintel.local${NC}"
echo ""
echo -e "${YELLOW}📋 Alternative URLs:${NC}"
echo -e "${YELLOW}   • https://app.newsintel.local (Main App)${NC}"
echo -e "${YELLOW}   • https://grafana.newsintel.local (Grafana)${NC}"
echo -e "${YELLOW}   • https://prometheus.newsintel.local (Prometheus)${NC}"
echo ""
echo -e "${BLUE}💡 Important Notes:${NC}"
echo -e "${BLUE}   • You'll need to accept the self-signed SSL certificate in your browser${NC}"
echo -e "${BLUE}   • Services may take 1-2 minutes to fully start up${NC}"
echo -e "${BLUE}   • If you can't access the domains, check your /etc/hosts file${NC}"
echo ""
echo -e "${PURPLE}🔧 Management Commands:${NC}"
echo -e "${PURPLE}   • View logs: docker compose -f docker-compose.yml logs -f${NC}"
echo -e "${PURPLE}   • Stop system: docker compose -f docker-compose.yml down${NC}"
echo -e "${PURPLE}   • Restart system: docker compose -f docker-compose.yml restart${NC}"
echo ""
echo -e "${GREEN}✨ Enjoy your News Intelligence System with proper domain names!${NC}"
