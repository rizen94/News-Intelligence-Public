# News Intelligence System v2.9.0 - Deployment & Scaling Guide

## Overview

The News Intelligence System now supports flexible deployment configurations to adapt to different scaling needs. You can run the frontend and backend independently or together, depending on your requirements.

## Deployment Options

### 1. Unified Deployment (All-in-One)
**File:** `docker-compose.unified.yml`
**Use Case:** Development, testing, or small production deployments

```bash
# Start everything together
docker compose -f docker-compose.unified.yml up -d

# Access points:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Grafana: http://localhost:3001
# - Prometheus: http://localhost:9090
```

### 2. Backend Only
**File:** `docker-compose.backend.yml`
**Use Case:** API-only deployments, microservices architecture, backend development

```bash
# Start backend services only
docker compose -f docker-compose.backend.yml up -d

# Access points:
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
```

### 3. Frontend Only
**File:** `docker-compose.frontend.yml`
**Use Case:** Frontend development, CDN deployments, separate frontend scaling

```bash
# Start frontend only (requires backend to be running elsewhere)
docker compose -f docker-compose.frontend.yml up -d

# Access points:
# - Frontend: http://localhost:3000
# - Nginx (optional): http://localhost:80
```

### 4. Monitoring Stack
**File:** `docker-compose.monitoring.yml`
**Use Case:** Centralized monitoring, observability, production monitoring

```bash
# Start monitoring services only
docker compose -f docker-compose.monitoring.yml up -d

# Access points:
# - Grafana: http://localhost:3001
# - Prometheus: http://localhost:9090
# - Node Exporter: http://localhost:9100
# - PostgreSQL Exporter: http://localhost:9187
```

## Scaling Scenarios

### Scenario 1: High-Traffic Frontend
When you need to scale the frontend independently:

```bash
# Deploy multiple frontend instances
docker compose -f docker-compose.frontend.yml up -d --scale web=3

# Use a load balancer (nginx, traefik, etc.) to distribute traffic
```

### Scenario 2: Backend API Scaling
When you need to scale the backend API:

```bash
# Deploy multiple backend instances
docker compose -f docker-compose.backend.yml up -d --scale news-system=3

# Each instance will be available on different ports:
# - Instance 1: localhost:8000
# - Instance 2: localhost:8001
# - Instance 3: localhost:8002
```

### Scenario 3: Microservices Architecture
Deploy services independently across different servers:

**Server 1 (Database):**
```bash
docker compose -f docker-compose.backend.yml up -d postgres redis
```

**Server 2 (API):**
```bash
# Update environment variables to point to Server 1
export DB_HOST=server1-ip
export REDIS_HOST=server1-ip
docker compose -f docker-compose.backend.yml up -d news-system
```

**Server 3 (Frontend):**
```bash
# Update API URL to point to Server 2
export REACT_APP_API_URL=http://server2-ip:8000
docker compose -f docker-compose.frontend.yml up -d
```

**Server 4 (Monitoring):**
```bash
# Update database connection to point to Server 1
export DB_HOST=server1-ip
docker compose -f docker-compose.monitoring.yml up -d
```

## Environment Variables

### Backend Configuration
```bash
# Database
DB_PASSWORD=your_secure_password
DB_HOST=postgres  # or external database host

# Redis
REDIS_PASSWORD=your_redis_password
REDIS_HOST=redis  # or external redis host

# Application
LOG_LEVEL=INFO
RSS_INTERVAL_MINUTES=60
ENABLE_ML_PROCESSING=true
ENABLE_RAG_SYSTEM=true
ENABLE_AUTOMATION=true

# NAS Storage
NAS_STORAGE_PATH=/mnt/terramaster-nas
```

### Frontend Configuration
```bash
# API Connection
REACT_APP_API_URL=http://localhost:8000  # or external API URL
REACT_APP_VERSION=2.9.0
REACT_APP_ENVIRONMENT=production
```

### Monitoring Configuration
```bash
# Grafana
GRAFANA_PASSWORD=your_grafana_password

# Database (for monitoring)
DB_PASSWORD=your_secure_password
DB_HOST=postgres  # or external database host
```

## Production Deployment

### 1. Prepare Environment
```bash
# Copy environment template
cp env.example .env

# Edit environment variables
nano .env
```

### 2. Deploy Backend
```bash
# Start backend services
docker compose -f docker-compose.backend.yml up -d

# Verify backend is running
curl http://localhost:8000/health
```

### 3. Deploy Frontend
```bash
# Set API URL to backend server
export REACT_APP_API_URL=http://your-backend-server:8000

# Start frontend
docker compose -f docker-compose.frontend.yml up -d

# Verify frontend is running
curl http://localhost:3000
```

### 4. Deploy Monitoring (Optional)
```bash
# Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Access Grafana at http://localhost:3001
# Default credentials: admin / admin123
```

## Development Workflow

### Backend Development
```bash
# Start only backend services
docker compose -f docker-compose.backend.yml up -d

# Make changes to backend code
# Restart backend container
docker compose -f docker-compose.backend.yml restart news-system
```

### Frontend Development
```bash
# Start only frontend (with hot reload)
cd web
npm start

# Or use Docker for production-like environment
docker compose -f docker-compose.frontend.yml up -d
```

### Full Stack Development
```bash
# Start everything for full development
docker compose -f docker-compose.unified.yml up -d
```

## Troubleshooting

### Common Issues

1. **Frontend can't connect to backend:**
   - Check `REACT_APP_API_URL` environment variable
   - Verify backend is running and accessible
   - Check network connectivity between containers

2. **Database connection issues:**
   - Verify `DB_HOST` and `DB_PASSWORD` environment variables
   - Check if PostgreSQL container is healthy
   - Verify network connectivity

3. **Port conflicts:**
   - Check if ports are already in use: `netstat -tulpn | grep :8000`
   - Modify port mappings in docker-compose files if needed

### Health Checks

```bash
# Check all services status
docker compose -f docker-compose.unified.yml ps

# Check specific service logs
docker logs news-system-app
docker logs news-system-web
docker logs news-system-postgres

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/health
```

## Security Considerations

1. **Change default passwords** in production
2. **Use HTTPS** for production deployments
3. **Configure firewall** rules appropriately
4. **Regular security updates** for base images
5. **Monitor logs** for suspicious activity

## Performance Optimization

1. **Resource limits:** Set appropriate CPU/memory limits
2. **Database tuning:** Optimize PostgreSQL configuration
3. **Caching:** Leverage Redis for session and data caching
4. **Load balancing:** Use nginx or similar for high availability
5. **Monitoring:** Set up alerts and performance monitoring

## Backup and Recovery

```bash
# Database backup
docker exec news-system-postgres pg_dump -U NewsInt_DB news_system > backup.sql

# Restore database
docker exec -i news-system-postgres psql -U NewsInt_DB news_system < backup.sql

# Volume backup
docker run --rm -v newsintelligence_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

This flexible deployment approach allows you to scale and adapt the News Intelligence System to your specific needs, whether you're running a small development environment or a large-scale production deployment.


