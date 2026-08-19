# Network Port Mapping - News Intelligence System

This document defines the standard port assignments for all services in the News Intelligence system to prevent port conflicts and ensure consistent configuration across environments.

## Primary Service Ports

| Service | Port | Protocol | Description | Configuration Reference |
|---------|------|----------|-------------|-------------------------|
| **News Intelligence API** | 8000 | HTTP | Main FastAPI application serving all domain endpoints | `API_PORT=8000` in `.env`, `uvicorn main:app --port 8000` |
| **Frontend Web Application** | 3000 | HTTP | React frontend application | `FRONTEND_PORT=3000` in `.env` |
| **WebSocket Service** | 8001 | WS/WSS | Real-time updates and live data streaming | `WEBSOCKET_PORT=8001` in `.env` |
| **Ollama LLM Service (CPU)** | 11434 | HTTP | Primary LLM service for text generation | `OLLAMA_HOST=http://localhost:11434` |
| **Ollama LLM Service (GPU)** | 11434 | HTTP | GPU-accelerated LLM service on PopOS machine | `OLLAMA_POP_OS_HOST=http://192.168.93.99:11434` |
| **Prometheus Monitoring** | 9090 | HTTP | Metrics collection and storage | `PROMETHEUS_PORT=9090` in `.env` |
| **Grafana Dashboard** | 3000 | HTTP | Visualization dashboard (Note: conflicts with frontend) | `GRAFANA_PORT=3000` in `.env` |
| **SMTP Email Service** | 587 | TCP | Outgoing email delivery | `SMTP_PORT=587` in `.env` |
| **Redis Cache/Queue** | 6379 | TCP | In-memory data structure store | `REDIS_PORT=6379` in `.env` |

## Port Conflicts and Resolutions

### Known Conflicts:
1. **Frontend (3000) vs Grafana (3000)**: Both configured to use port 3000
   - **Resolution**: In production, these should run on separate subdomains or use reverse proxy path-based routing
   - **Development**: Frontend typically runs on 3000, Grafana should be disabled or moved to another port

### Special Purpose Ports:

| Port | Usage | Notes |
|------|-------|-------|
| 80 | HTTP | Often used by reverse proxy (Caddy/Nginx) for SSL termination and routing |
| 443 | HTTPS | Secure web traffic via reverse proxy |
| 8080-8082 | Development/Testing | Alternate ports used for temporary instances during development |
| 5432 | PostgreSQL | Direct database connection (maintenance/admin) |
| 6432 | PgBouncer | Pooled database connection for application runtime |

## Configuration Sources

### Primary Configuration Files:
1. `.env` - Environment variables (project root)
2. `configs/env.example` - Template for environment configuration
3. `api/config/settings.py` - Python configuration loading
4. `docker-compose.yml` (if applicable) - Container port mappings

### Key Environment Variables:
- `API_PORT` - Main API port (default: 8000)
- `FRONTEND_PORT` - Frontend dev server port (default: 3000)
- `WEBSOCKET_PORT` - WebSocket service port (default: 8001)
- `DB_PORT` - Database connection port (5432 direct, 6432 via PgBouncer)
- `REDIS_PORT` - Redis connection port (default: 6379)
- `PROMETHEUS_PORT` - Prometheus metrics port (default: 9090)
- `GRAFANA_PORT` - Grafana dashboard port (default: 3000)
- `SMTP_PORT` - Email service port (default: 587)

## Service-to-Service Communication

### Internal API Calls:
All internal service communication uses the main API on port 8000:
- Frontend → Monitoring API: `GET /api/finance/finance/credit-spread`
- Monitoring API → Finance Service: Internal function calls
- Automation Manager → Various services: Direct API calls to localhost:8000

### External Dependencies:
- **Ollama**: Services connect to `OLLAMA_HOST` (default: localhost:11434) or `OLLAMA_POP_OS_HOST` for GPU workloads
- **Database**: Services use connection strings built from `DB_HOST`, `DB_PORT`, `DB_NAME`, etc.
- **Redis**: Used for caching and queuing via configured connection strings

## Verification Commands

To check if services are running on their assigned ports:

```bash
# Check API (should return News Intelligence system info)
curl -s http://localhost:8000/ | jq .data.name

# Check frontend (should return React app)
curl -s http://localhost:3000/

# Check WebSocket endpoint (may return upgrade required)
curl -s -i http://localhost:8001/ws

# Check Ollama availability
curl -s http://localhost:11434/api/version

# Check database connectivity (requires psql)
pg_isready -h localhost -p 5432 -U newsapp

# Check Redis
redis-cli -p 6379 ping
```

## Port Assignment Guidelines

1. **Always check this document** before assigning a new port
2. **Prefer established ports** from the table above for consistency
3. **Document any new ports** added to this document immediately
4. **Use environment variables** for port configuration, never hardcode
5. **Consider reverse proxy** for port 80/443 exposure instead of direct service exposure
6. **Development vs Production**: 
   - Development may use alternate ports (8080-8082) to avoid conflicts
   - Production should strictly follow the mappings above

## Troubleshooting Port Conflicts

If you encounter "Address already in use" errors:

1. Identify the conflicting process:
   ```bash
   lsof -i :<PORT_NUMBER>
   netstat -tlnp | grep :<PORT_NUMBER>
   ss -tlnp | grep :<PORT_NUMBER>
   ```

2. Resolve by either:
   - Stopping the conflicting service
   - Changing the port in your service's configuration
   - Using a different port range for development/testing

## Recent Changes

- **2026-07-11**: Documented port mapping after discovering Dental Service running on port 8000 instead of News Intelligence API
- Standardized on port 8000 for main API based on codebase analysis
- Maintained existing port assignments from configs/env.example where they didn't conflict

---
*This document should be kept up-to-date with any changes to service port assignments.*