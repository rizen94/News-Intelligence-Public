# News Intelligence System — Project Overview

**Purpose:** High-level outline of what the system is and how it works. Suitable for stakeholders, onboarding, and presentations.  
**Version:** 8.0 | **Last updated:** March 2026

---

## 1. What It Is

News Intelligence is an **AI-powered news aggregation and analysis platform** that:

- **Collects** news from RSS feeds (and optional document sources).
- **Processes** content with local ML (summarization, entities, topics, sentiment, quality).
- **Builds intelligence** over time: storylines, entity profiles, tracked events, claims, and cross-domain patterns.
- **Delivers** editorial-style outputs: daily briefings, storyline narratives, entity dossiers, and fact-checked insights.

All LLM processing runs **locally via Ollama** (no cloud LLM by default). The system is designed to run on a small infrastructure footprint: Primary (API + frontend + ML), Widow (PostgreSQL + RSS worker), and optional NAS for storage.

---

## 2. How It Works (End-to-End)

### 2.1 Data flow (intelligence cascade)

1. **Ingestion** — RSS collector (and document collector) writes articles into per-domain PostgreSQL schemas (`politics`, `finance`, `science_tech`). Full-text enrichment (e.g. trafilatura) fills content when feeds provide only excerpts.
2. **ML processing** — Summarization, key points, sentiment, and quality scoring are written into `articles.ml_data` and related columns. Content is never overwritten; pipelines merge/accumulate.
3. **Entity and topic extraction** — People, organizations, and topics are extracted and stored in `article_entities`, `article_keywords`, and topic clusters. Entity resolution maps mentions to canonical entities and aliases.
4. **Context creation** — A context processor syncs article content into the shared `intelligence.contexts` table, preserving domain and metadata. Contexts are the bridge between domain content and cross-domain intelligence.
5. **Intelligence extraction** — Claims, tracked events, entity profiles, and pattern discovery run on contexts. Results live in the `intelligence` schema (claims, tracked_events, entity_profiles, entity_dossiers, etc.).
6. **Storylines and editorial** — Storylines group articles and contexts; editorial documents and briefings are generated from storylines, events, and entity dossiers. Fact verification and synthesis consume claims and multiple sources.
7. **Output** — The web UI and API expose dashboards, storylines, entity dossiers, events, briefings, and monitoring. Finance has a dedicated orchestrator for market data, evidence, and analysis.

### 2.2 Pipeline and automation

- **Collection cycle (v8)** — Runs on an interval (e.g. every 2 hours): RSS fetch, enrichment drain, document collection, and document processing drain. This is the only phase that loads new raw data.
- **Analysis pipeline** — Between collection cycles, ordered steps run: context sync → entity extraction → claim extraction → event tracking → storyline discovery → synthesis → editorial generation → data cleanup. Time budgets and re-enqueue caps prevent any step from starving others.
- **Governors** — Collection and processing governors decide when to run collection and which analysis phase to run next, using importance, watchlist, and backlog.
- **Finance** — The Finance Orchestrator runs on its own schedule (market data refresh, evidence ingest, analysis tasks) and uses SQLite + ChromaDB in addition to PostgreSQL.

### 2.3 Three-machine layout (typical)

| Machine   | Role |
|----------|------|
| **Primary** | API (FastAPI), frontend (React), Ollama, Redis. Runs automation coordinator and pipeline. |
| **Widow**   | PostgreSQL (all content + intelligence schemas), RSS worker, DB backups. |
| **NAS**     | Optional storage/archives; no application or database by default. |

---

## 3. Core Concepts

- **Domains** — Content is partitioned into domains: `politics`, `finance`, `science-tech`. Each domain has its own schema (e.g. `politics.articles`, `finance.storylines`) and shared intelligence in `intelligence.*`.
- **Storylines** — Evolving clusters of articles and contexts around a theme. They have editorial narratives, timelines, and optional automation.
- **Entities** — People and organizations are resolved to canonical entities with aliases; entity profiles and dossiers aggregate claims, positions, and relationships.
- **Tracked events** — Time-bounded happenings with chronicles and editorial briefings.
- **Editorial documents** — Primary output: structured narratives (lede, developments, analysis, outlook) for storylines and events, plus daily/weekly briefings.

---

## 4. Design principles (invariants)

1. **Content is king** — If an article was processed, its key facts are derivable from stored content and ML data.
2. **Intelligence accumulates** — Each stage enriches; nothing reduces content to counts only.
3. **Narratives over metrics** — User-facing APIs and UI lead with stories and editorial output, not raw statistics.
4. **Editorial documents are primary** — Storyline and event value is expressed in editorial_document and editorial_briefing.

See [CORE_ARCHITECTURE_PRINCIPLES.md](CORE_ARCHITECTURE_PRINCIPLES.md) and [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) for detail.

---

## 5. Capabilities snapshot (technical)

| Layer | Technology |
|-------|------------|
| Backend | Python 3, FastAPI, uvicorn |
| Frontend | React 18, TypeScript, Vite, Material-UI v5 |
| Database | PostgreSQL (per-domain schemas + `intelligence`); single access path `shared.database.connection` |
| Cache | Redis (optional Docker) |
| LLM | Ollama — local models (e.g. Llama 3.1 8B primary, Mistral 7B secondary, embeddings) |

**Domains:** `politics`, `finance`, `science-tech` (URL key `science-tech`, schema `science_tech`) with shared patterns: articles, storylines, topics, rss_feeds, events, entity pipeline. **Cross-domain:** `intelligence.*` (contexts, claims, tracked events, dossiers, documents, patterns). **Global:** watchlist, system_monitoring, health.

**Major capabilities:** RSS + document ingestion; ML enrichment on `articles.ml_data`; entity resolution and merges; storyline CRUD, automation, RAG discovery, editorial documents; intelligence hub (RAG, synthesis, briefings, fact verification); Finance orchestrator (market data, evidence, ChromaDB); in-process `AutomationManager` driving phased analysis (v8 collect-then-analyze). Full feature lists and automation intervals are preserved in [_archive/consolidated/PROJECT_CAPABILITIES_BRIEF.md](_archive/consolidated/PROJECT_CAPABILITIES_BRIEF.md).

---

## 6. Scope and development status

- **Current line:** v8 collect-then-analyze (ordered analysis pipeline after collection cycles); flat API paths `/api/...` (no version prefix).
- **Stack map:** Web (React `/:domain/*`) → FastAPI (`api/main.py`) → PostgreSQL (+ Finance SQLite/Chroma, optional Redis). See [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) for route/service map and [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) for hosts and ops.
- **Connectivity:** News aggregation, content analysis, storylines, intelligence hub, entity resolution, fact verification, PDF/document processing, finance, and system monitoring are wired DB → API → web; user-management UI is partial.

Detailed matrices (domain × layer), v6 quality-first notes, and gap discussion remain in [_archive/consolidated/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md](_archive/consolidated/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md).

---

## 7. Where to go next

- **Code navigation:** [CODEBASE_MAP.md](CODEBASE_MAP.md), [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md), [CODE_REVIEW_AND_RUN_CAVEATS.md](CODE_REVIEW_AND_RUN_CAVEATS.md)
- **Setup and runtime:** [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md)
- **Operations:** [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md)
- **Database:** [DATABASE.md](DATABASE.md) (schema and data I/O)
- **API:** [API_REFERENCE.md](API_REFERENCE.md) (endpoints and integrations)
- **Security (ops + API):** [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)
- **Documentation index:** [DOCS_INDEX.md](DOCS_INDEX.md)

Planning and development history are in [archive/planning/](archive/planning/) for historic reference.
