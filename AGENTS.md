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
| Politics — official U.S. government data (Congress.gov bills) | `api/domains/politics/routes/official.py` → `/api/politics/official/...` |
| Frontend | `web/src/App.tsx` |
| API client | `web/src/services/api/` + `apiService.ts` |
| DB (single source) | `api/shared/database/connection.py` |
| Domain layout / shell | `web/src/layout/MainLayout.tsx` (routes in `App.tsx`: `/:domain` with MainLayout) |
| Background automation | `api/services/automation_manager.py`; scheduling semantics (`last_run`, lanes, parallel groups): [`docs/AUTOMATION_MANAGER_SCHEDULING.md`](docs/AUTOMATION_MANAGER_SCHEDULING.md) |
| Human reviewer navigation | `docs/CODEBASE_MAP.md`, `docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md`, `docs/PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md` (includes **quality-first phase contracts**: success criteria, skip/ignore rules, handoffs), `docs/DIAGNOSTICS_EVENT_COLLECTOR.md`, `docs/CODE_REVIEW_AND_RUN_CAVEATS.md` |
| Public HTTPS read-only demo | `docs/PUBLIC_DEPLOYMENT.md` (TLS, env, `NEWS_INTEL_DEMO_*`, `GET /api/public/demo_config`) |
| **Claim subject gaps** (research list for unpromoted claim subjects) | `GET/POST /api/context_centric/claim_subject_gaps/...`, **`POST .../bulk_ignore`**, `api/scripts/claim_subject_gap_bulk_ignore.py`, `api/services/claim_subject_gap_service.py`, migration **`198_claim_subject_gap_catalog.sql`**; automation **`claim_subject_gap_refresh`** / **`extracted_claims_dedupe`** (`context_centric.yaml`); dedupe CLI **`scripts/merge_duplicate_extracted_claims.py`** |
| **Curated entity seed** (bulk canonicals + profiles for major actors) | `api/config/seed_world_entities.yaml`, `api/scripts/seed_world_entities_from_yaml.py`, `api/services/entity_seed_catalog_service.py` |
| **External entity seeds** (REST Countries, Wikidata SPARQL, CSV, DB frequency pass) | `docs/EXTERNAL_ENTITY_SEEDS.md`, `api/scripts/restcountries_seed.py`, `wikidata_sparql_seed.py`, `seed_entities_from_csv.py`, `second_pass_frequent_subjects.py` |

---

## Architecture Principles

1. **Single source of truth** — One config per concern (e.g. `config/database.py` shims to `shared.database.connection`).
2. **Reuse before create** — Search existing and archived code before adding new services.
3. **Consolidate, don't proliferate** — Extend existing modules instead of creating "Enhanced" or "Unified" variants.
4. **snake_case** (Python): files, functions, variables, routes, DB tables/columns.
5. **PascalCase** (React): components, classes.

---

## Domain Structure

- **Domains:** `politics`, `finance`, `science-tech` are **built-in** (always registered; YAML cannot replace them). **Additional silos** are onboarded via `api/config/domains/{domain_key}.yaml` — same pipeline, routes, and data model once migrated and provisioned; see [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](docs/DOMAIN_EXTENSION_TEMPLATE.md). **`shared.domain_registry`** (YAML `is_active` + built-ins) decides which silos are in the pipeline: RSS **`url_schema_pairs()`**, **`get_all_domains()`** (automation/batch), **`get_schema_names_active()`**. **`public.domains`** is the DB catalog — keep it aligned when provisioning; **`public.domains.is_active`** does **not** exclude a silo from RSS/automation (disable via YAML **`is_active: false`** or remove the YAML file). **`data_sources.rss.seed_feed_urls`** in domain YAML are written to **`{schema}.rss_feeds`** by **`api/scripts/provision_domain.py`** (after SQL, unless `--no-seed-rss`) or **`api/scripts/seed_domain_rss_from_yaml.py`** for backfill; silo **`rss_feeds.category`** is NOT NULL — seeding sets **`seed_feed_category`** (default `General`) or use the YAML key under `data_sources.rss`. March 2026 registry/provisioning changes: [`docs/DOMAIN_REGISTRY_AND_PROVISIONING_2026_03.md`](docs/DOMAIN_REGISTRY_AND_PROVISIONING_2026_03.md) (dynamic **`is_valid_domain_key`**, shape-only path pattern, **`run_migration_180.py`** post-SQL hooks, **`shared.services.domain_silo_post_migration`**).
- **Additional silos (full parity):** After onboarding (one **`domain_key`** / **`schema_name`**, migration + **`provision_domain.py`**), treat the silo like the built-ins: same code paths, isolated schema. Grep for legacy hardcoded three-domain tuples and extend shared helpers. **Modular data, shared app** — one codebase; per-domain Postgres schemas, not separate deployables. See **Permanent domain contract** and **Architecture: modular silos vs monolith** in [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](docs/DOMAIN_EXTENSION_TEMPLATE.md).
- **New silo verification:** After migration + **`provision_domain.py`**, run **`api/scripts/verify_domain_provision.py`** (non-zero on errors; **`--strict`** if CI should fail on warnings too); run **`api/scripts/ensure_domain_silo_alignment.py`** on each host that shares the DB. Template: **`api/config/domains/_template.example.yaml`**.
- **Template parallel silos (`politics-2`, `finance-2`):** Migration **`201`** + YAML **`politics-2.yaml`**, **`finance-2.yaml`** add **`politics_2`** / **`finance_2`** schemas alongside legacy built-ins (minimal **science_tech**-shaped core only). Migration **`206`** adds **finance**-only tables to **`finance_2`** (`research_topics`, `topic_extraction_queue`, `market_patterns`, `corporate_announcements`, `financial_indicators`) without changing **201** — run **`api/scripts/run_migration_206.py`** before copying **`finance` → `finance_2`** for those tables. Migration **`208`** adds **`article_topic_clusters`** to **`politics_2`** and **`finance_2`** (omitted from **201**; same gap as **193** for optional silos) — run **`api/scripts/run_migration_208.py`** so **`GET /api/{domain}/content_analysis/topics`** does not 500 for **politics-2** / **finance-2**. **`api/scripts/switch_domain_rss_ingest.py`** sets **`rss_feeds.is_active`** off on **`politics`** and on on **`politics-2`** so **`collect_rss_feeds`** ingests only the template silo; set **`RSS_INGEST_EXCLUDE_DOMAIN_KEYS=politics`** after cutover to avoid duplicate URL collection (`configs/env.example`). **`FINANCE_PG_CONTENT_DOMAIN_KEY`** / **`FINANCE_CONTEXT_DOMAIN_KEY`** and **`POLITICS_PG_CONTENT_DOMAIN_KEY`** align finance orchestration and future politics article helpers. Finance HTTP routes **`/api/{domain}/finance/...`** use the URL **`domain`** (e.g. **`finance-2`**) for PostgreSQL-backed article views. **Bootstrap data:** **`api/scripts/copy_domain_silo_table_data.py`** copies shared tables from **`politics` → `politics_2`** (read-only on source; **`--replace`** truncates target first) and syncs **`entity_profiles`** for **`politics-2`**. Per-silo DDL extensions: **`docs/DOMAIN_EXTENSION_TEMPLATE.md`** § Per-silo DDL extensions.
- **After changing YAML** (`is_active`, new file, `domain_key` / `schema_name`): **restart the API and worker processes** — `DOMAIN_PATH_PATTERN` and `ACTIVE_DOMAIN_KEYS` are computed at import time.
- **Web domain list:** `GET /api/system_monitoring/registry_domains` (active domains for nav and API client routing); SPA fetches this at startup with a static fallback.
- **Per-domain:** `articles`, `storylines`, `topics`, `rss_feeds`, `events`.
- **Global:** watchlist, monitoring (`system_monitoring`), health.

---

## Key Flows

1. **Article:** RSS → processing → storyline linking → event extraction. Optional **`STRICT_ARTICLE_ENRICHMENT_GATES_SINCE`** (ISO UTC) tightens enrichment gates for rows with **`created_at`** on or after that instant (`api/shared/article_processing_gates.py`, RSS + `content_enrichment` fast-path); older rows unchanged — see **`docs/PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md`**. **Terminal phase skips:** `entity_extraction`, `sentiment_analysis`, `quality_scoring`, and `event_extraction` can mark repeated per-article failures under `articles.metadata.pipeline_skip` and exclude those rows from selection/backlog counts after env-tunable caps (`*_MAX_FAILURES` in `configs/env.example`) to prevent wasteful re-queue cycles. **Shared surnames:** `api/services/entity_resolution_service.py` introduces **`family`** canonicals (e.g. *Trump family*) and **`member_of_family`** edges to distinct **person** rows when resolution would otherwise collapse multiple people; SQL **`199`** / **`200`** widen **`entity_type`** checks (`configs/env.example`: **`SURNAME_FAMILY_*`**, **`ENTITY_EXTRACTION_*`**).
2. **Storyline:** create → add articles → **queued refinement** (`intelligence.content_refinement_queue` + automation phase `content_refinement_queue`) for deep analysis, ~70B finisher, and timeline narratives — UI reads **stored** summaries/narratives; `POST /api/{domain}/storylines/{id}/refinement_jobs` enqueues work (migration `181_*.sql`).
3. **Events (v5):** extract → deduplicate → story continuation → alerts. **Tracked events (cross-domain):** `intelligence.tracked_events.domain_keys` is unioned from chronicle-linked `contexts`; migration **196** adds **`global_narrative`** (neutral spine) and **`narrative_lenses`** (desk views derived only from that spine). Automation phase **`editorial_briefing_generation`** runs **`run_tracked_event_narrative_stack`** then legacy JSON briefing for rows still without a spine. **`POST /api/tracked_events/{event_id}/narrative_stack`** triggers the stack for one event.
4. **Narrative bootstrap:** `proactive_detection` clusters unlinked articles → can promote to domain **`storylines`** + **`storyline_articles`** + **`story_entity_index`** (see `docs/_archive/retired_root_docs_2026_03/NARRATIVE_BOOTSTRAP_AND_DB_OUTAGE.md`). DB down: **`AUTOMATION_PAUSE_WHEN_DB_DOWN`** pauses scheduling; failed **`automation_run_history`** writes spill to **`.local/db_pending_writes`** and **`pending_db_flush`** replays.
5. **Ollama:** Model routing — `api/shared/services/ollama_model_caller.py` + `ollama_model_policy.py`; primary/secondary defaults in **`config.settings.MODELS`** (`OLLAMA_MODEL_PRIMARY`, `OLLAMA_MODEL_SECONDARY`, optional **`OLLAMA_USE_QWEN_FOR_EXTRACTION`**, **`OLLAMA_USE_PHI_FOR_FAST_SIMPLE`**). Optional dual-host lane routing (`OLLAMA_DUAL_HOST_ROUTING_ENABLED`, `OLLAMA_CPU_HOST`, `OLLAMA_GPU_HOST`, `OLLAMA_CPU_CONCURRENCY`, `OLLAMA_GPU_CONCURRENCY`) lets routine CPU-lane calls run separately from GPU-lane narrative/synthesis calls. Routine **`ollama pull`** — `api/scripts/refresh_ollama_models.py` (`docs/SETUP_ENV_AND_RUNTIME.md`). **Storyline finisher (~70B):** final narrative editor only — `InvocationKind.STORYLINE_NARRATIVE_FINISH` → `ModelType.LLAMA_70B` (`NARRATIVE_FINISHER_MODEL`); see `docs/_archive/retired_root_docs_2026_03/STORYLINE_70B_NARRATIVE_FINISHER.md` and `api/services/storyline_narrative_finisher_service.py`.
6. **Widow vs main GPU:** **AutomationManager** runs on the **main** API host only. **Widow** can run **RSS** (`newsplatform-secondary` or `run_widow_db_adjacent.py --rss`) and **DB-adjacent cron** (`context_sync`, `entity_profile_sync`, `pending_db_flush`) per `docs/WIDOW_DB_ADJACENT_CRON.md`; main `.env` uses **`AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE`** and **`AUTOMATION_DISABLED_SCHEDULES`** to avoid duplicate work.
7. **Claims → facts:** `promote_claims_to_versioned_facts` resolves claim subjects to **`intelligence.entity_profiles`** (context mentions, article entities, canonicals, metadata, optional **`pg_trgm`** similarity) before inserting **`intelligence.versioned_facts`**; **`CLAIMS_TO_FACTS_DRAIN`** (default on) loops daytime promotes until idle; **`NIGHTLY_CLAIMS_TO_FACTS_BATCH_LIMIT`** unset matches **`CLAIMS_TO_FACTS_BATCH_LIMIT`**; see `docs/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md`.
8. **Legislative ground truth:** Migration **`197_*.sql`** adds **`intelligence.legislative_references`** (Congress.gov bill JSON + CRS summaries + text-version pointers) and **`intelligence.legislative_article_scans`**. Automation phase **`legislative_references`** scans **politics** and **legal** articles for federal bill citations (`H.R.`, `S.`, `H.J.Res.`, etc.), then fetches official data when **`CONGRESS_GOV_API_KEY`** is set — compare with **`intelligence.extracted_claims`** for media-vs-statute analysis.
9. **Source credibility:** **`api/config/orchestrator_governance.yaml`** section **`source_credibility`** drives tier multipliers at RSS ingest (`quality_score` + **`articles.metadata`**), copied to **`intelligence.contexts.metadata`**, and scales stored claim confidence; see `docs/_archive/retired_root_docs_2026_03/SOURCE_CREDIBILITY.md`.
10. **Nightly backlog window (America/New_York):** default **`NIGHTLY_PIPELINE_START_HOUR=2`** / **`END_HOUR=7`** (02:00–07:00 local) — phase **`nightly_enrichment_context`** runs kickoff RSS (once per local day), drains **`content_enrichment`** and **`context_sync`**, runs **`NIGHTLY_SEQUENTIAL_PHASES`** with backlog idle checks (`api/services/nightly_phase_idle.py`, **`get_all_pending_counts()`**), then **`process_nightly_gpu_refinement_drain`**. **`NIGHTLY_PIPELINE_EXCLUSIVE`** (default on) restricts scheduled phases in-window to **`nightly_enrichment_context`**, **`health_check`**, **`pending_db_flush`**. Set **`NIGHTLY_UNIFIED_PIPELINE_ENABLED=false`** to disable the window and rely on the main AutomationManager schedule only (`api/services/nightly_ingest_window_service.py`). **Pipeline domain scope:** **`PIPELINE_INCLUDE_DOMAIN_KEYS`** (optional allowlist) and **`PIPELINE_EXCLUDE_DOMAIN_KEYS`** — iterators **`pipeline_url_schema_pairs()`** / **`get_pipeline_schema_names_active()`** / **`get_pipeline_active_domain_keys()`** (`api/shared/domain_registry.py`). RSS de-duplication remains **`RSS_INGEST_EXCLUDE_DOMAIN_KEYS`**. Strict entity resolution (match seeded canonicals only): **`ENTITY_EXTRACTION_RESOLVE_STRICT_DOMAIN_KEYS`**. SQL: **`190`–`191`** `public.ml_processing_queue` + **`schema_name`**; **`192`** RSS URL refresh (`configs/env.example`).

---

## Web UI and monitoring vs pipeline

- **Web interface and monitoring are independent of the data pipeline.** The site and health/status endpoints always respond with currently available data; they do not wait for background processing (enrichment, entity extraction, synthesis).
- **Health checks and statuses** (e.g. `/api/system_monitoring/health`, `/automation/status`) are ready at any time; automation status uses a short timeout so the UI never blocks on the pipeline. **`GET /api/system_monitoring/automation/status`** includes `pending_counts`, **`document_pipeline`** (PDF backlog / extracted 24h / permanent failures), and **`work_balancer`** (effective workload-driven cooldowns per phase; `WORKLOAD_BALANCER_*` env). **`GET /api/system_monitoring/backlog_status`** includes **`nightly_catchup`** (unified nightly window, drain-phase automation counts, sequential backlogs, recent **`nightly_enrichment_context`** rows from **`automation_run_history`**) for Monitor backlog progression. **`GET /api/system_monitoring/processing_progress`** returns pipeline dimension throughput (1h/24h/7d), per-phase **`pending_records`** (unprocessed DB rows), **`estimated_batch_per_run`** (modeled rows per scheduled run from **`backlog_metrics._per_run_batch_size`**), **`batches_to_drain`** = runs to clear queue `ceil(pending ÷ rows_per_run)` (or `null` if no row-batch model), **pass %** from **`automation_run_history.success`**, and 72h hourly buckets (Monitor **Processing pulse**). First request after restart is expensive (many SQL passes + **`get_all_pending_counts()`**); responses are cached **~90s** per API worker (`cached_response`). Monitor SPA loads overview + pipeline first, then fetches **`processing_progress`** asynchronously so the shell stays responsive. Automation **`backlog_counts`** from **`get_all_backlog_counts()`** remains row-excess `max(0, pending − batch)` for scheduling only. Cross-source event dedup: **`EVENT_DEDUP_*`** in **`event_deduplication_service.py`** (canonical **`source_count`** / **`last_corroborated_at`** preserve sources).
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
2. **Four psycopg2 pools + SA** — Worker (background phases), UI (page loads/monitoring), **Health** (automation `health_check` probes + `automation_run_history` for that phase only; `DB_POOL_HEALTH_MIN/MAX`), SQLAlchemy (ORM). Don't use the health pool for pipeline work. Don't mix pools or create direct `psycopg2.connect()` calls in services.
3. **Don't hold connections across slow I/O** — close before LLM calls, HTTP requests, or sleeps; reopen afterward.
4. **Pool env vars** — `DB_POOL_WORKER_MIN/MAX`, `DB_POOL_UI_MIN/MAX`, `DB_POOL_HEALTH_MIN/MAX`, `DB_POOL_SA_SIZE/OVERFLOW`. Total must stay under PostgreSQL `max_connections` (or under PgBouncer→Postgres pool size when using a pooler). Defaults favor **UI pool** for page loads/monitoring and a **moderate worker max**; scale worker max up when observability shows spare capacity. **Footprint** = sum over every process (API workers, automation host, scripts) × each pool’s max. **PgBouncer** — `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md`.
5. **Reset / shrink idle sessions** — **Restart** API and every worker that imports `shared.database.connection` (pools are per process). Graceful API shutdown calls `close_pool()` (psycopg2 + SQLAlchemy dispose). Do not call `close_pool()` while other threads in the same process are using the DB. Reduce **`DB_POOL_*_MIN`**, **uvicorn worker count**, and fix **`idle in transaction`** (code + PostgreSQL `idle_in_transaction_session_timeout`) so `max_connections` can stay modest.
6. **Checkout timeouts** — Worker: 30 s, UI: 3 s. A timeout error means connections are leaking; find and fix the leak.
7. See `docs/CODING_STYLE_GUIDE.md` § "Database connection lifecycle" and "Connection Pool Architecture" for full details and code examples.
8. **Migration verification** — Active SQL lives in `api/database/migrations/`; pre-176 history is in `api/database/migrations/archive/historical/` (runners resolve both via `shared.migration_sql_paths`). After applies, run `PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py` (checks **133**, **160–172**, **176** `applied_migrations`, **177–179** domain pipeline objects). Exit code **0** means all listed objects exist; **1** lists what to apply. Record **176+** applies with `api/scripts/register_applied_migration.py` and diff files vs ledger with `api/scripts/migration_ledger_report.py`. See `api/database/migrations/README.md`. Full assessment (archived): `docs/_archive/retired_root_docs_2026_03/DB_FULL_ASSESSMENT.md`. Manual event extraction: `scripts/run_event_pipeline_manual.py`.
9. **Timeline generation** — The legacy ML queue module **`TimelineGenerator`** (`timeline_events` / unscoped `articles`) is **removed**. Use automation task **`timeline_generation`** (`TimelineBuilderService` + **`public.chronological_events`**) or **`GET /api/{domain}/storylines/{id}/timeline`**. `TaskType.TIMELINE_GENERATION` in the ML queue completes with **0 events** and a deprecation message.
10. **Resource budgets and lean pipeline** — Treat RAM and DB connections as explicit per-process budgets; prefer chunking large text, one canonical store for expensive recomputation (embeddings, parsed content), bounded scheduling/backpressure, and periodic phase audits. See **`docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md`**.

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
