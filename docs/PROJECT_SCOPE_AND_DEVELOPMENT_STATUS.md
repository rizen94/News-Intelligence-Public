# News Intelligence — High-Level Scope & Development Status

> **Purpose:** Full scope view of what is built, how it connects, and where gaps or disconnects are. Use this to assess “database → API → web” and plan next steps.  
> **Audience:** Product/tech lead, onboarding.  
> **Last updated:** 2026-03-03.

---

## 1. What We Have: Version and Naming

- **Product:** News Intelligence — AI-powered news aggregation, analysis, and intelligence.
- **Backend:** FastAPI app in `api/main_v4.py`; **version string is v5.0** (“News Intelligence System v5.0”).
- **API:** **Flat paths** — `/api/...` (no `/api/v4/` or `/api/v5/` in code). Some older docs still say “/api/v4”; treat those as stale.
- **Optional “v6”:** **Newsroom Orchestrator v6** is a feature-flagged component (event bus, roles: chief_editor, archivist, etc.). It is **optional** and not the main user-facing surface. When we say “v6,” we usually mean this orchestrator; the main platform is v5.

---

## 2. Architecture: Three Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│  WEB (React + MUI + Vite)                                                │
│  DomainLayout → /:domain/dashboard, articles, storylines, finance/...   │
│  API calls via getApi() → baseURL (env/proxy) + /api/{domain}/...       │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  API (FastAPI, main_v4.py)                                               │
│  Domains: news_aggregation, content_analysis, storyline_management,       │
│           intelligence_hub, finance, user_management, system_monitoring │
│  + OrchestratorCoordinator, FinanceOrchestrator, AutomationManager       │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌──────────────────┐    ┌────────────────────────────┐    ┌──────────────────┐
│  PostgreSQL      │    │  SQLite (finance +         │    │  Redis (optional)│
│  (Widow default)  │    │  orchestrator state)       │    │  Cache/sessions  │
│  schemas:        │    │  market_data, evidence_    │    └──────────────────┘
│  politics,       │    │  ledger, orchestrator_    │
│  finance,        │    │  state.db, api_cache       │
│  science_tech,   │    └────────────────────────────┘
│  public          │
└──────────────────┘
```

- **Web:** Single React SPA. Routes are domain-scoped under `/:domain/*` (e.g. `/finance/analysis`, `/politics/dashboard`). API base URL from `VITE_API_URL` or localStorage; health check uses `/api/system_monitoring/health`.
- **API:** One FastAPI app. Domain routers are mounted with prefix `/api`; paths look like `/api/{domain}/finance/analyze`, `/api/{domain}/storylines`, `/api/orchestrator/status`, etc.
- **Data:** PostgreSQL holds per-domain content (articles, storylines, topics, rss_feeds, etc.). Finance also uses SQLite (market data, evidence ledger, orchestrator state, API cache). ChromaDB holds finance EDGAR embeddings.

---

## 3. Data Stores and Who Writes/Reads

| Store | Location | Written by | Read by |
|-------|----------|------------|---------|
| **PostgreSQL** | Widow (default) or NAS tunnel | RSS collector (per-domain schemas), article/topic/storyline pipelines, AutomationManager, topic workers | All domain APIs, ArticleService, evidence collector (finance.articles) |
| **market_data.db** | data/finance/ | Gold/FRED refresh (FinanceOrchestrator, gold_amalgamator) | Gold routes, get_stored, market-trends |
| **evidence_ledger.db** | data/finance/ | Finance refresh/ingest (orchestrator) | Ledger API, provenance |
| **orchestrator_state.db** | data/orchestrator_state.db | OrchestratorCoordinator, governors | /api/orchestrator/*, dashboard |
| **ChromaDB** | data/finance/chroma/ | EDGAR ingest (FinanceOrchestrator) | Analysis vector search, evidence chunks |
| **api_cache.db** | data/finance/ | FRED/gold fetch | FRED path |

**RSS → articles chain:** `collect_rss_feeds()` (rss_collector) reads `{schema}.rss_feeds`, fetches feeds, inserts into `{schema}.articles` (politics, finance, science_tech). So **finance.articles** is populated by RSS when feeds are registered for the finance domain. The **evidence collector** reads finance.articles via ArticleService(domain="finance") for the “News / RSS” section in analysis. So that chain is connected.

---

## 4. Domains and Capabilities (What’s Built)

| Domain / area | Backend | Frontend | DB / state | Connected? |
|---------------|---------|----------|------------|------------|
| **News aggregation** | Routes: feeds, articles, fetch_articles, collect_now | RSSFeeds, (articles via DomainLayout) | PostgreSQL per-domain | Yes (feeds CRUD, collect_now → RSS collector) |
| **Content analysis** | Topics, dedup, topic queue, LLM activity | Topics, ArticleDeduplication, MLProcessing | PostgreSQL, queue tables | Yes |
| **Storyline management** | CRUD, discovery, consolidation, automation, timeline, watchlist | Storylines, Discover, Consolidation, Timeline, Watchlist | PostgreSQL storylines, storyline_articles | Yes |
| **Intelligence hub** | RAG, analysis, synthesis, briefings, events | Intelligence, Analysis, RAG, Briefings, Events, Tracking | PostgreSQL, RAG/vector | Yes |
| **Finance** | Orchestrator: refresh (gold/FRED/EDGAR), analyze, schedule, tasks, evidence, verification, market-trends/patterns/corporate-announcements (minimal), evidence preview | FinancialAnalysis, FinancialAnalysisResult, EvidenceExplorer, SourceHealth, RefreshSchedule, FactCheckViewer, MarketResearch, MarketPatterns, CorporateAnnouncements | PostgreSQL (finance.articles), SQLite (market, ledger), ChromaDB | Yes (submit analyze → task → poll → result; evidence collector → RSS in prompt) |
| **User management** | Routes under /api/user_management | (Limited UI) | PostgreSQL | Partial (backend present) |
| **System monitoring** | Health, pipeline status, metrics, logs, orchestrator status/dashboard, route_supervisor | Monitoring page (dashboard, pipeline, orchestrator card, etc.) | PostgreSQL metrics, orchestrator_state.db | Yes (orchestrator dashboard API used by Monitoring page) |

---

## 5. End-to-End Chains (Top to Bottom)

### 5.1 Finance analysis (full chain)

1. **User:** Opens `/finance/analysis`, enters query, submits.
2. **Web:** `apiService.submitFinanceAnalysis(...)` → POST `/api/{domain}/finance/analyze` (domain = finance when on finance).
3. **API:** Finance route → `request.app.state.finance_orchestrator.submit_task(analysis, ...)` → returns `task_id`.
4. **Web:** Navigates to `/finance/analysis/:taskId`, polls GET `/api/{domain}/finance/tasks/{id}/status` (phase, progress).
5. **API:** Orchestrator runs refresh (gold/FRED if needed), evidence index, **evidence collector** (RSS from finance.articles), vector search, prompt build, LLM, verification → task complete.
6. **Web:** GET `/api/{domain}/finance/tasks/{id}` returns result with `output.response`, `output.rss_snippets`, `verification`, provenance.
7. **DB:** Gold/FRED from market_data + evidence_ledger; RSS from PostgreSQL `finance.articles`; EDGAR from ChromaDB.

**Verdict:** Chain is connected from **database (PostgreSQL + SQLite + Chroma) → API → web**. Result page can show analysis, evidence, and (if we add it) “News used” from `output.rss_snippets`.

### 5.2 RSS → articles → evidence in analysis

1. **Cron or API:** `collect_rss_feeds()` or POST collect_now.
2. **RSS collector:** Reads `{schema}.rss_feeds`, fetches, inserts into `{schema}.articles` (including `finance.articles`).
3. **Analysis:** Evidence collector calls `ArticleService(domain="finance").get_articles(...)` → reads `finance.articles` → `rss_snippets` in prompt.
**Verdict:** Connected. Finance analysis sees RSS-derived news when finance-domain articles exist.

### 5.3 Orchestrator coordinator (collection loop)

1. **Lifespan:** `OrchestratorCoordinator` started with `get_finance_orchestrator=lambda: app.state.finance_orchestrator`, `collect_rss_feeds_fn=collect_rss_feeds`.
2. **Loop:** Coordinator asks CollectionGovernor → runs RSS or gold refresh → records in orchestrator_state.db.
3. **API:** GET `/api/orchestrator/status`, `/api/orchestrator/dashboard` read from coordinator and state.
4. **Web:** Monitoring page calls `getOrchestratorDashboard()` and shows Orchestrator card.
**Verdict:** Connected.

### 5.4 Storylines and articles (content flow)

1. **RSS** → articles in domain schema.
2. **AutomationManager / topic workers** → topic extraction, ML, etc.
3. **Storyline APIs** → CRUD, discovery, add articles; frontend Storylines, Discover, Consolidation.
**Verdict:** Connected; articles and storylines are in PostgreSQL and used by APIs and UI.

---

## 6. Built but Not (or Weakly) Connected

| Item | Status | Note |
|------|--------|------|
| **Evidence preview API** | Built, not used by UI | GET `/api/{domain}/finance/evidence/preview` exists; no frontend button/page that calls it. Optional “Preview evidence” on finance analysis page would close the loop. |
| **RSS snippets in result** | Backend done, UI optional | `output.rss_snippets` is in task result; FINANCE_TODO suggested showing “News used” on result page — not yet added. |
| **Newsroom Orchestrator v6** | Feature-flagged, stubs | Chief editor / archivist are no-op stubs; event bus exists. Not required for main flows. |
| **User management** | Backend routes exist | Limited or no dedicated frontend; auth not a primary focus in current scope. |
| **DOCS: API version** | Stale | RELEASE_v5.0_STABLE and PROJECT_CAPABILITIES_BRIEF still mention “/api/v4/”; code uses flat `/api/`. Should update docs. |

---

## 7. Not Built / Deferred

- **User preemption:** Queue ordering so user tasks preempt scheduled (deferred).
- **EDGAR checkpointing:** Resume long ingest from checkpoint (deferred).
- **evaluate_ingest:** Automated check that EDGAR chunks are retrievable after ingest (deferred).
- **Periodic evidence collection:** Separate scheduled job that pre-aggregates evidence (optional; we have on-demand in analysis + preview API).
- **Unified “Remaining” doc:** One place that links MIGRATION_TODO Phase 8, FINANCE_TODO deferred, etc. (optional; see CLEANUP_PLAN section 6 for remaining doc tasks).

---

## 8. Development Status Summary

| Dimension | Status |
|-----------|--------|
| **DB → API** | Connected: PostgreSQL (domains, articles, storylines, topics), SQLite (finance, orchestrator), ChromaDB (EDGAR) are read/written by the right services. |
| **API → Web** | Connected: Domain routes and orchestrator routes are called by the frontend (financeAnalysis, monitoring, storylines, articles, etc.) with correct paths (`/api/{domain}/...` or `/api/orchestrator/...`). |
| **End-to-end flows** | Finance analysis, RSS→articles→evidence, orchestrator loop, storylines/content: all wired top to bottom. |
| **Gaps** | Evidence preview and “News used” UI are nice-to-haves; user management and v6 newsroom are partial/optional; docs have minor version/path stale references. |
| **Risks** | No major “built but not connected” for core flows. Ensure `VITE_API_URL` (or proxy) and domain (e.g. finance) are correct when testing from the browser. |

---

## 9. Orchestrators vs independent portions

**Orchestrators are not fully in control of the whole system.** Summary:

- **Under orchestrator control:** (1) **FinanceOrchestrator** — all finance-domain refresh and analysis. (2) **OrchestratorCoordinator** — only the *timing* of RSS collection and gold refresh (it calls `collect_rss_feeds()` and `FinanceOrchestrator.submit_task(refresh, gold)` when the CollectionGovernor says so).
- **Still independent:** **AutomationManager** (its own loop; runs RSS, article processing, ML, topics, storylines, RAG, cleanup on its own schedule), **cron** (RSS, log archive), **StorylineConsolidationService** (30 min timer), **TopicExtractionQueueWorker** and **MLProcessingService** (started from lifespan, run independently). Pipeline and “collect_now” API triggers also fire without going through the coordinator.

So the **data-processing pipeline** (article → ML → topics → storylines → RAG) is not under OrchestratorCoordinator. For full “orchestrators in control,” the coordinator (or a meta-orchestrator) would need to drive or gate AutomationManager phases and cron, or those would need to be migrated into the coordinator’s decision loop. See **CONTROLLER_ARCHITECTURE.md §2.6** for the same breakdown.

---

## 10. Suggested Next Steps (Priority)

1. **Docs:** ~~Update RELEASE_v5.0 and PROJECT_CAPABILITIES_BRIEF to say API uses flat `/api/`.~~ Done; CODING_STYLE_GUIDE now says to retroactively update docs on major changes.
2. **UX:** Add “News used” (from `output.rss_snippets`) on the finance analysis result page.
3. **Optional:** Add “Preview evidence” button that calls GET `/api/{domain}/finance/evidence/preview` and shows the bundle in a modal or panel.
4. **Deferred:** Leave user preemption, EDGAR checkpointing, evaluate_ingest as backlog unless needed for a release.
5. **Optional (orchestrator control):** If the goal is “orchestrators fully in control,” design how OrchestratorCoordinator (or a meta-orchestrator) drives or gates AutomationManager phases and cron, or migrate those into the coordinator’s loop; see CONTROLLER_ARCHITECTURE.md §2.6.

---

*This document is the single high-level scope and development-status reference. For controller/orchestrator detail see CONTROLLER_ARCHITECTURE.md and ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md; for cleanup see CLEANUP_PLAN.md. Historical: _archive/ORCHESTRATOR_DEVELOPMENT_PLAN.md.*
