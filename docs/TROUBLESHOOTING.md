# Troubleshooting Guide - News Intelligence System v3.0

**Last Updated**: September 26, 2025

## 🚨 Quick Diagnostics

### **System Health Check**
```bash
# Check if all services are running
docker ps

# Check system health
curl http://localhost:8000/api/health/

# Check web interface
curl http://localhost:80
```

### **Common Issues & Solutions**

## 🔧 Service Issues

### **API Not Responding (current — v6, no Docker)**

**Symptoms**: `curl` to `localhost:8000` times out; TCP connects but no HTTP response; frontend shows "Cannot connect to API".

**Quick diagnostic:**
```bash
# 1. Is the process running?
pgrep -fa "uvicorn.*main_v4"

# 2. Is the port open?
ss -tlnp | grep 8000

# 3. Does the health check respond?
curl -s --max-time 5 http://localhost:8000/api/system_monitoring/health

# 4. Dump all thread stacks (output goes to logs/api_server.log)
kill -SIGUSR1 $(pgrep -f "uvicorn.*main_v4")
tail -80 logs/api_server.log
```

**Root cause checklist (most common first):**

| Cause | How to spot | Fix |
|-------|-------------|-----|
| Slow sync query on main event loop | SIGUSR1 dump shows main thread in a DB query inside an `async def` route handler | Change handler to plain `def` (FastAPI runs it in a thread pool) or add `SET LOCAL statement_timeout` |
| `asyncio.create_task` for background service on main loop | SIGUSR1 dump shows main thread in a background service's loop | Move service to its own `threading.Thread` with `asyncio.new_event_loop()` |
| Import shadowing (`import threading` / `import asyncio` inside `lifespan`) | API log shows `cannot access local variable 'threading'` | Remove redundant imports inside the function; use the module-level import |
| Too many ThreadPoolExecutor workers (GIL starvation) | API responds intermittently; many threads at low CPU each | Reduce `max_workers` in executors; keep automation `max_concurrent_tasks` ≤ 4 |
| `uvicorn --reload` with background threads | API accepts TCP but never responds; removing `--reload` fixes it | Never use `--reload` in production; it conflicts with multiprocessing + threads |

**Restart:**
```bash
./stop_system.sh && ./start_system.sh
```

---

### **API Not Responding (legacy Docker — v3)**
**Symptoms**: 500 errors, connection refused, timeout
**Solutions**:
```bash
# Check API container status
docker ps | grep api

# Restart API container
docker restart news-intelligence-api

# Check API logs
docker logs news-intelligence-api --tail 50

# Check if port 8000 is available
netstat -tlnp | grep 8000
```

### **Monitoring page down after CLI restart** (non-Docker)
**Symptoms**: After running `./start_system.sh` or `start-news-intelligence`, the Monitoring page shows errors or "down"; startup log may say "API server already running" then "❌ API Server: Not responding".

**Cause**: The script had previously skipped starting the API when it saw a leftover uvicorn process (e.g. still shutting down after `pkill`), so no healthy API was running.

**Fix (in script)**: `start_system.sh` now (1) waits for the API process to exit after `pkill` (and uses SIGKILL if needed), and (2) if it thinks the API is already running, it checks `GET /api/system_monitoring/health`; if that fails, it force-kills and starts a new API. After updating the script, run `./start_system.sh` again. If the Monitoring page is still down, run: `curl -s http://localhost:8000/api/system_monitoring/health` to confirm the API is up.

### **Database Connection Issues**
**Symptoms**: Database errors, connection timeouts
**Solutions**:
```bash
# Check database container
docker ps | grep postgres

# Restart database
docker restart news-intelligence-postgres

# Check database logs
docker logs news-intelligence-postgres --tail 50

# Test database connection
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;"
```

### **Web page slow or failing to load (API logs: assignment_context does not exist)**
**Symptoms**: Frontend hangs or shows errors; API logs show repeated `column "assignment_context" of relation "article_topic_assignments" does not exist` and Route Supervisor reports "Cannot connect to API server".
**Cause**: Topic clustering writes to `article_topic_assignments`; the table in one or more domain schemas was missing `assignment_context` and `model_version` columns.
**Fix**: Run migration 166 to add the columns, then restart the API so the server is less overloaded by repeated errors:
```bash
# From project root (uses .env or .db_password_widow for DB)
PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_166.py
./stop_system.sh && ./start_system.sh
```

### **Frontend Not Loading**
**Symptoms**: 404 errors, blank page, connection refused
**Solutions**:
```bash
# Check nginx container
docker ps | grep nginx

# Restart nginx
docker restart news-intelligence-nginx

# Check nginx logs
docker logs news-intelligence-nginx --tail 50

# Check if port 80 is available
netstat -tlnp | grep 80
```

### **Database not accessible (503, "Save as topic" fails)**
**Symptoms**: "Request failed with status code 503" or "Database unavailable" when saving a research topic (or any endpoint that uses PostgreSQL).

**How the API connects** (see `api/shared/database/connection.py`):
- **Default (Widow)**: `DB_HOST=192.168.93.101`, `DB_PORT=5432`, `DB_NAME=news_intel`. Direct TCP to the Widow machine.
- **NAS rollback**: `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence`. Requires an SSH tunnel; the API checks that the tunnel process is running.

**Common causes**:
1. **Widow unreachable** — You're not on the same network as 192.168.93.101, or Widow is off, or a firewall blocks port 5432.
2. **API started without DB env** — If you start the API from an IDE or `uvicorn` without going through `./start_system.sh`, ensure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` are set (e.g. in `.env` or exported). The API defaults to 192.168.93.101:5432; if that host is unreachable, every DB call returns 503.
3. **NAS tunnel not running** — If you use `DB_HOST=localhost` and `DB_PORT=5433`, the tunnel must be up: `./scripts/setup_nas_ssh_tunnel.sh`. If the tunnel dies, the API gets no connection.
4. **Wrong or missing password** — Store the PostgreSQL password in the project-root **`.env`** file as `DB_PASSWORD=your_password`. The API and `start_system.sh` read it from there. If `DB_PASSWORD` is missing or wrong, connections fail. (`.env` is in `.gitignore`; copy from `configs/env.example` if needed.)

**Quick checks**:
```bash
# 1) See what the API is using (from project root, with same .env as API)
source .env 2>/dev/null || true
echo "DB_HOST=${DB_HOST:-192.168.93.101} DB_PORT=${DB_PORT:-5432} DB_NAME=${DB_NAME:-news_intel}"

# 2) Widow reachable?
ping -c 1 "${DB_HOST:-192.168.93.101}"

# 3) PostgreSQL accepting connections?
pg_isready -h "${DB_HOST:-192.168.93.101}" -p "${DB_PORT:-5432}" -U "${DB_USER:-newsapp}"

# 4) Full connection test (requires PGPASSWORD or .pgpass)
PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST:-192.168.93.101}" -p "${DB_PORT:-5432}" -U "${DB_USER:-newsapp}" -d "${DB_NAME:-news_intel}" -c "SELECT 1;" 2>&1
```
If (2) or (3) fails, fix network/Widow/PostgreSQL. If (4) fails with "password authentication failed", fix `DB_PASSWORD`. Restart the API after changing env so the connection pool picks up the new config.

### **Common log errors (logs/api_server.log, logs/app.log)**

| Log message | Cause | What to do |
|-------------|--------|------------|
| `fe_sendauth: no password supplied` | API has no `DB_PASSWORD` in env | Set `DB_PASSWORD` in project-root `.env` and **restart the API** (e.g. `./start_system.sh`). |
| `Error validating domain X: 'NoneType' object has no attribute 'close'` | DB connection was `None`; code tried to close it | Fixed in code (validate_domain now checks for None). Ensure `DB_PASSWORD` is set and restart so DB connects. |
| `426 Client Error: Upgrade Required` (News API) | News API plan or endpoint requires upgrade | Historic context uses News API; 426 means the API key/plan may need upgrading at newsapi.org. Analysis still runs using other sources (RSS, price data). |
| `relation "intelligence.historic_context_requests" does not exist` | Migration 149 not applied | Run migration 149 if you want historic context requests persisted. Optional; fetches still run in-memory. |
| `EDGAR fetch index failed for CIK 0000001832: 404` | SEC returns 404 for that CIK (e.g. AEM) | Data/source issue; one company’s filings may be missing or CIK wrong. Safe to ignore or fix CIK mapping in config. |
| `ChromaDB not installed; finance vector store disabled` (one-time INFO) | ChromaDB not in the runtime env (wrong venv or Python &lt; 3.11) | Use the project `.venv` (Python 3.11+). From project root: `uv venv --python python3.12 --clear .venv` then `uv sync`. Restart the API so it uses `.venv`. See **Setup and Deployment** → Finance vector store (ChromaDB). |
| `EVAL_FAILED … all_sources_failed` | Finance task had no successful data sources | Often a follow-on from DB or EDGAR issues. Fix DB password and restart; then re-run the analysis. |

### **Health check showing "degraded"**
**Symptoms**: Monitoring page or health endpoint shows overall status **degraded** instead of healthy.

**How it works**: The API `GET /api/system_monitoring/health` sets status to **degraded** when:
1. **Database check fails** — e.g. connection timeout (2s), no password, or connection error. The health check runs a quick `SELECT 1` via `get_db_connection()` in a thread with a 2s timeout.
2. **Circuit breakers open** — e.g. Ollama (or another service) was unreachable and the circuit opened; until it resets, the API reports degraded.

**What to do**:
1. **See the reason** — The health response now includes `degraded_reasons` (e.g. `["database: unhealthy: connection timeout"]` or `["circuit_breakers: 1 open (e.g. ollama)"]`). The Monitoring page shows these under the status chip when status is degraded.
2. **If database** — Same as "Database not accessible" above: ensure `DB_PASSWORD` in project-root `.env`, start API with that env (e.g. `./start_system.sh`), and restart after changing `.env`. Check Widow reachability and `pg_isready` / `psql` as in the quick checks above.
3. **If circuit breakers** — If Ollama (or another checked service) was down, the circuit may be open. Restart the API to reset circuits, or wait for the circuit’s reset window; once the service is reachable again, the next successful call will close the circuit.

**Quick check**:
```bash
curl -s http://localhost:8000/api/system_monitoring/health | jq '.status, .degraded_reasons, .services.database'
```
Interpret `status`, `degraded_reasons`, and `services.database` to see why it’s degraded.

### **Financial Analysis: "Network Error" or no result**
**Symptoms**: Submit works then result page shows "Network Error", or submit fails with "Cannot reach API".
**Causes**: (1) Backend not running or wrong API URL; (2) Finance orchestrator failed to start.
**Solutions**:
- **API reachable?** From the same host as the frontend: `curl -s http://localhost:8000/api/system_monitoring/health` (or your API base URL). If you get connection refused, start the API (e.g. from `api/`: `uvicorn main_v4:app --host 0.0.0.0 --port 8000`).
- **Proxy/API URL**: With Vite dev server, `/api` is proxied to `http://localhost:8000`. If the app is built or served elsewhere, set the API base URL (e.g. `VITE_API_URL` or the in-app API URL setting).
- **Finance orchestrator**: If the backend starts but Finance Orchestrator fails to init, all finance analyze/task requests return **503** with detail "Finance orchestrator not available". Check API startup logs (stdout/stderr) for: `❌ Failed to initialize Finance Orchestrator: …`. Fix the underlying cause (e.g. missing ChromaDB, FRED key, or import error) then restart the API.
- **Recent request in logs**: The API logs each finance analyze request (e.g. `Finance analyze request: domain=finance query='...' topic=...`). Logs go to stdout and, if file logging is enabled, to `api/logs/` (see `api/config/logging_config.py` and `LOG_DIR` in `api/config/settings.py`). Run the API in a terminal to see recent requests and any 503/orchestrator messages.

### **ML / processing / story continuation phases failing or timing out**
**Symptoms**: Automation phases (event_tracking, event_extraction, story_continuation, claim_extraction, ml_processing, etc.) show as failed in the Monitor, or logs show "Task X failed", "Event tracking failed", "canceling statement due to user request", or "statement timeout".

**Are we loading too much?** Batch sizes are bounded (e.g. 30–100 contexts per event_tracking batch, 50 claim_extraction, 30 story_continuation). The pipeline does **not** load unbounded data; it processes in fixed-size batches. Failures are usually due to **timeouts** or **slow queries**, not memory or "too much data" in one go.

**Main causes of fail state**:

1. **Database statement timeout (most common)**  
   The connection pool uses a per-statement timeout (default **60 seconds**; configurable via `DB_STATEMENT_TIMEOUT_MS`). Any single SQL that runs longer is killed by PostgreSQL ("canceling statement due to user request").  
   - **Event tracking** and **backlog_metrics** run queries that scan `intelligence.contexts` and `intelligence.event_chronicles` with `NOT EXISTS` and `LIKE` on JSONB text. As data grows, these can exceed the timeout.  
   - **Fix**: For the process that runs the automation manager (same process as the API), set a higher timeout so long-running phase queries are not killed:
     - In project root `.env`: `DB_STATEMENT_TIMEOUT_MS=120000` (2 minutes) or `300000` (5 minutes).  
     - Restart the API so the pool is recreated with the new value.  
   - Default was raised to 60000 (1 min); for heavy processing (event_tracking, story_continuation, entity_profile_build), **120000–300000** is recommended.

2. **Slow or heavy queries**  
   - **Event tracking**: "Unlinked contexts" and "event chronicles" use a pattern like `ec.developments::text LIKE '%"context_id": 123%'`, which cannot use a normal index. With large tables, these queries get slower and hit the statement timeout.  
   - **Backlog counts**: Refreshed every 30s; the same style of query can hit the timeout if `contexts` / `event_chronicles` are large.  
   - **Mitigation**: Increase `DB_STATEMENT_TIMEOUT_MS` as above. Longer term, consider an index or a junction table (e.g. `context_id` → `event_id`) so "context linked to event" does not require a full scan of `event_chronicles`.

3. **Ollama / LLM congestion**  
   Phases that call Ollama (event_extraction, story_continuation, claim_extraction, ml_processing, etc.) share a semaphore (`MAX_CONCURRENT_OLLAMA_TASKS = 3`). If Ollama is slow or busy, tasks wait; the **HTTP client** has a 180s timeout, so very long calls can fail.  
   - **Fix**: Ensure Ollama is running and not overloaded; reduce concurrent load (e.g. fewer phases enabled) or increase Ollama resources if many phases run at once.

4. **Retries and backoff**  
   The automation manager retries failed tasks (up to `max_retries`) with backoff. If the **root cause** is statement timeout, increase `DB_STATEMENT_TIMEOUT_MS` so the first run succeeds instead of relying on retries.

**Quick checks**:
```bash
# Current timeout in use (API must be running with same env)
# In .env:
grep DB_STATEMENT_TIMEOUT_MS .env || echo "Not set (using default 60000 ms)"

# Logs: look for timeout or cancel
grep -E "canceling|statement timeout|Task .* failed|event_tracking failed|story_continuation failed" api/logs/*.log 2>/dev/null | tail -20
```

## 🐛 Error Messages

### **"generator object has no attribute 'query'"**
**Cause**: Database connection pattern issue
**Solution**: This was fixed in the latest update. Restart the API container:
```bash
docker restart news-intelligence-api
```

### **"column does not exist"**
**Cause**: Database schema mismatch
**Solution**: Check database schema and run migrations:
```bash
# Check table structure
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "\d articles"

# Check for missing columns
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'articles';"
```

### **"connection refused"**
**Cause**: Service not running or port conflict
**Solution**: Check service status and ports:
```bash
# Check all containers
docker ps

# Check port usage
netstat -tlnp | grep -E "(80|8000|5432|6379)"

# Restart all services
docker-compose down && docker-compose up -d
```

### **"invalid input syntax for type integer"**
**Cause**: Route conflict (e.g., /stats being caught by /{id} route)
**Solution**: This was fixed in the latest update. Restart the API container:
```bash
docker restart news-intelligence-api
```

## 🔍 Log Analysis

### **API Logs**
```bash
# View recent API logs
docker logs news-intelligence-api --tail 100

# Follow API logs in real-time
docker logs -f news-intelligence-api

# Search for errors
docker logs news-intelligence-api 2>&1 | grep -i error
```

### **Database Logs**
```bash
# View database logs
docker logs news-intelligence-postgres --tail 100

# Search for database errors
docker logs news-intelligence-postgres 2>&1 | grep -i error
```

### **Nginx Logs**
```bash
# View nginx logs
docker logs news-intelligence-nginx --tail 100

# Check access logs
docker logs news-intelligence-nginx 2>&1 | grep "GET /"
```

## 🔄 Recovery Procedures

### **Complete System Restart**
```bash
# Stop all services
docker-compose down

# Remove containers (if needed)
docker-compose down --volumes

# Start services
docker-compose up -d

# Wait for services to start
sleep 30

# Check health
curl http://localhost:8000/api/health/
```

### **Database Recovery**
```bash
# Check database status
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;"

# If database is corrupted, restore from backup
# (Backup procedures should be implemented)

# Reset database (WARNING: This will lose all data)
docker-compose down
docker volume rm news-intelligence_postgres_data
docker-compose up -d
```

### **File Synchronization Issues**
```bash
# Check if container files are up to date
docker exec news-intelligence-api ls -la /app/domains/news_aggregation/routes/

# Copy updated route file to container (example: news_aggregation domain)
docker cp api/domains/news_aggregation/routes/news_aggregation.py news-intelligence-api:/app/domains/news_aggregation/routes/news_aggregation.py

# Restart API container
docker restart news-intelligence-api
```

## 📊 Performance Issues

### **Slow API Responses**
**Symptoms**: API responses > 1 second
**Solutions**:
```bash
# Check database performance
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT * FROM pg_stat_activity;"

# Check system resources
docker stats

# Check for memory leaks
docker exec news-intelligence-api ps aux
```

### **High Memory Usage**
**Symptoms**: System running out of memory
**Solutions**:
```bash
# Check memory usage
free -h
docker stats

# Restart services to free memory
docker-compose restart

# Check for memory leaks in logs
docker logs news-intelligence-api 2>&1 | grep -i memory
```

## 🔧 Maintenance

### **Regular Health Checks**
```bash
# Daily health check script
#!/bin/bash
echo "=== News Intelligence System Health Check ==="
echo "1. API Health:"
curl -s http://localhost:8000/api/health/ | jq .success
echo "2. Database:"
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;" > /dev/null && echo "OK" || echo "ERROR"
echo "3. Frontend:"
curl -s http://localhost:80 > /dev/null && echo "OK" || echo "ERROR"
echo "4. Container Status:"
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### **Log Rotation**
```bash
# Set up log rotation for Docker logs
# Add to /etc/docker/daemon.json:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## 📞 Getting Help

### **Before Asking for Help**
1. Check this troubleshooting guide
2. Run the health check script
3. Check the logs for errors
4. Try the recovery procedures

### **Information to Provide**
- System status output
- Error messages from logs
- Steps you've already tried
- System configuration details

### **Emergency Contacts**
- System administrator
- Development team
- Documentation: This guide and API reference

---

**Troubleshooting Guide**: 🟢 **UP TO DATE**  
**Last Updated**: September 26, 2025  
**Next Review**: Recommended monthly
