# Orchestrator Behaviors vs Planning Documents — Gap Analysis

**Purpose:** List what each orchestrator actually does in code, compare to the planning docs, and assess whether the implementation captures project intent or leaves empty/disconnected pieces.

**References:** [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md), [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md), [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md).

---

## 1. Implemented orchestrator behaviors (what the code does)

### 1.1 OrchestratorCoordinator (`api/services/orchestrator_coordinator.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| Single loop (assess → plan → execute → learn → sleep) | ✅ | `_run_loop()` every `loop_interval_seconds` (default 60). |
| Ask CollectionGovernor for next action | ✅ | `recommend_fetch(last_times)` → `{"source": "rss"}` or `{"source": "gold"}` or `None`. |
| Execute RSS collection | ✅ | Calls `collect_rss_feeds()` (from `collectors.rss_collector`) in thread executor. |
| Execute gold refresh | ✅ | Calls `FinanceOrchestrator.submit_task(TaskType.refresh, {"topic": "gold"})`. |
| Record result (last_collection_times, decision_log) | ✅ | `record_fetch_result()`, `append_decision_log()`, `save_controller_state()`. |
| ResourceGovernor.record_usage | ✅ | After execute. |
| Periodic LearningGovernor.run_pattern_analysis | ✅ | Every 30 cycles (~30 min). |
| get_status() for API | ✅ | cycle, last_collection_times, running, resource_budget. |
| run_manual_collect(source) | ✅ | Used by API manual override. |
| **Ask ProcessingGovernor for next processing** | ❌ | **Not implemented.** Coordinator never asks "what processing phase to run." |
| **Trigger AutomationManager phases** | ❌ | Coordinator does not call AutomationManager; it only does collection (RSS/gold). |

**Conclusion:** Coordinator does **collection timing only** (RSS + gold). It does **not** decide or trigger article processing, ML, context sync, storylines, etc. Those are entirely under AutomationManager’s own scheduler.

---

### 1.2 CollectionGovernor (`api/services/collection_governor.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| recommend_fetch(last_times) | ✅ | Uses min/max_fetch_interval, effective_interval (backoff for empty fetches). |
| record_fetch_result(source, success, observations_count) | ✅ | Updates last_collection_times, source_profiles (historical_update_times, last_empty_fetch_count). |
| ResourceGovernor.can_run("collection") gating | ✅ | Optional; used when check_resources=True. |
| Config from orchestrator_governance.yaml | ✅ | Via get_orchestrator_governance_config(). |

**Conclusion:** Fully implemented for its current role (when to fetch RSS/gold). No "what to process" or importance/watchlist input.

---

### 1.3 AutomationManager (`api/services/automation_manager.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| Own scheduler loop | ✅ | 10s poll; enqueues tasks by schedule (interval + last_run). |
| rss_processing | ✅ | Calls `get_rss_processor().process_all_feeds()` (**different path** from `collect_rss_feeds()`). |
| context_sync | ✅ | `sync_domain_articles_to_contexts()` per domain (context-centric). |
| entity_profile_sync | ✅ | `sync_domain_entity_profiles()` per domain. |
| claim_extraction | ✅ | `run_claim_extraction_batch(30)`. |
| event_tracking | ✅ | `run_event_tracking_batch(20)`. |
| entity_profile_build | ✅ | `run_profile_builder_batch(15)`. |
| pattern_recognition | ✅ | `run_pattern_discovery_batch()`. |
| article_processing, ml_processing, topic_clustering, etc. | ✅ | Each has `_execute_*` calling real services (article_service, ML, topic extractor, etc.). |
| Context-centric task gating | ✅ | context_centric_config.is_context_centric_task_enabled() before context_* tasks. |
| **Invoked by OrchestratorCoordinator** | ❌ | **No.** AutomationManager runs on its own timer; coordinator never calls it. |
| **Exposes run_phase(phase_name, domain=…)** | ❌ | **No.** No API for coordinator to request "run context_sync now." |

**Conclusion:** AutomationManager is a **second, independent loop**. It runs real pipeline code (RSS via a different service, context-centric, ML, topics, storylines, etc.) but is **not** driven by OrchestratorCoordinator. Planning doc (Phase A) intended it to become an **executor** called by the coordinator; that has not been done.

---

### 1.4 ProcessingGovernor (`api/services/processing_governor.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| get_processing_status() | ✅ | AutomationManager status + FinanceOrchestrator schedule_status. |
| trigger_finance_analysis(query, topic, priority) | ✅ | Submits analysis task to FinanceOrchestrator. |
| **Recommend "next processing action" (phase + domain)** | ❌ | **No.** No `recommend_next_processing()` or priority queue. |
| **Used by OrchestratorCoordinator** | ❌ | **No.** Coordinator never instantiates or calls ProcessingGovernor. |

**Conclusion:** ProcessingGovernor exists but is **not wired into the coordinator loop**. Roadmap expected it to answer "what phase to run next" (Phase B); that behavior does not exist, and the coordinator does not call it.

---

### 1.5 FinanceOrchestrator (`api/domains/finance/orchestrator.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| Scheduler + queue worker | ✅ | start_scheduler(), start_queue_worker(); runs refresh, ingest, analysis tasks. |
| submit_task(TaskType, params, priority) | ✅ | Used by OrchestratorCoordinator (gold refresh) and API. |
| Gold/EDGAR/FRED/analysis tasks | ✅ | Real implementations. |

**Conclusion:** Fully under its own control; coordinator only triggers gold refresh via recommend_fetch. Aligns with CONTROLLER_ARCHITECTURE.

---

### 1.6 LearningGovernor (`api/services/learning_governor.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| run_pattern_analysis() | ✅ | Reads decision_log, aggregates outcomes, writes orchestrator_learned_patterns. |
| get_learning_stats() / get_predictions() | ✅ | Used by orchestrator API dashboard. |
| **Influence on CollectionGovernor or ProcessingGovernor** | ❌ | Pattern data is stored but not read by governors to change recommendations. |

**Conclusion:** Learning runs and persists patterns but does not yet **feed back** into what to collect or process next.

---

### 1.7 ResourceGovernor (`api/services/resource_governor.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| can_run("collection") | ✅ | Used by CollectionGovernor when check_resources=True. |
| record_usage(RESOURCE_API_CALLS, 1.0) | ✅ | Called by coordinator after execute. |
| get_budget_status() | ✅ | In get_status(). |

**Conclusion:** Implemented and used for collection gating and usage recording.

---

### 1.8 NewsroomOrchestrator (`api/orchestration/base.py`)

| Behavior | Implemented | Notes |
|----------|-------------|--------|
| Optional start (feature-flagged) | ✅ | main_v4 lifespan: if newsroom config enabled, starts in thread. |
| Event-driven roles (Reporter, Editor, etc.) | ✅ | Handlers registered; can consume events. |
| **Integration with OrchestratorCoordinator** | ❌ | Separate loop; not invoked by coordinator. |

**Conclusion:** Optional v6 event-driven orchestrator; runs in parallel, not as the "single loop" owner.

---

### 1.9 Other independent runners (not orchestrated by coordinator)

| Component | Trigger | What it does |
|-----------|---------|--------------|
| Cron (rss_collection_with_health_check.sh) | 6 AM, 6 PM | Calls `collect_rss_feeds()` (same as coordinator). |
| StorylineConsolidationService | 30 min timer (lifespan) | run_all_domains() consolidation. |
| TopicExtractionQueueWorker | Per-domain loop (lifespan) | Processes topic queue. |
| MLProcessingService | Started in lifespan | Background ML processing. |
| POST /api/system_monitoring/pipeline/trigger | API | Runs RSS (collect_rss_feeds) + topic clustering + simple sentiment in sequence. |
| POST /api/{domain}/rss_feeds/collect_now | API | Calls collect_rss_feeds(). |

**Conclusion:** Multiple independent triggers for RSS and processing. No single owner.

---

## 2. Comparison to planning documents

### 2.1 CONTROLLER_ARCHITECTURE.md

| Doc claim | Reality |
|-----------|--------|
| "OrchestratorCoordinator runs a single loop: load state → ask CollectionGovernor → execute (RSS or gold) → record → save state → sleep" | ✅ Matches. |
| "Orchestrators do not yet fully control the system" / "AutomationManager runs its own loop" | ✅ Still true. AutomationManager has not been gated or driven by the coordinator. |
| "RSS collection runs from: AutomationManager (1h), cron (2x daily), pipeline route, collect_now" | ✅ Still true; overlap not removed. |

**Verdict:** The doc accurately describes current state. The **proposed** architecture (single loop, controller 2 = data processing under one owner) is **not** implemented.

---

### 2.2 ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md

| Roadmap phase | Doc intent | Implemented? |
|---------------|------------|--------------|
| **Phase A: Single control loop** | Coordinator is the only component that triggers pipeline work; AutomationManager runs only when coordinator says "run this now." | ❌ No. AutomationManager still has its own scheduler. Coordinator never calls AutomationManager or ProcessingGovernor. |
| A.1 Expose AutomationManager phases as callables | Coordinator (or ProcessingGovernor) can invoke "run rss_processing," "run context_sync," etc. | ❌ No. No run_phase(phase_name, domain=…) exposed; coordinator does not call automation. |
| A.2 Coordinator asks ProcessingGovernor each cycle | "What processing should run next?" Execute at most one collection + one processing action per cycle. | ❌ No. Coordinator only asks CollectionGovernor (collection). ProcessingGovernor is never asked. |
| A.3 Stop AutomationManager's own scheduler | AutomationManager only executes when coordinator requests a phase. | ❌ No. AutomationManager still runs its 10s poll and own schedule. |
| A.4 Route cron and API through coordinator | Cron/API call coordinator "force_collect_now" / "run_phase" or are deprecated. | ❌ No. Cron and collect_now still call collect_rss_feeds directly; pipeline/trigger runs its own sequence. |
| **Phase B: ProcessingGovernor drives "what"** | ProcessingGovernor returns ranked list of next best actions (phase + domain/storyline). | ❌ No. ProcessingGovernor has no recommend API; coordinator does not call it. |
| **Phase C–E: Importance, initiative, user guidance** | Importance scores, watchlist, proposed focus, user guidance as input. | ❌ Not started. No importance model, no editorial/proposed-focus queue, no central user-guidance state read by governors. |

**Verdict:** The roadmap’s **target state** (one loop, one place that decides what runs) is **not** implemented. Phase A (single control loop) is the foundation and is **incomplete**. What we built is:

- A **collection-only** coordinator (RSS + gold timing).
- A **separate** AutomationManager that runs all processing (including context-centric) on its own schedule.
- Governors (Processing, Learning, Resource) that exist but are either not used by the loop (ProcessingGovernor) or only used in a limited way (LearningGovernor periodic analysis, ResourceGovernor for collection gating).

---

### 2.3 CONTEXT_CENTRIC_UPGRADE_PLAN.md

| Doc intent | Implemented? |
|------------|--------------|
| Context-centric pipeline (contexts, entity_profiles, claims, events, patterns) | ✅ Yes. Services and DB exist; AutomationManager runs context_sync, entity_profile_sync, claim_extraction, event_tracking, entity_profile_build, pattern_recognition on schedule. |
| RSS collector calls ensure_context_for_article after new article | ✅ Yes. |
| Feature flags (context_centric.yaml) gate tasks | ✅ Yes. |
| API and frontend for entity profiles, contexts, events, search, management | ✅ Yes (Phase 4). |

**Verdict:** **Context-centric** is implemented and **works together**: collector → articles; context_sync → contexts; entity_profile_sync/build → profiles; claim/event/pattern services → claims, events, patterns. The gap is **orchestration**: context-centric tasks are run by AutomationManager’s own loop, not by a single coordinator loop as in the roadmap.

---

## 3. Do we have empty functions or do they work together?

### 3.1 Not empty — real behavior

- **OrchestratorCoordinator:** Real loop; really calls `collect_rss_feeds()` and FinanceOrchestrator; really records state and decision log; really runs LearningGovernor periodically.
- **CollectionGovernor:** Really recommends RSS vs gold based on intervals and backoff; really records results and updates source profiles.
- **AutomationManager:** Real execution of many phases (RSS via rss_processor, context_sync, entity_profile_*, claim_extraction, event_tracking, pattern_recognition, article_processing, ML, topic_clustering, storylines, etc.). Each `_execute_*` calls real services.
- **Context-centric services:** context_processor_service, entity_profile_sync/builder, claim_extraction_service, event_tracking_service, pattern_recognition_service are implemented and used by AutomationManager.
- **FinanceOrchestrator:** Real scheduler and queue; real gold/EDGAR/analysis.
- **LearningGovernor / ResourceGovernor:** Real logic and used (learning periodically, resource gating for collection).

So we do **not** have "empty functions." The pieces that exist **do** run real work.

### 3.2 What does not work together as planned

1. **Two RSS paths:**  
   - **OrchestratorCoordinator** uses `collect_rss_feeds()` (collectors/rss_collector.py) → domain tables.  
   - **AutomationManager** uses `get_rss_processor().process_all_feeds()` (services/rss/processing.py) → different pipeline (session, dedup, etc.).  
   So RSS can be run by both the coordinator and AutomationManager on different schedules and via different code paths. Overlap and potential duplication.

2. **No single control loop:**  
   The roadmap says: "Only OrchestratorCoordinator (and its governors) decide what runs." In reality, the **coordinator** decides only **collection** (RSS/gold). **AutomationManager** decides all **processing** (article, ML, context-centric, topics, storylines, etc.) on its own. So we have **two** decision points, not one.

3. **ProcessingGovernor not in the loop:**  
   ProcessingGovernor exists and can report status and trigger finance analysis, but the **coordinator never asks it "what to run next"** and never triggers AutomationManager phases. So the intended "single loop" that chooses both collection and processing is **not** there.

4. **Learning and resource not driving "what":**  
   LearningGovernor writes patterns; ResourceGovernor gates collection. Neither is used to choose **which** processing phase or storyline to run (no importance, no priority queue of phases).

### 3.3 Summary table

| Question | Answer |
|----------|--------|
| Are orchestrator functions empty? | **No.** They call real services and DB. |
| Do context-centric and collection pipelines work? | **Yes.** Articles → contexts → profiles → claims/events/patterns; coordinator runs RSS/gold. |
| Does the system match "one loop decides everything"? | **No.** Coordinator decides collection only; AutomationManager decides all processing independently. |
| Does the system match the roadmap (Phase A–E)? | **No.** Phase A (single control loop, coordinator triggers processing) is not done. ProcessingGovernor and "run_phase" are not wired in. |
| Can we "just start the orchestrators" and have everything run? | **Yes.** Starting the API starts both OrchestratorCoordinator and AutomationManager (and others). Data collection and context-centric processing do run; they are just **not** coordinated by one loop as in the roadmap. |

---

## 4. Recommendations

1. **Short term (no refactor):** Treat the current design as **two loops**: (1) OrchestratorCoordinator = collection timing (RSS + gold), (2) AutomationManager = all processing (including context-centric). Document this clearly so operators know "starting the API starts both; collection and processing run on their own schedules."
2. **To align with ORCHESTRATOR_ROADMAP_TO_INITIATIVE Phase A:**  
   - Expose AutomationManager (or a thin facade) with something like `run_phase(phase_name, domain=None)`.  
   - Have OrchestratorCoordinator (or ProcessingGovernor) **recommend** the next processing action (e.g. from schedule + last run).  
   - Each coordinator cycle: run at most one collection action (current behavior) **and** one processing action (new: call AutomationManager.run_phase).  
   - Optionally **disable** AutomationManager’s own scheduler so it only runs when the coordinator requests a phase (or keep a slow fallback).
3. **RSS duplication:** Decide on one RSS entry point (e.g. `collect_rss_feeds()` only) and have either the coordinator or AutomationManager call it, and deprecate or redirect the other path so there is a single pipeline for RSS ingestion.
4. **ProcessingGovernor:** Implement `recommend_next_processing()` (e.g. next due phase from AutomationManager schedule + last run) and have the coordinator call it and then execute the returned phase via AutomationManager.

---

*Generated from code and docs as of the audit date. Update this file when Phase A or RSS consolidation is implemented.*
