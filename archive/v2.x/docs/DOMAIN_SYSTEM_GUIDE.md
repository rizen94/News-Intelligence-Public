# News Intelligence System v2.9.0 - Domain System Guide

## Overview

The News Intelligence System now uses a proper domain-based URL system instead of localhost and port numbers. This provides a more professional, scalable, and user-friendly experience that mimics production environments.

## Domain Structure

### Primary Domains
- **`newsintel.local`** - Main application (frontend)
- **`api.newsintel.local`** - Backend API and documentation
- **`monitor.newsintel.local`** - Grafana monitoring dashboard
- **`metrics.newsintel.local`** - Prometheus metrics

### Alternative Domains
- **`app.newsintel.local`** - Alternative main application URL
- **`grafana.newsintel.local`** - Direct Grafana access
- **`prometheus.newsintel.local`** - Direct Prometheus access

## Quick Setup

### Automated Setup (Recommended)
```bash
# Run the complete setup script
./scripts/setup-domain-system.sh
```

This script will:
1. Generate SSL certificates
2. Configure local DNS resolution
3. Build and start all services
4. Test domain accessibility

### Manual Setup

#### Step 1: Generate SSL Certificates
```bash
./scripts/generate-ssl-certs.sh
```

#### Step 2: Configure Local DNS
```bash
# Run as root/sudo
sudo ./scripts/setup-local-dns.sh
```

Or manually add to `/etc/hosts`:
```
127.0.0.1 newsintel.local
127.0.0.1 api.newsintel.local
127.0.0.1 app.newsintel.local
127.0.0.1 monitor.newsintel.local
127.0.0.1 grafana.newsintel.local
127.0.0.1 metrics.newsintel.local
127.0.0.1 prometheus.newsintel.local
```

#### Step 3: Start Services
```bash
docker compose -f docker-compose.unified.yml up -d
```

## Accessing Your Services

### Main Application
- **URL:** https://newsintel.local
- **Description:** React frontend with full News Intelligence System interface
- **Features:** Dashboard, RSS Management, Deduplication, Intelligence Analysis

### API Documentation
- **URL:** https://api.newsintel.local/docs
- **Description:** Interactive API documentation (Swagger/OpenAPI)
- **Features:** Test endpoints, view schemas, authentication

### Monitoring Dashboard
- **URL:** https://monitor.newsintel.local
- **Description:** Grafana dashboards for system monitoring
- **Features:** System metrics, performance graphs, alerts

### Metrics Collection
- **URL:** https://metrics.newsintel.local
- **Description:** Prometheus metrics interface
- **Features:** Raw metrics, queries, targets

## SSL Certificates

### Self-Signed Certificates
The system uses self-signed SSL certificates for local development. When you first access the domains, your browser will show a security warning.

### Accepting Certificates
1. Click "Advanced" or "Show Details"
2. Click "Proceed to newsintel.local (unsafe)" or similar
3. The certificate will be accepted for this session

### Certificate Details
- **Domain:** newsintel.local
- **Valid for:** 365 days
- **Type:** Self-signed (development only)
- **Location:** `api/docker/nginx/ssl/`

## Architecture

### Nginx Reverse Proxy
The system uses nginx as a reverse proxy that:
- Handles SSL termination
- Routes requests to appropriate services
- Provides load balancing capabilities
- Manages security headers

### Service Routing
```
https://newsintel.local → Frontend (React)
https://api.newsintel.local → Backend API (FastAPI)
https://monitor.newsintel.local → Grafana
https://metrics.newsintel.local → Prometheus
```

### Network Configuration
- **Network:** `newsintelligence_news-network`
- **Subnet:** `172.20.0.0/16`
- **Internal Communication:** Services communicate via container names

## Development Workflow

### Frontend Development
```bash
# Access frontend
https://newsintel.local

# API calls from frontend go to
https://api.newsintel.local
```

### Backend Development
```bash
# API documentation
https://api.newsintel.local/docs

# Health check
https://api.newsintel.local/health
```

### Monitoring Development
```bash
# System monitoring
https://monitor.newsintel.local

# Metrics and queries
https://metrics.newsintel.local
```

## Production Considerations

### For Production Deployment
1. **Replace self-signed certificates** with proper SSL certificates from a CA
2. **Configure proper DNS** instead of hosts file entries
3. **Set up load balancing** for high availability
4. **Configure monitoring alerts** and notifications
5. **Implement proper security headers** and rate limiting

### Environment Variables
```bash
# Frontend
REACT_APP_API_URL=https://api.yourdomain.com
REACT_APP_VERSION=2.9.0
REACT_APP_ENVIRONMENT=production

# Backend
DB_HOST=your-database-host
REDIS_HOST=your-redis-host
```

## Troubleshooting

### Common Issues

#### 1. "This site can't be reached"
**Cause:** DNS resolution not working
**Solution:** 
```bash
# Check hosts file
cat /etc/hosts | grep newsintel

# Re-run DNS setup
sudo ./scripts/setup-local-dns.sh
```

#### 2. "Your connection is not private"
**Cause:** Self-signed certificate warning
**Solution:** Accept the certificate in your browser

#### 3. "502 Bad Gateway"
**Cause:** Backend services not ready
**Solution:**
```bash
# Check service status
docker compose -f docker-compose.unified.yml ps

# Check logs
docker compose -f docker-compose.unified.yml logs news-system-app
```

#### 4. Frontend can't connect to API
**Cause:** API URL configuration issue
**Solution:**
```bash
# Check environment variables
docker compose -f docker-compose.unified.yml exec web env | grep REACT_APP

# Rebuild frontend
docker compose -f docker-compose.unified.yml build web
```

### Health Checks
```bash
# Check all services
curl -k https://newsintel.local
curl -k https://api.newsintel.local/health
curl -k https://monitor.newsintel.local
curl -k https://metrics.newsintel.local

# Check container status
docker compose -f docker-compose.unified.yml ps
```

### Logs and Debugging
```bash
# View all logs
docker compose -f docker-compose.unified.yml logs -f

# View specific service logs
docker compose -f docker-compose.unified.yml logs -f news-system-app
docker compose -f docker-compose.unified.yml logs -f nginx
docker compose -f docker-compose.unified.yml logs -f web
```

## Security Features

### SSL/TLS
- **Protocols:** TLSv1.2, TLSv1.3
- **Ciphers:** Strong encryption ciphers
- **HSTS:** HTTP Strict Transport Security enabled

### Security Headers
- **X-Frame-Options:** SAMEORIGIN
- **X-Content-Type-Options:** nosniff
- **X-XSS-Protection:** 1; mode=block
- **Referrer-Policy:** strict-origin-when-cross-origin
- **Strict-Transport-Security:** max-age=31536000; includeSubDomains

### Rate Limiting
- **API:** 10 requests/second with burst of 10
- **Frontend:** 100 requests/second with burst of 20

## Performance Optimization

### Caching
- **Static Assets:** 1 year cache with immutable headers
- **API Responses:** Configured via backend caching
- **Gzip Compression:** Enabled for text-based content

### Load Balancing
- **Nginx:** Acts as load balancer for multiple instances
- **Health Checks:** Automatic health monitoring
- **Failover:** Automatic failover for unhealthy services

## Maintenance

### Certificate Renewal
```bash
# Regenerate certificates (valid for 365 days)
./scripts/generate-ssl-certs.sh
```

### DNS Management
```bash
# Remove domain entries
sudo sed -i '/newsintel.local/d' /etc/hosts

# Re-add domain entries
sudo ./scripts/setup-local-dns.sh
```

### Service Updates
```bash
# Update and restart services
docker compose -f docker-compose.unified.yml down
docker compose -f docker-compose.unified.yml build --no-cache
docker compose -f docker-compose.unified.yml up -d
```

This domain system provides a professional, scalable foundation for the News Intelligence System that can easily be adapted for production environments while maintaining the convenience of local development.


