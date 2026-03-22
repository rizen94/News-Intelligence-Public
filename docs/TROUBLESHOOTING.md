# Troubleshooting Guide - News Intelligence System v3.0

**Last Updated**: September 26, 2025

## 🚨 Quick Diagnostics

### **Database assessment & alignment**

For full-stack DB alignment (schema, API, web, automation persistence), baseline scripts, and cleanup bundles:

- [_archive/retired_root_docs_2026_03/DB_FULL_ASSESSMENT.md](_archive/retired_root_docs_2026_03/DB_FULL_ASSESSMENT.md) — matrices, gates, expert checklist  
- [_archive/retired_root_docs_2026_03/DB_CLEANUP_BUNDLES.md](_archive/retired_root_docs_2026_03/DB_CLEANUP_BUNDLES.md) — bundles A/B/C and pre-delete rules  
- Commands: `PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py`, `PYTHONPATH=api uv run python scripts/db_full_inventory.py`, `PYTHONPATH=api uv run python scripts/db_persistence_gates.py`

### **`claims_to_facts` runs but `versioned_facts` stays empty**

Automation can report success while **zero rows** are inserted if claim subjects cannot be resolved to `intelligence.entity_profiles.id`. A resolver bug (invalid `display_name` column + wrong `old_entity_to_new` join) caused **all** resolutions to fail until fixed.

- Doc (archived): [_archive/retired_root_docs_2026_03/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md](_archive/retired_root_docs_2026_03/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md)  
- Diagnose: `PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py`

### **Entity enrichment never updates `entity_profiles`**

If the backlog of profiles missing a Wikipedia section exceeds the old **1000-row** guard, the batch used to **skip entirely**. That guard is relaxed (warn-only above `ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD`, default 5000). See `api/services/entity_enrichment_service.py`.

### **System Health Check** (bare metal)
```bash
# API process and health
pgrep -fa "uvicorn.*main:app"
curl -s --max-time 5 http://localhost:8000/api/system_monitoring/health

# Frontend (Vite dev server)
curl -s --max-time 3 http://localhost:3000 | head -1
```

Legacy Docker commands (if you restore Compose) live in [`archive/docker_stack/TROUBLESHOOTING_DOCKER_LEGACY.md`](archive/docker_stack/TROUBLESHOOTING_DOCKER_LEGACY.md).

### **Common Issues & Solutions**

## 🔧 Service Issues

### **API Not Responding (current — v8, no Docker)**

**Symptoms**: `curl` to `localhost:8000` times out; TCP connects but no HTTP response; frontend shows "Cannot connect to API".

**Quick diagnostic:**
```bash
# 1. Is the process running?
pgrep -fa "uvicorn.*main:app"

# 2. Is the port open?
ss -tlnp | grep 8000

# 3. Does the health check respond?
curl -s --max-time 5 http://localhost:8000/api/system_monitoring/health

# 4. Dump all thread stacks (output goes to logs/api_server.log)
kill -SIGUSR1 $(pgrep -f "uvicorn.*main:app")
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

### **Log review after a crash or restart**

**Where to look:** `logs/api_server.log` (API/uvicorn), `logs/startup.log` (start/stop and SIGKILL), `logs/activity.log` (requests). For errors: `grep -E "Error|Exception|Traceback|failed" logs/api_server.log | tail -80`.

**Common post-crash patterns:**

| Log message | Cause | Fix |
|-------------|--------|-----|
| `Entity dossier compile failed: 'AutomationManager' object has no attribute '_executor'` | AutomationManager used `_executor` but only `executor` was set. | Fixed in code: `_executor` alias added in `automation_manager.py`. |
| `Error in keyword search: the JSON object must be str, bytes or bytearray, not list` | JSONB columns (e.g. `entities`, `topics`, `keywords`) returned as list/dict; code called `json.loads()` on them. | Fixed in `api/services/rag/retrieval.py`: use `_parse_json_column()` so we only parse when value is str/bytes. |
| `Error discovering articles for storyline X: can't subtract offset-naive and offset-aware datetimes` | Datetime timezone mismatch in storyline discovery. | Ensure all `published_at` / comparison datetimes use timezone-aware values (e.g. `timezone.utc`). |
| `current transaction is aborted, commands ignored until end of transaction block` | One query failed in a transaction; PostgreSQL aborts the transaction so all later commands on that connection fail until ROLLBACK. | Fix the **first** failing operation (often keyword search, entity search, or a missing table). Restart API to clear pooled connections. |
| `relation "intelligence.context_entity_mentions" does not exist` | Schema/table not created or wrong `search_path`. | Run migrations for the `intelligence` schema; or disable/guard the feature that uses this table. |
| `relation "watchlist" does not exist` | Watchlist may live in a domain schema (e.g. `politics.watchlist`). | Use schema-qualified name or set `search_path` in the session. |
| `Task event_deduplication failed: 'NoneType' object has no attribute 'get'` | Automation task received None where a dict was expected. | Add null checks in the task; ensure config or DB returns a dict. |

After fixing code, restart the API so the connection pool is fresh and automation tasks run with the new logic.

---

### **Web page stops connecting when you run a process from Monitor**

**Symptoms:** You click "Run phase now" (or "Trigger pipeline") on the Monitor/Monitoring page and the site stops loading; API health checks time out.

**Cause:** Long-running or blocking work was running on the same thread as the API event loop, so new requests could not be handled.

**Fixes applied in code:**
- **AutomationManager** now gets DB connections via `run_in_executor`, so connection acquisition no longer blocks the event loop.
- **Pipeline trigger** (`POST /api/system_monitoring/pipeline/trigger`) now starts the pipeline in a dedicated daemon thread, so it never blocks the API.

**If it still happens:** Heavy phases (e.g. topic_clustering, collection_cycle) still do sync DB and CPU work on the automation worker. Restart the API to recover. Prefer "Trigger pipeline" from the Monitoring page (runs in a separate thread) or run phases during low traffic. To confirm the process is running, check `logs/api_server.log` and the Monitor "Current activity" section.

---

### **Statement timeouts killing planned work**

**Symptoms**: Migrations or batch jobs fail with `canceling statement due to statement timeout`; ALTER TABLE or long UPDATE never finishes.

**Policy**: The DB connection pool uses a **statement timeout** so one stuck query doesn’t hang the app. Default is **2 minutes** (`DB_STATEMENT_TIMEOUT_MS=120000`). That’s fine for normal API and automation. **Planned long-running work** (migrations, backfills, big reports) must run with no timeout so they aren’t cut off early.

| Context | Timeout | Notes |
|--------|---------|--------|
| Pool (API, automation) | 2 min default | Override with `DB_STATEMENT_TIMEOUT_MS` (e.g. `300000` = 5 min, `0` = off). |
| Migration scripts | Off | All `run_migration_*.py` scripts set `SET statement_timeout = 0` before running SQL. |
| Content enrichment batch | 5 min | Service sets 300s for the batch, then restores pool default. |
| Backlog metrics (dashboard) | 3 s | Short `SET LOCAL statement_timeout = '3s'` for quick counts. |

**If a migration still times out**: Another process may be holding a lock (e.g. API or cron). Stop the API/workers, run the migration, then restart. Or run the migration during a quiet window.

---

### **Database connection crashes / pool exhausted**

**Symptoms:** API or automation fails with "Database connection failed (pool and direct)", "connection pool timeout", or "current transaction is aborted, commands ignored until end of transaction block". PostgreSQL may show many idle or idle-in-transaction connections.

**Causes and fixes:**

| Cause | Fix |
|-------|-----|
| **Connection leaks** | Every `get_db_connection()` must be closed (returns to pool). Use `with get_db_connection_context() as conn:` or `try: ... finally: conn.close()`. Never leave a connection open on exception paths. |
| **Pool exhausted** | Set `DB_GETCONN_TIMEOUT_SECONDS=30` in `.env` so the process fails fast instead of blocking forever when the pool is exhausted. Fix leaks and/or increase `DB_POOL_MAX` (default 20) if you have many concurrent workers. |
| **Aborted transaction** | If one query fails, the connection stays in "aborted transaction" and all further commands fail until rollback. The shared module now does `rollback()` before returning a connection to the pool so the next user gets a clean connection. Ensure code that holds a connection long-lived uses `conn.rollback()` or `conn.commit()` before reusing the same conn for another operation. |
| **Blocking the event loop** | Async code must not call `get_db_connection()` directly; it blocks the event loop. AutomationManager uses `run_in_executor` for `_get_db_connection()`. Other async callers should do the same or use a sync wrapper in a thread. |

**Connection methods (single source: `api/shared/database/connection.py`):**

- **`get_db_connection()`** — Returns a pooled connection. Caller **must** call `conn.close()` when done (or use the context manager).
- **`get_db_connection_context()`** — Context manager: `with get_db_connection_context() as conn: ...` — always closes on exit.
- **`get_db_cursor()`** — Context manager that yields a RealDictCursor and closes both cursor and connection on exit.
- **`get_db_config()`** / **`get_db_connect_kwargs()`** — For scripts or one-off connections with the same timeouts.

**Recommended:** Prefer `get_db_connection_context()` or `get_db_cursor()` for new code so connections are never leaked. Set `DB_GETCONN_TIMEOUT_SECONDS=30` in production so pool exhaustion fails fast instead of hanging the process.

---

### **Article content enrichment: fallbacks and bad-datapoint removal**

Full-text enrichment tries up to four sources in order; if all fail, the article is treated as a bad datapoint and soft-removed.

**Pipeline order**

1. **Live** — trafilatura fetch from the article URL (current behaviour). If usable text and not paywalled, done.
2. **Browser** (optional) — headless browser (Playwright) for fully rendered HTML. Only if live failed. Requires `ENABLE_BROWSER_ENRICHMENT=1` and Playwright installed.
3. **Wayback** (optional) — Archive.org snapshot. Only if browser failed or is disabled. Requires `ENABLE_WAYBACK_ENRICHMENT=1`.
4. **archive.today** (optional) — Memento snapshot. Only if Wayback failed or is disabled. Requires `ENABLE_ARCHIVETODAY_ENRICHMENT=1`.

If all enabled steps return no usable text (or paywalled), the **batch** enrichment path **removes** the article: sets `enrichment_status = 'removed'` and deletes its row from `topic_extraction_queue`. Removed articles are excluded from article lists, backlog counts, storylines, and context sync. No removal at RSS ingest; only the batch cleanup removes after trying all fallbacks.

**Environment flags (all optional; off if unset)**

| Variable | Effect |
|----------|--------|
| `ENABLE_BROWSER_ENRICHMENT=1` | Enable step 2 (headless browser). |
| `ENABLE_WAYBACK_ENRICHMENT=1` | Enable step 3 (Archive.org). |
| `ENABLE_ARCHIVETODAY_ENRICHMENT=1` | Enable step 4 (archive.today). |

Rate limits and timeouts apply to browser and archive fetches so we do not overload external services. Logs indicate which path succeeded (live / browser / wayback / archivetoday) and when an article is removed.

---

### **Finance (or other domain) storylines not showing**

**Symptoms:** You open **Storylines** in the Finance (or Science & Tech) domain and see an empty list, even though Politics has storylines or you expect discovery to have run.

**Cause:** Storylines are **per domain**. Each domain has its own table: `politics.storylines`, `finance.storylines`, `science_tech.storylines`. The UI shows only the storylines for the **current domain** (the one in the URL, e.g. `/finance/storylines`). If no discovery or manual creation has populated that domain’s table, the list is empty.

**What to do:**

1. **Confirm domain** — In the Storylines page, check the domain chip next to the title (e.g. "Finance"). The URL should be `/{domain}/storylines` (e.g. `/finance/storylines`). If you were on Politics before, switch to Finance via the domain switcher and open Storylines again.
2. **Run discovery for this domain** — On the Storylines page, use **Discover storylines now**. Discovery runs for the **current domain only** and writes to that domain’s `storylines` table. It needs enough recent articles in that domain (e.g. finance RSS articles) and typically 2–5 minutes. After it finishes, refresh the list.
3. **Scheduled discovery** — The automation manager can run storyline discovery for all domains (politics, finance, science-tech) on a schedule. If the scheduler is enabled and the task runs, new storylines will appear after the next run. Check automation/scheduler configuration and logs to confirm the task runs and that it’s not failing for the finance domain. **Eligibility:** `storyline_discovery` depends on `collection_cycle`; the scheduler only requires a short settle window after collection completes (capped by `AUTOMATION_DEPENDENCY_SETTLE_CAP_SEC`, default 180s), not the full collection estimated duration—so discovery should not stay blocked while collection runs on a timer.
4. **Auto-created status** — Discovery inserts rows with status `suggested` or `active`. The Storylines list shows all statuses unless you filter by status in the UI.
5. **Create one manually** — Use **Create Storyline** or go to **Story Management**, create a storyline in the Finance domain, and add articles. It will then appear on the Finance Storylines list.

**Quick check (DB):** To see if any finance storylines exist at all:
```sql
SELECT COUNT(*) FROM finance.storylines;
```
If this is 0, no storylines have been created for finance yet; run discovery or create one manually.

---

### **Automation queue depth keeps growing (hundreds of tasks)**

**Symptoms:** Monitor shows a very large pending task count vs. worker count; backlog never shrinks.

**Behavior (v8+):** When `AUTOMATION_QUEUE_SOFT_CAP` is set (default **200**, `0` disables), the scheduler stops enqueueing most scheduled phases, stops continuous batch re-queues, and skips dependency-chain `request_phase` bursts while combined depth (`task_queue` + requested queue) is at or above the cap. **`collection_cycle`** and **`health_check`** remain allowlisted so ingestion and liveness continue. Tune with `AUTOMATION_QUEUE_SOFT_CAP`, `AUTOMATION_QUEUE_PAUSE_ALLOW` (comma-separated phase names), and inspect `get_status()` fields `combined_queue_depth`, `queue_soft_cap`, `scheduled_enqueue_paused`.

---

### **Known gaps and tech debt (Entity Intelligence / v8)**

| Gap | Impact | Notes |
|-----|--------|------|
| **Timeline builder not domain-scoped** | `TimelineBuilderService` queries `chronological_events` and `storylines` without a schema prefix. If your DB uses per-domain schemas (e.g. `politics`, `finance`, `science_tech`) and `chronological_events` lives in `public`, timeline events may not be scoped to the requested domain. | Route `GET /api/{domain}/storylines/{id}/timeline` receives `domain` but does not pass it to the service. Future fix: pass domain/schema into `TimelineBuilderService` and use `{schema}.chronological_events` (or ensure search_path is set per request). |
| **Storylines API response shape** | List endpoint returns `{ data: StorylineListItem[], pagination, domain }` with no top-level `success` field. Consumers that only check `response.success` will miss the data. | Fixed in Articles and Briefings: treat `response.data` as the array when present; Briefings fallback also accepts `response.data` as the storyline list. |

---

### **Monitoring page down after CLI restart**
**Symptoms**: After running `./start_system.sh` or `start-news-intelligence`, the Monitoring page shows errors or "down"; startup log may say "API server already running" then "❌ API Server: Not responding".

**Cause**: The script had previously skipped starting the API when it saw a leftover uvicorn process (e.g. still shutting down after `pkill`), so no healthy API was running.

**Fix (in script)**: `start_system.sh` now (1) waits for the API process to exit after `pkill` (and uses SIGKILL if needed), and (2) if it thinks the API is already running, it checks `GET /api/system_monitoring/health`; if that fails, it force-kills and starts a new API. After updating the script, run `./start_system.sh` again. If the Monitoring page is still down, run: `curl -s http://localhost:8000/api/system_monitoring/health` to confirm the API is up.

### **Database Connection Issues**
**Symptoms**: Database errors, connection timeouts  
**Solutions** (Widow or tunnel — see `.env` `DB_HOST` / `DB_PORT` / `DB_NAME`):
```bash
pg_isready -h "$DB_HOST" -p "$DB_PORT" -U newsapp
# Example direct test:
psql -h "$DB_HOST" -p "$DB_PORT" -U newsapp -d news_intel -c "SELECT 1;"
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
**Solutions** (default dev: Vite on **3000**):
```bash
ss -tlnp | grep 3000
tail -40 logs/frontend.log
./stop_system.sh && ./start_system.sh
```

### **Database not accessible (503, "Save as topic" fails)**
**Symptoms**: "Request failed with status code 503" or "Database unavailable" when saving a research topic (or any endpoint that uses PostgreSQL).

**How the API connects** (see `api/shared/database/connection.py`):
- **Default (Widow)**: `DB_HOST=<WIDOW_HOST_IP>`, `DB_PORT=5432`, `DB_NAME=news_intel`. Direct TCP to the Widow machine.
- **NAS rollback**: `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence`. Requires an SSH tunnel; the API checks that the tunnel process is running.

**Common causes**:
1. **Widow unreachable** — You're not on the same network as <WIDOW_HOST_IP>, or Widow is off, or a firewall blocks port 5432.
2. **API started without DB env** — If you start the API from an IDE or `uvicorn` without going through `./start_system.sh`, ensure `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` are set (e.g. in `.env` or exported). The API defaults to <WIDOW_HOST_IP>:5432; if that host is unreachable, every DB call returns 503.
3. **NAS tunnel not running** — If you use `DB_HOST=localhost` and `DB_PORT=5433`, the tunnel must be up: `./scripts/setup_nas_ssh_tunnel.sh`. If the tunnel dies, the API gets no connection.
4. **Wrong or missing password** — Store the PostgreSQL password in the project-root **`.env`** file as `DB_PASSWORD=your_password`. The API and `start_system.sh` read it from there. If `DB_PASSWORD` is missing or wrong, connections fail. (`.env` is in `.gitignore`; copy from `configs/env.example` if needed.)

**Quick checks** (run from project root; ensure `DB_HOST` is set in `.env` — default in code is documented in [DATABASE.md](DATABASE.md)):
```bash
source .env 2>/dev/null || true
echo "DB_HOST=${DB_HOST} DB_PORT=${DB_PORT:-5432} DB_NAME=${DB_NAME:-news_intel}"
test -n "${DB_HOST}" || { echo "Set DB_HOST in .env"; exit 1; }

ping -c 1 "${DB_HOST}"
pg_isready -h "${DB_HOST}" -p "${DB_PORT:-5432}" -U "${DB_USER:-newsapp}"
PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT:-5432}" -U "${DB_USER:-newsapp}" -d "${DB_NAME:-news_intel}" -c "SELECT 1;" 2>&1
```
If `ping` or `pg_isready` fails, fix network or PostgreSQL. If `psql` fails with "password authentication failed", fix `DB_PASSWORD`. Restart the API after changing env so the connection pool picks up the new config.

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
- **API reachable?** From the same host as the frontend: `curl -s http://localhost:8000/api/system_monitoring/health` (or your API base URL). If you get connection refused, start the API (e.g. from `api/`: `uvicorn main:app --host 0.0.0.0 --port 8000`).
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
   Phases that call Ollama share a semaphore (`MAX_CONCURRENT_OLLAMA_TASKS` in `api/services/automation_manager.py`, `OLLAMA_CONCURRENCY` in `api/shared/services/llm_service.py`). If Ollama is slow or busy, tasks wait; the HTTP client has a 180s timeout.
   - **Fix**: Ensure Ollama is running; reduce concurrency if the GPU is saturated, or run `uv run python scripts/full_system_status_check.py` to assess headroom and tune (see scripts/SCRIPTS_INDEX.md).
   - **Burst (48h catch-up)**: Settings may be raised temporarily (e.g. concurrency 6, content_enrichment interval 300s, batch 60, `RATE_LIMIT_SLEEP` 0.4). Revert to normal (5, 600, 40, 0.6) after catch-up.

4. **Retries and backoff**  
   The automation manager retries failed tasks (up to `max_retries`) with backoff. If the **root cause** is statement timeout, increase `DB_STATEMENT_TIMEOUT_MS` so the first run succeeds instead of relying on retries.

**Quick checks**:
```bash
# Current timeout in use (API must be running with same env)
# In .env:
grep DB_STATEMENT_TIMEOUT_MS .env || echo "Not set (using default 60000 ms)"

# Logs: look for timeout or cancel
grep -E "canceling|statement timeout|Task .* failed|event_tracking failed|story_continuation failed" logs/api_server.log 2>/dev/null | tail -20
```

### **Enrichment backlog not decreasing / “700 per hour” but backlog grows**

**Symptoms**: Monitor shows ~700/hr (or another high rate) and an ETA for the article enrichment queue, but after hours the “articles remaining” count does not drop, or even increases.

**What the logs show (typical)**:

- **Content enrichment (v8)** is the phase that reduces the “short/missing content” backlog (trafilatura full-text fetch); it runs as part of the collection cycle.
- Successful runs log: `Content enrichment (v8): N articles enriched` (N often 55–58 per run when batch=60).
- Failed runs log: `Content enrichment failed: canceling statement due to statement timeout` and complete **0** articles for that run.

**Why the backlog doesn’t drop**:

1. **Actual throughput is much lower than 700/hr**  
   Example from a single day’s logs: 4 successful runs (58+57+58+55 = 228 articles) and 2 runs lost to statement timeout (0 each) over ~2 hours → **~114 articles/hour actual**. The “700” was a theoretical burst rate (batch 60 every 5 min); real rate is lower because (a) some runs are killed by timeout and (b) trafilatura often fails on many URLs (empty content), so not every attempted article becomes “enriched”.

2. **Statement timeout (60s default)**  
   The content_enrichment batch runs in one thread and can hold a DB connection for several minutes (many fetches + UPDATEs + context refresh). If any single statement exceeds 60s (e.g. a slow `UPDATE intelligence.contexts` or a heavy scan), PostgreSQL cancels it and the **entire** run commits 0. So you can have 2–3 runs per hour that do 0.

3. **Inflow vs outflow**  
   New RSS articles with short content arrive continuously. If inflow (e.g. 150–200/hr) is above actual enrichment outflow (~100–120/hr when timeouts occur), the backlog grows even though the system is “processing.”

**What we did**:

- **Dashboard**: Backlog status now uses a **measured** rate when possible (articles updated to full content in last 1h/24h), with fallback 300/hr and a “(measured 1h)”, “(measured 24h)”, or “(no recent data)” label. Restart the API so the new backlog endpoint is used; the displayed rate may still be inflated by other phases that update articles (entity/topic), so treat it as an upper bound.
- **Content enrichment batch**: The enrichment service sets a **5-minute** statement timeout for the duration of its batch only, then resets it, so long runs are no longer killed by the default 60s. This should reduce “Content enrichment failed: statement timeout” and increase actual enriched count per hour.

**Check actual enrichment rate from logs**:
```bash
# Successful enrichment counts (each run; duplicate lines are from service + automation_manager)
grep "Content enrichment (v8):" logs/api_server.log | tail -50

# Failures (0 articles that run)
grep "Content enrichment failed" logs/api_server.log | tail -20
```

## 🐛 Error Messages

### **"generator object has no attribute 'query'"**
**Cause**: Database connection pattern issue  
**Solution**: Fixed in current code. Restart the API: `./stop_system.sh && ./start_system.sh`

### **"column does not exist"**
**Cause**: Database schema mismatch  
**Solution**: Run the relevant migration, then verify with `psql` against your `DB_HOST` / `DB_NAME` (see [DATABASE.md](DATABASE.md)).

### **"connection refused"**
**Cause**: Service not running or port conflict  
**Solution**:
```bash
ss -tlnp | grep -E ":(3000|8000|5432) "
pgrep -fa "uvicorn.*main:app"
./stop_system.sh && ./start_system.sh
```

### **"invalid input syntax for type integer"**
**Cause**: Route conflict (e.g., /stats being caught by /{id} route)  
**Solution**: Fixed in current code. Restart the API: `./stop_system.sh && ./start_system.sh`

## 🔍 Log Analysis

### **API Logs**
```bash
tail -100 logs/api_server.log
tail -f logs/api_server.log
grep -i error logs/api_server.log | tail -40
```

### **Database**
PostgreSQL runs on **Widow** (or tunnel); use host logs or `psql` from any client with your `.env` credentials — not container logs.

### **Frontend**
```bash
tail -80 logs/frontend.log
```

## 🔄 Recovery Procedures

### **Complete application restart** (API + Vite)
```bash
./stop_system.sh && ./start_system.sh
curl -s --max-time 5 http://localhost:8000/api/system_monitoring/health
```

### **Database recovery**
Use your normal PostgreSQL backup/restore on **Widow** (or NAS). There is no Compose volume reset in the default bare-metal layout.

### **Code not reflected after edit**
You run from the repo checkout; restart the API so uvicorn reloads (or rely on `--reload` only in dev — production-style starts use `start_system.sh` without reload).

## 📊 Performance Issues

### **Slow API Responses**
```bash
psql -h "$DB_HOST" -p "$DB_PORT" -U newsapp -d news_intel -c "SELECT * FROM pg_stat_activity LIMIT 20;"
free -h
top -b -n1 | head -20
```

### **High Memory Usage**
```bash
free -h
./stop_system.sh && ./start_system.sh
grep -i memory logs/api_server.log | tail -20
```

## 🔧 Maintenance

### **Regular health checks**
```bash
curl -s http://localhost:8000/api/system_monitoring/health
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
pg_isready -h "${DB_HOST:-192.168.93.101}" -p "${DB_PORT:-5432}" -U newsapp || true
```

### **Log rotation**
Rotate `logs/*.log` with **logrotate** or your distro defaults; optional Docker log-driver settings are irrelevant when not using containers.

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
