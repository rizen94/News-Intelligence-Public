# News Intelligence System — Agent Guidance

> **HOST GUARDRAILS (read first)**  
> - **Migration complete (June 2026).** All NI development and queries belong on **Widow** (`192.168.93.101`).  
> - **Dev workspace:** `/home/pete/Documents/projects/News Intelligence` on Widow  
> - **Production runtime:** `/opt/news-intelligence` on Widow (API may run from here)  
> - **PopOS local copy** (`192.168.93.99`) is headed for NAS cold storage — do not treat it as authoritative.  
> - **Database:** NI owns `news_intel` on Widow `:5432`. Homelab Postgres MCP on PopOS reads it read-only — that is **not** Homelab's local Postgres on `:15432`.  
> - See [PROJECT_STATUS.md](PROJECT_STATUS.md) and [../PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md).

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

- **Domains:** `politics`, `finance`, `science-tech` (built-in); optional domains via `api/config/domains/*.yaml` and [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](docs/DOMAIN_EXTENSION_TEMPLATE.md).
- **Active pipeline domains** (June 2026): `politics` and `finance` per `public.domains` / `PIPELINE_INCLUDE`. `science-tech` remains in the registry but is **inactive** until enabled in the domain registry and YAML — do not expect RSS or automation for it while excluded.
- **After changing YAML:** restart API and worker processes — `DOMAIN_PATH_PATTERN` and `ACTIVE_DOMAIN_KEYS` are computed at import time.
- **Per-domain:** `articles`, `storylines`, `topics`, `rss_feeds`, `events`.
- **Global:** watchlist, monitoring (`system_monitoring`), health.

---

## Key Flows

1. **Article:** RSS → processing → storyline linking → event extraction.
2. **Storyline:** create → add articles → queued refinement (`intelligence.content_refinement_queue`).
3. **Events (v5):** extract → deduplicate → story continuation → alerts.
4. **Ollama:** Model routing via `api/shared/services/ollama_model_caller.py`. **Widow** (`OLLAMA_HOST`, `:11434`) runs all normal CPU- and GPU-lane work (8B, Qwen extraction, topic clustering, etc.). **PopOS** (`OLLAMA_POP_OS_HOST`, RTX 5090) is **GPU overflow only** — `:70b` narrative finisher and other models too large for Widow's GTX 1080. Do not enable `OLLAMA_DUAL_HOST_ROUTING_ENABLED` unless deliberately splitting lanes across two Ollama hosts.
5. **Public HTTPS:** PopOS Caddy → Widow nginx — see [docs/WIDOW_PUBLIC_STACK.md](docs/WIDOW_PUBLIC_STACK.md).
5. **Widow (post-migration):** Full stack on Widow. AutomationManager runs on Widow API host. DB-adjacent cron per `docs/WIDOW_DB_ADJACENT_CRON.md`.

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

## Database

- **Single module:** `shared.database.connection` — pooled psycopg2 + SQLAlchemy.
- **Canonical:** Widow `localhost:5432`, database `news_intel`, user `newsapp`.
- **See:** [docs/DATABASE.md](docs/DATABASE.md) for schema and connection rules.

### Database Connection Rules (MUST FOLLOW)

1. **Always close connections.** Use `get_db_connection_context()` or `try/finally`.
2. **Three pools exist** — Worker, UI, SQLAlchemy. Don't mix or use raw `psycopg2.connect()`.
3. **Don't hold connections across slow I/O** — close before LLM calls, HTTP, sleeps.
4. See `docs/CODING_STYLE_GUIDE.md` for pool env vars and lifecycle details.

---

## Keeping Documentation Aligned

When you change API routes or core behaviour, update `AGENTS.md`, relevant `docs/*.md`, and [PROJECT_STATUS.md](PROJECT_STATUS.md) if host/path authority changes.

---

## Cross-project boundary

News Intelligence is separate from **HomeLab AI Stack**. Homelab's `postgres-mcp` reads NI data read-only. Do not confuse Homelab local Postgres (`:15432`) with NI's `news_intel` (`:5432` on Widow). See [../PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md).
