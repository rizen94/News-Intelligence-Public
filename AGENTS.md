# News Intelligence System — Agent Guidance

> **HOST GUARDRAILS (read first)**
> - **Migration complete (June 2026).** All NI development and queries belong on **Widow** (`192.168.93.101`).
> - **Dev workspace:** `/home/pete/Documents/projects/News Intelligence` on Widow
> - **Production runtime:** `/opt/news-intelligence` on Widow (API may run from here)
> - **PopOS local copy** (`192.168.93.99`) is headed for NAS cold storage — do not treat it as authoritative.
> - **Database:** NI owns `news_intel` on Widow. **Apps** use PgBouncer **`DB_PORT=6432`**; **admin/migrations** use direct Postgres **`:5432`**. Homelab Postgres MCP on PopOS reads it read-only — that is **not** Homelab's local Postgres on `:15432`.
> - See [PROJECT_STATUS.md](PROJECT_STATUS.md) and [../PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md).

> **v10.1 (release/10.1):** Pipeline Exclusive Paths — feature registry, admission control, queue-based spine, conductor-only scheduling. Version SSOT: repo-root `VERSION`. New backend features must register in `api/config/features.yaml`. See [docs/UPGRADE_10.1.md](docs/UPGRADE_10.1.md) and [docs/FEATURE_REGISTRY.md](docs/FEATURE_REGISTRY.md).

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
| Domain keys | **legal**, **medicine**, **artificial-intelligence**, **politics**, **finance** | Politics, FINANCE, science-tech (retired) |
| Feed storage | **rss_feeds** | rssFeeds, RSS Feeds table |
| Content clusters | **topic_clusters** (pipeline); legacy **topics** (read-only CRUD) | clusters, themes |
| API routes | **`/api/{domain}/...`** (domain-scoped), **`/api/...`** (global) | `/api/v4/...` (legacy, removed) |
| DB config | **get_db_config**, **get_db_connection**, **get_db** | getDatabaseConfig |
| System health | **system_monitoring** | monitoring (ambiguous) |
| Intelligence features | **intelligence_hub** | intelligence hub |
| Investigation (FtM resolver) | **investigation** / `api/nri_core/` | NRI, nri-api |
| Investigation API | **`/api/investigation/*`** | — |
| Tracking discovery API | **`GET /api/tracking/discovery`** | Widow headless + OWUI thin client |
| Event reconciliation API | **`GET /api/event_reconciliation`** | Read-only tracked ↔ chronological ↔ storyline |

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
| Catch-up env defaults | `api/config/catchup_defaults.py`, `scripts/catchup_env.sh` |
| Automation extraction routing (PopOS GPU) | `api/shared/automation_llm_routing.py` |
| Pipeline resource policy (phase host/tier/batch) | `api/shared/pipeline_resource_policy.py` |
| Unified intake extraction (batched LLM fan-out) | `api/services/unified_intake_extraction_service.py` |
| Unified intake extraction runner | `api/shared/unified_intake_extraction_runner.py` |
| Spine SQL tail | `api/services/spine_sql_tail_service.py` |
| Pipeline controller (scheduling SSOT) | `api/services/pipeline_controller.py` |
| Monitor run vocabulary (activity ↔ run history SSOT) | `api/shared/monitor_run_vocabulary.py`, `docs/MONITOR_REPORTING_AND_METRICS.md`, `docs/monitor_alignment/` |
| Spine conductor (drain helpers) | `api/services/spine_pipeline_conductor.py` |
| Link indexer (post-spine pass 0) | `api/services/link_indexer_service.py` |
| Assembly conductor (drain helpers) | `api/services/assembly_conductor_service.py` |
| Editorial room loop | `api/services/editorial_room_loop_service.py` |
| Assembly phase order / retired phases | `api/shared/assembly_phase_order.py` |
| Unified intake backlog (actionable vs legacy backfill) | `api/shared/unified_intake_backlog.py` |
| Signal-first article lanes | `api/shared/article_signal_gate.py`, `docs/SIGNAL_FIRST_OPS.md` |
| RSS feed health / silencing | `api/services/rss_feed_health_service.py`, `api/scripts/rss_feed_yield_report.py` |
| Batched event extraction (legacy rollback) | `api/_archived/intake/event_extraction_runner.py` via `LEGACY_INTAKE_EXTRACTION_ENABLED` |
| Batched entity extraction (legacy rollback) | `api/_archived/intake/entity_extraction_runner.py` via `LEGACY_INTAKE_EXTRACTION_ENABLED` |
| Archived legacy intake / retired phases | `api/_archived/intake/`, `api/_archived/automation/retired_phase_handlers.py` |
| Legacy intake rollback loader | `api/shared/legacy_intake_rollback.py` |
| Entity resolution routes | `api/domains/intelligence_hub/routes/entity_resolution.py` |
| Entity service facade | `api/services/entity_service_facade.py` |
| Shared kernel | `api/shared/kernel/`, `api/shared/services/article_query_service.py` |
| API deprecation helper | `api/shared/api_deprecation.py` (HTTP 410 for retired global routes) |
| Investigation package | `api/nri_core/` |
| Config kernel | `api/config/runtime.py`, `database_targets.py`, `investigation_tables.py`, `schedulers.yaml` |
| Investigation docs | `docs/INVESTIGATION.md`, `docs/UNIFICATION_CUTOVER.md` |
| Agent domain DB queries | `docs/AGENT_DOMAIN_DB_INSIGHTS.md` (Postgres MCP, per-silo SQL) |
| Open WebUI DB explorer | Homelab `docs/NEWS_DB_EXPLORER_AGENT.md` — model `news-db-explorer` |
| Human reviewer navigation | `docs/CODEBASE_MAP.md`, `docs/PIPELINE_AND_AUTOMATION.md`, `docs/CODE_REVIEW_AND_RUN_CAVEATS.md` |
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

- **Pipeline-active domains** (June 2026, Widow): `legal`, `medicine`, `artificial-intelligence`, `politics`, `finance` — all `is_active=true` in `public.domains`. **`get_pipeline_active_domain_keys()`** returns the same five unless `PIPELINE_INCLUDE_DOMAIN_KEYS` / `PIPELINE_EXCLUDE_DOMAIN_KEYS` is set in env.
- **Registry vs pipeline:** **Registry active** = `public.domains.is_active`. **Pipeline active** = env-filtered subset via `get_pipeline_active_domain_keys()`. On Widow prod both sets are identical (no `PIPELINE_*` filter).
- **`science-tech` retired:** schema dropped (migration 212). See [`docs/LEGACY_DOMAIN_RETIREMENT.md`](docs/LEGACY_DOMAIN_RETIREMENT.md) — do not reference as an active silo.
- **YAML provisioning:** new silos via `api/config/domains/*.yaml` and [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](docs/DOMAIN_EXTENSION_TEMPLATE.md).
- **After changing YAML or registry:** restart API and worker processes — `DOMAIN_PATH_PATTERN` and `ACTIVE_DOMAIN_KEYS` are computed at import time.
- **Per-domain:** `articles`, `storylines`, `topic_clusters`, `article_topic_clusters`, `rss_feeds`, `events` (legacy `topics` read-only).
- **Global:** watchlist, monitoring (`system_monitoring`), health.

---

## Key Flows

1. **Article:** RSS → enrichment → storyline linking → intake extraction (unified or legacy per-phase).
2. **Unified intake (`UNIFIED_INTAKE_EXTRACTION_ENABLED=true`, default):** one batched PopOS LLM pass fans out to entities, events, claims, sentiment/quality; inline context on enrich via `sync_context_from_article_after_content_change`. **Fast NER pre-pass** (`FAST_NER_ENABLED`, spaCy + optional GLiNER) seeds entities before LLM. **Context chunking** (`CONTEXT_CHUNKING_ENABLED`) splits long articles into `article` + `article_chunk` contexts. Legacy per-phase intake runs only when `LEGACY_INTAKE_EXTRACTION_ENABLED=true`. **Legacy-aware backlog** (`UNIFIED_INTAKE_LEGACY_AWARE_BACKLOG=true`, default): Monitor/automation count only articles still needing unified LLM; legacy-complete rows get pass-marker backfill without re-extraction (`api/shared/unified_intake_backlog.py`, `api/scripts/backfill_unified_intake_pass_from_legacy.py`). See [docs/PIPELINE_AND_AUTOMATION.md](docs/PIPELINE_AND_AUTOMATION.md).
3. **Storyline:** create → add articles → queued refinement (`intelligence.content_refinement_queue`).
4. **Events (v5):** extract → deduplicate → story continuation → alerts.
5. **Ollama:** Model routing via `api/shared/services/ollama_model_caller.py`. **Widow** (`OLLAMA_HOST`, `:11434`) runs normal CPU- and GPU-lane work (8B, Qwen extraction, topic clustering, etc.). **PopOS** (`OLLAMA_POP_OS_HOST`, RTX 5090) is **GPU overflow** — `:70b` narrative finisher and models too large for Widow's GTX 1080. On Widow prod **`OLLAMA_DUAL_HOST_ROUTING_ENABLED=true`** splits overflow to PopOS; set `false` only when deliberately single-host.
6. **Public HTTPS:** PopOS Caddy → Widow nginx — see [docs/WIDOW_PUBLIC_STACK.md](docs/WIDOW_PUBLIC_STACK.md).
7. **Widow (post-migration):** Full stack on Widow. AutomationManager runs on Widow API host. DB-adjacent cron per `docs/WIDOW_DB_ADJACENT_CRON.md`.

---

## File Layout

| Area | Location |
|------|----------|
| API routes | `api/domains/*/routes/` |
| Services | `api/services/`, `api/domains/*/services/` |
| Frontend pages | `web/src/pages/` |
| Migrations | `api/database/migrations/` |

**Deployment:** Bare metal on Widow — production API via **`news-intelligence-api-public.service`** (single uvicorn embeds AutomationManager). Do **not** run `start_system.sh` alongside the systemd API. See [docs/WIDOW_BOOT_RESILIENCE.md](docs/WIDOW_BOOT_RESILIENCE.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## SSOT enforcement (NI + Investigation unification)

1. **`os.environ.get` only in `api/config/runtime.py`** (exception: test fixtures).
2. **DB access** via `shared.database.connection` or `database_targets.*_dsn()` for spine.
3. **No qualified `nri.` SQL literals** — import from `api/config/investigation_tables.py`.
4. **No new top-level `nri_*` service files** — code goes in `api/nri_core/`.
5. **Investigation routes** in `api/domains/intelligence_hub/routes/investigation.py`.
6. **CI lint:** `python3 scripts/verify_single_source_of_truth.py`

---

## Database

- **Single module:** `shared.database.connection` — pooled psycopg2 + SQLAlchemy.
- **Apps (API, workers):** Widow `localhost:6432` via PgBouncer (`DB_PORT=6432` in prod `.env`).
- **Admin / migrations / maintenance scripts:** direct Postgres `localhost:5432` (or `DB_MAINTENANCE_PORT`).
- **Database:** `news_intel`, user `newsapp`.
- **See:** [docs/DATABASE.md](docs/DATABASE.md) for schema and connection rules.

### Database Connection Rules (MUST FOLLOW)

1. **Always close connections.** Use `get_db_connection_context()` or `try/finally`.
2. **Three pools exist** — Worker, UI, SQLAlchemy. Don't mix or use raw `psycopg2.connect()`.
3. **Don't hold connections across slow I/O** — close before LLM calls, HTTP, sleeps.
4. **Prod pool sizes** (Widow `/opt/news-intelligence/.env`): `DB_POOL_WORKER_MAX=12`, `DB_POOL_UI_MAX=12` — tune vs `max_connections` before raising.
5. **Backlog cache:** `BACKLOG_CACHE_TTL_SECONDS` (default 90) + single-flight lock in `backlog_metrics._refresh_cache()`; unified stats cached separately (`UNIFIED_INTAKE_BACKLOG_STATS_TTL_SECONDS`, default 300).
6. See `docs/CODING_STYLE_GUIDE.md` for pool env vars and lifecycle details.

---

## Keeping Documentation Aligned

When you change API routes or core behaviour, update `AGENTS.md`, relevant `docs/*.md`, and [PROJECT_STATUS.md](PROJECT_STATUS.md) if host/path authority changes.

---

## Cross-project boundary

News Intelligence is separate from **HomeLab AI Stack**. Homelab's `postgres-mcp` reads NI data read-only. Do not confuse Homelab local Postgres (`:15432`) with NI's `news_intel` (apps `:6432` PgBouncer, Postgres `:5432` on Widow). See [../PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md).

---

*Last verified against Widow ground truth: 2026-07-04 — see [docs/DOCUMENTATION_FACT_CHECK_2026-06.md](docs/DOCUMENTATION_FACT_CHECK_2026-06.md) and [docs/generated/WIDOW_GROUND_TRUTH_2026-06-22.md](docs/generated/WIDOW_GROUND_TRUTH_2026-06-22.md). Recent improvements include event-driven eligibility for dossier/profile/RAG phases, entity organizer domain_key=None fix, and enhanced JSON parsing robustness in entity extraction services.*
