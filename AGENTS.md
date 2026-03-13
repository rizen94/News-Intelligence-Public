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
| API | `api/main_v4.py` |
| Frontend | `web/src/App.tsx` |
| API client | `web/src/services/api/` + `apiService.ts` |
| DB (single source) | `api/shared/database/connection.py` |
| Domain routing | `web/src/components/shared/DomainLayout/DomainLayout.tsx` |

---

## Architecture Principles

1. **Single source of truth** — One config per concern (e.g. `config/database.py` shims to `shared.database.connection`).
2. **Reuse before create** — Search existing and archived code before adding new services.
3. **Consolidate, don't proliferate** — Extend existing modules instead of creating "Enhanced" or "Unified" variants.
4. **snake_case** (Python): files, functions, variables, routes, DB tables/columns.
5. **PascalCase** (React): components, classes.

---

## Domain Structure

- **Domains:** `politics`, `finance`, `science-tech` (shared schemas).
- **Per-domain:** `articles`, `storylines`, `topics`, `rss_feeds`, `events`.
- **Global:** watchlist, monitoring (`system_monitoring`), health.

---

## Key Flows

1. **Article:** RSS → processing → storyline linking → event extraction.
2. **Storyline:** create → add articles → analyze → timeline → watchlist.
3. **Events (v5):** extract → deduplicate → story continuation → alerts.

---

## File Layout

| Area | Location |
|------|----------|
| API routes | `api/domains/*/routes/` |
| Services | `api/services/`, `api/domains/*/services/` |
| Frontend pages | `web/src/pages/` |
| API modules | `web/src/services/api/` (articles, watchlist, storylines, topics, rss, monitoring) |

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
- **Primary config:** Widow at `192.168.93.101:5432`, DB `news_intel`. Rollback: NAS via `DB_HOST=localhost`, `DB_PORT=5433` + `setup_nas_ssh_tunnel.sh`.

---

## Before Creating New Code

1. Search for existing or archived implementations.
2. Extend existing services instead of creating new ones.
3. Use `Logger` (frontend) or `logger` (backend) for logging.
4. Follow naming in this file and `docs/CODING_STYLE_GUIDE.md`.

---

## Planned / Future Work

**Expanded Election Tracker** (to develop later):

- Maps for election coverage and results
- Election updates and live tracking
- Politician profiles surfaced on maps and in updates

Planned for the politics domain. Not yet scoped or scheduled.
