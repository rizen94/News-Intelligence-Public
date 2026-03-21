> **Status:** Superseded by [SETUP_ENV_AND_RUNTIME.md](../../SETUP_ENV_AND_RUNTIME.md); kept for historical detail.

# Setup and Deployment Guide

**Last Updated**: December 2024  
**Status**: Production Ready

---

## 🚀 Quick Start

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

### Restart
Use after changing `.env` (e.g. `NEWS_API_KEY`) so the API reloads config:
```bash
./restart_system.sh
```

---

## 📋 System Requirements

### Required Software
- **PostgreSQL** 12+ (running on localhost:5432 or NAS)
- **Docker** and Docker Compose (for Redis and containers)
- **Python** 3.10+ (3.11+ recommended for Finance ChromaDB/embeddings; use project `.venv`)
- **Node.js** 16+ (with npm)
- **Redis** (via Docker container)

### System Resources
- **RAM**: 8GB minimum (16GB+ recommended)
- **Disk Space**: 20GB minimum (50GB+ recommended)
- **CPU**: Multi-core recommended for ML processing

---

## 🏗️ Architecture Overview

### Services
1. **PostgreSQL** - Database (port 5432 or NAS)
2. **API Server** - FastAPI backend (port 8000)
   - Auto-starts AutomationManager (RSS processing, Article processing, ML processing, Topic clustering)
   - Auto-starts MLProcessingService
3. **Frontend** - React application (port 80 via Docker or 3000 dev)
4. **Ollama** - AI models (port 11434, user-level service)

Redis and Docker are not required; the app uses an in-process event queue. Docker is only needed if you run the full stack via docker-compose (postgres, api, web).

### Access URLs
- **Frontend:** http://localhost:80 (production) or http://localhost:3000 (development)
- **API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/system_monitoring/health
- **Ollama:** http://localhost:11434

---

## 🔧 Installation Steps

### 1. Clone and Setup
```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"

# Install Python dependencies
cd api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Node dependencies
cd ../web
npm install
```

### 2. Database Setup

#### Local PostgreSQL
```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql
CREATE DATABASE news_intelligence;
CREATE USER newsapp WITH PASSWORD 'newsapp_password';
GRANT ALL PRIVILEGES ON DATABASE news_intelligence TO newsapp;
```

#### NAS PostgreSQL (Recommended)
See `docs/NAS_DATABASE_REQUIREMENT.md` and `docs/NAS_PERSISTENT_STORAGE_SETUP.md` for NAS database configuration.

#### Run migrations (v4/v5/v6 schema)
From the project root, with DB credentials in `.env` or `.db_password_widow`:
```bash
# Migrations 140–154 (orchestration, intelligence, context-centric, watch patterns)
PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_140_to_152.py

# Migrations 155–161 (quality feedback, cross-domain, processed_documents, automation_run_history, etc.)
PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_155_to_160.py
```
See `scripts/SCRIPTS_INDEX.md` for the full list.

### 3. Environment Configuration
```bash
# Copy example environment file
cp configs/env.example .env

# Edit .env with your configuration
# Required variables:
# - DB_HOST (NAS IP or localhost)
# - DB_NAME, DB_USER, DB_PASSWORD
# - NAS credentials (if using NAS)
```

#### Finance vector store (ChromaDB)
The Finance domain uses ChromaDB for evidence embeddings (e.g. EDGAR filings). To have it **working** (not just failing gracefully):

1. **Use the project virtualenv** — `start_system.sh` uses `.venv` when present. ChromaDB’s dependency (onnxruntime) needs **Python 3.11+**; the project’s `.venv` should be created with 3.11 or 3.12.
2. **Install/sync dependencies** from project root:
   ```bash
   uv sync
   ```
   If you previously had a Python 3.10 venv and see `onnxruntime` "no wheel for cp310", recreate the venv with 3.12:
   ```bash
   uv venv --python python3.12 --clear .venv
   uv sync
   ```
3. **Verify** — Run `./.venv/bin/python scripts/validate_finance_pipeline.py`; the "Vector Store (ChromaDB)" step should report **PASS**. Data is stored under `data/finance/chroma/`.

#### Optional: News API key (historic context)
For Finance Analysis **historic context** (news from a date range when you set Start/End dates), add a News API key:

1. **Get a key:** Go to [https://newsapi.org/register](https://newsapi.org/register), sign up (free tier available), and copy your API key.
2. **Add to .env:** In the project root, add or edit:
   ```bash
   NEWS_API_KEY=your_api_key_here
   ```
3. Restart the API server so it picks up the new variable. Historic context will then include News API results alongside Wikipedia, FRED, and SEC EDGAR.

### 4. Start Services
```bash
# Start all services
./start_system.sh

# Or start individually:
# PostgreSQL
sudo systemctl start postgresql

# Redis (Docker)
docker-compose up -d redis

# API Server
cd api
source venv/bin/activate
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (development)
cd web
npm start

# Frontend (production via Docker)
docker-compose up -d web
```

---

## 🔄 Background Services

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
- Uses Ollama models for analysis

---

## 🔐 Auto-Start on Reboot

### Systemd Service Installation
```bash
# 1. Copy service file
mkdir -p ~/.config/systemd/user
cp news-intelligence-system.service ~/.config/systemd/user/

# 2. Reload and enable
systemctl --user daemon-reload
systemctl --user enable news-intelligence-system

# 3. Enable lingering (run without login)
sudo loginctl enable-linger $USER

# 4. Start service
systemctl --user start news-intelligence-system
```

### Service Management
```bash
# Start/Stop/Restart
systemctl --user start news-intelligence-system
systemctl --user stop news-intelligence-system
systemctl --user restart news-intelligence-system

# Check status
systemctl --user status news-intelligence-system

# View logs
journalctl --user -u news-intelligence-system -f

# Disable auto-start
systemctl --user disable news-intelligence-system
```

---

## 📊 Logs

### Log Locations
- **API Logs:** `logs/api_server.log`
- **Frontend Logs:** `logs/frontend.log`
- **Startup Log:** `logs/startup.log`
- **Service Logs:** `journalctl --user -u news-intelligence-system`

### View Logs
```bash
# API logs
tail -f logs/api_server.log

# Frontend logs
tail -f logs/frontend.log

# Service logs
journalctl --user -u news-intelligence-system -f

# Docker logs
docker logs news-intelligence-api --tail 50
docker logs news-intelligence-redis --tail 50
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find what's using the port
lsof -i :8000  # API
lsof -i :3000  # Frontend
lsof -i :5432  # PostgreSQL

# Kill the process
kill -9 <PID>
```

### Services Not Starting
1. Check logs: `tail -f logs/api_server.log`
2. Verify dependencies:
   ```bash
   # PostgreSQL
   pg_isready -h localhost -p 5432 -U newsapp
   
   # Redis
   docker exec news-intelligence-redis redis-cli ping
   
   # Python
   python3 --version
   
   # Node
   node --version
   ```

### Database Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check if database exists
psql -h localhost -U newsapp -d news_intelligence -c "SELECT 1;"

# Check NAS database (if using)
psql -h <NAS_IP> -U newsapp -d news_intelligence -c "SELECT 1;"
```

### Docker Issues
```bash
# Check Docker status
docker info

# Restart Docker containers
docker-compose restart

# View container logs
docker logs news-intelligence-api
docker logs news-intelligence-redis
```

---

## 🚀 Production Deployment

### Pre-Deployment Checklist
- [ ] All tests pass
- [ ] No compilation errors
- [ ] No ESLint errors
- [ ] Frontend builds successfully
- [ ] API endpoints respond correctly
- [ ] Database schema is up to date
- [ ] All navigation links work
- [ ] Real data displays correctly
- [ ] Environment variables configured
- [ ] NAS storage mounted (if using)
- [ ] Backup strategy in place

### Deployment Steps
```bash
# 1. Build frontend
cd web
npm run build

# 2. Start Docker services
docker-compose up -d

# 3. Verify services
curl http://localhost:8000/api/health/
curl http://localhost:80

# 4. Check logs
docker logs news-intelligence-api --tail 50
```

### Production Verification
```bash
# Verify all services are healthy
curl http://localhost:8000/api/health/

# Test frontend accessibility
curl http://localhost:80

# Verify database connectivity
psql -h localhost -p 5432 -U newsapp -d news_intelligence -c "SELECT 1;"

# Check Docker container status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

## 🔒 Security Considerations

### Database Security
- Use strong passwords for database users
- Restrict database access to necessary IPs
- Use SSL/TLS for database connections (production)
- Regularly update PostgreSQL

### API Security
- Use environment variables for sensitive data
- Implement rate limiting
- Use HTTPS in production
- Regular security updates

### NAS Storage Security
- Use secure SMB credentials
- Mount with appropriate permissions
- Regular backups of NAS data

---

## 🚀 GPU Acceleration (Optional)

For enhanced ML performance, see **[Venv and GPU Setup](./VENV_AND_GPU_SETUP.md)** (optional GPU/container steps are in `_archive/GPU_SETUP.md`).

---

## 📚 Related Documentation

- **Coding standards**: `docs/CODING_STYLE_GUIDE.md`
- **NAS / storage**: `docs/NAS_LEGACY_AND_STORAGE.md`
- **Ollama**: `docs/OLLAMA_SETUP.md`
- **Venv and GPU**: `docs/VENV_AND_GPU_SETUP.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

---

*Last Updated: December 2024*  
*Status: Production Ready*  
*Version: 2.0*

