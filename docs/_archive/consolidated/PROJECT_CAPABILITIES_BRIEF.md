> **Status:** Superseded — canonical summary: [PROJECT_OVERVIEW.md](../retired_root_docs_2026_03/PROJECT_OVERVIEW.md) §5–6; full detail preserved here.

# News Intelligence — Current Capabilities Brief

**Purpose:** Onboard an AI advisor or developer with quick, accurate project context.  
**Audience:** Technical advisor needing fast orientation.  
**Last updated:** 2026-03-06

---

## 1. What It Is

**News Intelligence** is an AI-powered news aggregation and analysis platform. It collects RSS feeds and documents, extracts entities and claims, resolves entities across domains, tracks storylines and events over time, verifies facts against multiple sources, and delivers editorial intelligence. All LLM work runs on local models (Ollama).

**Core flow:** Collection → Entity/Topic extraction → Entity resolution → Claim/Context extraction → Storyline tracking → Event chronicles → Fact verification → Editorial output → Intelligence delivery

---

## 2. Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, FastAPI, uvicorn |
| Frontend | React 18, TypeScript (migration in progress), Vite, Material-UI v5 |
| Database | PostgreSQL (Widow at <WIDOW_HOST_IP>:5432; rollback: NAS via SSH tunnel) |
| Schemas | Per-domain (politics, finance, science_tech) + intelligence (cross-domain) |
| Cache | Redis (Docker) |
| LLM | Ollama — Llama 3.1 8B (primary), Mistral 7B (secondary), nomic-embed-text |
| PDF parsing | pdfplumber (text + tables + metadata extraction) |
| DB Access | psycopg2 connection pool + SQLAlchemy; `shared.database.connection` is single source |
| API paths | Flat `/api/...` (no version in path) |

---

## 3. Domains & Structure

Three content domains with shared schemas and per-domain tables:

| Domain key | Tables (per domain) | Purpose |
|------------|---------------------|---------|
| politics | articles, storylines, topics, rss_feeds, events, entity_canonical, article_entities | Political news |
| finance | same | Financial / business news |
| science-tech | same | Science & technology news |

**Cross-domain (intelligence schema):** entity_profiles, entity_dossiers, entity_positions, contexts, extracted_claims, tracked_events, event_chronicles, pattern_discoveries, processed_documents, document_intelligence, entity_relationships, narrative_threads.

**Global:** watchlist, system_monitoring, health.

---

## 4. Implemented Capabilities

### 4.1 News Aggregation
- **RSS collection:** Multi-feed collector; stores articles per domain with full `content:encoded` body
- **Feed management:** CRUD for feeds, duplicate detection
- **Morning pipeline:** Cron (4–6 AM) runs RSS fetch → entity extraction → topic extraction
- **PDF ingestion:** Download, parse (pdfplumber), extract sections/entities/findings → `processed_documents`

### 4.2 Content Analysis
- **Entity extraction:** LLM extracts people, orgs, subjects, dates, times, countries, keywords with contextual excerpts
- **Topic extraction:** LLM topic assignment via `TopicExtractionQueueWorker`
- **Deduplication:** Article and RSS duplicate detection
- **Quality scoring:** Content quality assessment
- **Sentiment analysis:** Per-article sentiment labels stored in `ml_data`
- **ML enrichment:** Summarization, key point extraction, argument analysis → `ml_data` JSONB

### 4.3 Entity Resolution
- **Disambiguation:** Title prefix stripping, last-name fallback, bigram fuzzy matching
- **Alias management:** Batch population from article mention variants
- **Merge detection & execution:** Automatic merging of high-confidence duplicates; manual merge UI
- **Cross-domain linking:** Same entity found across politics/finance/science-tech linked via entity_relationships
- **Integration:** Runs as part of `entity_organizer` phase in AutomationManager

### 4.4 Storyline Management
- **CRUD:** Create, read, update, delete storylines
- **Articles:** Add/remove articles; entity merge into `story_entity_index`
- **Automation:** RAG-enhanced discovery; modes: disabled, manual, auto-approve
- **Editorial documents:** `editorial_document` JSONB with lede, developments, analysis, outlook
- **Timeline:** Chronological event ordering with narrative summaries
- **Watchlist:** User watchlist for storylines

### 4.5 Intelligence Hub
- **RAG:** Semantic search, query expansion
- **Entity profiles & dossiers:** Cross-domain entity intelligence
- **Entity positions:** LLM-extracted policy stances, votes, statements
- **Contexts & claims:** Context creation from articles; claim extraction and tracking
- **Tracked events:** Event lifecycle with chronicle builder and editorial briefings
- **Narrative threads:** Cross-article narrative tracking
- **Content synthesis:** Domain/storyline/event/entity scoped intelligence aggregation
- **Briefings:** Editorial-first daily/weekly briefings with LLM lead generation
- **Fact verification:** Multi-source corroboration, contradiction detection, source reliability scoring

### 4.6 Finance
- **Orchestrator:** Gold/FRED/EDGAR refresh, analysis task queue, evidence collection
- **Analysis:** LLM-powered financial analysis with evidence provenance
- **Market data:** Commodity dashboard, market patterns, corporate announcements
- **Evidence:** RSS-derived news context included in analysis prompts

### 4.7 System Monitoring
- **Health:** DB, Redis, API, LLM status checks
- **Pipeline status:** ML processing, collection, and entity extraction status
- **Orchestrator dashboard:** Coordinator status, governor states, run history
- **Realtime monitoring:** Activity feeds, resource monitoring
- **Route supervisor:** Route consistency and DB connection monitoring

### 4.8 Automation (Background)

`AutomationManager` runs in-process with the API:

| Task | Interval | Purpose |
|------|----------|---------|
| rss_processing | 1 hour | RSS collection |
| article_processing | 20 min | Basic article processing |
| ml_processing | 20 min | Summarization, ML features |
| topic_clustering | 20 min | Topic assignment |
| entity_extraction | 20 min | Article entity extraction |
| entity_organizer | 20 min | Entity resolution batch (disambiguate, merge, link) |
| quality_scoring | 20 min | Quality scores |
| sentiment_analysis | 20 min | Sentiment |
| storyline_automation | Configurable | RAG-based article discovery |
| editorial_document_generation | 30 min | Generate/update storyline editorials |
| editorial_briefing_generation | 30 min | Generate/update event briefings |

---

## 5. Frontend

**Layout:** Domain-first routing — `/:domain/dashboard`, `/:domain/articles`, etc.

**Main pages (per domain):**
- Dashboard, Articles, ArticleDetail, FilteredArticles, ArticleDeduplicationManager
- Storylines, StorylineDiscovery, ConsolidationPanel, StoryDetail, SynthesizedView, StoryTimeline
- Topics, TopicArticles
- RSS Feeds, RSS Duplicate Manager
- Briefings (redesigned — editorial-first sections, LLM summary)

**Investigate section:**
- Entity profiles and canonical entity management (browse, merge, resolve)
- Event tracking and detail pages
- Processed documents (PDF pipeline status and results)
- Narrative threads

**Monitor section:**
- System health, pipeline status, orchestrator dashboard
- Realtime activity monitoring, resource tracking

**Finance-specific:** Market Research, Corporate Announcements, Market Patterns, Commodity Dashboard.

---

## 6. API Structure

| Domain | Path pattern | Key routes |
|--------|--------------|------------|
| news_aggregation | `/api/{domain}/...` | articles, feeds, collect_now |
| content_analysis | `/api/{domain}/content_analysis/...` | topics, extraction, dedup |
| storyline_management | `/api/{domain}/storylines/...` | storylines, automation, timeline, watchlist |
| intelligence_hub | `/api/intelligence_hub/...` | trends, RAG, synthesis, briefings |
| context_centric | `/api/tracked_events/...`, `/api/entities/...`, `/api/contexts/...` | events, entities, contexts, claims, documents |
| synthesis | `/api/synthesis/...` | domain, storyline, event, entity synthesis |
| verification | `/api/verification/...` | corroborate, contradictions, completeness, batch |
| cross_domain | `/api/cross_domain/...` | network graph, relationship extraction |
| quality | `/api/quality/...` | feedback, assessment |
| finance | `/api/{domain}/finance/...` | analyze, tasks, schedule, evidence, gold |
| system_monitoring | `/api/system_monitoring/...` | health, pipeline, metrics |
| orchestrator | `/api/orchestrator/...` | status, dashboard, decision_log |

---

## 7. Key Files & Entry Points

| Purpose | Path |
|---------|------|
| API entry | `api/main.py` |
| DB connection | `api/shared/database/connection.py` |
| Frontend entry | `web/src/App.tsx` |
| Domain layout | `web/src/layout/MainLayout.tsx` |
| Context-centric routes | `api/domains/intelligence_hub/routes/context_centric.py` |
| Entity resolution | `api/services/entity_resolution_service.py` |
| Fact verification | `api/services/fact_verification_service.py` |
| Content synthesis | `api/services/content_synthesis_service.py` |
| Document processing | `api/services/document_processing_service.py` |
| Editorial generation | `api/services/editorial_document_service.py` |
| Start system | `start_system.sh` |
| Agent guidance | `AGENTS.md` |

---

## 8. Constraints & Conventions

- **DB:** Default Widow at `<WIDOW_HOST_IP>:5432`; rollback to NAS via SSH tunnel `localhost:5433`
- **Ports:** DB 5432 (Widow) or 5433 (tunnel), API 8000, frontend 3000
- **Naming:** snake_case (Python, routes, DB); PascalCase (React components)
- **Config:** Use documented values; avoid inventing new ports/hosts
- **Single source:** One implementation per concern; `config.database` shims to `shared.database.connection`
- **Intelligence-first:** APIs return stories not statistics; editorial documents are primary outputs

---

## 9. Planned / Not Yet Implemented

- **Expanded election tracker:** Maps, live tracking, politician profiles (politics domain) — not scoped
- **GPU OCR for scanned PDFs** — current PDF parser handles text-based only
- **Multi-tenant, multi-language, advanced security** — on roadmap, not implemented

---

## 10. Documentation Map

| Need | Doc |
|------|-----|
| High-level scope | `docs/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md` |
| Coding standards | `docs/CODING_STYLE_GUIDE.md` |
| Architecture principles | `docs/CORE_ARCHITECTURE_PRINCIPLES.md` |
| Implementation rules | `docs/IMPLEMENTATION_CONSTRAINTS.md` |
| Intelligence cascade | `docs/DATA_FLOW_ARCHITECTURE.md` |
| Domain specs | `docs/DOMAIN_1_NEWS_AGGREGATION.md` … `DOMAIN_6_SYSTEM_MONITORING.md` |
| v6 upgrade status | `docs/V6_QUALITY_FIRST_TODO.md` |

---

*Use this brief to orient quickly; refer to the linked docs and `AGENTS.md` for detailed design and terminology.*
