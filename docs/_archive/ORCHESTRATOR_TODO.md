# Orchestrator System — To-Do List

> **Tied to:** [ORCHESTRATOR_DEVELOPMENT_PLAN.md](./ORCHESTRATOR_DEVELOPMENT_PLAN.md). Use this list for implementation order and tracking.  
> **Naming:** Follow [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md) (snake_case, PascalCase, existing paths).  
> **Last updated:** 2025-02-21.

---

## Phase 1: Foundation (Weeks 1–2)

### Config and state

- [x] Add `api/config/orchestrator_governance.yaml` with keys: `orchestrator.loop_interval_seconds`, `collection.*`, `processing.*`, `learning.*`, `resources.*` (all snake_case).
- [x] Add `api/config/orchestrator_governance.py` (or extend existing config module) with `get_orchestrator_governance_config()` returning a dict/object from the YAML.
- [x] Choose state backend: PostgreSQL schema `orchestrator` vs SQLite `api/data/orchestrator_state.db` → **SQLite** at `data/orchestrator_state.db`.
- [x] Create state tables (snake_case): `orchestrator_controller_state`, `orchestrator_source_profiles`, `orchestrator_learned_patterns`, `orchestrator_decision_history`, `orchestrator_performance_metrics`, `orchestrator_resource_usage`.
- [x] Add state accessor module (e.g. `api/services/orchestrator_state.py`) with functions: `get_controller_state()`, `save_controller_state()`, `update_source_profile()`, `append_decision_log()`, etc.

### OrchestratorCoordinator

- [x] Add `api/services/orchestrator_coordinator.py` with class `OrchestratorCoordinator`.
- [x] Implement primary loop: assess state → plan → execute highest-priority task → learn → update metrics → sleep (`loop_interval_seconds`). Use asyncio; non-blocking.
- [x] Implement `start()` / `stop()` (or `start_loop()` / `stop_loop()`) and wire into `main.py` lifespan (start after FinanceOrchestrator, stop on shutdown).
- [x] Load `orchestrator_governance.yaml` inside coordinator (or inject config); no hardcoded intervals.

### CollectionGovernor (basic)

- [x] Add `api/services/collection_governor.py` with class `CollectionGovernor`.
- [x] Implement interface used by coordinator: e.g. `get_next_action()` or `recommend_fetch(source_id)` and `record_fetch_result(source_id, success, observations_count)`.
- [x] Integrate with existing collectors: call `collect_rss_feeds()` (from `api/collectors/rss_collector.py`) when coordinator requests RSS collection; for finance, call `app.state.finance_orchestrator.submit_task(refresh, topic=gold)` or use existing API. No duplicate fetch logic.
- [x] Persist last collection times and simple source_profiles (e.g. last_empty_fetch_count, last_fetch_at) in orchestrator state tables.

### API and visibility

- [x] Add routes for status and metrics: e.g. `GET /api/orchestrator/status`, `GET /api/orchestrator/metrics`. Implement in `api/domains/system_monitoring/routes/orchestrator.py` (or new domain `api/domains/orchestrator/routes.py`) with prefix `/api/orchestrator`.
- [x] Include router in `main.py` so endpoints are reachable (included via system_monitoring router).

### Documentation and hygiene

- [x] Update [CONTROLLER_ARCHITECTURE.md](./CONTROLLER_ARCHITECTURE.md) to mention OrchestratorCoordinator and governors (and that they extend, not replace, existing controllers).
- [x] Add docstrings to `OrchestratorCoordinator` and `CollectionGovernor`; mention delegation to `FinanceOrchestrator`, `AutomationManager`, and `collect_rss_feeds`.

---

## Phase 2: Intelligence (Weeks 3–4)

### LearningGovernor

- [x] Add `api/services/learning_governor.py` with class `LearningGovernor`.
- [x] Implement pattern detection: read from `orchestrator_decision_history` and `orchestrator_performance_metrics`; write summaries or patterns to `orchestrator_learned_patterns` (e.g. source_patterns).
- [x] Implement feedback loop: outcomes already recorded in decision_history by coordinator.
- [x] Schedule pattern analysis every 30 cycles (~30 min at 60s) from coordinator; skip when `pause_learning` in state.

### ResourceGovernor

- [x] Add `api/services/resource_governor.py` with class `ResourceGovernor`.
- [x] Track LLM token usage and API call counts; persist in `orchestrator_resource_usage`. Coordinator records 1 api_call per collection action.
- [x] Implement budget checks: `can_run(task_type)` and `remaining_llm_budget()` using config.
- [x] Expose `get_budget_status()`; coordinator injects ResourceGovernor into CollectionGovernor for recommend_fetch(check_resources=True).

### CollectionGovernor (adaptive)

- [x] Implement backoff: exponential backoff for empty fetches (`_effective_interval_seconds` uses `last_empty_fetch_count` and `empty_fetch_penalty`).
- [x] Populate and use `orchestrator_source_profiles`: historical_update_times, average_interval_seconds updated in `record_fetch_result`.
- [x] Smart fetch decision: check ResourceGovernor.can_run("collection") when check_resources=True.

### ProcessingGovernor

- [x] Add `api/services/processing_governor.py` with class `ProcessingGovernor`.
- [x] Implement delegation: `get_processing_status()`, `trigger_finance_analysis(query, topic, priority)`.
- [x] Value-based prioritization: priority param (high/medium/low) passed to `submit_task`.

### API and decision log

- [x] Add `GET /api/orchestrator/decision_log` (paginated: limit, offset, since).
- [x] Add `GET /api/orchestrator/learning_stats` (pattern counts, recent sample).
- [x] Add `POST /api/orchestrator/manual_override` (action: force_collect_now, pause_learning, resume_learning; source for force_collect_now).

---

## Phase 3: Advanced (Weeks 5–6)

### Predictions and tuning

- [x] Implement optional prediction engine in LearningGovernor: `get_predictions()` returns next_source_updates (from source_profiles + average_interval), breaking_news_likelihood placeholder. Exposed via `GET /api/orchestrator/predictions`.
- [x] Multi-objective tuning: `config_overrides` in controller_state; CollectionGovernor reads `min_fetch_interval_seconds`, `max_fetch_interval_seconds`, `empty_fetch_penalty` from overrides. `POST /api/orchestrator/manual_override` action `set_config_override` with body `config_overrides: { ... }` (allowed keys: min_fetch_interval_seconds, max_fetch_interval_seconds, empty_fetch_penalty).

### Dashboard and observability

- [x] Add `GET /api/orchestrator/dashboard` (query param decision_log_limit): status, decision_log, learning_stats, predictions, recent_metrics, recent_resource_usage.
- [x] Orchestrator metrics exposed at `GET /api/orchestrator/metrics` and `GET /api/orchestrator/dashboard`; system_monitoring has its own PostgreSQL metrics at `GET /api/system_monitoring/metrics`.

### Performance and docs

- [x] Primary loop uses run_in_executor for RSS (non-blocking); pattern analysis every 30 cycles; config in YAML.
- [x] ORCHESTRATOR_TODO and ORCHESTRATOR_DEVELOPMENT_PLAN updated with Phase 3 deliverables.

---

## Ongoing (any phase)

- [ ] No new "Enhanced" or "Unified" duplicate services; all new code extends or coordinates existing `FinanceOrchestrator`, `AutomationManager`, `collect_rss_feeds`, and evidence pipeline.
- [ ] All new modules use snake_case filenames, PascalCase class names, snake_case functions/variables/tables/columns.
- [ ] New API routes use prefix `/api` (or `/api/orchestrator`) and snake_case path segments.
- [ ] State and config keys stay snake_case; intervals in seconds in config.

---

*Check off items as completed; refer to ORCHESTRATOR_DEVELOPMENT_PLAN.md for rationale and architecture.*
