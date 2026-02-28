# News Intelligence — Logging System Summary

## Executive Summary

The project uses multiple logging layers: a centralized component-based logger (NewsIntelligenceLogger), a newer standardized activity logger for API/RSS/orchestrator events, a pipeline trace logger for ML workflows, a frontend logging service with remote submission, and domain-specific evidence ledgers. Logs are written to `logs/` with per-component files and rotating handlers.

**Planned additions** (see §6.5 and §8): LLM interaction ledger, orchestrator decision graph, task execution traces (span tree), and a trace viewer UI — to capture *why* decisions were made, not just *what* happened.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOGGING LANDSCAPE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  FRONTEND (web)                                                          │
│  ├── loggingService.ts  → buffer + POST /api/v4/.../logs                 │
│  └── utils/logger.ts    → console (DEV only), no remote                  │
├─────────────────────────────────────────────────────────────────────────┤
│  BACKEND (api)                                                           │
│  ├── Activity Logger (shared/logging/)     → logs/activity.log, .jsonl  │
│  ├── LLM Logger (planned)                 → logs/llm_interactions.jsonl   │
│  ├── Decision Logger (planned)           → logs/orchestrator_decisions.jsonl │
│  ├── Trace Logger (planned)               → logs/task_traces.jsonl       │
│  ├── NewsIntelligenceLogger (config)       → logs/*.log, *_structured.json│
│  ├── Pipeline Logger (services/)          → logs/pipeline_trace.log + DB │
│  ├── Log Storage Service (services/)      → logs/log_analysis.db         │
│  └── Error Handler (middleware)           → error logger                 │
├─────────────────────────────────────────────────────────────────────────┤
│  AUDIT (separate from logs)                                              │
│  └── Finance evidence_ledger.db          → provenance, not logging      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Backend Logging Systems

### 2.1 NewsIntelligenceLogger (Primary Legacy)

**Location:** `api/config/logging_config.py`

**Components:** app, api, database, error, performance, ml, deduplication, rss, finance, security

**Per component:**
- Console handler (stdout)
- Rotating file (`logs/<component>.log`) — 10MB, 5 backups
- Rotating JSON (`logs/<component>_structured.json`)

**Usage:** `get_component_logger("finance")` → `news_intelligence.finance` logger

**Note:** The finance orchestrator’s `orchestrator_logger.py` uses `logging.getLogger("finance.orchestrator")`, which is not a child of `news_intelligence.finance`. Its output may go to root/console rather than `finance.log`.

### 2.2 Activity Logger (Standardized, New)

**Location:** `api/shared/logging/activity_logger.py`

**Purpose:** Unified schema for API requests, RSS pulls, orchestrator queue decisions.

**Outputs:** `logs/activity.log`, `logs/activity.jsonl`

**Schema:** `{ timestamp, component, event_type, status, ...event_fields }`

**Events:**
| Event           | Component   | When                          |
|-----------------|------------|-------------------------------|
| request         | api        | Every HTTP request (middleware) |
| feed_pull       | rss        | Every RSS fetch               |
| queue_decision  | orchestrator | Every task submitted        |

**Wired:** main_v4 middleware, news_aggregation process_rss_feeds, services/rss/fetching, collectors/rss_collector, finance orchestrator submit_task.

### 2.3 Pipeline Logger

**Location:** `api/services/pipeline_logger.py`

**Purpose:** Trace RSS feeds and articles through ML pipeline stages.

**Outputs:** `logs/pipeline_trace.log`, optional DB storage.

**Stages:** RSS_FEED_FETCH, ARTICLE_EXTRACTION, DEDUPLICATION, ML_SUMMARIZATION, etc.

**Used by:** RSS processing module, automation flows.

### 2.4 Log Storage Service

**Location:** `api/services/log_storage_service.py`

**Purpose:** Log analysis, retention, rotation, compression.

**Outputs:** `logs/log_analysis.db` (SQLite), compressed archives.

### 2.5 Error Handler

**Location:** `api/middleware/error_handling.py`

**Purpose:** Centralized exception handling, context capture, logging.

**Logger:** `get_component_logger('error')` → `errors.log`, `errors_structured.json`.

### 2.6 Finance Orchestrator Logger

**Location:** `api/domains/finance/orchestrator_logger.py`

**Events:** TASK_ACCEPTED, TASK_PLANNED, WORKER_DISPATCHED, WORKER_COMPLETED, EVAL_PASSED/FAILED, etc.

**Output:** JSON payload via `LOG` → may hit root/console; also calls `log_queue_decision` → activity.jsonl.

---

## 3. Frontend Logging

### 3.1 LoggingService (`web/src/services/loggingService.ts`)

- Session/user context, log levels, buffering.
- Sends errors/warnings to `/api/v4/system_monitoring/logs` in production.
- **Gap:** POST `/logs` and `/logs/batch` endpoints do not exist; remote logs are not persisted.
- Flushes buffer every 30s and on beforeunload.
- Sanitizes sensitive fields (password, token, etc.).

### 3.2 Logger (`web/src/utils/logger.ts`)

- Simple static methods (info, error, warn, debug).
- DEV: console only. Production: commented placeholders for remote.
- Not wired to LoggingService.

---

## 4. Configuration

| Setting       | Source              | Default   |
|---------------|---------------------|-----------|
| LOG_LEVEL     | os.environ          | INFO      |
| LOG_DIR       | config.paths        | PROJECT_ROOT/logs |
| LOG_LLM_FULL_TEXT | os.environ (planned) | false (prod), true (dev) |
| max_file_size | NewsIntelligenceLogger | 10MB  |
| backup_count  | NewsIntelligenceLogger | 5     |

---

## 5. Evidence Ledger (Audit, Not Logging)

**Location:** `api/domains/finance/data/evidence_ledger.py`

**Store:** `data/finance/evidence_ledger.db` (SQLite)

**Purpose:** Provenance for finance domain: source fetches, status, timestamps. Used for compliance and audit, not general observability.

---

## 6. Missing Items & Industry Standards Gap Analysis

### 6.1 Already in Place ✅

- Structured JSON logging
- Log rotation (10MB, 5 backups)
- Request/response logging (API middleware)
- RSS fetch logging
- Orchestrator decision logging with rationale
- Error context (traceback, request info)
- Frontend error remoting
- Sensitive data sanitization (frontend)
- Timestamp on all entries
- Separate error logger

### 6.2 Gaps & Recommendations

| Gap | Industry Standard | Recommendation |
|-----|-------------------|----------------|
| **Correlation IDs** | Request-scoped trace ID propagated across services | Add `X-Request-ID` (or similar) in middleware; include in all backend logs and activity entries. Frontend can send same ID. |
| **Log levels in activity** | Severity (INFO/WARN/ERROR) for filtering | Add `level` to activity schema; set `error` for 4xx/5xx, `warn` for slow requests. |
| **User/session identity** | User ID in logs for audit | Pass optional `user_id`/`session_id` through middleware; include in `log_api_request`. |
| **External API calls** | Log outbound HTTP (FRED, EDGAR, freegoldapi) | Add `log_external_call(url, status, duration)` to activity logger; instrument data source adapters. |
| **Database query logging** | Slow-query and error logging | Use `log_database_operation` from NewsIntelligenceLogger where DB is used; ensure it is actually called. |
| **LLM/GPU usage** | Log model, tokens, latency | Add `log_llm_call(model, tokens_in, tokens_out, duration_ms)`; instrument finance llm.py and shared LLM service. |
| **Startup/shutdown** | Structured lifecycle events | Log app start/stop with version, config hash; use activity logger or app logger. |
| **Sampling for high volume** | Avoid log explosion | Sample DEBUG/INFO at high rates; never sample ERROR. Document policy in LOGGING.md. |
| **Centralized log aggregation** | ELK, Loki, Datadog, etc. | Document that activity.jsonl is intended for export/ingestion; add note on tailing/parsing. |
| **Log retention policy** | Automated cleanup | LogStorageService has retention; verify it runs. Document retention in config. |
| **Orchestrator logger routing** | All finance logs in finance files | Change `orchestrator_logger.LOG` to use `get_component_logger("finance")` or add `finance.orchestrator` to logger hierarchy. |
| **Request ID propagation** | End-to-end tracing | Generate UUID in middleware; add to Request.state; use in all downstream logs. |
| **Health check logging** | Avoid noise from /health | Exclude health checks from activity logging, or log at DEBUG only. |
| **Security events** | Auth failures, rate limits | Use security_logger for auth/rate-limit events; ensure it’s invoked. |

| **Frontend log ingestion** | Persist client errors remotely | Add POST `/api/v4/system_monitoring/logs` and `/logs/batch`; store in activity.jsonl or errors.log. |

### Log Archive to NAS (2x/day)

Local JSONL logs are moved to the NAS PostgreSQL database twice daily (6 AM, 6 PM) to avoid filling local disk.

**Migration:** `api/database/migrations/139_log_archive_tables.sql` — creates `log_archive` table.

**Script:** `scripts/log_archive_to_nas.py` — reads activity.jsonl, llm_interactions.jsonl, orchestrator_decisions.jsonl, task_traces.jsonl; inserts into PostgreSQL; truncates local files.

**Cron setup:** `./scripts/setup_log_archive_cron.sh`

**Prerequisite:** SSH tunnel must be running (`./scripts/setup_nas_ssh_tunnel.sh` or `start_system.sh`). Uses `DB_*` from `.env`.

**First-time:** Run migration 139, then setup cron:
```bash
cd api && python scripts/run_migration_139.py
./scripts/setup_log_archive_cron.sh
```

### 6.3 Redundancy

- **Duplicate API logging:** NewsIntelligenceLogger has `log_api_request`; activity logger also logs API requests via middleware. Prefer activity logger as canonical; deprecate or redirect the other.
- **RSS logs in multiple places:** activity.jsonl, rss_processing.log, pipeline_trace.log. activity.jsonl is the canonical feed-level record; others can remain for pipeline/debug detail.

### 6.4 Priority Fixes

1. **Request ID:** Add `X-Request-ID` in middleware and propagate through logs.
2. **Orchestrator logger:** Route `finance.orchestrator` into finance log files.
3. **External API logging:** Log all outbound calls (FRED, EDGAR, etc.) with URL, status, duration.
4. **Exclude health checks:** Do not log `/health` (and similar) to activity, or log at DEBUG.
5. **Document retention:** State retention period and how LogStorageService is triggered.
6. **Frontend log endpoint:** Implement POST `/api/v4/system_monitoring/logs` and `/logs/batch` so client errors are persisted.

### 6.5 Log Analysis Recommendations (LLM & Orchestrator Observability)

*From log analysis: focus on capturing* why *decisions were made, not just* what *happened.*

**Core problem:** Orchestrator logs events (TASK_ACCEPTED, WORKER_COMPLETED, EVAL_PASSED) as a state-machine journal. They don't capture the reasoning at each transition — what alternatives existed, why one path was chosen, how quality of outputs shaped downstream decisions.

#### Layer 1: LLM Interaction Ledger

**New file:** `api/shared/logging/llm_logger.py` → `logs/llm_interactions.jsonl`

**Schema:** Every LLM call produces a structured record with:
- `interaction_id`, `task_id`, `request_id`, `phase`, `worker`
- **Input:** `model`, `prompt_template_id`, `prompt_hash`, `system_prompt_hash`, `input_token_count`, `context_documents` (RAG/evidence injected)
- **Output:** `output_token_count`, `response_hash`, `latency_ms`, `finish_reason`
- **Quality:** `self_eval_score`, `downstream_eval_score`, `eval_criteria`
- **Cost:** `estimated_cost_usd`
- **Optional (configurable):** `prompt_text`, `response_text` — via `LOG_LLM_FULL_TEXT` env (on in dev, off in prod)

**Implementation:** `@track_llm_call` decorator; wrapper between workers and LLM client. Instrument `finance/llm.py` and shared LLM service.

#### Layer 2: Orchestrator Decision Graph

**New file:** `api/shared/logging/decision_logger.py` → `logs/orchestrator_decisions.jsonl`

**Schema:** Decision record at every branching point:
- `decision_id`, `task_id`, `decision_point` (worker_selection | eval_gate | retry_policy | source_selection)
- **State:** `current_phase`, `elapsed_ms`, `iterations_so_far`, `available_options`
- **Choice:** `chosen_option`, `rationale`, `decision_inputs` (eval_score, threshold, failed_sources, etc.)
- **Outcome (backfilled):** `outcome_status`, `outcome_duration_ms`

**Implementation:** `log_decision()` at branching points; `log_decision_outcome(decision_id, status, duration)` when work completes. Instrument finance orchestrator.

#### Layer 3: Task Execution Trace (Span Tree)

**New file:** `api/shared/logging/trace_logger.py` → `logs/task_traces.jsonl`

**Schema:** Span model (OpenTelemetry-style, simplified):
- `span_id`, `parent_span_id`, `task_id`, `span_type` (phase | llm_call | data_fetch | decision | evaluation)
- `name`, `start_time`, `end_time`, `duration_ms`, `status`
- `attributes`, `linked_ids` (interaction_id, decision_id, evidence_refs)

**Implementation:** `SpanContext` context manager. Reconstruct trace from spans for a `task_id`; enables timeline, causal chain, cross-references.

#### Trace Viewer Page

**Route:** `/finance/trace/:taskId` (or under monitoring page)

**Purpose:** Visual timeline — Gantt-style chart (phases, LLM calls, decisions, eval gates). Click for detail. Recharts/D3.

#### What This Enables

- **Prompt regression detection:** Compare eval scores per prompt template before/after changes
- **Bottleneck identification:** Where time goes; cost/benefit of data sources
- **Revision loop diagnosis:** What failed at each eval gate; patterns in verification failures
- **Evidence retrieval quality:** Compare context_documents vs citations; detect hallucination vs over-fetch
- **Cost attribution:** Cost per task, phase, revision loop
- **Architecture experimentation:** Decision-outcome dataset for counterfactual analysis

#### Integration

- All three loggers use `log_activity()` and write to `activity.jsonl` (event types: `llm_interaction`, `orchestrator_decision`, `task_span`)
- Also write to dedicated files for easier querying
- Config: `LOG_LLM_FULL_TEXT` for prompt/response text (dev: on, prod: off, task-flag override for specific debug)

#### Log Analysis: What to Prioritize from Existing Gaps

| Priority | Item | Rationale |
|----------|------|-----------|
| High | Correlation IDs | Links frontend actions to backend task traces |
| High | External API logging | Data fetch failures/latencies major factor in task quality |
| Defer | Health check exclusion | Nice cleanup, doesn't affect diagnosis |
| Defer | Security event logging | Production concern, not architecture improvement |
| Defer | Centralized aggregation | JSONL + jq/grep sufficient until volume justifies |

---

## 7. File Inventory

| File | Purpose |
|------|---------|
| logs/activity.log | Canonical activity (API, RSS, orchestrator) |
| logs/activity.jsonl | Same, JSONL for parsing |
| logs/app.log | Application events |
| logs/api.log | Legacy API events |
| logs/database.log | DB operations |
| logs/errors.log | Errors with context |
| logs/performance.log | Performance metrics |
| logs/ml_processing.log | ML pipeline |
| logs/deduplication.log | Deduplication |
| logs/rss_processing.log | RSS processing |
| logs/finance.log | Finance domain |
| logs/security.log | Security events |
| logs/pipeline.log | settings.LOG_FILE reference |
| logs/pipeline_trace.log | PipelineLogger |
| logs/*_structured.json | JSON versions of above |
| logs/log_analysis.db | LogStorageService analysis |
| logs/llm_interactions.jsonl | *Planned* — LLM interaction ledger |
| logs/orchestrator_decisions.jsonl | *Planned* — Orchestrator decision graph |
| logs/task_traces.jsonl | *Planned* — Span-based task traces |

---

## 8. Comprehensive Implementation Plan

*Single update to implement all logging improvements.*

### Phase 0: Foundation (Do First)

| Task | Effort | Dependencies |
|------|--------|--------------|
| Fix orchestrator logger routing | Small | None — one-line change to use `get_component_logger("finance")` |
| Add `X-Request-ID` in middleware | Small | None — generate UUID, add to Request.state, include in log_api_request |
| Add `LOG_LLM_FULL_TEXT` and `LOG_DIR` to config | Small | None |

### Phase 1: Activity & Observability Infrastructure

| Task | Effort | Dependencies |
|------|--------|--------------|
| Add `log_external_call()` to activity logger | Small | Phase 0 |
| Instrument FRED, EDGAR, freegoldapi adapters | Medium | Phase 1 (log_external_call) |
| Exclude `/health` (and similar) from activity logging | Small | None |
| Implement POST `/api/v4/system_monitoring/logs` and `/logs/batch` | Medium | None |
| Add `level` to activity schema; user_id/session_id optional | Small | Phase 0 |
| Document retention policy and LogStorageService trigger | Small | None |

### Phase 2: LLM Interaction Ledger

| Task | Effort | Dependencies |
|------|--------|--------------|
| Create `api/shared/logging/llm_logger.py` | Medium | Phase 0 |
| Implement `log_llm_interaction()` + `@track_llm_call` decorator | Medium | Phase 2 |
| Wire into `finance/llm.py` and shared LLM service | Medium | Phase 2 |
| Add event type `llm_interaction` to activity logger | Small | Phase 2 |
| Optional: SQLite table for llm_interactions queryability | Medium | Phase 2 |

### Phase 3: Orchestrator Decision Graph

| Task | Effort | Dependencies |
|------|--------|--------------|
| Create `api/shared/logging/decision_logger.py` | Medium | Phase 0 |
| Implement `log_decision()`, `log_decision_outcome()` | Medium | Phase 3 |
| Instrument orchestrator at branching points (eval_gate, worker_selection, retry_policy, source_selection) | Large | Phase 3 |
| Add event type `orchestrator_decision` to activity logger | Small | Phase 3 |

### Phase 4: Task Execution Trace (Span Tree)

| Task | Effort | Dependencies |
|------|--------|--------------|
| Create `api/shared/logging/trace_logger.py` | Medium | Phase 0 |
| Implement `SpanContext` context manager + span model | Medium | Phase 4 |
| Instrument orchestrator phases (planning, data_collection, synthesis, verification, revision) | Large | Phase 2, 3 |
| Add event type `task_span` to activity logger | Small | Phase 4 |
| Trace reconstruction script (spans → tree by task_id) | Medium | Phase 4 |

### Phase 5: Trace Viewer UI

| Task | Effort | Dependencies |
|------|--------|--------------|
| Add route `/finance/trace/:taskId` or monitoring subpage | Medium | Phase 4 |
| Fetch spans for task_id; assemble tree | Medium | Phase 4 |
| Render Gantt-style timeline (Recharts/D3) | Large | Phase 5 |
| Click-to-detail for spans, LLM calls, decisions | Medium | Phase 5 |

### Phase 6: Cleanup & Documentation

| Task | Effort | Dependencies |
|------|--------|--------------|
| Deprecate duplicate API logging (NewsIntelligenceLogger.log_api_request) | Small | Phase 1 |
| Wire `utils/logger.ts` to LoggingService where appropriate | Small | Phase 1 |
| Update LOGGING.md with new schemas, config, query examples | Small | All phases |
| Verify LogStorageService retention runs; add to startup/scheduler | Small | Phase 1 |

### Suggested File Structure After Implementation

```
api/shared/logging/
├── __init__.py
├── activity_logger.py      # existing + log_external_call
├── llm_logger.py           # NEW
├── decision_logger.py      # NEW
└── trace_logger.py         # NEW

logs/
├── activity.log / .jsonl
├── llm_interactions.jsonl
├── orchestrator_decisions.jsonl
├── task_traces.jsonl
└── ... existing ...
```

### Order of Execution

1. **Phase 0** — unblocks everything
2. **Phase 1** — quick wins, fixes existing gaps
3. **Phase 2** — LLM ledger (highest value for prompt/retrieval diagnosis)
4. **Phase 3** — Decision graph (architectural insights)
5. **Phase 4** — Span tree (ties 2 + 3 together)
6. **Phase 5** — Trace viewer (makes it usable)
7. **Phase 6** — polish

---

## 9. Quick Reference

**Log an API request:** Middleware (automatic).

**Log an RSS pull:** `log_rss_pull()` from `shared.logging.activity_logger` (already wired in fetch paths).

**Log orchestrator decision:** `log_queue_decision()` (called from `submit_task`).

**Log generic activity:** `log_activity(component, event_type, status, message=..., **detail)`.

**Log to component file:** `get_component_logger("finance").info(...)`.

**Trace a task:** `grep <task_id> logs/activity.jsonl` or `logs/finance.log`.
