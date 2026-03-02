# News Intelligence System v4.0 - Quick Start Guide

## Overview

The News Intelligence System consists of multiple services that need to run concurrently:

1. **PostgreSQL** - Database on Widow (192.168.93.101:5432)
2. **Redis** - Cache (Docker container)
3. **API Server** - FastAPI backend (port 8000)
   - Auto-starts AutomationManager (RSS processing, Article processing, ML processing, Topic clustering)
   - Auto-starts MLProcessingService
4. **Frontend** - React development server (port 3000)

## Quick Start

### Start Everything

```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"
./start_system.sh
```

This script will:
- ✅ Check/start PostgreSQL
- ✅ Start Redis (Docker)
- ✅ Start API Server (with all background services)
- ✅ Start React Frontend
- ✅ Verify all services are running

### Check Status

```bash
./status_system.sh
```

### Stop Services

```bash
./stop_system.sh
```

**Note:** This stops API and Frontend but keeps PostgreSQL and Redis running.

## Manual Service Management

### Start Individual Services

#### PostgreSQL
```bash
sudo systemctl start postgresql
# or
sudo systemctl start postgresql@*
```

#### Redis
```bash
docker start news-intelligence-redis
# or if using docker-compose
docker-compose up -d redis
```

#### API Server
```bash
cd api
source venv/bin/activate  # or ../.venv/bin/activate
python3 -m uvicorn main_v4:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend
```bash
cd web
CHOKIDAR_USEPOLLING=true npm start
```

## Background Services

The API server automatically starts these background services:

### AutomationManager
- **RSS Processing** - Every 10 minutes
- **Article Processing** - Every 10 minutes (depends on RSS)
- **ML Processing** - Every 10 minutes (depends on Article Processing)
- **Topic Clustering** - Every 5 minutes (continuous refinement)
- **Entity Extraction** - Every 10 minutes (parallel with ML)
- **Quality Scoring** - Every 10 minutes (parallel with ML)

### MLProcessingService
- Continuous ML model processing for articles

## Access URLs

- **Frontend:** http://localhost:3000
- **API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v4/system-monitoring/health

## Logs

- **API Logs:** `logs/api_server.log`
- **Frontend Logs:** `logs/frontend.log`
- **Startup Log:** `logs/startup.log`

## Troubleshooting

### Port Already in Use

If you see "Port XXXX is already in use":

```bash
# Find what's using the port
lsof -i :8000  # API
lsof -i :3000  # Frontend

# Kill the process
kill -9 <PID>
```

### Services Not Starting

1. Check logs: `tail -f logs/api_server.log`
2. Verify dependencies:
   - PostgreSQL: `pg_isready -h localhost -p 5432 -U newsapp`
   - Redis: `docker exec news-intelligence-redis redis-cli ping`
   - Python: `python3 --version`
   - Node: `node --version`

### Database Connection Issues

Database runs on Widow (192.168.93.101). Ensure Widow is reachable.

```bash
# Check Widow reachability
ping 192.168.93.101

# Check PostgreSQL on Widow
pg_isready -h 192.168.93.101 -p 5432 -U newsapp
```

## System Requirements

- **PostgreSQL** 16 (on Widow 192.168.93.101:5432)
- **Docker** (for Redis)
- **Python** 3.9+ (with virtual environment)
- **Node.js** 16+ (with npm)
- **Redis** (via Docker container)

## Auto-Start on Reboot

To enable auto-start on system reboot, see `INSTALL_STARTUP_SERVICE.md`

