#!/bin/bash

# News Intelligence System v2.9.0 - SSL Certificate Generator
# Generates self-signed SSL certificates for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="newsintel.local"
SSL_DIR="api/docker/nginx/ssl"
CERT_FILE="$SSL_DIR/$DOMAIN.crt"
KEY_FILE="$SSL_DIR/$DOMAIN.key"

echo -e "${BLUE}🔐 News Intelligence System - SSL Certificate Generator${NC}"
echo -e "${BLUE}====================================================${NC}"

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DIR"

# Check if certificates already exist
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo -e "${YELLOW}⚠️  SSL certificates already exist.${NC}"
    read -p "Do you want to regenerate them? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}✅ Using existing certificates.${NC}"
        exit 0
    fi
fi

echo -e "${BLUE}📝 Generating SSL certificates for domain: $DOMAIN${NC}"

# Generate private key
echo -e "${BLUE}🔑 Generating private key...${NC}"
openssl genrsa -out "$KEY_FILE" 2048

# Generate certificate signing request
echo -e "${BLUE}📋 Generating certificate signing request...${NC}"
openssl req -new -key "$KEY_FILE" -out "$SSL_DIR/$DOMAIN.csr" -subj "/C=US/ST=Local/L=Local/O=News Intelligence System/OU=Development/CN=$DOMAIN"

# Generate self-signed certificate
echo -e "${BLUE}📜 Generating self-signed certificate...${NC}"
openssl x509 -req -days 365 -in "$SSL_DIR/$DOMAIN.csr" -signkey "$KEY_FILE" -out "$CERT_FILE" \
    -extensions v3_req -extfile <(
        echo "[req]"
        echo "distinguished_name = req_distinguished_name"
        echo "req_extensions = v3_req"
        echo "prompt = no"
        echo ""
        echo "[req_distinguished_name]"
        echo "C = US"
        echo "ST = Local"
        echo "L = Local"
        echo "O = News Intelligence System"
        echo "OU = Development"
        echo "CN = $DOMAIN"
        echo ""
        echo "[v3_req]"
        echo "keyUsage = keyEncipherment, dataEncipherment"
        echo "extendedKeyUsage = serverAuth"
        echo "subjectAltName = @alt_names"
        echo ""
        echo "[alt_names]"
        echo "DNS.1 = $DOMAIN"
        echo "DNS.2 = api.$DOMAIN"
        echo "DNS.3 = app.$DOMAIN"
        echo "DNS.4 = monitor.$DOMAIN"
        echo "DNS.5 = grafana.$DOMAIN"
        echo "DNS.6 = metrics.$DOMAIN"
        echo "DNS.7 = prometheus.$DOMAIN"
        echo "IP.1 = 127.0.0.1"
        echo "IP.2 = ::1"
    )

# Set proper permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

# Clean up CSR file
rm -f "$SSL_DIR/$DOMAIN.csr"

echo -e "${GREEN}✅ SSL certificates generated successfully!${NC}"
echo -e "${GREEN}   Certificate: $CERT_FILE${NC}"
echo -e "${GREEN}   Private Key: $KEY_FILE${NC}"
echo ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo -e "${YELLOW}   1. Add the following entries to your /etc/hosts file:${NC}"
echo -e "${YELLOW}      127.0.0.1 newsintel.local${NC}"
echo -e "${YELLOW}      127.0.0.1 api.newsintel.local${NC}"
echo -e "${YELLOW}      127.0.0.1 app.newsintel.local${NC}"
echo -e "${YELLOW}      127.0.0.1 monitor.newsintel.local${NC}"
echo -e "${YELLOW}      127.0.0.1 grafana.newsintel.local${NC}"
echo -e "${YELLOW}      127.0.0.1 metrics.newsintel.local${NC}"
echo -e "${YELLOW}      127.0.0.1 prometheus.newsintel.local${NC}"
echo ""
echo -e "${YELLOW}   2. Restart your Docker containers:${NC}"
echo -e "${YELLOW}      docker compose -f docker-compose.yml down${NC}"
echo -e "${YELLOW}      docker compose -f docker-compose.yml up -d${NC}"
echo ""
echo -e "${YELLOW}   3. Access your services at:${NC}"
echo -e "${YELLOW}      https://newsintel.local (Main App)${NC}"
echo -e "${YELLOW}      https://api.newsintel.local (API)${NC}"
echo -e "${YELLOW}      https://monitor.newsintel.local (Grafana)${NC}"
echo -e "${YELLOW}      https://metrics.newsintel.local (Prometheus)${NC}"
echo ""
echo -e "${RED}⚠️  Note: You'll need to accept the self-signed certificate in your browser.${NC}"
