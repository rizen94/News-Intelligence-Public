#!/bin/bash

# News Intelligence System v2.9.0 - Local DNS Setup
# Automatically configures local DNS resolution for development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="newsintel.local"
HOSTS_FILE="/etc/hosts"
BACKUP_FILE="/etc/hosts.backup.$(date +%Y%m%d_%H%M%S)"

# Domain entries to add
DOMAINS=(
    "newsintel.local"
    "api.newsintel.local"
    "app.newsintel.local"
    "monitor.newsintel.local"
    "grafana.newsintel.local"
    "metrics.newsintel.local"
    "prometheus.newsintel.local"
)

echo -e "${BLUE}🌐 News Intelligence System - Local DNS Setup${NC}"
echo -e "${BLUE}============================================${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    echo -e "${YELLOW}   Run: sudo ./scripts/setup-local-dns.sh${NC}"
    exit 1
fi

# Backup existing hosts file
echo -e "${BLUE}📋 Backing up existing hosts file...${NC}"
cp "$HOSTS_FILE" "$BACKUP_FILE"
echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"

# Check if entries already exist
echo -e "${BLUE}🔍 Checking for existing entries...${NC}"
EXISTING_ENTRIES=false
for domain in "${DOMAINS[@]}"; do
    if grep -q "$domain" "$HOSTS_FILE"; then
        EXISTING_ENTRIES=true
        echo -e "${YELLOW}⚠️  Found existing entry for $domain${NC}"
    fi
done

if [ "$EXISTING_ENTRIES" = true ]; then
    echo -e "${YELLOW}⚠️  Some entries already exist in hosts file.${NC}"
    read -p "Do you want to remove existing entries and add new ones? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}✅ Keeping existing entries.${NC}"
        exit 0
    fi
    
    # Remove existing entries
    echo -e "${BLUE}🗑️  Removing existing entries...${NC}"
    for domain in "${DOMAINS[@]}"; do
        sed -i "/$domain/d" "$HOSTS_FILE"
    done
fi

# Add new entries
echo -e "${BLUE}➕ Adding News Intelligence System domains...${NC}"
echo "" >> "$HOSTS_FILE"
echo "# News Intelligence System v2.9.0 - Local Development Domains" >> "$HOSTS_FILE"
echo "# Added on $(date)" >> "$HOSTS_FILE"
for domain in "${DOMAINS[@]}"; do
    echo "127.0.0.1 $domain" >> "$HOSTS_FILE"
    echo -e "${GREEN}✅ Added: 127.0.0.1 $domain${NC}"
done

echo ""
echo -e "${GREEN}🎉 Local DNS setup completed successfully!${NC}"
echo ""
echo -e "${YELLOW}📋 Configured domains:${NC}"
for domain in "${DOMAINS[@]}"; do
    echo -e "${YELLOW}   • https://$domain${NC}"
done
echo ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo -e "${YELLOW}   1. Generate SSL certificates: ./scripts/generate-ssl-certs.sh${NC}"
echo -e "${YELLOW}   2. Start the system: docker compose -f docker-compose.yml up -d${NC}"
echo -e "${YELLOW}   3. Access the main application: https://newsintel.local${NC}"
echo ""
echo -e "${BLUE}💡 To remove these entries later, run:${NC}"
echo -e "${BLUE}   sudo sed -i '/newsintel.local/d' /etc/hosts${NC}"
echo ""
echo -e "${BLUE}💡 To restore the original hosts file:${NC}"
echo -e "${BLUE}   sudo cp $BACKUP_FILE /etc/hosts${NC}"
