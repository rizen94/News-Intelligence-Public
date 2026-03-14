# Database connection audit — single source of truth and consistency

**Why the DB has been unreliable since migration:** The codebase uses **two patterns** and several **wrong defaults**. After the NAS → Widow migration, the canonical config (Widow host, `news_intel` DB, password from env) lives in one place; other code sometimes builds its own config with old or empty defaults and never sees your `.env`.

---

## Single source of truth

| What | Where |
|------|--------|
| **Config** | `api/shared/database/connection.py` → `get_db_config()` |
| **Connections (pooled)** | `api/shared/database/connection.py` → `get_db_connection()` |
| **Re-export (compat)** | `api/config/database.py` re-exports the above; use either. |

`get_db_config()` reads **only** from `os.environ`: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`. Defaults: host `192.168.93.101`, port `5432`, database `news_intel`, user `newsapp`, password `""`. So **if the process is started without `DB_PASSWORD` in the environment** (e.g. API started from an IDE or before `.env` is loaded), every path that uses this config gets an empty password and connections fail.

---

## Two patterns in the codebase

### Pattern A: Use the pool (preferred)

- **Code:** `conn = get_db_connection()` (from `shared.database.connection` or `config.database`).
- **Used by:** Most routes (finance, storylines, content_analysis, system_monitoring, context_centric, etc.), compatibility layer, many services that take a connection or call `get_db_connection` per request.
- **Behaviour:** First call initializes the pool from `get_db_config()`; later calls take a connection from the pool. One place to fix (env + restart) and everything using the pool is fixed.

### Pattern B: Service holds a `db_config` dict and calls `psycopg2.connect(**self.db_config)`

- **Code:** Service is constructed with `db_config = get_db_config()` (or a dict); later it does `psycopg2.connect(**self.db_config)`.
- **Used by:** AutomationManager, StorylineConsolidationService, ML queue manager, background_processor, RAG base, topic clustering, ai_storyline_discovery, etc.
- **Behaviour:** Config is **snapshotted when the service is created** (usually at app startup in `main_v4.py`). So they use the same env as the pool **if** they get `db_config` from `get_db_config()` at startup. If the process had no `DB_PASSWORD` at startup, that snapshot has empty password and every `connect()` fails.

**Problem:** Some services or scripts build their own config with **different defaults** (e.g. host `postgres` or `localhost`, password `newsapp_password` or `Database@NEWSINT2025`). Those defaults were for Docker/NAS; after migration to Widow they are wrong or stale, and they bypass the single source of truth.

---

## Inconsistencies fixed (all now use shared `get_db_config()`)

| Location | Issue | Status |
|----------|--------|--------|
| `api/config/database.py` | Re-exports shared | ✅ Single source |
| `api/scripts/utilities/scheduler.py` | Own config: host `postgres`, DB `news_system` | ✅ Uses shared `_get_db_config()` |
| `api/services/api_usage_monitor.py` | Hardcoded `news-system-postgres`, `Database@NEWSINT2025` | ✅ Uses shared |
| `api/collectors/rss_collector.py` | Fallback dict at load time | ✅ Uses shared `_db_config()` |
| `api/collectors/enhanced_rss_collector.py` | Fallback: host `postgres`, DB `news_system` | ✅ Uses shared `_db_config()` |
| `api/scripts/analyze_existing_articles.py` | Fallback dict | ✅ Uses shared `get_db_config()` |
| `api/services/storyline_consolidation_service.py` | Inline dict: localhost, `newsapp_password` | ✅ Uses shared when `db_config` is None |
| `api/services/ai_storyline_discovery.py` | Inline dict: localhost, `newsapp_password` | ✅ Uses shared when None |
| `api/modules/deduplication/advanced_deduplication_service.py` | Inline dict: `Database@NEWSINT2025` | ✅ Uses shared when None |
| `api/services/rag/base.py` | Inline dict: localhost, `newsapp_password` | ✅ Uses shared when None |
| `api/services/storyline_service.py` | Inline dict and getter: `news-system-postgres`, `Database@NEWSINT2025` | ✅ Uses shared |
| `api/services/progressive_enhancement_service.py` | Inline dict: `news-system-postgres`, `Database@NEWSINT2025` | ✅ Uses shared |
| `api/services/intelligence_analysis_service.py` | Inline dict: localhost, `newsapp_password` | ✅ Uses shared when None |
| `api/services/automation_manager.py` | Fallback dict for topic clustering task: `newsapp_password` | ✅ Uses shared in that task |
| `api/domains/content_analysis/services/topic_clustering_service.py` | `.get('password', 'newsapp_password')` | ✅ Uses shared when config missing/incomplete |
| `api/domains/storyline_management/routes/storyline_discovery.py` | Two inline dicts: `newsapp_password` | ✅ Uses shared |
| `api/scripts/utilities/manage_intelligence.py` | Multiple inline dicts: postgres, `secure_password_123`, dockside_admin | ✅ Uses shared `_get_db_config()` |
| `api/scripts/utilities/manage_ingestion.py` | Own `get_db_config()`: postgres, news_system | ✅ Uses shared `_get_db_config()` |
| `api/scripts/utilities/manage_intelligence_database.py` | Inline dict: postgres, news_system | ✅ Uses shared when None |
| `api/scripts/utilities/populate_db.py` | Inline connect: localhost | ✅ Uses shared |
| `api/scripts/utilities/create_clusters.py` | Hardcoded postgres, `secure_password_123` | ✅ Uses shared `_get_db_config()` |
| `api/scripts/utilities/process_articles.py` | Hardcoded postgres, `secure_password_123` | ✅ Uses shared |
| `api/scripts/ml_worker.py` | Hardcoded postgres, `newsapp_password` | ✅ Uses shared |
| `api/scripts/optimized_ml_worker.py` | Hardcoded postgres, `Database@NEWSINT2025` | ✅ Uses shared |
| `api/scripts/rss_duplicate_detector.py` | Inline connect: localhost, `newsapp_password` | ✅ Uses shared |
| `api/scripts/disconnect_v3_tables.py` | Inline connect: localhost, `newsapp_password` | ✅ Uses shared |

**Scripts:** Run from `api/` (e.g. `python scripts/utilities/manage_ingestion.py`) or with `PYTHONPATH=api` so `shared.database.connection` resolves. Ensure `.env` is loaded (e.g. `source .env` or `./start_system.sh` exports `DB_*`).

---

## What you must do for a reliable connection

1. **Set `DB_PASSWORD` in project-root `.env`** (and optionally other `DB_*` vars). This is the only place the app reads password from when using the canonical path.
2. **Start the API with that env loaded.** Use `./start_system.sh` (which sources `.env` and exports `DB_*`) or, if you start uvicorn manually, run from a shell that has run `source .env` or `export DB_PASSWORD=...`.
3. **Restart the API after changing `.env`.** The pool and any service that took `db_config` at startup are initialized once; they do not re-read `.env` until the process restarts.

Once the process has `DB_PASSWORD` in the environment at startup, **all code now uses the same config** from `shared.database.connection.get_db_config()` (or the pool via `get_db_connection()`). Isolated defaults have been removed; all connection paths use the pool or `get_db_connect_kwargs()`.

---

## Connection behaviour (no silent fallbacks)

- **`get_db_connection()`** returns a live connection from the pool (or a direct connection only when the pool is unusable). It **raises `ConnectionError`** if the database is unreachable (e.g. turned off). Callers should not expect `None`; they get a connection or an exception.
- **Pool validation:** When taking a connection from the pool, the layer runs a quick `SELECT 1`; if it fails, the connection is discarded and another is tried. Fallback to a direct connection is used only when the pool cannot provide a valid connection, and only when the DB is actually up.
- **`get_db_connect_kwargs()`** returns a dict suitable for `psycopg2.connect(**kwargs)` (includes `connect_timeout` and `options` for `statement_timeout`). Use for one-off scripts that must open a direct connection instead of the pool. Do **not** pass `get_db_config()` to `psycopg2.connect()` — it includes `statement_timeout_ms`, which is not a valid connect argument.

---

## Reliability: main lever vs tooling

**Treat reliability fixes in `connection.py` and config as the main lever.** Pool sizing, fallback behaviour, timeouts, and env (`DB_POOL_MIN`, `DB_POOL_MAX`, `DB_STATEMENT_TIMEOUT_MS`, `DB_CONNECT_TIMEOUT`) are where we improve and harden DB behaviour. IDE extensions (e.g. PostgreSQL in Cursor/VS Code) and MCP tools (DB Query, Database Explorer) are for **visibility and faster diagnosis**—running `pg_stat_activity`, checking connection count, finding slow queries—not for changing how the application connects. Keep prioritising changes in the shared connection layer and `.env` over editor add-ons.
