# News Intelligence System — Agent Guidance

Context for AI assistants. Use project terminology consistently.

---

## Project Intent

**News Intelligence System** is an AI-powered news aggregation and analysis platform. It collects news from RSS feeds, analyzes content, tracks storylines over time, and delivers actionable intelligence.

**Core mission:** Automated collection → intelligent processing → storyline evolution → intelligence delivery.

---

## Terminology (Use Consistently)

| Concept | Use This | Avoid |
|---------|----------|-------|
| Evolving news clusters | **storylines** | stories, threads |
| Per-domain silos | **domains** | sections, buckets |
| Domain keys | **politics**, **finance**, **science-tech** | Politics, FINANCE |
| Feed storage | **rss_feeds** | rssFeeds, RSS Feeds table |
| Content clusters | **topics** | clusters, themes |
| API routes | **`/api/{domain}/...`** (domain-scoped), **`/api/...`** (global) | `/api/v4/...` (legacy, removed) |
| DB config | **get_db_config**, **get_db_connection**, **get_db** | getDatabaseConfig |
| System health | **system_monitoring** | monitoring (ambiguous) |
| Intelligence features | **intelligence_hub** | intelligence hub |

---

## Entry Points

| Role | Path |
|------|------|
| API | `api/main.py` |
| Frontend | `web/src/App.tsx` |
| API client | `web/src/services/api/` + `apiService.ts` |
| DB (single source) | `api/shared/database/connection.py` |
| Domain layout / shell | `web/src/layout/MainLayout.tsx` (routes in `App.tsx`: `/:domain` with MainLayout) |
| Background automation | `api/services/automation_manager.py` |
| Human reviewer navigation | `docs/CODEBASE_MAP.md`, `docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md`, `docs/CODE_REVIEW_AND_RUN_CAVEATS.md` |
| Public HTTPS read-only demo | `docs/PUBLIC_DEPLOYMENT.md` (TLS, env, `NEWS_INTEL_DEMO_*`, `GET /api/public/demo_config`) |

---

## Architecture Principles

1. **Single source of truth** — One config per concern (e.g. `config/database.py` shims to `shared.database.connection`).
2. **Reuse before create** — Search existing and archived code before adding new services.
3. **Consolidate, don't proliferate** — Extend existing modules instead of creating "Enhanced" or "Unified" variants.
4. **snake_case** (Python): files, functions, variables, routes, DB tables/columns.
5. **PascalCase** (React): components, classes.

---

## Domain Structure

- **Domains:** `politics`, `finance`, `science-tech` (built-in); optional domains via `api/config/domains/*.yaml` and [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](docs/DOMAIN_EXTENSION_TEMPLATE.md). **`shared.domain_registry`** is the runtime source of truth for which silos run (RSS, automation, iteration). **`public.domains`** is the DB catalog — keep it aligned when provisioning; pipeline behavior follows YAML/registry if they drift. **`data_sources.rss.seed_feed_urls`** in domain YAML are written to **`{schema}.rss_feeds`** by **`api/scripts/provision_domain.py`** (after SQL, unless `--no-seed-rss`) or **`api/scripts/seed_domain_rss_from_yaml.py`** for backfill; silo **`rss_feeds.category`** is NOT NULL — seeding sets **`seed_feed_category`** (default `General`) or use the YAML key under `data_sources.rss`. March 2026 registry/provisioning changes: [`docs/DOMAIN_REGISTRY_AND_PROVISIONING_2026_03.md`](docs/DOMAIN_REGISTRY_AND_PROVISIONING_2026_03.md) (dynamic **`is_valid_domain_key`**, shape-only path pattern, **`run_migration_180.py`** post-SQL hooks, **`shared.services.domain_silo_post_migration`**).
- **Permanent optional domains:** Treat established template domains like built-in silos: one **`domain_key`** / **`schema_name`**, **`is_active`** in YAML **and** **`public.domains`**, migration + **`provision_domain.py`**, then grep for legacy three-domain tuples. **Modular data, shared app** — one codebase; per-domain Postgres schemas, not separate deployables. See **Permanent domain contract** and **Architecture: modular silos vs monolith** in [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](docs/DOMAIN_EXTENSION_TEMPLATE.md).
- **After changing YAML** (`is_active`, new file, `domain_key` / `schema_name`): **restart the API and worker processes** — `DOMAIN_PATH_PATTERN` and `ACTIVE_DOMAIN_KEYS` are computed at import time.
- **Web domain list:** `GET /api/system_monitoring/registry_domains` (active domains for nav and API client routing); SPA fetches this at startup with a static fallback.
- **Per-domain:** `articles`, `storylines`, `topics`, `rss_feeds`, `events`.
- **Global:** watchlist, monitoring (`system_monitoring`), health.

---

## Key Flows

1. **Article:** RSS → processing → storyline linking → event extraction.
2. **Storyline:** create → add articles → **queued refinement** (`intelligence.content_refinement_queue` + automation phase `content_refinement_queue`) for deep analysis, ~70B finisher, and timeline narratives — UI reads **stored** summaries/narratives; `POST /api/{domain}/storylines/{id}/refinement_jobs` enqueues work (migration `181_*.sql`).
3. **Events (v5):** extract → deduplicate → story continuation → alerts.
4. **Narrative bootstrap:** `proactive_detection` clusters unlinked articles → can promote to domain **`storylines`** + **`storyline_articles`** + **`story_entity_index`** (see `docs/_archive/retired_root_docs_2026_03/NARRATIVE_BOOTSTRAP_AND_DB_OUTAGE.md`). DB down: **`AUTOMATION_PAUSE_WHEN_DB_DOWN`** pauses scheduling; failed **`automation_run_history`** writes spill to **`.local/db_pending_writes`** and **`pending_db_flush`** replays.
5. **Ollama:** Model routing — `api/shared/services/ollama_model_caller.py` + `ollama_model_policy.py`; routine **`ollama pull`** — `api/scripts/refresh_ollama_models.py` (`docs/SETUP_ENV_AND_RUNTIME.md`). **Storyline finisher (~70B):** final narrative editor only — `InvocationKind.STORYLINE_NARRATIVE_FINISH` → `ModelType.LLAMA_70B` (`NARRATIVE_FINISHER_MODEL`); see `docs/_archive/retired_root_docs_2026_03/STORYLINE_70B_NARRATIVE_FINISHER.md` and `api/services/storyline_narrative_finisher_service.py`.
6. **Widow vs main GPU:** **AutomationManager** runs on the **main** API host only. **Widow** can run **RSS** (`newsplatform-secondary` or `run_widow_db_adjacent.py --rss`) and **DB-adjacent cron** (`context_sync`, `entity_profile_sync`, `pending_db_flush`) per `docs/WIDOW_DB_ADJACENT_CRON.md`; main `.env` uses **`AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE`** and **`AUTOMATION_DISABLED_SCHEDULES`** to avoid duplicate work.
7. **Claims → facts:** `promote_claims_to_versioned_facts` resolves claim subjects to **`intelligence.entity_profiles`** (context mentions, article entities, canonicals, metadata, optional **`pg_trgm`** similarity) before inserting **`intelligence.versioned_facts`**; see `docs/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md`.
8. **Source credibility:** **`api/config/orchestrator_governance.yaml`** section **`source_credibility`** drives tier multipliers at RSS ingest (`quality_score` + **`articles.metadata`**), copied to **`intelligence.contexts.metadata`**, and scales stored claim confidence; see `docs/_archive/retired_root_docs_2026_03/SOURCE_CREDIBILITY.md`.
9. **Nightly backlog window (America/New_York):** default **`NIGHTLY_PIPELINE_START_HOUR=1`** / **`END_HOUR=7`** — phase **`nightly_enrichment_context`** runs kickoff RSS (once per local day), drains **`content_enrichment`** and **`context_sync`**, runs **`NIGHTLY_SEQUENTIAL_PHASES`** with backlog idle checks (`api/services/nightly_phase_idle.py`, **`get_all_pending_counts()`**), then **`process_nightly_gpu_refinement_drain`**. **`NIGHTLY_PIPELINE_EXCLUSIVE`** (default on) restricts scheduled phases in-window to **`nightly_enrichment_context`**, **`health_check`**, **`pending_db_flush`**. SQL: **`190`–`191`** `public.ml_processing_queue` + **`schema_name`**; **`192`** RSS URL refresh (`configs/env.example`).

---

## Web UI and monitoring vs pipeline

- **Web interface and monitoring are independent of the data pipeline.** The site and health/status endpoints always respond with currently available data; they do not wait for background processing (enrichment, entity extraction, synthesis).
- **Health checks and statuses** (e.g. `/api/system_monitoring/health`, `/automation/status`) are ready at any time; automation status uses a short timeout so the UI never blocks on the pipeline. **`GET /api/system_monitoring/automation/status`** includes `pending_counts`, **`document_pipeline`** (PDF backlog / extracted 24h / permanent failures), and **`work_balancer`** (effective workload-driven cooldowns per phase; `WORKLOAD_BALANCER_*` env).
- **Pipeline work** (RSS, content enrichment, entity extraction, pattern matching, etc.) runs as background tasks; it may yield when the user loads a non-monitoring page so the UI stays responsive. Polling paths (Monitor, health, status, backlog) do not trigger that yield so the pipeline can keep running while the user views the dashboard.

### Automation and pipeline visibility (where runs are recorded)

- **Phase completions:** `public.automation_run_history` — inserts via `shared.services.automation_run_history_writer.persist_automation_run_history` (AutomationManager completions; optional **`POST /api/system_monitoring/cron_heartbeat`** with **`CRON_HEARTBEAT_KEY`** + **`X-Cron-Heartbeat-Key`** for cron markers such as `cron_rss`).
- **Pipeline DB rows:** `pipeline_traces` / `pipeline_checkpoints` — `shared.services.pipeline_trace_writer.log_pipeline_trace` (Monitoring **Trigger pipeline**; OrchestratorCoordinator RSS uses stage **`orchestrator_rss_collection`**).
- **Operator report:** `scripts/run_last_24h_report.sh` → `scripts/last_24h_activity_report.py`; narrative (archived): **`docs/_archive/retired_root_docs_2026_03/AUTOMATION_AND_LAST_24H_ACTIVITY.md`**.

---

## File Layout

| Area | Location |
|------|----------|
| API routes | `api/domains/*/routes/` |
| Services | `api/services/`, `api/domains/*/services/` |
| Frontend pages | `web/src/pages/` |
| API modules | `web/src/services/api/` (articles, watchlist, storylines, topics, rss, monitoring) |
| Docker (archived, not default) | `docs/archive/docker_stack/` — Compose + Dockerfiles + legacy scripts only |
| Planning proposals (not v8 spec) | `docs/archive/planning_incubator/` — PDF/UI/v6 write-ups tagged **TAG_INCORPORATE** |
| Legacy pytest under `api/` | `api/_archived/legacy_pytest_tree_2026_03/` — CI uses repo-root `tests/` only |
| Old React tree (not bundled) | `web/_archived_duplicates/_archived_interface/` |

**Deployment:** Canonical path is **bare metal** (`start_system.sh`, Widow PostgreSQL, local `.venv`). Do not assume Docker for development or home ops.

---

## Coding Standards

- **Python:** See `docs/CODING_STYLE_GUIDE.md` — snake_case, `APIResponse(success, data, message)`.
- **Frontend:** See `web/FRONTEND_STYLE_GUIDE.md` — use `Logger` (not `console.log`) for logging.
- **API routes:** `snake_case` paths (e.g. `/rss_feeds/`, `/storylines/{id}/timeline`).

---

## API URL Conventions

- **Backend routes all mount at `/api`** — no version prefix in the path.
- **Domain-scoped:** `/api/{domain}/articles`, `/api/{domain}/storylines`, `/api/{domain}/finance/gold`, etc.
- **Global:** `/api/system_monitoring/...`, `/api/orchestrator/...`, `/api/watchlist`, `/api/entity_profiles`, `/api/context_centric/...`.
- **Frontend API modules** (`web/src/services/api/*.ts`) build URLs directly (e.g. `` `/api/${domainKey}/articles` ``).
- **Request interceptor** (`apiConnectionManager.ts`) injects the domain for the few URLs that omit it, and sets the correct base URL for global vs domain-scoped routes.
- **Never use `/api/v4/`** in frontend URLs — that prefix was removed; the backend has never used it.
- See `docs/WEB_API_CONNECTIONS.md` for the full connection flow.

---

## Database

- **Single module:** `shared.database.connection` — pooled psycopg2 + SQLAlchemy.
- **Shim:** `config.database` re-exports for backward compatibility.
- **Primary config:** Widow at `<WIDOW_HOST_IP>:5432`, DB `news_intel`. Rollback: NAS via `DB_HOST=localhost`, `DB_PORT=5433` + `setup_nas_ssh_tunnel.sh`.

### Database Connection Rules (MUST FOLLOW)

1. **Always close connections.** Use `get_db_connection_context()` (preferred) or `try/finally` with `conn = None` before the `try`. Never put `conn.close()` only inside `try` — exceptions will skip it and leak the connection.
2. **Three pools exist** — Worker (psycopg2, background), UI (psycopg2, page loads), SQLAlchemy (ORM services). Don't mix them or create direct `psycopg2.connect()` calls in services.
3. **Don't hold connections across slow I/O** — close before LLM calls, HTTP requests, or sleeps; reopen afterward.
4. **Pool env vars** — `DB_POOL_WORKER_MIN/MAX`, `DB_POOL_UI_MIN/MAX`, `DB_POOL_SA_SIZE/OVERFLOW`. Total must stay under PostgreSQL `max_connections` (or under PgBouncer→Postgres pool size when using a pooler). Defaults favor **UI pool** for page loads/monitoring and a **moderate worker max**; scale worker max up when observability shows spare capacity. **Footprint** = sum over every process (API workers, automation host, scripts) × each pool’s max. **PgBouncer** — `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md`.
5. **Reset / shrink idle sessions** — **Restart** API and every worker that imports `shared.database.connection` (pools are per process). Graceful API shutdown calls `close_pool()` (psycopg2 + SQLAlchemy dispose). Do not call `close_pool()` while other threads in the same process are using the DB. Reduce **`DB_POOL_*_MIN`**, **uvicorn worker count**, and fix **`idle in transaction`** (code + PostgreSQL `idle_in_transaction_session_timeout`) so `max_connections` can stay modest.
6. **Checkout timeouts** — Worker: 30 s, UI: 3 s. A timeout error means connections are leaking; find and fix the leak.
7. See `docs/CODING_STYLE_GUIDE.md` § "Database connection lifecycle" and "Connection Pool Architecture" for full details and code examples.
8. **Migration verification** — Active SQL lives in `api/database/migrations/`; pre-176 history is in `api/database/migrations/archive/historical/` (runners resolve both via `shared.migration_sql_paths`). After applies, run `PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py` (checks **133**, **160–172**, **176** `applied_migrations`, **177–179** domain pipeline objects). Exit code **0** means all listed objects exist; **1** lists what to apply. Record **176+** applies with `api/scripts/register_applied_migration.py` and diff files vs ledger with `api/scripts/migration_ledger_report.py`. See `api/database/migrations/README.md`. Full assessment (archived): `docs/_archive/retired_root_docs_2026_03/DB_FULL_ASSESSMENT.md`. Manual event extraction: `scripts/run_event_pipeline_manual.py`.
9. **Timeline generation** — The legacy ML queue module **`TimelineGenerator`** (`timeline_events` / unscoped `articles`) is **removed**. Use automation task **`timeline_generation`** (`TimelineBuilderService` + **`public.chronological_events`**) or **`GET /api/{domain}/storylines/{id}/timeline`**. `TaskType.TIMELINE_GENERATION` in the ML queue completes with **0 events** and a deprecation message.

---

## Before Creating New Code

1. Search for existing or archived implementations.
2. Extend existing services instead of creating new ones.
3. Use `Logger` (frontend) or `logger` (backend) for logging.
4. Follow naming in this file and `docs/CODING_STYLE_GUIDE.md`.

---

## Keeping Documentation Aligned

When you change the **API** (routes, path segments, response shape) or **core behaviour** (entry points, DB config, domain layout):

1. **Update docs in the same change** (or the next commit): `AGENTS.md`, `docs/CODING_STYLE_GUIDE.md`, `docs/ARCHITECTURE_AND_OPERATIONS.md`, `docs/SECURITY_OPERATIONS.md` (if exposure, CORS, or error-handling changes), and any domain or feature doc that references the change. For **public repos**, use LAN placeholders (`<WIDOW_HOST_IP>`, etc.) in markdown per `docs/OBFUSCATION.md`; never commit `configs/doc_obfuscation.local.yaml`.
2. **Paths:** Use flat `/api` (no version in path). Route path segments: `snake_case` (e.g. `system_monitoring`, `rss_feeds`). Domain-scoped: `/api/{domain}/...` with domain `politics` | `finance` | `science-tech`.
3. **Code and tests:** Keep test URLs and frontend API calls in sync with the real routes (no `/api/v4/`, no kebab-case route segments).
4. **Single source:** Entry points and file layout in `AGENTS.md` and the “Project structure” in `CODING_STYLE_GUIDE.md` must match the repo (e.g. `main.py`, `api/domains/*/routes/`, `MainLayout.tsx`).

---

## Planned / Future Work

**Expanded Election Tracker** (to develop later):

- Maps for election coverage and results
- Election updates and live tracking
- Politician profiles surfaced on maps and in updates

Planned for the politics domain. Not yet scoped or scheduled.
