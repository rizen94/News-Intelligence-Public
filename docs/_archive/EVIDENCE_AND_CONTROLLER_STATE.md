# Evidence Collection System & Controller Structure — Current State

> **Purpose:** Outline the current state of evidence collection and controller/orchestrator architecture so a design plan can be drafted (e.g. for an evidence collector that aggregates RSS, API pulls, and RAG for analysis prompts).  
> **Audience:** Design phase (e.g. Claude) then implementation.  
> **Last updated:** 2025-02-21.

---

## 1. Executive Summary

- **Evidence today** is built **per analysis task** inside the Finance Orchestrator: it comes from (1) **refresh results** (gold, FRED, EDGAR) and (2) **semantic search** over the finance vector store (EDGAR chunks only). RSS and article RAG are **not** fed into finance analysis.
- **No unified evidence collector** exists that runs periodically (or on demand) to compile RSS, API pulls, and RAG into a single evidence set for prompts.
- **Controllers** are three conceptual areas: **Finance** (FinanceOrchestrator), **Data Processing** (AutomationManager, RSS, ML, topics, storylines, RAG), and **Review & Cleanup** (consolidation, cleanup, dedup). They run in parallel with no single coordinator; API paths use flat `/api/...` (no path versioning).

---

## 2. Evidence Collection — Current State

### 2.1 What “Evidence” Means in This Codebase

- **Evidence index:** A list of verifiable facts (e.g. gold price on date X, FRED value, EDGAR chunk count) each with a `ref_id` (e.g. REF-001), source, date, value, unit. Used in the analysis prompt and for post-generation fact-checking.
- **Evidence chunks:** Text excerpts from semantic (vector) search, included in the prompt as “Relevant excerpts.”
- **Evidence ledger:** A separate audit store (SQLite) that records *provenance* of fetches (which source was called, success/failure, timestamps). It is not the same as the in-memory evidence index used in the prompt.

### 2.2 Where Evidence Comes From (Finance Analysis Only)

When a user (or schedule) triggers a **finance analysis** (`POST /{domain}/finance/analyze`), the Finance Orchestrator:

1. **Plans** — topic (e.g. `gold`), query, `n_chunks` for vector search.
2. **Refresh (if topic is gold/all/fred):**
   - **Gold:** `gold_amalgamator.fetch_all(start, end)` → FreeGoldAPI + FRED IQ12260 → results stored in `task.context.fetched_data["refresh_results"]["gold"]["results"]` (and in market_data_store + evidence_ledger).
   - **FRED:** On-demand or when topic is fred; observations in `refresh_results["fred"]`.
   - **EDGAR:** Ingest (10-K sections) populates ChromaDB and adds a summary entry to the evidence index; not re-fetched on every analysis.
3. **Fallback:** If refresh returns no gold data, the orchestrator tries `gold_amalgamator.get_stored()` and merges that into `refresh_results` so the evidence index can still be built from previously stored data.
4. **Build evidence index** — `_build_evidence_index(task)` reads `task.context.fetched_data["refresh_results"]` and produces `task.context.evidence_index` (list of `EvidenceIndexEntry`).
5. **Vector retrieve** — Query is embedded; finance vector store (ChromaDB) is queried for top `n_chunks`; results go to `task.context.evidence_chunks`.
6. **Stats** — Optional stats (e.g. latest_gold_usd, gold_price_change_pct) are computed from the evidence index.
7. **Prompt** — `_build_analysis_prompt()` builds the user prompt with: Query, Evidence (REF-ids), Computed stats, Relevant excerpts (from vector store), then “Provide a concise analysis.”
8. **LLM** — Single serialized call; output is then verified against the evidence index (REF-ids, dollar amounts, dates).

So **current evidence sources for the finance analysis prompt are:**

| Source            | When / How it gets into the prompt                          |
|-------------------|--------------------------------------------------------------|
| Gold (API)        | Refresh → `refresh_results["gold"]` → evidence index          |
| FRED              | Refresh (topic=fred) → `refresh_results["fred"]` → index     |
| EDGAR             | Ingest → ChromaDB; refresh/ingest summary → index; chunks from vector search |
| Stored gold       | Fallback when refresh returns no data → same shape as gold   |
| Vector store text | Semantic search over ChromaDB (EDGAR chunks only) → “Relevant excerpts” |

**Not currently used for finance analysis evidence:**

- RSS feeds or collected articles (they live in PostgreSQL per domain; used for topics, storylines, intelligence hub, not for finance prompt).
- Any “article RAG” or intelligence-hub RAG (those services exist but are not wired into the finance orchestrator’s evidence assembly).

### 2.3 Data Stores Involved in Evidence

| Store              | Path / location                    | Role |
|--------------------|------------------------------------|------|
| Market data        | `data/finance/market_data.db`      | Time series: gold, FRED. Used by gold_amalgamator and refresh. |
| Vector store       | `data/finance/chroma/`             | ChromaDB; EDGAR chunks only. Queried for “evidence_chunks” in analysis. |
| Evidence ledger    | `data/finance/evidence_ledger.db`  | Provenance: each fetch (gold, FRED, EDGAR) recorded with report_id, source_type, source_id, evidence_data, timestamps. |
| API cache          | `data/finance/api_cache.db`        | HTTP response cache for external APIs. |

Evidence index and evidence_chunks are **in-memory per task**; they are not persisted as a single “evidence collection” table. The ledger persists *that* a fetch happened and its outcome, not the assembled index used in the prompt.

### 2.4 Key Code Locations (Evidence)

| Concern                    | File(s) |
|---------------------------|---------|
| Build evidence index       | `api/domains/finance/orchestrator.py` — `_build_evidence_index()`, `_execute_analysis()` |
| Refresh (gold/FRED/EDGAR)  | `api/domains/finance/orchestrator.py` — `_plan_refresh()`, `_execute_refresh()` |
| Gold fetch + store         | `api/domains/finance/gold_amalgamator.py` — `fetch_all()`, `get_stored()` |
| Evidence ledger            | `api/domains/finance/data/evidence_ledger.py` — `record()`, list/get helpers |
| Analysis prompt            | `api/domains/finance/orchestrator.py` — `_build_analysis_prompt()` |
| Vector store query         | `api/domains/finance/embedding.py`, `api/domains/finance/data/vector_store.py` |

### 2.5 Evidence Collector (Implemented)

An **evidence collector** now aggregates RSS (finance-domain articles), optional API summary (gold/FRED from store), and optional RAG (finance vector store) into a single bundle:

- **Module:** `api/domains/finance/evidence_collector.py` — `collect(...)` returns `{ rss_snippets, api_summary, rag_chunks }`.
- **Usage in analysis:** The finance orchestrator calls it during `_execute_analysis`; RSS is in `task.context.rss_snippets` and the prompt includes "## News / RSS (recent finance articles)".
- **API:** `GET /api/{domain}/finance/evidence/preview` — on-demand preview (query, topic, hours, max_rss, include_rss, include_api_summary, include_rag).

---

## 3. Controller Structure — Current State

### 3.1 Three Conceptual Controllers (from CONTROLLER_ARCHITECTURE.md)

| Controller                    | Scope                      | Primary role |
|------------------------------|----------------------------|--------------|
| **Finance Controller**       | Finance domain only        | Gold, EDGAR, FRED refresh; analysis; scheduled ingest |
| **Data Processing Controller** | News/content pipelines   | RSS, article processing, ML, topics, storylines, RAG |
| **Review & Cleanup Controller** | Maintenance               | Consolidation, dedup, cleanup, log archive |

### 3.2 Finance Controller (Implemented)

- **Component:** `FinanceOrchestrator` in `api/domains/finance/orchestrator.py`.
- **Started in:** `main_v4.py` lifespan: constructed with source_loader, market_data_store, vector_store, evidence_ledger, embedding_module, stats_module, llm_wrapper; then `start_scheduler()` and `start_queue_worker()`.
- **Stopped in:** lifespan shutdown calls `finance_orchestrator.stop_scheduler()` (which also stops the queue worker).
- **Schedule:** Driven by `api/config/finance_schedule.yaml` (e.g. gold_refresh 24h, edgar_ingest 168h). Scheduler loop runs ~60s; checks due tasks and submits low-priority tasks.
- **Queue worker:** Processes queued tasks (e.g. analysis with `wait=false`): picks by priority then FIFO, runs `run_task(task_id)`.
- **Control surface:**
  - Internal: `submit_task()`, `run_task()`, `start_scheduler()` / `stop_scheduler()`, `start_queue_worker()` / `stop_queue_worker()`, `get_schedule_status()`.
  - API (flat paths): `POST /{domain}/finance/gold/fetch`, `POST /{domain}/finance/edgar/ingest`, `POST /{domain}/finance/analyze`, `POST /{domain}/finance/fetch-fred`, `GET /{domain}/finance/schedule`, `GET /{domain}/finance/tasks`, `GET /{domain}/finance/tasks/{id}`, `GET /{domain}/finance/evidence` (and others — see finance routes).

### 3.3 Data Processing Controller (AutomationManager + Others)

- **Components:** AutomationManager (`api/services/automation_manager.py`), RSS collector (`api/collectors/rss_collector.py`), topic queue workers, ML processing, storyline consolidation (separate thread), etc.
- **Started in:** `main_v4.py`: AutomationManager started in a background thread; topic extraction queue workers started in another background thread.
- **Behavior:** AutomationManager polls on an interval (e.g. 10s); runs phases such as rss_processing, article_processing, ml_processing, topic_clustering, storyline_processing, rag_enhancement, etc. RSS is also triggered by cron (e.g. 6 AM, 6 PM) and by API (`collect_now`, `fetch_articles`, pipeline `run_all`).
- **Overlap:** Multiple entry points for RSS and topic clustering (AutomationManager, cron, pipeline route, manual API). No single “evidence collector” that feeds finance.

### 3.4 Review & Cleanup Controller

- **Components:** StorylineConsolidationService (e.g. 30 min interval from main_v4), AutomationManager’s data_cleanup (e.g. 24h), cache_cleanup, cron log archive, dedup APIs.
- **Note:** AutomatedCleanupSystem (standalone script) is not started from main_v4.

### 3.5 API and Path Conventions

- **API base:** Flat paths are used; no version in path (e.g. `/api/system_monitoring/health`, `/api/{domain}/finance/analyze`). Previous `/api/v4/...` references in docs have been migrated to `/api/...` in code.

### 3.6 Key File Locations (Controllers)

| Component              | File(s) |
|------------------------|---------|
| Finance orchestrator   | `api/domains/finance/orchestrator.py` |
| Finance schedule      | `api/config/finance_schedule.yaml` |
| Finance routes        | `api/domains/finance/routes/finance.py` |
| AutomationManager     | `api/services/automation_manager.py` |
| RSS collector         | `api/collectors/rss_collector.py` |
| Pipeline trigger       | `api/domains/system_monitoring/routes/system_monitoring.py` (e.g. execute_pipeline_orchestration) |
| Storyline consolidation | `api/services/storyline_consolidation_service.py` |
| Topic queue worker    | `api/domains/content_analysis/.../topic_extraction_queue_worker.py` |
| App lifespan          | `api/main_v4.py` |

---

## 4. Document References

- **Controller architecture (proposal):** `docs/CONTROLLER_ARCHITECTURE.md`
- **Finance pipeline (stores and flow):** `docs/FINANCE_PIPELINE.md`
- **Finance orchestrator build (phases, data structures):** `docs/FINANCE_ORCHESTRATOR_BUILD.md`
- **Finance TODO (evidence explorer, citations):** `docs/FINANCE_TODO.md`

---

## 5. Suggested Design Directions (For a Follow-On Design Plan)

- **Evidence collector:** Define a component that runs periodically (or when the orchestrator deems necessary), pulling from: (1) RSS / finance-domain articles, (2) API pulls (gold, FRED, and any other designated series), (3) RAG results (finance vector store + optionally article/intelligence RAG). Output: a single “evidence collection” (or equivalent) that the analysis pipeline can consume so the prompt includes RSS-derived content and RAG in addition to current refresh + EDGAR chunks.
- **Placement:** Decide whether the evidence collector lives under the Finance Controller, the Data Processing Controller, or a shared service used by both; and how it is triggered (schedule vs on-demand vs both).
- **Storage:** Decide whether to persist “evidence collections” (e.g. by time window or by topic) or keep assembling per request with a cache; and how that interacts with the existing evidence ledger and market_data_store.
- **Controller coordination:** Optional: document how the evidence collector interacts with AutomationManager (e.g. after RSS run) and with FinanceOrchestrator (e.g. before or during analysis), without duplicating CONTROLLER_ARCHITECTURE.md.

---

*This document summarizes the current state as of 2025-02-21 for use in a design plan and subsequent implementation.*
