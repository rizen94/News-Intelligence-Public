# News Intelligence — Current Capabilities Brief

**Purpose:** Onboard an AI advisor (e.g., Claude 4.6) for advising on a new version.  
**Audience:** Technical advisor needing quick, accurate project context.  
**Last updated:** 2026-02-27

---

## 1. What It Is

**News Intelligence** is an AI-powered news aggregation and analysis platform. It collects RSS feeds, extracts entities and topics, tracks storylines over time, and delivers intelligence dashboards. All LLM work runs on local models (Ollama).

**Core flow:** Collection → Entity/Topic extraction → Storyline tracking → Intelligence delivery

---

## 2. Tech Stack (Current)

| Layer | Technology |
|-------|------------|
| Backend | Python 3, FastAPI, uvicorn |
| Frontend | React, Material-UI, Vite |
| Database | PostgreSQL (on NAS, via SSH tunnel) |
| Cache | Redis (Docker) |
| LLM | Ollama — Llama 3.1 8B (primary), Mistral 7B (secondary), nomic-embed-text |
| DB Access | psycopg2 connection pool + SQLAlchemy; `shared.database.connection` is single source |
| API version | v4 (`/api/v4/...`) |

---

## 3. Domains & Structure

Three content domains with shared schemas and per-domain tables:

| Domain key | Tables (per domain) | Purpose |
|------------|---------------------|---------|
| politics | articles, storylines, topics, rss_feeds, events | Political news |
| finance | same | Financial / business news |
| science-tech | same | Science & technology news |

**Global:** watchlist, system_monitoring, health.

**Database:** NAS at `192.168.93.100`; access via SSH tunnel `localhost:5433 → NAS:5432`. Direct DB connections are blocked.

---

## 4. Implemented Capabilities

### 4.1 News Aggregation

- **RSS collection:** Multi-feed collector; stores articles per domain
- **Feed management:** CRUD for feeds, duplicate detection
- **Morning pipeline:** Cron (4–6 AM) runs `run_rss_and_process_all.py` — RSS fetch → entity extraction → topic extraction
- **Scripts:** `scripts/rss_collection_with_health_check.sh`, `scripts/morning_data_pipeline.sh`

### 4.2 Content Analysis

- **Entity extraction:** `ArticleEntityExtractionService` — LLM extracts people, orgs, subjects, recurring events, dates, times, countries, keywords
- **Schema:** `article_entities`, `article_extracted_dates`, `article_extracted_times`, `article_extracted_countries`, `article_keywords`, `entity_canonical` (per domain)
- **Topic extraction:** `LLMTopicExtractor`, `TopicExtractionQueueWorker` — queues articles, assigns topics; prompts exclude dates/times/countries from topics
- **Deduplication:** Article and RSS duplicate detection
- **Quality scoring:** Content quality assessment
- **Sentiment:** Sentiment analysis (basic)

### 4.3 Storyline Management

- **CRUD:** Create, read, update, delete storylines
- **Articles:** Add/remove articles to storylines
- **Automation:** RAG-enhanced discovery; modes: disabled, manual (suggestions), auto-approve
- **Entity merge:** `article_entities` merged into `story_entity_index` when articles are added
- **Timeline:** Chronological event ordering
- **Watchlist:** User watchlist for storylines

### 4.4 Intelligence Hub

- **IntelligenceHub:** Trends, briefings, analysis views
- **RAG:** Semantic search, query expansion
- **Synthesis:** Content synthesis endpoints
- **Watchlist:** Shared watchlist integration

### 4.5 System Monitoring

- **Health:** DB, Redis, API, LLM status
- **Route supervisor:** Route consistency and DB connection monitoring
- **LLM activity:** Ollama usage tracking

### 4.6 Automation (Background)

`AutomationManager` runs in-process with the API:

| Task | Interval | Purpose |
|------|----------|---------|
| rss_processing | 1 hour | RSS collection |
| article_processing | 20 min | Basic article processing |
| ml_processing | 20 min | Summarization, ML features |
| topic_clustering | 20 min | Topic assignment |
| entity_extraction | 20 min | Article entity extraction |
| quality_scoring | 20 min | Quality scores |
| sentiment_analysis | 20 min | Sentiment |
| storyline_automation | Configurable | RAG-based article discovery for storylines |

---

## 5. Frontend (Current)

**Layout:** Domain-first routing — `/:domain/dashboard`, `/:domain/articles`, etc.

**Main pages (per domain):**

- Dashboard, Articles, ArticleDetail, FilteredArticles, ArticleDeduplicationManager
- Storylines, StorylineDiscovery, ConsolidationPanel, StoryDetail, SynthesizedView, StoryTimeline
- Topics, TopicArticles
- RSS Feeds, RSS Duplicate Manager
- Intelligence, IntelligenceAnalysis, DomainRAG, StorylineTracking, Briefings, Events, Watchlist
- ML Processing, Story Control Dashboard

**Finance-specific:** Market Research, Corporate Announcements, Market Patterns.

**Global:** Monitoring, Settings.

---

## 6. API Structure

| Domain | Prefix | Key routes |
|--------|-------|-----------|
| news_aggregation | `/api/v4/news_aggregation` | articles, feeds |
| content_analysis | `/api/v4/content_analysis` | topics, extraction, dedup |
| storyline_management | `/api/v4/storyline_management` | storylines, automation, timeline, watchlist |
| intelligence_hub | `/api/v4/intelligence_hub` | trends, RAG, synthesis |
| finance | `/api/v4/finance` | finance-specific |
| system_monitoring | `/api/v4/system_monitoring` | health, supervisor |

**Compatibility:** v3 compatibility layer for legacy clients.

---

## 7. Key Files & Entry Points

| Purpose | Path |
|---------|------|
| API entry | `api/main_v4.py` |
| DB connection | `api/shared/database/connection.py` |
| DB shim | `api/config/database.py` (re-exports) |
| Frontend entry | `web/src/App.tsx` |
| Domain layout | `web/src/components/shared/DomainLayout/DomainLayout.tsx` |
| Start system | `start_system.sh` (tunnel, Redis, API, frontend) |
| SSH tunnel | `scripts/setup_nas_ssh_tunnel.sh` |
| Morning pipeline | `scripts/morning_data_pipeline.sh` |
| Agent guidance | `AGENTS.md` |

---

## 8. Constraints & Conventions

- **DB:** SSH tunnel required (`localhost:5433`); no direct NAS connection
- **Ports:** DB 5433 (tunnel), API 8000, frontend 3000
- **Naming:** snake_case (Python, routes, DB); PascalCase (React components)
- **Config:** Use documented values; avoid inventing new ports/hosts
- **Single source:** One implementation per concern; `config.database` shims to `shared.database.connection`

---

## 9. Planned / Not Yet Implemented

- **Expanded election tracker:** Maps, live tracking, politician profiles (politics domain) — not scoped
- **Multi-tenant, multi-language, advanced security** — on roadmap, not implemented

---

## 10. Documentation Map

| Need | Doc |
|------|-----|
| Coding standards | `docs/CODING_STYLE_GUIDE.md` |
| Entity schema design | `docs/ARTICLE_ENTITY_SCHEMA_DESIGN.md` |
| Storyline automation | `docs/STORYLINE_AUTOMATION_GUIDE.md` |
| NAS / DB setup | `docs/NAS_DATABASE_CONFIGURATION.md` |
| Domain specs | `docs/DOMAIN_1_NEWS_AGGREGATION.md` … `DOMAIN_6_SYSTEM_MONITORING.md` |
| API reference | `docs/API_DOCUMENTATION.md` |

---

*Use this brief to orient quickly; refer to the linked docs and `AGENTS.md` for detailed design and terminology.*
