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

**Knowledge thesis:** Content is stored and *improved* over time. On the same subject, facts and vault timelines grow; quality writes (canonical narrative, briefs) should get clearer by using that pile — and the prior desk prose — not by starting from nothing. Prefer full rewrite when evidence is material; skip when unchanged; defer narrow deltas to nightly debt drain. Full design: [`docs/KNOWLEDGE_LOOP.md`](docs/KNOWLEDGE_LOOP.md). Operator env: [`docs/STORYLINE_HISTORICAL_MEMORY.md`](docs/STORYLINE_HISTORICAL_MEMORY.md). Living twin: [`docs/VAULT_NOTES_AND_PULL_CONTEXT.md`](docs/VAULT_NOTES_AND_PULL_CONTEXT.md).

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
| Live ops console | **Monitor** (in-app) | Grafana (history/infra) |
| History / infra charts | **Homelab Grafana** (`ni_*` scrape) | embedding Grafana into Monitor |
| Intelligence features | **intelligence_hub** | intelligence hub |

---

## Entry Points

| Role | Path |
|------|------|
| API | `api/main.py` |
| Frontend | `web/src/App.tsx` |
| Finance product (trackers / markets / reporting) | `web/src/finance/` — routes under `/finance/*` |
| API client | `web/src/services/api/` + `apiService.ts` |
| DB (single source) | `api/shared/database/connection.py` |
| Product root switcher | `web/src/shell/ProductRootSwitcher.tsx` — News `/` · Finance `/finance` · Admin `/admin` |
| News (default) | `web/src/v2/` — `/`, `/news`, `/current`, `/hubs` (Situations index), `/one-offs`, `/research`, `/storylines/:domain/:id`, `/hubs/:idOrSlug` on **https://news-intelligence-ag.duckdns.org** (Living context + Pull context + cluster hubs). Legacy `/v2/*` redirects. |
| Admin (ops) | `web/src/v2/pages/admin/` — `/admin` (Monitor, Work, SQL, Audit) |
| Classic UI | **Retired** — cold storage `archive/classic_web_ui/` (not mounted) |
| Reader APIs (additive) | `api/domains/reader/` — `GET /api/reader/home`, `GET /api/reader/storylines/{id}`, vault notes + hubs (`GET /api/reader/vault-hubs`, `/hubs/:idOrSlug`), `POST .../pull-context`. Home serves morning briefing + expansion catalog from cache only. Storyline `editorial_document` is durable package/desk projection (not the QUICK_SUMMARY batch phases). |
| Morning Briefing Manager | `api/services/morning_briefing_manager_service.py` + MemPalace (`mempalace_brief_memory.py`) — 70b curator for two-lane daily brief; see `docs/VAULT_NOTES_AND_PULL_CONTEXT.md` |
| Background automation | `api/services/automation_manager.py` |
| Knowledge loop (intent) | `docs/KNOWLEDGE_LOOP.md` — compounding clarity; materiality + prior canonical + narrow debt |
| Human reviewer navigation | `docs/CODEBASE_MAP.md`, `docs/PIPELINE_AND_AUTOMATION.md`, `docs/CODE_REVIEW_AND_RUN_CAVEATS.md` |
| Monitor vs Grafana | `docs/MONITOR_REPORTING_AND_METRICS.md`, `api/monitoring/grafana/README.md` |
| Public HTTPS read-only demo | `docs/PUBLIC_DEPLOYMENT.md` (TLS, env, `NEWS_INTEL_DEMO_*`, `GET /api/public/demo_config`) |
| Research papers (scientific) | `api/services/research_paper_classifier.py` + `research_paper_profile_service.py` → profiles → literature bridge → `claim_evidence_appraisal` → `knowledge_profiles` / `research_claim_ledger`; reader `/research` subject board + paper list. Papers are **not** news storylines (excluded from discovery/proactive/claim/event). See [`docs/RESEARCH_PAPER_PATHWAY.md`](docs/RESEARCH_PAPER_PATHWAY.md). |

**Product roots:** News `/`, Finance `/finance`, Admin `/admin` on **https://news-intelligence-ag.duckdns.org**. Single SPA architecture (`web/src/v2/` + finance); classic domain IA is cold-stored, not served.

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
- **Global:** watchlist, monitoring (`system_monitoring`), health. **Monitor** = live/action ops console; **Homelab Grafana** = history/infra via `GET /api/system_monitoring/prometheus` (`ni_*`).

---

## Key Flows

1. **Article:** RSS → processing → storyline linking → event extraction.
2. **Storyline:** create → add articles → queued refinement (`intelligence.content_refinement_queue`).
3. **Knowledge loop (canonical narrative):** membership admit / fact snapshot → materiality classify → skip | mark narrow debt | full ~70B rewrite with **prior canonical** in the prompt → stamp `evidence_fingerprint`. Nightly drain force-finishes `narrow_debt_pending`. See [`docs/KNOWLEDGE_LOOP.md`](docs/KNOWLEDGE_LOOP.md).
4. **Events (v5):** extract → deduplicate → story continuation → alerts.
5. **Ollama:** Model routing via `api/shared/services/ollama_model_caller.py` + `ollama_model_policy.py`. **Throughput-bound** intake (`STRUCTURED_EXTRACTION`, Qwen/8B) stays on **Widow** (`OLLAMA_HOST`, `:11434`). **Quality-bound** durable narrative uses `STORYLINE_NARRATIVE_FINISH` (PopOS `OLLAMA_POP_OS_HOST` / 70b-class when dual-host is on) — storyline finisher, Morning Briefing Manager, package compose. Do not enable `OLLAMA_NARRATIVE_FINISHER_FALLBACK_TO_PRIMARY` in production. Do not enable `OLLAMA_DUAL_HOST_ROUTING_ENABLED` unless deliberately splitting lanes across two Ollama hosts. All generate/embed traffic goes through `llm_service` (CB hub). Under backpressure: **defer** (requeue pending) and **trickle** drain; **shed** intake when any of `OLLAMA_CB_KEYS` is OPEN; **overload** (timeout/5xx) does not trip — host down does. Monitor: `POST /api/system_monitoring/circuit_breakers/reset`. See `docs/MONITOR_REPORTING_AND_METRICS.md`.
6. **Public HTTPS:** PopOS Caddy → Widow nginx — see [docs/WIDOW_PUBLIC_STACK.md](docs/WIDOW_PUBLIC_STACK.md).
7. **Widow (post-migration):** Full stack on Widow. AutomationManager runs on Widow API host. DB-adjacent cron per `docs/WIDOW_DB_ADJACENT_CRON.md`.

---

## File Layout

| Area | Location |
|------|----------|
| API routes | `api/domains/*/routes/` |
| Services | `api/services/`, `api/domains/*/services/` |
| Frontend pages (legacy) | `archive/classic_web_ui/` (cold storage; not mounted) |
| Frontend pages (News / Admin) | `web/src/v2/pages/` |
| Frontend pages (Finance) | `web/src/finance/` + shared `web/src/pages/Finance`, `web/src/pages/Monitor` |
| Migrations | `api/database/migrations/` |

**Deployment:** Bare metal on Widow — production API via **`news-intelligence-api-public.service`** (single uvicorn embeds AutomationManager). Do **not** run `start_system.sh` alongside the systemd API. See [docs/WIDOW_BOOT_RESILIENCE.md](docs/WIDOW_BOOT_RESILIENCE.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## Database

- **Single module:** `shared.database.connection` — pooled psycopg2 + SQLAlchemy.
- **Canonical:** Widow `localhost:5432` (or PgBouncer `:6432`), database `news_intel`, user `newsapp`.
- **See:** [docs/DATABASE.md](docs/DATABASE.md) for schema and connection rules.

### Database Connection Rules (MUST FOLLOW)

1. **Always close connections.** Use `get_db_connection_context()` or `try/finally`.
2. **Four pools exist** — Worker, UI, Health, SQLAlchemy. Don't mix or use raw `psycopg2.connect()`.
3. **Don't hold connections across slow I/O** — close before LLM calls, HTTP, sleeps.
4. **Checkout waits/retries** on pool exhaustion (no unaccounted direct sessions unless `DB_ALLOW_DIRECT_FALLBACK=true`). Automation defers *new* schedules on worker `pressure`/`waiters`; PopOS workers read `public.db_pool_pressure_advisory`.
5. See `docs/CODING_STYLE_GUIDE.md` and `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md` for pool env vars and lifecycle details.

**Widow vs PopOS (same code tree):** `~/ni-popos-worker` is a symlink to this workspace. Use one `connection.py` / `pool_pressure_advisory.py` everywhere. On PopOS UI/API hosts set `AUTOMATION_MANAGER_ENABLED=false` so only Widow (or the designated API) runs AutomationManager; PopOS phase workers still share the advisory table and the same pool wait/retry behavior.

---

## Keeping Documentation Aligned

When you change API routes or core behaviour, update `AGENTS.md`, relevant `docs/*.md`, and [PROJECT_STATUS.md](PROJECT_STATUS.md) if host/path authority changes.

---

## Cross-project boundary

News Intelligence is separate from **HomeLab AI Stack**. Homelab's `postgres-mcp` reads NI data read-only. Do not confuse Homelab local Postgres (`:15432`) with NI's `news_intel` (`:5432` on Widow). See [../PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md).
