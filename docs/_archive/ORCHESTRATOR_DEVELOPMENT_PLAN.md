# Orchestrator System Development Plan

> **Source:** Based on the Governance Controller project planning document, adapted to News Intelligence coding style and existing architecture.  
> **Goal:** Seamlessly improve the orchestrator system with a continuous learning loop, coordinated collection/processing, and resource-aware scheduling without replacing existing components.  
> **References:** [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md), [EVIDENCE_AND_CONTROLLER_STATE.md](./EVIDENCE_AND_CONTROLLER_STATE.md), [CONTROLLER_ARCHITECTURE.md](./CONTROLLER_ARCHITECTURE.md).  
> **Last updated:** 2025-02-21.

---

## 1. Overview

### 1.1 Philosophy

**"Continuous context building with intelligent restraint"** — The system continuously uses existing data to build deeper context while managing external collection and LLM use based on learned patterns and resource limits.

### 1.2 Design Principles (aligned with codebase)

- **Reuse before create:** Extend `FinanceOrchestrator`, `AutomationManager`, and existing collectors; add a coordination layer and governors that delegate to them. No "Enhanced" or "Unified" duplicate services.
- **Single source of truth:** One config file for orchestrator governance (`orchestrator_governance.yaml`); state in one store (e.g. `orchestrator_controller_state`).
- **Naming:** snake_case (files, functions, variables, DB tables/columns), PascalCase (classes), UPPER_SNAKE_CASE (constants). Route paths snake_case; API prefix `/api`.
- **Existing controllers unchanged by default:** Finance Controller (`FinanceOrchestrator`), Data Processing (`AutomationManager`, RSS, topic workers), Review & Cleanup (consolidation, cleanup) remain; the new layer coordinates and learns.

---

## 2. Target Architecture (mapped to current code)

### 2.1 Coordinator and governors

| Planning-doc concept      | In-code name / location | Role |
|---------------------------|--------------------------|------|
| Master controller         | **OrchestratorCoordinator** | Central loop, state, priority arbitration, resource allocation. New class in `api/services/orchestrator_coordinator.py` (or `api/domains/orchestrator/coordinator.py`). |
| Collection Governor       | **CollectionGovernor**  | Source monitoring, fetch scheduling, source health, duplicate prevention. Wraps/delegates to `collect_rss_feeds`, `FinanceOrchestrator` refresh, and new source health tracker. New: `api/services/collection_governor.py` (or under `api/domains/orchestrator/`). |
| Processing Governor       | **ProcessingGovernor**   | Analysis pipeline, context accumulation, cross-domain. Delegates to `AutomationManager` phases and `FinanceOrchestrator.run_task(analysis)`. New: `api/services/processing_governor.py`. |
| Learning Governor        | **LearningGovernor**     | Pattern detection, predictions, feedback, model updates. New: `api/services/learning_governor.py`. |
| Resource Governor        | **ResourceGovernor**     | LLM token budget, API rate limits, compute scheduling, storage. New: `api/services/resource_governor.py`. |

Governors are **new modules** that use existing services (e.g. `collect_rss_feeds` from `api/collectors/rss_collector.py`, `FinanceOrchestrator` on `app.state.finance_orchestrator`, `AutomationManager` on `app.state.automation`) rather than reimplementing their logic.

### 2.2 Existing components (unchanged roles, coordinated by coordinator)

- **FinanceOrchestrator** — `api/domains/finance/orchestrator.py`: gold/FRED/EDGAR refresh, analysis, schedule, queue worker. Stays the main finance controller; CollectionGovernor and ProcessingGovernor call it or respect its schedule.
- **AutomationManager** — `api/services/automation_manager.py`: rss_processing, article_processing, ml_processing, topic_clustering, storyline, etc. ProcessingGovernor can delegate to it and/or respect its phases.
- **RSS collector** — `api/collectors/rss_collector.py`: `collect_rss_feeds()`, `collect_rss_feed()`. CollectionGovernor decides when to call (or not) based on source profiles and backoff.
- **Evidence / finance pipeline** — Evidence index and prompt building remain in `api/domains/finance/orchestrator.py`. An **evidence collector** (`api/domains/finance/evidence_collector.py`) feeds RSS (and optional API summary/RAG) into the same pipeline; see EVIDENCE_AND_CONTROLLER_STATE.md §2.5.

---

## 3. State and configuration (naming aligned)

### 3.1 State (persisted)

Store in a single place: either a new PostgreSQL schema `orchestrator` or SQLite under `api/data/` (e.g. `orchestrator_state.db`). Table names snake_case:

| Table / store | Purpose |
|---------------|---------|
| `orchestrator_controller_state` | current_cycle, last_collection_times (source → timestamp), processing_queue snapshot, active_investigations, resource_usage, performance_metrics. |
| `orchestrator_source_profiles` | source_id, historical_update_times, average_interval_seconds, reliability_score, content_value_score, last_empty_fetch_count, predicted_next_update. |
| `orchestrator_learned_patterns` | pattern_type, pattern_data (JSON), confidence, updated_at. |
| `orchestrator_decision_history` | timestamp, decision, factors (JSON), weights (JSON), outcome, learning_notes. |
| `orchestrator_performance_metrics` | metric_name, value, recorded_at. |
| `orchestrator_resource_usage` | resource_type, usage, limit, recorded_at. |

If using SQLite (like finance evidence_ledger), one DB file with these tables and `idx_<table>_<column>` indexes.

### 3.2 Configuration

Single YAML under existing config: `api/config/orchestrator_governance.yaml`. Keys snake_case; values match existing style (e.g. intervals in seconds).

```yaml
# api/config/orchestrator_governance.yaml (target structure)
orchestrator:
  loop_interval_seconds: 60
  learning_rate: 0.1

  collection:
    min_fetch_interval_seconds: 300
    max_fetch_interval_seconds: 7200
    empty_fetch_penalty: 2.0
    breaking_news_threshold: 0.8

  processing:
    batch_size: 10
    max_concurrent: 3
    context_window_days: 7

  learning:
    pattern_detection_window_days: 30
    model_update_frequency_seconds: 21600
    min_confidence_threshold: 0.7

  resources:
    daily_llm_tokens: 100000
    max_api_calls_per_hour: 1000
    storage_warning_threshold: 0.8
```

Load via a small helper in `api/config/` (e.g. `get_orchestrator_governance_config()`) so the rest of the app does not duplicate config logic.

---

## 4. Loop and background jobs

### 4.1 Primary loop (OrchestratorCoordinator)

- **Cycle:** 1–5 minutes (configurable via `loop_interval_seconds`).
- **Steps:** (1) Assess current state, (2) Plan next actions, (3) Execute highest-priority task, (4) Learn from results, (5) Update models/metrics, (6) Sleep until next cycle.
- **Implementation:** asyncio loop in `OrchestratorCoordinator.run_loop()`; non-blocking, concurrent with FastAPI. Start from `main.py` lifespan (same pattern as FinanceOrchestrator scheduler / queue worker).

### 4.2 Background loops (can be same coordinator, different intervals)

| Loop | Interval (example) | Responsibility |
|------|---------------------|----------------|
| Source health check | 15 min | CollectionGovernor: update source health, refresh source_profiles. |
| Pattern analysis | 30 min | LearningGovernor: detect patterns, update learned_patterns. |
| Model / threshold update | 6 h | LearningGovernor: retrain or adjust thresholds from feedback. |
| System optimization | 24 h | ResourceGovernor + LearningGovernor: storage, metrics archival, calibration. |

Intervals come from `orchestrator_governance.yaml` so they can be tuned without code changes.

---

## 5. Collection intelligence (CollectionGovernor)

- **Inputs:** `orchestrator_source_profiles`, `orchestrator_controller_state.last_collection_times`, resource availability from ResourceGovernor.
- **Decision tree:** (1) Check source profile, (2) Time since last update, (3) Global/news cycle (optional), (4) Resource availability, (5) Predicted value of fetch, (6) Fetch vs wait.
- **Backoff:** Exponential backoff for empty fetches; reduced frequency in quiet periods; optional rapid response to breaking-news signals. Store backoff state in `orchestrator_source_profiles` or controller_state.
- **Integration:** CollectionGovernor does **not** replace `collect_rss_feeds()` or `FinanceOrchestrator.submit_task(refresh)`. It decides *when* to trigger them (e.g. by calling existing APIs or functions) and records outcomes in decision_history and source_profiles.

---

## 6. Processing intelligence (ProcessingGovernor)

- **Context layers:** immediate (24 h), recent (7 d), historical (30 d), deep (all). Used for prioritization and which evidence window to use (align with existing evidence/date ranges in finance).
- **Value-based prioritization:** High-value entity mentions, developing story updates, cross-domain connections, watchlist items, anomaly investigations. Implement as priority weights or filters when delegating to AutomationManager and FinanceOrchestrator.
- **Integration:** ProcessingGovernor calls or triggers existing processing (e.g. topic queue, storyline consolidation, finance analysis) rather than reimplementing pipelines. Coordination only.

---

## 7. Learning and resource management

- **LearningGovernor:** Consume decision_history and performance_metrics; update learned_patterns; optional prediction_engine (e.g. next source update, breaking news likelihood). Feedback loop: action → result → evaluation; prediction → reality → adjustment.
- **ResourceGovernor:** Track LLM token usage, API call counts, optional CPU/memory; enforce daily_llm_tokens and max_api_calls_per_hour from config. Expose `can_run(task_type)` or budget checks to OrchestratorCoordinator and governors so high-priority (e.g. user analysis, watchlist) can preempt low-priority when budget is low.

---

## 8. API surface (flat /api, snake_case paths)

All under one router prefix, e.g. `prefix="/api/orchestrator"` (or `/api/system_monitoring/orchestrator` if preferred to keep under system_monitoring). Routes snake_case:

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/api/orchestrator/status` | GET | Current coordinator state, last cycle, next run. |
| `/api/orchestrator/metrics` | GET | performance_metrics, resource_usage (current/recent). |
| `/api/orchestrator/decision_log` | GET | Paginated decision_history (query params: limit, offset, since). |
| `/api/orchestrator/predictions` | GET | Current predictions (e.g. next source updates). |
| `/api/orchestrator/manual_override` | POST | One-off override (e.g. force collection now, pause learning). |
| `/api/orchestrator/learning_stats` | GET | LearningGovernor stats (pattern counts, accuracy if applicable). |

Response shapes: consistent with existing API (e.g. `success`, `data`, `timestamp`); use existing response schemas where applicable.

---

## 9. Integration with existing system

- **AutomationManager:** OrchestratorCoordinator or ProcessingGovernor can trigger pipeline phases via existing entry points (e.g. `POST /api/system_monitoring/pipeline/run_all` or internal method calls if exposed). Do not duplicate AutomationManager logic inside governors.
- **RSS / cron:** CollectionGovernor can decide *when* to run collection; actual runs still use `collect_rss_feeds()` or domain `collect_now`. Optionally consolidate RSS triggers over time (cron vs AutomationManager vs orchestrator) per CONTROLLER_ARCHITECTURE recommendations.
- **FinanceOrchestrator:** Stays the single finance controller. CollectionGovernor may request gold/FRED refresh via `submit_task(refresh)` or API; ProcessingGovernor may request analysis via `submit_task(analysis)`. No change to finance evidence index or prompt building in Phase 1.

---

## 10. Implementation phases (high level)

- **Phase 1 — Foundation (Weeks 1–2):** Core loop, state persistence, config loading, basic OrchestratorCoordinator and one governor (e.g. CollectionGovernor) that delegates to existing RSS + finance refresh. No change to existing scheduler contracts; coordinator runs alongside them.
- **Phase 2 — Intelligence (Weeks 3–4):** LearningGovernor (pattern detection, decision_history logging), ResourceGovernor (token/API budgets), adaptive scheduling in CollectionGovernor (backoff, source_profiles). ProcessingGovernor delegates to AutomationManager and finance analysis.
- **Phase 3 — Advanced (Weeks 5–6):** Predictions (next source updates, breaking_news_likelihood), config_overrides in state and `set_config_override` manual action, dashboard endpoint, performance and docs. **Done:** `GET /api/orchestrator/predictions`, `GET /api/orchestrator/dashboard`, `POST /api/orchestrator/manual_override` with `set_config_override`; CollectionGovernor reads `config_overrides` from state.

---

## 10.1 Orchestrator API endpoints (all phases)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/orchestrator/status` | GET | Coordinator state, cycle, last_collection_times, resource_budget. |
| `/api/orchestrator/metrics` | GET | performance_metrics, resource_usage (query: metric_name, resource_type, limit). |
| `/api/orchestrator/decision_log` | GET | Paginated decision_history (limit, offset, since). |
| `/api/orchestrator/learning_stats` | GET | Pattern counts by type, recent patterns sample. |
| `/api/orchestrator/predictions` | GET | next_source_updates, breaking_news_likelihood (Phase 3). |
| `/api/orchestrator/dashboard` | GET | Single payload: status, decision_log, learning_stats, predictions, recent_metrics, recent_resource_usage (Phase 3). |
| `/api/orchestrator/manual_override` | POST | action: force_collect_now, pause_learning, resume_learning, set_config_override; optional source, config_overrides. |

---

## 11. File and module map (target)

| Purpose | File / path |
|--------|-------------|
| Coordinator | `api/services/orchestrator_coordinator.py` |
| Collection governor | `api/services/collection_governor.py` |
| Processing governor | `api/services/processing_governor.py` |
| Learning governor | `api/services/learning_governor.py` |
| Resource governor | `api/services/resource_governor.py` |
| Config loader | `api/config/orchestrator_governance.py` (loads `orchestrator_governance.yaml`) |
| State persistence | `api/services/orchestrator_state.py` or `api/data/orchestrator_state.db` + accessor module |
| API routes | `api/domains/system_monitoring/routes/orchestrator.py` or new `api/domains/orchestrator/routes.py` with prefix `/api/orchestrator` |
| Config YAML | `api/config/orchestrator_governance.yaml` |

If the team prefers a domain-style layout, governors and coordinator can live under `api/domains/orchestrator/` (e.g. `coordinator.py`, `collection_governor.py`) with routes in `api/domains/orchestrator/routes.py`, keeping `api/services/` for shared, non-domain services.

---

## 12. Success criteria (measurable)

- Fewer redundant or empty fetches (e.g. 50% reduction in empty RSS fetches where backoff is applied).
- Better resource efficiency (e.g. 30% improvement in LLM token use per unit of value, if measured).
- High breaking-news detection rate (e.g. 90%) when signals are integrated.
- Fast response to major events (e.g. &lt;5 min) when coordinator prioritizes them.
- Self-improving behavior: decision_log and learning_stats show pattern updates and threshold adjustments over time.
- Graceful degradation: if coordinator or a governor fails, existing AutomationManager and FinanceOrchestrator continue to run.

---

*This plan is the single reference for implementing the orchestrator system improvements. Implement in order of phases and check off items in ORCHESTRATOR_TODO.md.*
