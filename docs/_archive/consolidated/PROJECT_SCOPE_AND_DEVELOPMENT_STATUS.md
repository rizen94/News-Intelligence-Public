> **Status:** Superseded — canonical summary: [PROJECT_OVERVIEW.md](../../PROJECT_OVERVIEW.md) §5–6; full detail preserved here.

# News Intelligence — High-Level Scope & Development Status

> **Purpose:** Full scope view of what is built, how it connects, and where gaps or disconnects are. Use this to assess "database → API → web" and plan next steps.  
> **Audience:** Product/tech lead, onboarding.  
> **Last updated:** 2026-03-06.

---

## 1. What We Have: Version and Naming

- **Product:** News Intelligence — AI-powered news aggregation, analysis, and intelligence.
- **Backend:** FastAPI app in `api/main.py`; **version string is v8.0** — "News Intelligence System v8.0".
- **API:** **Flat paths** — `/api/...` (no version in path).
- **v8 Collect-then-Analyze:** Current. Collection cycle every 2h; pipeline-ordered analysis (Foundation → Extraction → Intelligence → Output); full-history data scopes; storyline discovery dedup and automation; document/topic/dossier bridges.
- **v6 Quality-First Upgrade:** Completed. Intelligence-first architecture: entity resolution, editorial documents, fact verification, PDF processing, content synthesis, event tracking, entity dossiers.

---

## 2. Architecture: Three Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│  WEB (React + MUI + Vite)                                               │
│  MainLayout → /:domain/dashboard, articles, storylines, finance/...     │
│  Discover / Investigate / Monitor — entity profiles, events, documents  │
│  API calls via getApi() → baseURL (env/proxy) + /api/{domain}/...      │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  API (FastAPI, main.py)                                              │
│  Domains: news_aggregation, content_analysis, storyline_management,     │
│           intelligence_hub, finance, user_management, system_monitoring │
│  + OrchestratorCoordinator, AutomationManager, FinanceOrchestrator     │
│  + Entity Resolution, Fact Verification, Content Synthesis, PDF Parser │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌──────────────────┐    ┌────────────────────────────┐    ┌──────────────────┐
│  PostgreSQL       │    │  SQLite (finance +         │    │  Redis (optional)│
│  (Widow default)  │    │  orchestrator state)       │    │  Cache/sessions  │
│  schemas:         │    │  market_data, evidence_    │    └──────────────────┘
│  politics,        │    │  ledger, orchestrator_     │
│  finance,         │    │  state.db, api_cache       │
│  science_tech,    │    └────────────────────────────┘
│  public,          │
│  intelligence     │ ← entity_profiles, contexts, claims, events,
│                   │   dossiers, positions, documents, patterns
└──────────────────┘
```

- **Web:** Single React SPA. Routes are domain-scoped under `/:domain/*`. Investigate section for entities, events, documents, narrative threads. Monitor section for system health and orchestrator status.
- **API:** One FastAPI app. Domain routers mounted with prefix `/api`. Context-centric intelligence routes under `/api/entities/*`, `/api/synthesis/*`, `/api/verification/*`, `/api/tracked_events/*`.
- **Data:** PostgreSQL holds per-domain content (articles, storylines, topics, rss_feeds) and the `intelligence` schema (entity_profiles, contexts, claims, tracked_events, entity_dossiers, entity_positions, processed_documents, pattern_discoveries, narrative_threads). Finance also uses SQLite + ChromaDB.

---

## 3. Data Stores and Who Writes/Reads

| Store | Location | Written by | Read by |
|-------|----------|------------|---------|
| **PostgreSQL** | Widow (default) or NAS tunnel | RSS collector (per-domain schemas), article/topic/storyline pipelines, AutomationManager, entity resolution, fact verification, document processing | All domain APIs, ArticleService, evidence collector, content synthesis, editorial generation |
| **intelligence schema** | PostgreSQL (cross-domain) | Entity sync, context processor, claim extraction, event chronicle builder, dossier compiler, position tracker, document processing, pattern recognition | Context-centric APIs, synthesis service, verification service, editorial document service |
| **market_data.db** | data/finance/ | Gold/FRED refresh (FinanceOrchestrator) | Gold routes, market-trends |
| **evidence_ledger.db** | data/finance/ | Finance refresh/ingest | Ledger API, provenance |
| **orchestrator_state.db** | data/orchestrator_state.db | OrchestratorCoordinator, governors | /api/orchestrator/*, dashboard |
| **ChromaDB** | data/finance/chroma/ | EDGAR ingest | Analysis vector search |

---

## 4. Domains and Capabilities (What's Built)

| Domain / area | Backend | Frontend | DB / state | Connected? |
|---------------|---------|----------|------------|------------|
| **News aggregation** | Routes: feeds, articles, fetch_articles, collect_now | RSSFeeds, articles via MainLayout | PostgreSQL per-domain | Yes |
| **Content analysis** | Topics, dedup, topic queue, LLM activity, quality scoring | Topics, ArticleDeduplication, MLProcessing | PostgreSQL, queue tables | Yes |
| **Storyline management** | CRUD, discovery, consolidation, automation, timeline, watchlist, editorial_document | Storylines, Discover, Consolidation, Timeline, Watchlist | PostgreSQL storylines | Yes |
| **Intelligence hub** | RAG, analysis, synthesis, briefings, events, entity profiles, dossiers, claims, contexts, documents, narrative threads, content synthesis | Intelligence, Analysis, RAG, Briefings, Events, Investigate (entities, events, documents, threads) | PostgreSQL + intelligence schema | Yes |
| **Entity resolution** | Disambiguation (title-strip, last-name, fuzzy), alias population, merge candidates, auto-merge, cross-domain linking | Canonical entities tab: browse, search, merge, resolve | entity_canonical + intelligence.entity_relationships | Yes |
| **Fact verification** | Multi-source corroboration, contradiction detection, source reliability (4-tier), completeness assessment | API endpoints; integrates with editorial pipeline | extracted_claims, articles, contexts | Yes |
| **PDF processing** | Download + pdfplumber extraction, section identification, entity/findings extraction, batch processing | Processed documents page | intelligence.processed_documents | Yes |
| **Content synthesis** | Domain/storyline/event/entity scoped aggregation, LLM-ready text rendering | API endpoints consumed by editorial services | Cross-schema aggregation | Yes |
| **Finance** | Orchestrator: refresh, analyze, evidence, market-trends/patterns/corporate-announcements | FinancialAnalysis, EvidenceExplorer, MarketResearch, CommodityDashboard | PostgreSQL + SQLite + ChromaDB | Yes |
| **User management** | Routes under /api/user_management | (Limited UI) | PostgreSQL | Partial |
| **System monitoring** | Health, pipeline, metrics, logs, orchestrator dashboard, realtime | Monitoring page, Monitor page | PostgreSQL, orchestrator_state.db | Yes |

---

## 5. v6 Quality-First Upgrade — Completed Features

### 5.1 Intelligence Pipeline (Audit: 34 violations remediated)

The full intelligence cascade is now wired end-to-end:

```
article → content → ml_data → entities → contexts → claims/events → storylines
    ↓          ↓          ↓          ↓           ↓            ↓            ↓
  stored    summary    canonical   profiles   extracted    tracked    editorial_document
  content   key_pts    aliases     sections   claims       events     editorial_briefing
            entities   positions   mentions   patterns    chronicles
```

Key changes:
- RSS collector captures full `content:encoded` body
- ML enrichments (`ml_data`) are consumed by all downstream phases
- Entity extraction stores contextual excerpts alongside entity names
- Storyline/basic summary phases seed `editorial_document` when empty
- RAG analysis writes back to `editorial_document`
- Briefings use editorial-first ordering (ledes → headlines → storylines → events → metrics)
- LLM `generate_briefing_lead` produces narrative-quality leads
- All API endpoints return editorial_document/editorial_briefing fields

### 5.2 Entity Resolution (T1.2)

- **Disambiguation:** Title stripping ("President Biden" → "Joe Biden"), last-name fallback, bigram fuzzy matching
- **Alias population:** Batch collects article mention variants into entity_canonical.aliases
- **Merge detection:** Finds duplicate entities via shared names, substring matching, similarity scoring
- **Auto-merge:** Automated merging above configurable confidence threshold
- **Cross-domain linking:** Finds same entity across politics/finance/science-tech schemas
- **Orchestrator integration:** `entity_organizer` phase runs full resolution batch
- **API:** `/api/entities/resolve`, `/api/entities/canonical`, `/api/entities/merge_candidates`, `/api/entities/merge`, `/api/entities/auto_merge`, `/api/entities/cross_domain_link`, `/api/entities/run_resolution_batch`

### 5.3 Entity Positions & Dossiers (T2.2)

- **Position tracker:** LLM extraction of policy stances, votes, statements from articles; heuristic fallback
- **Pattern linking:** Dossier compilation pulls pattern_discoveries into entity_dossiers.patterns
- **Dossier enrichment:** Positions and patterns included alongside chronicle_data and relationships

### 5.4 Content Synthesis Service

Centralized aggregation of all intelligence phases into unified context blocks:
- **Domain scope:** Articles + ML enrichments + storylines + events + entities + claims + patterns
- **Storyline scope:** Articles with full enrichments, entities, claims from linked contexts
- **Event scope:** Metadata, chronicles, editorial briefing
- **Entity scope:** Dossier, positions, relationships, recent articles
- **LLM rendering:** `render_synthesis_for_llm()` converts synthesis to structured text for prompts
- **API:** `/api/synthesis/domain`, `/api/synthesis/storyline/{id}`, `/api/synthesis/event/{id}`, `/api/synthesis/entity/{id}`

### 5.5 PDF Document Processing (T3.2)

- **Download:** Fetches PDFs from source_url with size/type validation
- **Extraction:** pdfplumber for text, tables, and page-level content
- **Section identification:** Heading detection (numbered, titled, all-caps patterns)
- **Entity extraction:** LLM-based with heuristic fallback (capitalized phrases)
- **Key findings:** LLM extraction of findings, conclusions, recommendations
- **Batch processing:** Processes all unprocessed documents automatically
- **API:** POST `/api/processed_documents/{id}/process`, POST `/api/processed_documents/batch_process`

### 5.6 Fact Verification (T3.3)

- **Multi-source corroboration:** Full-text search across articles; counts distinct sources confirming a claim
- **Contradiction detection:** Groups claims by subject; checks for opposing predicates, numeric divergence, direct negation
- **Source reliability:** 4-tier scoring (wire services → major papers → broadcast → other)
- **Completeness assessment:** Source diversity, temporal coverage, sentiment spread, gap identification
- **Full verification pipeline:** Corroboration + contradiction + reliability in one call
- **API:** `/api/verification/claim/{id}`, `/api/verification/corroborate`, `/api/verification/contradictions`, `/api/verification/completeness`, `/api/verification/batch`, `/api/verification/source_reliability`

---

## 6. End-to-End Chains (Top to Bottom)

### 6.1 Intelligence cascade (primary chain)

1. **RSS/PDF:** RSS collector fetches feeds → articles per domain. Document processor downloads PDFs → extracted sections/findings.
2. **ML enrichment:** AutomationManager runs entity extraction, topic clustering, sentiment, quality scoring, summarization. Results stored in `ml_data`, `article_entities`, `entity_canonical`.
3. **Entity resolution:** Organizer phase merges duplicates, populates aliases, links cross-domain entities.
4. **Context-centric:** Contexts created from articles; claims extracted; patterns discovered; entity profiles built.
5. **Storyline management:** CRUD, article linking, editorial_document generation/seeding.
6. **Event tracking:** Tracked events with chronicle builder; editorial_briefing generation.
7. **Fact verification:** Claims verified against multiple sources; contradictions detected.
8. **Content synthesis:** Aggregates all enrichments for editorial or briefing generation.
9. **Briefings:** Editorial-first daily briefings with optional LLM lead paragraph.

### 6.2 Finance analysis (full chain)

1. User submits query → FinanceOrchestrator → refresh + evidence + LLM → result with provenance.
2. Evidence collector reads `finance.articles` via ArticleService for RSS-derived context.

### 6.3 Orchestrator coordination

1. OrchestratorCoordinator drives collection timing (RSS, gold refresh).
2. AutomationManager runs processing pipeline (phases 1–2, entity organizer with resolution batch).
3. Scheduled dossier compilation and event chronicle updates from coordinator.

---

## 7. Built but Not (or Weakly) Connected

| Item | Status | Note |
|------|--------|------|
| **Evidence preview API** | Built, not used by UI | GET `/api/{domain}/finance/evidence/preview` exists; no frontend button. |
| **User management** | Backend routes exist | Limited or no dedicated frontend; auth not a primary focus. |
| **Newsroom Orchestrator v6** | Feature-flagged, stubs | Chief editor / archivist are no-op stubs; event bus exists. Not required for main flows. |

---

## 8. Not Built / Deferred

- **Expanded election tracker:** Maps, live tracking, politician profiles (politics domain) — not scoped.
- **User preemption:** Queue ordering so user tasks preempt scheduled (deferred).
- **EDGAR checkpointing:** Resume long ingest from checkpoint (deferred).
- **Full GPU PDF OCR:** Current PDF parsing handles text-based PDFs; image-heavy/scanned PDFs would need OCR (deferred).
- **Multi-tenant, multi-language, advanced security** — on roadmap, not implemented.

---

## 9. Development Status Summary

| Dimension | Status |
|-----------|--------|
| **DB → API** | Connected: PostgreSQL (domain schemas + intelligence schema), SQLite (finance, orchestrator), ChromaDB (EDGAR) are read/written by the right services. |
| **API → Web** | Connected: Domain routes, context-centric routes, entity resolution, verification, synthesis all callable from frontend. |
| **End-to-end flows** | Finance analysis, RSS→articles→ML→entities→storylines→editorial, orchestrator loop, entity resolution, fact verification, PDF processing: all wired. |
| **Intelligence cascade** | Complete: article content flows through ML enrichment → entity resolution → context/claims → event tracking → editorial documents → briefings. |
| **v6 TODO** | 55/61 items checked; 6 remaining are style-checklist reminders (ongoing conventions). All feature work complete. |
| **Gaps** | Evidence preview UI, user management UI, and v6 newsroom stubs are partial/optional. |

---

## 10. Suggested Next Steps (Priority)

1. **UX:** Expose fact verification and content synthesis in the frontend (verification badges on claims, synthesis panels on storylines/events).
2. **Data sources:** Configure additional RSS feeds and document sources (government PDFs, think tank reports) to exercise the PDF pipeline.
3. **Entity enrichment:** Populate entity positions for key political/financial entities to demonstrate the position tracker.
4. **Editorial product:** Build the "Today's Report" page that consumes synthesis API and editorial documents for a reader-facing daily briefing.
5. **Deferred:** Leave GPU OCR, multi-tenant, EDGAR checkpointing as backlog unless needed for a release.

---

*This document is the single high-level scope and development-status reference. For architectural principles see CORE_ARCHITECTURE_PRINCIPLES.md; for the v6 upgrade plan see V6_QUALITY_FIRST_UPGRADE_PLAN.md and V6_QUALITY_FIRST_TODO.md; for controller detail see CONTROLLER_ARCHITECTURE.md.*
