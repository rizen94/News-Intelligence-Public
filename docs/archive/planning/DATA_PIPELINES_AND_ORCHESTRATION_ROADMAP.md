# Data Pipelines and Orchestration — Full Roadmap

**Purpose:** Single reference for orchestrators, governors, collection/processing/routing flows, and the full API stack. Use this as the roadmap for how data moves through the system and how it is controlled.

**See also:** [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md) (production timings), [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md) (context-centric model), [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) (ops and troubleshooting).

---

## 1. High-level architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                     ORCHESTRATOR COORDINATOR                      │
                    │  Loop (60s): assess → plan (governors) → execute → learn → sleep  │
                    └───────────────┬─────────────────────────────┬────────────────────┘
                                    │                             │
              ┌─────────────────────▼─────────────────┐   ┌───────▼──────────────────────┐
              │      COLLECTION GOVERNOR              │   │    PROCESSING GOVERNOR        │
              │  recommend_fetch() → RSS / Finance     │   │  recommend_next_processing()  │
              │  record_fetch_result()                 │   │  → request_phase(automation) │
              └─────────────────────┬─────────────────┘   └───────┬──────────────────────┘
                                    │                             │
              ┌─────────────────────▼───────────┐     ┌──────────▼──────────────────────┐
              │  RSS: collect_rss_feeds()         │     │   AUTOMATION MANAGER              │
              │  Finance: FinanceOrchestrator    │     │   Scheduler (5s) + workers (8)   │
              │  .submit_task(refresh/analysis)  │     │   Phases: context_sync, claims,   │
              └─────────────────────────────────┘     │   event_tracking, ML, storylines,│
                                                        │   RAG, entity profiles, etc.    │
                                                        └──────────────────────────────────┘
```

- **Collection** is driven by the Orchestrator Coordinator using the Collection Governor (when to fetch RSS vs gold/silver/platinum/edgar).
- **Processing** is driven by the same coordinator using the Processing Governor (which phase to run next) and by the **Automation Manager** on its own schedule (intervals per phase).
- **Resource Governor** and **Learning Governor** feed into decisions (budgets, pattern analysis).

---

## 2. Orchestrators

### 2.1 Orchestrator Coordinator

| Aspect | Detail |
|--------|--------|
| **Role** | Central loop: assess state → plan (collection + processing) → execute one collection and optionally one processing phase → learn (decision log) → sleep. |
| **Location** | `api/services/orchestrator_coordinator.py` |
| **Started** | On API startup (`main_v4.py` lifespan); runs in main asyncio loop. |
| **Loop interval** | 60 seconds (`orchestrator_governance.yaml` → `orchestrator.loop_interval_seconds`) |
| **Collection** | Calls `CollectionGovernor.recommend_fetch(last_collection_times)`. If a source is due, runs RSS (`collect_rss_feeds`) or Finance (`FinanceOrchestrator.submit_task(refresh)`). Records result and appends decision log. |
| **Processing** | Calls `ProcessingGovernor.recommend_next_processing(state, resource_ok)`. If a phase is due, calls `AutomationManager.request_phase(phase, domain?, storyline_id?)`. One phase request per cycle. |
| **State** | `orchestrator_state`: current_cycle, last_collection_times, last_processing_times, last_finance_interest_analysis, config_overrides, decision_log, performance_metrics, resource_usage. |
| **API** | Status/metrics/decision_log/learning/dashboard/manual_override: `GET/POST /api/orchestrator/*` (system_monitoring routes). |

### 2.2 Automation Manager

| Aspect | Detail |
|--------|--------|
| **Role** | Scheduled and continuous batch processing: context sync, claim extraction, event tracking, ML, topic clustering, storylines, RAG, entity profiles, event extraction, etc. Re-enqueues phases when work remains (continuous until empty). |
| **Location** | `api/services/automation_manager.py` |
| **Started** | On API startup in a **background thread** with its own asyncio loop. |
| **Scheduler** | Runs every **5 seconds**; drains `request_phase` queue (from coordinator or API), then evaluates interval-based schedules and enqueues tasks. |
| **Workers** | **8** concurrent tasks (`max_concurrent_tasks`). |
| **Phases** | See [Production schedule](#4-routine-processing-schedule) and `schedules` in code. Key: context_sync (15 min), claim_extraction (30 min), event_tracking (1 h), story_state_triggers (5 min), story_enhancement (5 min), entity_enrichment (30 min), plus article_processing, ml_processing, topic_clustering, event_extraction, timeline_generation, etc. |
| **Batch sizes** | Defined in execute methods and [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md): e.g. context 100, claims 50, events 100, fact_change_log 100, queue 10–20. |
| **API** | Trigger phase: `POST /api/system_monitoring/monitoring/trigger_phase` (body: `phase`). Overview (health + activities): `GET /api/system_monitoring/monitoring/overview`. |

### 2.3 Finance Orchestrator

| Aspect | Detail |
|--------|--------|
| **Role** | Finance-domain collection and analysis: refresh topics (gold, silver, platinum, edgar), run analysis tasks. Task queue with priorities. |
| **Location** | `api/domains/finance/orchestrator.py` (and types in `orchestrator_types.py`) |
| **Started** | On API startup; scheduler and queue worker run in main process. |
| **Collection** | Invoked by Orchestrator Coordinator when Collection Governor recommends a finance source; coordinator calls `submit_task(TaskType.refresh, {topic})`. |
| **Analysis** | `TaskType.analysis` for user/watchlist-driven or areas-of-interest queries (from config `finance_areas_of_interest`). |
| **API** | Finance routes under `/api` (e.g. analysis, refresh); orchestrator status via coordinator/orchestrator_state. |

### 2.4 Health Monitor Orchestrator

| Aspect | Detail |
|--------|--------|
| **Role** | Polls health feeds (API, DB, external); creates alerts on failure. |
| **Location** | `api/services/health_monitor_orchestrator.py` |
| **Started** | On API startup; runs in background. |

### 2.5 Newsroom Orchestrator (v6)

| Aspect | Detail |
|--------|--------|
| **Role** | Event-driven, role-based orchestration (Chief Editor, Reporter, Journalist, Editor, Archivist). Complements AutomationManager; migrates workflows incrementally. |
| **Location** | `api/orchestration/` (base, roles, events, plugins) |
| **Status** | Available; integration with main loop is optional. |

### 2.6 Other background processors

| Component | Role | Location |
|-----------|------|----------|
| **Topic Extraction Queue Worker** | Per-domain queue: articles → LLM topic extraction; adaptive poll (5s when work, 60s when idle); batch 10. | `domains/content_analysis/services/topic_extraction_queue_worker.py` |
| **ML Processing Service** | Processes articles needing ML analysis (summaries, features). | `modules/ml/` + automation_manager `ml_processing` phase |
| **Storyline Consolidation Service** | Periodic storyline consolidation (merge, dedupe). | `services/storyline_consolidation_service.py` |
| **Route Supervisor** | Monitors routes and DB connections; frontend health. | `shared/services/route_supervisor.py` |

---

## 3. Governors

Governors provide **decision logic**; the Orchestrator Coordinator uses them to decide what to run next.

| Governor | Role | Config / state |
|----------|------|-----------------|
| **Collection Governor** | Recommends next **collection** source (RSS, gold, silver, platinum, edgar) based on `last_collection_times`, min/max fetch interval, empty-fetch penalty. Records fetch results. | `orchestrator_governance.yaml` → `collection` (sources, min/max_fetch_interval_seconds, empty_fetch_penalty). State: `last_collection_times`. |
| **Processing Governor** | Recommends next **processing** phase (and optional domain/storyline_id) based on `last_processing_times`, `processing.phases` intervals, user guidance (watchlist, automation storylines). | `orchestrator_governance.yaml` → `processing.phases`. State: `last_processing_times`. |
| **Resource Governor** | Tracks LLM token and API call usage; `can_run("collection"|"processing")`, `remaining_llm_budget()`. | `orchestrator_governance.yaml` → `resources` (daily_llm_tokens, max_api_calls_per_hour). State: resource_usage. |
| **Learning Governor** | Pattern analysis over decision_history; writes learned_patterns; used for learning_stats and predictions. | `orchestrator_governance.yaml` → `learning`. |

---

## 4. Routine processing schedule

Aligned with [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md). Automation Manager runs these phases on intervals; many re-enqueue when work remains (continuous until empty).

| Phase | Interval | Batch / constraint | Notes |
|-------|----------|--------------------|-------|
| context_sync | 15 min | 100 contexts/domain | Articles → intelligence.contexts |
| claim_extraction | 30 min | 50 contexts | Contexts → extracted_claims (LLM) |
| event_tracking | 1 hour | 100 limit (≈1000 contexts scan) | Contexts → tracked_events, event_chronicles |
| story_state_triggers | 5 min | 100 fact_change_log, 20 queue | fact_change_log → story_update_queue → story state |
| story_enhancement | 5 min | 10 stories, 60s budget | Triggers + entity enrichment + profile build |
| entity_enrichment | 30 min | 20 entities/run | Wikipedia → entity_profiles; skip if queue > 1000 |
| entity_profile_build | 15 min | 15 profiles | Contexts → entity_profiles.sections |
| article_processing | 5 min | 20 articles | Content cleaning |
| ml_processing | 5 min | 50 articles | ML queue |
| topic_clustering | 5 min | domain batch | Topic assignment |
| entity_extraction | 5 min | 50 articles | Entities |
| quality_scoring | 5 min | 50 articles | Quality score |
| storyline_processing | 5 min | all storylines needing summary | master_summary |
| basic_summary_generation | 5 min | storylines needing summary | Basic summary |
| rag_enhancement | 5 min | storylines needing RAG | rag_context_summary |
| storyline_automation | 5 min | 5 storylines/domain (automation_enabled) | RAG discovery |
| timeline_generation | 5 min | storylines needing timeline | timeline_summary |
| event_extraction | 5 min | 30 articles | timeline_processed, events |
| event_deduplication | 10 min | 100 | Dedupe events |
| story_continuation | 10 min | 30 | Match events to storylines |
| rss_processing | 30 min | full collect | collect_rss_feeds (also triggered by coordinator) |
| health_check | 2 min | — | Health check |
| data_cleanup | 24 h | — | Maintenance |

---

## 5. End-to-end data flow

### 5.1 Collection → ingestion

1. **RSS**  
   Coordinator (or manual_override / trigger_phase) → `collect_rss_feeds()` → per-domain `rss_feeds` → fetch → dedupe → insert into `{domain}.articles` (and optional `ensure_context_for_article` if context-centric on insert).

2. **Finance**  
   Coordinator → `FinanceOrchestrator.submit_task(refresh, topic)` → evidence collection (e.g. gold/silver/platinum/edgar) → finance evidence/state and any article-like storage used by finance.

### 5.2 Domain articles → context-centric pipeline

1. **Context sync** (Automation Manager or API)  
   `sync_domain_articles_to_contexts(domain, limit=100)` → creates `intelligence.contexts` and `article_to_context` for articles that don’t have a context yet; links context to entity_profiles via `context_entity_mentions`.

2. **Entity profile sync**  
   Ensures `entity_canonical` → `entity_profiles` and `old_entity_to_new`; run periodically (e.g. 6 h).

3. **Claim extraction**  
   Contexts without claims → LLM → `intelligence.extracted_claims`.

4. **Event tracking**  
   Contexts → event discovery → `tracked_events`, `event_chronicles` (with participant → entity_profiles where applicable).

5. **Entity profile build**  
   Contexts mentioning an entity → LLM → `entity_profiles.sections`, relationships_summary.

6. **Pattern recognition**  
   Writes to `pattern_discoveries` (network, temporal, behavioral, event).

### 5.3 Storyline and RAG pipeline

1. **Article / ML / topic / entity**  
   Automation Manager phases: article_processing → ml_processing, topic_clustering, entity_extraction, quality_scoring (and event_extraction for v5 events).

2. **Storyline processing**  
   storylines missing master_summary → generate; basic_summary_generation → progressive enhancement; rag_enhancement → rag_context_summary; timeline_generation → timeline_summary.

3. **Story state**  
   fact_change_log (from versioned_facts / profile updates) → story_update_queue → story state refresh (storyline_states, etc.).

4. **Story enhancement**  
   One cycle: fact_change_log batch + story_update_queue batch + entity enrichment batch + entity profile build batch (see enhancement_orchestrator_service).

5. **Storyline automation**  
   Automation-enabled storylines → RAG discovery (discover_articles_for_storyline).

### 5.4 Event pipeline (v5)

- event_extraction: articles (processing_status=completed, timeline_processed=false) → events.
- event_deduplication: dedupe events.
- story_continuation: match events to storylines, lifecycle states.
- watchlist_alerts: reactivation and new-event alerts.

---

## 6. Full API stack

### 6.1 Route prefix overview

| Prefix | Domain / area | Main responsibility |
|--------|----------------|---------------------|
| `/api` | Shared / domain-prefixed | Many routes live under `/api` with `/{domain}/...` for politics, finance, science-tech. |
| `/api/{domain}/rss_feeds` | News aggregation | RSS CRUD, collect_now. |
| `/api/{domain}/articles` | News aggregation | Articles list, detail, dedupe. |
| `/api/{domain}/content_analysis` | Content analysis | Topics, topic queue, LLM activity. |
| `/api/{domain}/storylines` | Storyline management | CRUD, discovery, consolidation, automation, articles, evolution, analysis, timeline, watchlist. |
| `/api/intelligence_hub` | Intelligence hub | Intelligence hub UI endpoints. |
| `/api` (flat) | Intelligence / context-centric | context_centric: sync_contexts, run_story_state_triggers, run_enhancement_cycle, run_entity_enrichment, run_pattern_matching; entity_profiles, contexts, tracked_events, claims; RAG, content synthesis, intelligence analysis. |
| `/api` (flat) | Finance | Finance analysis, corporate announcements, market patterns, etc. |
| `/api/user_management` | User management | Users, auth. |
| `/api/system_monitoring` | System monitoring | Health, monitoring overview, fast_stats, pipeline, route_supervisor, resource_dashboard. |
| `/api/orchestrator` | Orchestrator API | status, metrics, decision_log, learning_stats, predictions, dashboard, manual_override (force_collect_now, pause_learning, etc.). |

### 6.2 Domain routers (included in main_v4)

- **News aggregation** — `domains/news_aggregation/routes`: `/api` + `/{domain}/rss_feeds`, `/{domain}/articles`, etc.
- **Content analysis** — `domains/content_analysis/routes`: `/api` + topics, topic queue, article dedupe, LLM activity.
- **Storyline management** — `domains/storyline_management/routes`: `/api` + storylines (discovery, consolidation, automation, crud, articles, evolution, analysis, timeline, watchlist).
- **Intelligence hub** — `domains/intelligence_hub/routes`: `/api/intelligence_hub`, plus context_centric, RAG, content synthesis, intelligence analysis under `/api`.
- **Finance** — `domains/finance/routes/finance`: `/api` + finance endpoints.
- **User management** — `domains/user_management/routes`: `/api/user_management`.
- **System monitoring** — `domains/system_monitoring/routes`: `/api/system_monitoring`, `/api/orchestrator`, route_supervisor, resource_dashboard.

### 6.3 Key context-centric and pipeline APIs

- `POST /api/context_centric/sync_contexts` — Sync articles → contexts (limit default 100).
- `POST /api/context_centric/run_story_state_triggers` — fact_change_log + story_update_queue (fact_batch=100, queue_batch=20).
- `POST /api/context_centric/run_enhancement_cycle` — Full cycle (fact_batch=100, queue_batch=10, enrich_limit=10, build_limit=10).
- `POST /api/context_centric/run_entity_enrichment` — Entity enrichment batch (limit=20).
- `POST /api/context_centric/run_pattern_matching` — Watch pattern matching.
- `GET /api/entity_profiles`, `GET /api/contexts`, `GET /api/tracked_events`, `GET /api/claims` — Context-centric reads.
- `GET /api/system_monitoring/monitoring/overview` — Health + activity feed (current/recent).
- `POST /api/system_monitoring/monitoring/trigger_phase` — Request a phase (e.g. rss_processing).
- `GET/POST /api/orchestrator/*` — Status, metrics, decision log, learning, dashboard, manual_override.

---

## 7. Configuration and design notes

### 7.1 Orchestrator governance

- **File:** `api/config/orchestrator_governance.yaml` (loaded by `config/orchestrator_governance.py`).
- **Sections:** `orchestrator` (loop_interval_seconds), `collection` (sources, min/max_fetch_interval_seconds, empty_fetch_penalty), `processing` (phases with interval_seconds and scope), `finance_areas_of_interest`, `learning`, `resources`.
- **Used by:** OrchestratorCoordinator, CollectionGovernor, ProcessingGovernor, ResourceGovernor, LearningGovernor.

### 7.2 Context-centric feature flags

- **File:** `api/config/context_centric.yaml`; **code:** `api/config/context_centric_config.py`.
- **Flags:** context_sync, entity_profile_sync, claim_extraction, event_tracking, entity_profile_build, pattern_recognition. Set to `false` to disable a task.

### 7.3 Batch processing and backpressure

- **Doc:** [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md).
- **Principles:** Small batches frequently; realistic LLM/embedding limits; queue limits and skip-when-overloaded (e.g. entity enrichment queue > 1000); cost controls.

### 7.4 Database and schemas

- **Per-domain schemas:** politics, finance, science_tech (articles, storylines, rss_feeds, topic_extraction_queue, etc.).
- **Intelligence schema:** contexts, article_to_context, entity_profiles, old_entity_to_new, context_entity_mentions, extracted_claims, tracked_events, event_chronicles, fact_change_log, story_update_queue, pattern_discoveries, etc.
- **Single source of truth for DB:** `shared/database/connection.py` (get_db_config, get_db_connection).

---

## 8. Startup order (main_v4 lifespan)

1. DB pool init, config load.
2. Finance Orchestrator (scheduler + queue worker).
3. Orchestrator Coordinator (start_loop).
4. Automation Manager (background thread).
5. ML Processing Service start.
6. Topic Extraction Queue Workers (background thread, per domain).
7. Route Supervisor (background thread).
8. Health Monitor Orchestrator.
9. Storyline Consolidation Service (periodic background).

Shutdown: reverse order where applicable (e.g. coordinator stop, automation stop, route_supervisor stop).

---

## 9. Quick reference — where to look

| Need | Where |
|------|--------|
| Change collection frequency / sources | `orchestrator_governance.yaml` → collection.sources, min/max_fetch_interval_seconds |
| Change processing phase frequency | `orchestrator_governance.yaml` → processing.phases; `automation_manager.py` → schedules |
| Change batch sizes | `automation_manager.py` execute methods; context_processor_service, claim_extraction_service, event_tracking_service, story_state_trigger_service, enhancement_orchestrator_service, entity_enrichment_service; [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md) |
| Disable a context-centric task | `context_centric.yaml` → task flag false |
| Orchestrator status / manual trigger | `GET /api/orchestrator/status`, `POST /api/orchestrator/manual_override` |
| Activity feed / trigger phase | `GET /api/system_monitoring/monitoring/overview`, `POST /api/system_monitoring/monitoring/trigger_phase` |
| Full API list | FastAPI app in `main_v4.py`; OpenAPI at `/docs` or `/redoc` |

This roadmap, together with [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md) and [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md), describes the full data pipelines and processing design. For **planned enhancements** (feedback loops, cross-domain synthesis, source quality, real-time, relationships, predictive, products, anomaly investigation), see [DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md](DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md).
