# News Intelligence v6 Planning — High-Level Overview

> **Purpose:** Provide Claude and human planners with a concise, accurate summary of the v5 system for v6 project development.

---

## 1. What the System Is

**News Intelligence** is an AI-powered news aggregation and analysis platform. It:

1. **Collects** RSS feeds from multiple sources
2. **Processes** articles (entity extraction, topic assignment, summarization, quality scoring)
3. **Tracks** storylines over time with RAG-enhanced discovery
4. **Delivers** intelligence dashboards and analysis views

All LLM work runs on local models (Ollama).

**Core flow:** Collection → Entity/Topic extraction → Storyline tracking → Intelligence delivery

---

## 2. Architecture (v5 — Three-Machine)

| Machine | IP | Role |
|---------|-----|------|
| **Primary** | 192.168.93.99 | API (FastAPI), ML, Ollama, Redis, Frontend |
| **Widow** | 192.168.93.101 | PostgreSQL, RSS worker, DB backups |
| **NAS** | 192.168.93.100 | Storage only (no PostgreSQL) |

### Data Flow

- **Primary** runs the FastAPI app, connects to Widow's database over LAN
- **Widow** runs PostgreSQL 16 and the RSS collector (systemd), backs up locally (or NAS if mounted)
- **NAS** is used for archives/backups; no application logic

---

## 3. Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, FastAPI, uvicorn |
| Frontend | React 18, Material-UI, Vite 7 |
| Database | PostgreSQL 16 (on Widow) |
| Cache | Redis |
| LLM | Ollama — Llama 3.1 8B, Mistral 7B, nomic-embed-text |
| DB Access | psycopg2 + SQLAlchemy; `api/shared/database/connection` |
| API version | v4 (routes at `/api/v4/...`) |
| App version | v5.0 (stable) |

---

## 4. Domains (Content Silos)

Three content domains with schema-based isolation:

| Domain key | Schema | Purpose |
|------------|--------|---------|
| politics | `politics` | Political news |
| finance | `finance` | Financial / business news |
| science-tech | `science_tech` | Science & technology news |

Each domain has its own schema with: `articles`, `topics`, `storylines`, `rss_feeds`, `article_topic_assignments`, `topic_clusters`, `topic_cluster_memberships`, `topic_learning_history`. Finance has additional tables: `market_patterns`, `corporate_announcements`, `financial_indicators`.

**Global (public):** `domains`, `domain_metadata`, watchlist, system_monitoring, health, API cache.

---

## 5. Implemented Capabilities

### 5.1 News Aggregation

- Multi-feed RSS collector; stores articles per domain
- Feed management CRUD, duplicate detection
- Morning pipeline cron runs RSS fetch → entity extraction → topic extraction

### 5.2 Content Analysis

- **Entity extraction:** People, orgs, subjects, dates, times, countries, keywords
- **Topic extraction:** LLM-based; queues articles, assigns topics
- Deduplication, quality scoring, sentiment analysis

### 5.3 Storyline Management

- CRUD for storylines; add/remove articles
- RAG-enhanced discovery; modes: disabled, manual (suggestions), auto-approve
- Entity merge into `story_entity_index`; timeline ordering; watchlist

### 5.4 Intelligence Hub

- Trends, briefings, analysis views; RAG semantic search; content synthesis; watchlist

### 5.5 System Monitoring

- Health checks (DB, Redis, API, LLM); route supervisor; LLM activity tracking

### 5.6 Automation (AutomationManager)

Runs in-process with the API: RSS processing (1h), article processing, ML processing, topic clustering, entity extraction, quality scoring, sentiment, storyline automation (configurable), cleanup (24h).

---

## 6. Key URLs and Scripts

| Item | Value |
|------|-------|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/v4/system_monitoring/health |

| Script | Purpose |
|--------|---------|
| `start_system.sh` | Start API, frontend, Redis |
| `status_system.sh` | Check all services |
| `stop_system.sh` | Stop API and frontend |
| `scripts/deploy_to_widow.sh` | Deploy code to Widow |
| `scripts/configure_widow_no_sleep.sh` | Disable Widow sleep |

---

## 7. Documentation References

| Doc | Purpose |
|-----|---------|
| `docs/ARCHITECTURE_AND_OPERATIONS.md` | Ops, troubleshooting |
| `docs/PROJECT_CAPABILITIES_BRIEF.md` | Capabilities overview |
| `docs/CONTROLLER_ARCHITECTURE.md` | Proposed controller design |
| `docs/DOCS_INDEX.md` | Full docs index |

---

## 8. v6 Planning Notes

- v5 is stable; v6 is the next development target
- API routes remain at `/api/v4/` unless explicitly versioned
- Database schema evolved through many migrations; see `02_DATABASE_SCHEMA.md`
