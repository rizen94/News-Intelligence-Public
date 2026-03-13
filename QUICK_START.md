# News Intelligence System v5.0 - Quick Start Guide

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

From the project directory:

```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"
./start_system.sh
```

**Run from anywhere:** Create a symlink so you can start the system from any directory:

```bash
mkdir -p ~/bin
ln -sf "/home/pete/Documents/projects/Projects/News Intelligence/start-news-intelligence.sh" ~/bin/start-news-intelligence
```

Ensure `~/bin` is in your PATH (many distros add it automatically). If not, add to `~/.bashrc`:

```bash
export PATH="$HOME/bin:$PATH"
```

Then from any directory:

```bash
start-news-intelligence
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
- **Health Check:** http://localhost:8000/api/system_monitoring/health

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

## After reboot

If auto-start is enabled (see below), the API and frontend start automatically.
Otherwise:

1. `cd` to project directory and run `./start_system.sh`
2. Verify: `./status_system.sh`
3. Test frontend: http://localhost:3000
4. Test API: http://localhost:8000/docs

## Auto-start on boot

Run the setup script once to enable auto-start:

```bash
bash scripts/setup_autostart.sh
```

This creates two **systemd user services** that start at boot (even before login):

| Service | What it runs | Port |
|---------|-------------|------|
| `news-intel-api` | uvicorn (API server + all background services) | 8000 |
| `news-intel-web` | Vite dev server (frontend) | 3000 |

**Manage the services:**

```bash
systemctl --user status news-intel-api     # Check API status
systemctl --user status news-intel-web     # Check frontend status
systemctl --user restart news-intel-api    # Restart API
systemctl --user stop news-intel-api       # Stop API
journalctl --user -u news-intel-api -f     # Tail API logs
```

**Disable auto-start:**

```bash
systemctl --user disable news-intel-api news-intel-web
```

> **Note:** The services read DB credentials from `.env`. The API waits 10 seconds
> after boot for the network to settle; the frontend waits for the API to start first.
> If Widow (DB host) is unreachable at boot, the API will fail and systemd will
> retry after 10 seconds (up to the default retry limit).

Service files live at `~/.config/systemd/user/news-intel-api.service` and
`~/.config/systemd/user/news-intel-web.service`.

You can still use `./start_system.sh` for manual starts — it also handles Redis
and runs pre-flight checks that the systemd services skip.

