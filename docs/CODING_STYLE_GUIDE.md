# News Intelligence System — Coding Style Guide

## Overview

Coding standards, naming conventions, and architectural patterns for the News Intelligence System. Ensures consistency, maintainability, and a single source of truth for config.

**Last updated:** 2026-03  
**Status:** Active  
**API:** Flat `/api` (no version in path). See "Router Prefix Convention" below.  
**Resource discipline:** Core principle 5 and § Database standards → **Resource discipline and lean pipeline**; see also `docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md`.

---

## 🎯 **CORE PRINCIPLES**

### **1. Consistency Over Cleverness**
- Use established patterns consistently
- Prefer readability over brevity
- Follow existing conventions

### **2. Single Source of Truth**
- One configuration file per concern
- Centralized environment management
- No duplicate functionality

### **3. Explicit Over Implicit**
- Clear naming conventions
- Explicit imports and dependencies
- Obvious code structure

### **4. Reuse Before Create** ⭐ **CORE DESIGN PHILOSOPHY**
- **Search existing AND archived code before writing anything new**
- **Restore and modernize archived code** rather than rebuilding from scratch
- **Improve existing code** before creating new files
- **Use composition over duplication** - Add features to existing services, don't create "Enhanced" versions
- **Consolidate, don't proliferate** - Merge duplicate functionality into single source
- **Delete legacy files** - Remove old versions after migration, don't keep them as "legacy"

#### **The Archive-First Workflow**
Before creating any new file, service, or component:
1. Search the active codebase for similar functionality
2. Search `archive/` directories for previously-built code that could be restored
3. If found: restore, modernize (e.g. JS→TSX), and integrate
4. If nothing exists: only then create from scratch

Archive locations to check:
- `archive/` — full project backups and old versions
- `web/_archived_interface/` — archived frontend components (e.g. old DomainLayout)
- `api/_archived/` — archived API files
- `scripts/archive/` — archived scripts
- `docs/_archive/` — archived documentation (excluded from Cursor context)

#### **The "Improve Existing" Pattern**
```python
# ❌ WRONG - Creating duplicate services
class RSSService:
    def fetch(self): pass

class EnhancedRSSService:  # ❌ Duplicate!
    def fetch(self): pass  # Same logic duplicated
    def fetch_with_cache(self): pass

# ✅ CORRECT - Improve existing service with composition
class RSSService:
    def __init__(self, cache=None, deduplicator=None):
        self.cache = cache  # Optional feature via composition
        self.deduplicator = deduplicator  # Optional feature
    
    def fetch(self, use_cache=True):
        if use_cache and self.cache:
            return self.cache.get_or_fetch(...)
        return self._fetch_raw()
```

#### **The "Consolidation" Pattern**
```python
# ❌ WRONG - Multiple versions of same functionality
# Dashboard.js, Dashboard.tsx, EnhancedDashboard.js, UnifiedDashboard.js, Phase2Dashboard.tsx

# ✅ CORRECT - Single source of truth
# Dashboard.tsx (consolidates all features from other versions)
```

#### **The "Feature Module" Pattern**
```python
# ❌ WRONG - Separate files for each feature level
# rag_service.py, enhanced_rag_service.py, enhanced_rag_retrieval.py, rag_enhanced_service.py

# ✅ CORRECT - Feature modules within single service
# services/rag/
#   ├── __init__.py      # Main RAGService class
#   ├── base.py          # Base RAG operations
#   ├── retrieval.py     # Retrieval feature
#   ├── enhancement.py   # Enhancement feature
#   └── domain_knowledge.py  # Domain knowledge feature
```

#### **Red Flags to Avoid**
- ❌ Creating "Enhanced" versions (EnhancedXService, EnhancedXPage)
- ❌ Creating "Unified" versions (UnifiedXService, UnifiedXPage)
- ❌ Creating "New" versions (NewXService, NewXPage)
- ❌ Marking files as "Legacy" but keeping them active
- ❌ Creating new files for small features instead of extending existing
- ❌ Duplicating logic instead of extracting to shared utilities

#### **Before Creating a New File, Ask:**
1. Can I extend an existing file instead?
2. Can I use composition to add this feature?
3. Is there duplicate functionality I should consolidate first?
4. Can I refactor existing code to support this feature?

### **5. Resource Budgets and Bounded Work**
Treat **RAM**, **DB connections**, and **async/LLM concurrency** as explicit **budgets** per process—not unlimited resources.

- **Footprint math:** Sum each pool’s **max** × every process that imports `shared.database.connection` (API workers, automation host, scripts). Stay under PostgreSQL `max_connections` and PgBouncer limits. See **`docs/PGBOUNCER_AND_CONNECTION_BUDGET.md`**.
- **Connection lifetime:** Never hold a pooled connection across LLM calls, HTTP, or `sleep`; close and reopen (see `AGENTS.md` database rules).
- **Large text:** Prefer **chunks** and **truncated prompts**; avoid keeping multiple full copies of the same document in memory.
- **Expensive-once work:** Embeddings, parsed HTML, normalized body—store **one canonical** result or use a **bounded** cache with stable keys and TTLs; do not recompute the same row from two unrelated phases.
- **Scheduling:** Bounded scheduler tick + cooldown + optional backpressure are **features**; unbounded in-memory queues are **debt**. Tune `AUTOMATION_*` and `OLLAMA_*_CONCURRENCY` together with DB pools.
- **Audits:** Periodically review phases with **highest wall time** and **largest backlog** (`scripts/automation_run_analysis.py`, backlog status endpoints).

Full checklist and env reference: **`docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md`**.

---

## 🐍 **PYTHON CODING STANDARDS**

### **File Naming Conventions**
```python
# ✅ CORRECT - Use snake_case for files
api/config/database.py
api/domains/news_aggregation/routes/news_aggregation.py
api/services/article_service.py

# ❌ WRONG - Don't use camelCase or kebab-case
api/config/databaseConfig.py
api/domains/news_aggregation/routes/article-routes.py
```

### **Class Naming Conventions**
```python
# ✅ CORRECT - Use PascalCase for classes
class DatabaseManager:
    pass

class HealthService:
    pass

class ArticleProcessor:
    pass

# ❌ WRONG - Don't use snake_case for classes
class database_manager:
    pass
```

### **Function and Variable Naming**
```python
# ✅ CORRECT - Use snake_case for functions and variables
def get_database_connection():
    connection_pool = create_pool()
    return connection_pool

# ❌ WRONG - Don't use camelCase
def getDatabaseConnection():
    connectionPool = createPool()
    return connectionPool
```

### **Constant Naming**
```python
# ✅ CORRECT - Use UPPER_SNAKE_CASE for constants
DATABASE_CONFIG = {
    'host': 'news-intelligence-postgres',
    'port': 5432
}

MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30

# ❌ WRONG - Don't use lowercase for constants
database_config = {...}
max_retries = 5
```

### **Import Organization**
```python
# ✅ CORRECT - Organize imports in this order
# 1. Standard library imports
import os
import sys
import logging
from pathlib import Path

# 2. Third-party imports
import psycopg2
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

# 3. Local application imports
from config.database import get_db
from schemas.robust_schemas import APIResponse
from services.health_service import HealthService
```

---

## 🐳 **DOCKER STANDARDS**

### **Service Naming Convention**
```yaml
# ✅ CORRECT - Use news-intelligence-{service} pattern
services:
  postgres:
    container_name: news-intelligence-postgres
  redis:
    container_name: news-intelligence-redis
  api:
    container_name: news-intelligence-api
  frontend:
    container_name: news-intelligence-frontend
  monitoring:
    container_name: news-intelligence-monitoring

# ❌ WRONG - Don't use inconsistent naming
services:
  postgres:
    container_name: postgres
  redis:
    container_name: redis
  api:
    container_name: news-api
```

### **Environment Variable Standards**
```yaml
# ✅ CORRECT - Use consistent environment variable names
environment:
  # Database Configuration
  DB_HOST: news-intelligence-postgres
  DB_NAME: news_intelligence
  DB_USER: newsapp
  DB_PASSWORD: newsapp_password
  DB_PORT: 5432
  DATABASE_URL: postgresql://newsapp:newsapp_password@news-intelligence-postgres:5432/news_intelligence
  
  # Redis Configuration
  REDIS_URL: redis://news-intelligence-redis:6379/0
  
  # Application Configuration
  ENVIRONMENT: production
  LOG_LEVEL: info
  PYTHONPATH: /app
```

### **Volume Naming Convention**
```yaml
# ✅ CORRECT - Use {service}_data pattern
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  prometheus_data:
    driver: local

# ❌ WRONG - Don't use inconsistent volume names
volumes:
  postgres_storage:
    driver: local
  redis_cache:
    driver: local
  monitoring_data:
    driver: local
```

---

## 🗄️ **DATABASE STANDARDS**

### **Table Naming Convention**
```sql
-- ✅ CORRECT - Use snake_case for table names
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rss_feeds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL
);

-- ❌ WRONG - Don't use camelCase or PascalCase
CREATE TABLE Articles (
    id SERIAL PRIMARY KEY,
    Title TEXT NOT NULL
);
```

### **Column Naming Convention**
```sql
-- ✅ CORRECT - Use snake_case for column names
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    published_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ❌ WRONG - Don't use camelCase
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    publishedDate TIMESTAMP,
    createdAt TIMESTAMP
);
```

### **Connection Pool Architecture**

The system uses four independent psycopg2 pools plus SQLAlchemy. In production, point **`DB_HOST` / `DB_PORT`** at **PgBouncer** so many app slots multiplex onto fewer PostgreSQL backends; see **`docs/PGBOUNCER_AND_CONNECTION_BUDGET.md`**.

All pool sizes are configurable via environment variables. Defaults favor **UI responsiveness** (reserved pool, short checkout timeout) and a **moderate worker cap** so automation does not crowd out small `max_connections` budgets; raise worker limits when metrics show headroom.

| Pool | Library | Env Vars | Defaults | Purpose |
|------|---------|----------|----------|---------|
| **UI** | psycopg2 `ThreadedConnectionPool` | `DB_POOL_UI_MIN/MAX` | 2 / 16 | Page loads, monitoring, hot read paths (3 s checkout) |
| **Worker** | psycopg2 `ThreadedConnectionPool` | `DB_POOL_WORKER_MIN/MAX` | 2 / 28 | Automation, enrichment, collection; `DB_POOL_MAX` legacy if `DB_POOL_WORKER_MAX` unset |
| **Health** | psycopg2 `ThreadedConnectionPool` | `DB_POOL_HEALTH_MIN/MAX` | 1 / 2 | Automation `health_check` probes + `automation_run_history` for that phase only (2 s checkout; `DB_HEALTH_GETCONN_TIMEOUT_SECONDS`) |
| **SQLAlchemy** | SQLAlchemy `QueuePool` | `DB_POOL_SA_SIZE/OVERFLOW` | 3 / 8 | ORM-based services (storylines, RSS, timelines) |

**Maximum client connections per process (worst case):** UI max + worker max + health max + SA size + SA overflow = **16 + 28 + 2 + 3 + 8 = 57** by default (not 1:1 with Postgres sessions when PgBouncer is used).
Ensure PostgreSQL **`max_connections`** (and PgBouncer **`default_pool_size`**) accommodate **every** process that connects (API workers, Widow cron, dev hosts), plus admin headroom.

**Checkout timeouts** (how long to wait for a free connection before raising):
- Worker pool: 30 s (env `DB_WORKER_GETCONN_TIMEOUT_SECONDS`)
- UI pool: 3 s (env `DB_UI_GETCONN_TIMEOUT_SECONDS`)
- Health pool: 2 s (env `DB_HEALTH_GETCONN_TIMEOUT_SECONDS`)
- SQLAlchemy pool: 30 s (built-in `pool_timeout`)

**When to use which pool:**
- `get_db_connection()` / `get_db_connection_context()` → Worker pool (automation, writes, heavy batch)
- `get_ui_db_connection()` / `get_ui_db_connection_context()` → UI pool (monitoring, page-load routes)
- `get_health_db_connection()` / `get_health_db_connection_context()` → Health pool only (automation `health_check`; do not use for pipeline work)
- `DomainAwareService.get_read_db_connection()` → UI pool with `search_path` set (domain-scoped **reads** only; listings / detail views)
- `get_db()` / `next(get_db())` → SQLAlchemy pool (ORM-based services only)
- Never mix: don't use SQLAlchemy sessions for heavy background batch work unless
  `DB_POOL_SA_SIZE` is sized for it.

### **Resource discipline and lean pipeline (mandatory mindset)**

Align with **Core principle 5** (above). When adding or changing background work:

| Concern | What to do |
|--------|------------|
| **Budgets** | Treat `DB_POOL_*`, `AUTOMATION_MAX_CONCURRENT_TASKS`, `MAX_CONCURRENT_OLLAMA_TASKS`, `OLLAMA_CPU_CONCURRENCY` / `OLLAMA_GPU_CONCURRENCY`, and `AUTOMATION_EXECUTOR_MAX_WORKERS` as a **single system**. Raising automation concurrency without DB or Ollama headroom moves waits, not magic throughput. |
| **Chunking** | Read and process **large text in slices**; truncate prompts consistently; avoid loading full corpora into Python lists for routine paths. |
| **No duplicate expensive work** | One canonical place for embeddings, parsed HTML, or normalized content where feasible; if two phases need the same artifact, **read from storage** or a shared service—do not re-embed the same row twice. |
| **Scheduling** | Bounded tick (`AUTOMATION_SCHEDULER_TICK_SECONDS`), cooldown (`AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS`), collection throttle, optional `AUTOMATION_QUEUE_SOFT_CAP` (prefer `0` = off). Unbounded queue growth is a bug. |
| **Proof** | Before micro-optimizing, **measure**: phase duration from `automation_run_history` (`scripts/automation_run_analysis.py`), backlog counts, pool utilization. |

**Reference:** `docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md` (checklist, env names, audit commands).

### **Index Naming Convention**
```sql
-- ✅ CORRECT - Use idx_{table}_{column} pattern
CREATE INDEX idx_articles_published_date ON articles(published_date);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_rss_feeds_status ON rss_feeds(status);

-- ❌ WRONG - Don't use inconsistent index names
CREATE INDEX articles_published_date ON articles(published_date);
CREATE INDEX idx_articles_category_idx ON articles(category);
```

---

## 🌐 **API STANDARDS**

### **Router Prefix Convention (CRITICAL)**
The project uses **flat `/api`** — no version segment in the path (e.g. `/api/{domain}/finance/...`, not `/api/...`).

```python
# ✅ CORRECT - Main domain routers (included directly in main.py)
# Use prefix /api; no version in path
router = APIRouter(
    prefix="/api",
    tags=["Domain Name"]
)

# ✅ CORRECT - Sub-routers (included in other routers)
# These should NOT have a prefix - the parent router provides it
router = APIRouter(
    tags=["Sub-feature Name"]
)

# ✅ CORRECT - Feature-specific routers with sub-paths
router = APIRouter(
    prefix="/api/system_monitoring",  # Full path if included in main
    tags=["System Monitoring"]
)

# ❌ WRONG - Double prefix (causes /api/api/...)
# Parent router has /api, child router also has /api
parent_router = APIRouter(prefix="/api")
child_router = APIRouter(prefix="/api")  # ❌ WRONG!
parent_router.include_router(child_router)  # Results in /api/api/...

# ✅ CORRECT - Child router without prefix
parent_router = APIRouter(prefix="/api")
child_router = APIRouter()  # ✅ No prefix - inherits from parent
parent_router.include_router(child_router)  # Results in /api/...
```

### **Router Inclusion Pattern**
```python
# ✅ CORRECT - In api/main.py:
from domains.storyline_management.routes import router as storyline_management_router
app.include_router(storyline_management_router)  # Router has prefix="/api"

# In api/domains/storyline_management/routes/__init__.py:
router = APIRouter(prefix="/api")
router.include_router(crud_router)      # Sub-routers have no prefix
router.include_router(articles_router)

# In api/domains/storyline_management/routes/storyline_crud.py:
router = APIRouter()  # No prefix — path comes from parent
```

### **Route Naming Convention**
```python
# ✅ CORRECT - Use snake_case for route paths
@router.get("/articles/")
@router.get("/rss_feeds/")
@router.get("/health/")
@router.post("/articles/")
@router.put("/articles/{article_id}")
@router.delete("/articles/{article_id}")

# ❌ WRONG - Don't use camelCase or kebab-case
@router.get("/articles-list/")
@router.get("/rssFeeds/")
@router.get("/health-check/")
```

### **Response Model Naming**
```python
# ✅ CORRECT - Use descriptive response model names
@router.get("/articles/", response_model=APIResponse)
@router.get("/health/", response_model=HealthResponse)
@router.get("/dashboard/", response_model=DashboardResponse)

# ❌ WRONG - Don't use generic names
@router.get("/articles/", response_model=Response)
@router.get("/health/", response_model=Data)
```

### **Error Handling Standards**
```python
# ✅ CORRECT - Use consistent error handling
@router.get("/articles/")
async def get_articles():
    try:
        # Business logic here
        return APIResponse(
            success=True,
            data=articles,
            message="Articles retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve articles"
        )

# ❌ WRONG - Don't use inconsistent error handling
@router.get("/articles/")
async def get_articles():
    # No error handling
    return articles
```

---

## ⚡ **THREADING & ASYNC RULES** (Critical for API Responsiveness)

The API uses uvicorn with a single-threaded asyncio event loop for HTTP handling.
Background services (automation, orchestration, finance, topic extraction) run in
their own daemon threads with their own event loops.  Violating these rules will
make the API unresponsive.

### **Rule 1: Never block the main event loop**

Background services must **not** use `asyncio.create_task()` on the main event
loop.  Start them in a dedicated `threading.Thread` with `asyncio.new_event_loop()`:

```python
# ✅ CORRECT — own thread, own loop
def _run_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_start())

threading.Thread(target=_run_background, daemon=True).start()

# ❌ WRONG — blocks the main uvicorn event loop
asyncio.create_task(my_service.run_loop())
```

### **Rule 2: Sync route handlers for DB-heavy endpoints**

If a route handler does synchronous work (psycopg2 queries, file I/O, subprocess),
declare it as a plain `def` — FastAPI will run it in a thread pool automatically:

```python
# ✅ CORRECT — sync handler; FastAPI runs in thread pool, event loop stays free
@router.get("/heavy_report")
def get_heavy_report():
    conn = get_db_connection()
    ...

# ❌ WRONG — async handler doing sync DB work blocks the event loop
@router.get("/heavy_report")
async def get_heavy_report():
    conn = get_db_connection()  # blocks event loop!
    ...
```

Use `async def` only when the handler truly `await`s async I/O (e.g. httpx, aiofiles).

### **Rule 3: No import shadowing inside lifespan / long functions**

Python treats `import X` anywhere in a function as making `X` a local variable
for the **entire** function.  If `X` is already imported at module level, a later
`import X` inside the same function shadows it and causes `UnboundLocalError`
before that line is reached:

```python
import threading          # module-level

async def lifespan(app):
    threading.Thread(...)  # ❌ UnboundLocalError — shadowed by line below
    ...
    import threading       # shadows the module-level import for the WHOLE function
```

**Fix:** remove redundant inner imports; use the module-level import.

### **Rule 4: Database connection lifecycle (CRITICAL — prevents pool exhaustion)**

Every `get_db_connection()` call **must** be paired with a guaranteed `conn.close()`.
Failure to close leaks a connection from the pool; once all slots are exhausted the
process deadlocks.

```python
# ✅ BEST — context manager (zero risk of leak)
from shared.database.connection import get_db_connection_context

with get_db_connection_context() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT ...")

# ✅ ACCEPTABLE — manual try/finally (conn = None before try)
conn = None
try:
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT ...")
    conn.commit()
finally:
    if conn:
        conn.close()

# ❌ WRONG — conn.close() only in try (exception skips it)
try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT ...")
    conn.close()           # skipped if cur.execute raises!
except Exception:
    pass

# ❌ WRONG — conn.close() after try/except (exception in except skips it)
try:
    conn = get_db_connection()
    ...
except Exception:
    ...
conn.close()               # NameError if get_db_connection raised
```

**Additional rules:**
- Never hold a connection across an LLM call, HTTP request, `time.sleep()`, or any
  I/O that might take seconds. Fetch data, close the connection, do slow work, then
  reopen if you need to write back.
- SQLAlchemy sessions (`get_db()` / `next(get_db())`) follow the same rule:
  always `db.close()` in a `finally` block, and initialise `db = None` before the
  `try` so the `finally` guard never hits a `NameError`.
- For UI/monitoring endpoints, use `get_ui_db_connection()` (or `get_ui_db_connection_context()`)
  which draws from a dedicated pool with a 3-second checkout timeout.
- Direct `psycopg2.connect()` calls are **forbidden** in services; use
  `get_db_connect_kwargs()` only in one-off scripts that genuinely cannot use the pool.

### **Rule 5: Guard DB queries with statement timeouts**

Any DB query callable from an API endpoint (directly or transitively) must have a
local statement timeout so a slow query cannot block the thread indefinitely:

```python
cur.execute("SET LOCAL statement_timeout = '3s'")
cur.execute("SELECT ...")
```

### **Rule 6: Limit background thread pools**

Keep `ThreadPoolExecutor(max_workers=...)` small (2–4) in background services.
Each worker thread competes for the GIL; too many workers starve the main thread.
The automation manager caps at `max_concurrent_tasks = 3`.

### **Debugging a hung API**

```bash
# Send SIGUSR1 to dump all thread tracebacks to api_server.log
kill -SIGUSR1 $(pgrep -f "uvicorn.*main:app")
tail -100 logs/api_server.log
```

The main thread's stack trace will show exactly where it is blocked.

---

## 📁 **FILE STRUCTURE STANDARDS**

### **Project Structure**
```
News Intelligence/
├── api/                          # Backend API
│   ├── main.py                # Application entry point
│   ├── config/
│   │   ├── database.py           # Re-exports shared.database.connection
│   │   └── paths.py               # Path management
│   ├── shared/
│   │   └── database/
│   │       └── connection.py     # ✅ SINGLE source: get_db_config, get_db_connection
│   ├── domains/                  # Domain-scoped routes and services
│   │   └── {domain}/routes/      # e.g. storyline_management, system_monitoring
│   ├── services/                 # Business logic
│   └── database/migrations/     # SQL migrations (active); archive/historical/ for pre-176 DDL
├── web/                          # Frontend (React + Vite + MUI)
│   ├── src/
│   │   ├── App.tsx               # Routes, DomainProvider, MainLayout
│   │   ├── layout/MainLayout.tsx # Domain shell (sidebar, nav)
│   │   ├── pages/
│   │   ├── components/
│   │   └── services/api/         # API client modules
│   └── package.json
├── docs/                         # Documentation
│   ├── DOCS_INDEX.md             # Start here
│   ├── CODING_STYLE_GUIDE.md
│   ├── ARCHITECTURE_AND_OPERATIONS.md
│   └── _archive/                 # Superseded docs (excluded from Cursor)
└── scripts/                      # Utility scripts
```

### **Configuration File Standards**
```python
# ✅ CORRECT - Single source per concern
api/shared/database/connection.py  # get_db_config, get_db_connection (pool)
api/config/database.py             # Re-exports shared (backward compat)
api/config/paths.py                # Path management

# ❌ WRONG - Duplicate or legacy config
api/config/robust_database.py
api/config/unified_database.py
# Do not use inline DB config; use get_db_config() or get_db_connection()
```

---

## 🔧 **ENVIRONMENT VARIABLE STANDARDS**

### **Naming Convention**
```bash
# ✅ CORRECT - Use UPPER_SNAKE_CASE
DB_HOST=news-intelligence-postgres
DB_NAME=news_intelligence
DB_USER=newsapp
DB_PASSWORD=newsapp_password
REDIS_URL=redis://news-intelligence-redis:6379/0
API_V1_STR=/api
PROJECT_NAME=News Intelligence System

# ❌ WRONG - Don't use camelCase or lowercase
dbHost=news-intelligence-postgres
db_name=news_intelligence
redisUrl=redis://news-intelligence-redis:6379/0
```

### **Environment File Organization**
```bash
# ✅ CORRECT - Use .env in project root
.env

# ❌ WRONG - Don't create multiple env files
.env.local
.env.production
.env.development
configs/.env
```

---

## 📝 **DOCUMENTATION STANDARDS**

### **Keep docs in sync with code**
When you make a **major change** (e.g. API path scheme, versioning, removal of a feature, or a new system boundary), **retroactively update all affected docs** so they stay accurate. Check at least:
- [DOCS_INDEX.md](DOCS_INDEX.md), [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md), archived product narrative: [_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md](_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md); release notes in `_archive/releases/` and `_archive/retired_root_docs_2026_03/`
- Architecture trio: [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md), [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md), [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) when exposure or ops change
- API reference or route tables in any of the above

Avoid leaving references to old paths, versions, or behavior (e.g. `/api/` when the code uses flat `/api/`).

### **File Naming Convention**
```markdown
# ✅ CORRECT - Use UPPER_SNAKE_CASE for documentation files
ARCHITECTURAL_STANDARDS.md
CODING_STYLE_GUIDE.md
API_DOCUMENTATION.md
DATABASE_SCHEMA_DOCUMENTATION.md

# ❌ WRONG - Don't use camelCase or kebab-case
architectural-standards.md
codingStyleGuide.md
api-documentation.md
```

### **Documentation Structure**
```markdown
# 📝 Document Title

## 📋 **OVERVIEW**
Brief description of the document's purpose.

## 🎯 **CORE PRINCIPLES**
Key principles and guidelines.

## 📊 **DETAILED SECTIONS**
Specific implementation details.

## ✅ **COMPLIANCE CHECKLIST**
Items to verify compliance.

---

*Last Updated: YYYY-MM-DD*
*Version: X.X*
*Status: Active*
```

---

## 🚫 **ANTI-PATTERNS TO AVOID**

### **Configuration Fragmentation**
```python
# ❌ WRONG - Multiple database config files
from config.database import get_db
from config.robust_database import get_robust_db
from config.unified_database import get_unified_db
from database.connection import get_connection

# ✅ CORRECT - Single database config file
from config.database import get_db
```

### **Inconsistent Naming**
```python
# ❌ WRONG - Inconsistent naming
class database_manager:
    def getDatabaseConnection():
        pass

# ✅ CORRECT - Consistent naming
class DatabaseManager:
    def get_database_connection():
        pass
```

### **Container sprawl (out of scope for default dev)**
Bare-metal runs use `start_system.sh` and `.env` for Postgres (Widow/tunnel). Any Docker Compose material is **archived** under `docs/archive/docker_stack/` and is not part of the active programming path.

---

## 🔍 **VALIDATION TOOLS**

### **Code Style Validation**
```bash
# Run linting
python3 -m flake8 api/
python3 -m black api/
python3 -m isort api/
```

### **Architecture Validation**
```bash
# Validate configuration consistency
python3 api/scripts/validate_architecture.py

# Test database connectivity
python3 api/scripts/test_database_connection.py
```

---

## **Automation and tooling**

**AutomationManager** scheduling semantics (`last_run`, CPU/GPU lanes vs Ollama, parallel groups, worker counts): [`AUTOMATION_MANAGER_SCHEDULING.md`](AUTOMATION_MANAGER_SCHEDULING.md).

These commands align the repo with this guide. **CI** (`.github/workflows/ci.yml`) runs Ruff + a small pytest smoke suite + frontend lint/format/tsc.

**Python (from repository root, with `uv`):**

```bash
uv sync --extra dev
uv run ruff format api tests          # apply formatting
uv run ruff check api tests           # lint
uv run pytest tests/unit/test_orchestrator_types.py tests/unit/test_orchestrator_utils.py -q
```

**Optional — Git hooks:** install [pre-commit](https://pre-commit.com/) and run `pre-commit install` to run Ruff on commit (see `.pre-commit-config.yaml`).

**Frontend (`web/`):**

```bash
cd web && npm ci && npm run lint && npm run format:check
```

Release builds run **`npm run build`** (TypeScript + Vite). Standalone **`npx tsc --noEmit`** is not yet clean across the whole tree; use it locally when touching types.

**Editor:** root `.editorconfig` sets **4 spaces** for `*.py` and **2 spaces** for JS/TS/JSON/YAML.

**Ruff:** Rules and ignores live in `pyproject.toml` under `[tool.ruff]` — expand `select` and trim `ignore` over time.

---

## 📋 **IMPLEMENTATION CHECKLIST**

### **Before Writing New Code**
- [ ] Searched active codebase for existing similar functionality
- [ ] Searched archive directories for previously-built code
- [ ] Confirmed no existing code can be extended or restored
- [ ] Follow established naming conventions
- [ ] Use single source of truth for configuration
- [ ] Follow error handling patterns
- [ ] Add appropriate logging
- [ ] Write clear documentation

### **Before Adding New Features**
- [ ] Searched archive for prior implementations of this feature
- [ ] Check if existing functionality can be extended
- [ ] Follow architectural standards
- [ ] Update documentation
- [ ] Add validation tests
- [ ] Follow naming conventions

### **Before Production Deployment**
- [ ] All code follows style guide
- [ ] No configuration fragmentation
- [ ] All services use consistent naming
- [ ] Documentation is updated
- [ ] Validation tests pass

---

## **Documentation alignment**

When you change the **API** (routes, path segments, response shape) or **core behaviour** (entry points, DB config, domain layout):

1. **Update docs in the same change (or next commit):** `AGENTS.md`, this guide, `ARCHITECTURE_AND_OPERATIONS.md`, and any domain/feature doc that references the change.
2. **Paths:** Flat `/api` (no version in path). Route segments: `snake_case` (e.g. `system_monitoring`, `rss_feeds`). Domain-scoped: `/api/{domain}/...` with domain `politics` | `finance` | `science-tech`.
3. **Code and tests:** Keep test URLs and frontend API calls in sync with real routes (no `/api/v4/`, no kebab-case route segments).
4. **Single source:** Entry points and file layout in `AGENTS.md` and “Project structure” in this guide must match the repo (`main.py`, `api/domains/*/routes/`, `MainLayout.tsx`).

---

## 📚 **REFERENCE DOCUMENTATION**

### **Related Documents**
- [DOCS_INDEX.md](./DOCS_INDEX.md) - Documentation index
- [ARCHITECTURE_AND_OPERATIONS.md](./ARCHITECTURE_AND_OPERATIONS.md) - Architecture and ops
- [DATABASE_SCHEMA_DOCUMENTATION.md](./_archive/retired_root_docs_2026_03/DATABASE_SCHEMA_DOCUMENTATION.md) - Legacy database schema snapshot (archived)
- [API_REFERENCE.md](./API_REFERENCE.md) - API endpoints

### **External References**
- [PEP 8 - Python Style Guide](https://pep8.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

*This coding style guide is the single source of truth for News Intelligence System code standards and should be referenced before any code changes.*
