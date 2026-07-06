# Pipeline tuning registry

Canonical map of **who reads what**, known **conflicts**, and **defunct** knobs after multiple dev cycles.

**Precedence (highest wins):** explicit env var → `orchestrator_governance.yaml` (`pipeline_controller`, `pipeline_conductor`) → code default.

**Not authoritative:** `self.schedules[phase].interval` — display/fallback only; **PipelineController** enqueues from backlog counters.

---

## 1. Schedulers (v10.1)

| Layer | Trigger | What it schedules |
|-------|---------|-----------------|
| **PipelineController** | Worker done → `notify_worker_done()` → replan | Processing phases from backlog + lane/host caps |
| **AutomationManager** | Controller `reconcile_and_enqueue` | Runs queued tasks; standalone `health_check` loop |
| **OrchestratorCoordinator** | 60s loop (when controller absent for collection) | RSS/finance collection; finance interest analysis |
| **NRI mention resolver** | In-process **`mention_resolution`** phase | CEM drain (external timer retired) |

**Conductor config:** `pipeline_conductor` in YAML — post-collection kickoff, external scheduler docs. See `api/services/pipeline_conductor_service.py`.

---

## 2. AutomationManager — caps & gates

| Env | Default | Purpose | Notes |
|-----|---------|---------|-------|
| `AUTOMATION_MAX_CONCURRENT_TASKS` | 12 | Phase worker pool size | Main throughput cap |
| `AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE` | 1 | Queued duplicates per phase | Prevents asyncio queue explosion |
| `AUTOMATION_PER_PHASE_CONCURRENT_CAP` | 2 | Same phase parallel runs | Long GPU drain occupies cap |
| `AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES` | — | e.g. `claim_extraction:1` | |
| `AUTOMATION_QUEUE_SOFT_CAP` | **0** (off) | Pause enqueue when deep queue | Prefer caps above |
| `AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED` | true | Defer replans when worker pool hot | See `connection.automation_db_pool_should_defer_phase` |
| `AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD` | 0.82 | Pool util threshold | |
| `COLLECTION_THROTTLE_PENDING_THRESHOLD` | 1200 | Block `collection_cycle` when downstream heavy | |
| `COLLECTION_CYCLE_INTERVAL_SECONDS` | 7200 | yaml `collection_cycle.interval_seconds` | Controller gates on backlog |
| `AUTOMATION_DISABLED_SCHEDULES` | — | Comma-separated phase disable list | |
| `PIPELINE_BACKFILL_MODE` | false | Pause RSS/docs during catch-up | |

### Time windows (hard gates — override everything)

| Env | Effect |
|-----|--------|
| `PIPELINE_SCHEDULE_TZ` / `NIGHTLY_PIPELINE_TZ` | Local TZ |
| `PIPELINE_NIGHTLY_*` / `NIGHTLY_PIPELINE_*` | 00:00–07:00 nightly heavy |
| `PIPELINE_DAYTIME_*` | Mon–Fri 07:00–16:00 |
| `PIPELINE_QUIET_ALLOWED_PHASES` | Only these run in quiet (weekends/evenings) |
| `NIGHTLY_PIPELINE_EXCLUSIVE` | **Default on** — daytime blocks most phases; only nightly drain |
| `NIGHTLY_UNIFIED_PIPELINE_ENABLED` | false → no unified nightly window |

---

## 3. Per-phase throughput (batch + drain)

| Phase | Batch size env | Drain budget env | Service notes |
|-------|----------------|------------------|---------------|
| `entity_extraction` | `ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN` (40) | `ENTITY_EXTRACTION_RUN_BUDGET_SECONDS` (900) | `ENTITY_EXTRACTION_PARALLEL`, `POST_SYNC` |
| `ml_processing` | `ML_PROCESSING_BATCH_LIMIT` (50/domain) | `ML_PROCESSING_RUN_BUDGET_SECONDS` (900) | Queues `ml_processing_queue` only |
| `sentiment_analysis` | `SENTIMENT_ANALYSIS_BATCH_LIMIT` (100/domain) | `SENTIMENT_ANALYSIS_RUN_BUDGET_SECONDS` (900) | Inline LLM |
| `claim_extraction` | `CLAIM_EXTRACTION_BATCH_LIMIT` | `CLAIM_EXTRACTION_DRAIN_MAX_SECONDS` (**900**) | `CLAIM_EXTRACTION_DRAIN=true` default; internal drain loop |
| `claims_to_facts` | `CLAIMS_TO_FACTS_BATCH_LIMIT` | `CLAIMS_TO_FACTS_DRAIN_MAX_SECONDS` (**900**) | `CLAIMS_TO_FACTS_DRAIN` |

**Monitor mismatch:** `backlog_metrics._per_run_batch_size()` now reads live env for `unified_intake_extraction`, `entity_profile_build`, `entity_dossier_compile`, and `event_tracking`. Legacy `BATCH_SIZE_PER_TASK` entries remain fallbacks for other phases.

### Assembly conductor drain loops (v10.1+)

When `ASSEMBLY_PIPELINE_MODE=ordered`, batch-capable phases loop until cycle budget or stall:

| Phase | Cycle budget env | Batch env |
|-------|------------------|-----------|
| `entity_profile_build` | `ASSEMBLY_ENTITY_PROFILE_BUILD_CYCLE_BUDGET_SECONDS` (600) | `ENTITY_PROFILE_BUILD_LIMIT` |
| `entity_dossier_compile` | `ASSEMBLY_ENTITY_DOSSIER_COMPILE_CYCLE_BUDGET_SECONDS` (600) | `ENTITY_DOSSIER_COMPILE_MAX` |
| `event_tracking` | `ASSEMBLY_EVENT_TRACKING_CYCLE_BUDGET_SECONDS` (120) | `EVENT_TRACKING_ASSEMBLY_BATCH_LIMIT` / `EVENT_TRACKING_ASSEMBLY_BATCH_MAX` (300) |
| `graph_connection_distillation` | `ASSEMBLY_GRAPH_CONNECTION_DISTILLATION_CYCLE_BUDGET_SECONDS` (60) | processor default |

**Automation drain (v10.1+):** When `ENTITY_PROFILE_BUILD_DRAIN=true` (default), each scheduled `entity_profile_build` task loops batches until idle or `ENTITY_PROFILE_BUILD_RUN_BUDGET_SECONDS` / assembly cycle budget. Parallel in-flight profiles: `ENTITY_PROFILE_BUILD_PARALLEL` (default 3). First-pass (empty sections) uses fast single-LLM path (`ENTITY_PROFILE_BUILD_FAST_CONTEXT_LIMIT`, default 15); refresh builds use full iterative path (`ENTITY_PROFILE_BUILD_FULL_CONTEXT_LIMIT`, default 75).

| Env | Default | Purpose |
|-----|---------|---------|
| `ENTITY_PROFILE_BUILD_DRAIN` | `true` | Multi-batch drain per scheduler task |
| `ENTITY_PROFILE_BUILD_PARALLEL` | `3` | Concurrent profiles per batch |
| `ENTITY_PROFILE_BUILD_FAST_CONTEXT_LIMIT` | `15` | Context cap for first_pass (single LLM) |
| `ENTITY_PROFILE_BUILD_FULL_CONTEXT_LIMIT` | `75` | Context cap for refresh builds |
| `ENTITY_PROFILE_BUILD_PRIORITY_FIRST_PASS` | `true` | Dequeue empty-section profiles first |
| `ENTITY_PROFILE_BUILD_ITERATIVE_MIN_CONTEXTS` | `30` | Iterative chunking only on refresh path above this count |
| `ENTITY_PROFILE_BUILD_RUN_BUDGET_SECONDS` | `0` (unlimited) | Optional automation task wall-clock cap |

Dossier defer: `ASSEMBLY_DEFER_DOSSIER_PROFILE_FIRST_PASS` (default 8000) uses profile **first-pass** count; dossier **retry** backlog above that threshold can still run compile.

### Adaptive batch policy (`api/shared/adaptive_batch_policy.py`)

| Env | Default | Purpose |
|-----|---------|---------|
| `AUTOMATION_ADAPTIVE_BATCH_ENABLED` | true when `PIPELINE_BACKFILL_MODE=true` | Headroom-based batch tuning |
| `ADAPTIVE_BATCH_INCREASE_HEADROOM` | 0.50 | Raise batch when headroom ≥ this |
| `ADAPTIVE_BATCH_DECREASE_HEADROOM` | 0.25 | Lower batch when headroom < this |

Persists last tuned batch per phase in `public.automation_state` (`adaptive_batch:{phase}`). Wired into spine enrichment, unified intake, and assembly drain phases.

---

## 4. Backlog / pass markers

| Env | Default | Purpose |
|-----|---------|---------|
| `PIPELINE_BACKLOG_USE_PASS_MARKERS` | true | Pending = needs `metadata.pipeline.<phase>` |
| `<PHASE>_BACKLOG_USE_PASS_MARKER` | — | Per-phase override |
| `TOPIC_CLUSTERING_BACKLOG_USE_PASS_MARKER` | true | Separate from global |
| `TOPIC_CLUSTERING_ITERATIVE_REFINEMENT` | false | **Keep false** — true causes expensive churn |

---

## 5. orchestrator_governance.yaml — what is actually wired

| Section | Wired? | Consumer |
|---------|--------|----------|
| `collection.sources` | Yes | CollectionGovernor, OrchestratorCoordinator |
| `processing.phases.*.interval_seconds` | Display | Phase registry / Monitor (not enqueue driver) |
| `pipeline_conductor` | Yes | Post-collection kickoff, external scheduler docs |
| `pipeline_controller` | Yes | Run budgets, host balance, lane caps, post-collection phases |
| `resources.daily_llm_tokens` | Partial | Blocks orchestrator **analysis/synthesis** only |
| `entity_tracking.enabled` | Yes | Coordinator dossier compile (default false in yaml) |

---

## 6. Defunct or legacy (safe to ignore)

| Knob | Why |
|------|-----|
| `analysis_pipeline.*` | Removed — v8 analysis-window scheduling retired |
| `pipeline_orchestration_harmony` | Module deleted; budgets moved to `pipeline_controller` |
| `AUTOMATION_SCHEDULER_TICK_SECONDS` | Legacy scheduler loop |
| `AUTOMATION_GAP_FILL_ENABLED` / `AUTOMATION_HARMONY_*` | Harmony module deleted |
| `WORKLOAD_BALANCER_ENABLED` | `workload_balancer.py` deleted |
| `AUTOMATION_MAX_REQUEUE_PER_WINDOW` | Continuous self re-queue retired |
| `orchestrator_processing_nudge_enabled` | Orchestrator `request_phase` nudge retired |
| `PIPELINE_CONDUCTOR_ORCHESTRATOR_NUDGE` | Same |
| `AUTOMATION_SCHEDULE` (cron string in env.example) | Not read by AutomationManager |
| `CELERY_*` | No Celery worker in NI API |
| `ENRICHMENT_BACKLOG_FIRST_*` | Removed from automation_manager |
| `articles.entities` jsonb | Unused; entities in `article_entities` |
| `processing_status` on articles | Never updated by extraction; use pass markers |

---

## 7. NRI (separate repo / systemd)

| Env / unit | Default | Notes |
|------------|---------|-------|
| Timer | `*:0/5` | Was 15 min |
| `NRI_MENTION_RESOLVE_BATCH_LIMIT` | 500 | Per inner batch |
| `NRI_MENTION_RESOLVE_BUDGET_SECONDS` | 240 | Per timer tick drain |

Not controlled by NI AutomationManager.

---

## 8. Recommended “single panel” env (Widow catch-up)

Set only these unless debugging one phase:

```bash
# Global concurrency + adaptive batches
AUTOMATION_MAX_CONCURRENT_TASKS=12
AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING=false
AUTOMATION_PER_PHASE_CONCURRENT_CAP=3
AUTOMATION_ADAPTIVE_BATCH_ENABLED=true

# Unified intake (spine bottleneck)
UNIFIED_INTAKE_EXTRACTION_ARTICLES_PER_DOMAIN=60
UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE=3
UNIFIED_INTAKE_EXTRACTION_PARALLEL=10

# Assembly throughput
EVENT_TRACKING_ASSEMBLY_BATCH_LIMIT=150
EVENT_TRACKING_ASSEMBLY_BATCH_MAX=300
ENTITY_PROFILE_BUILD_LIMIT=100
ENTITY_PROFILE_BUILD_PARALLEL=3
ENTITY_PROFILE_BUILD_DRAIN=true
ENTITY_PROFILE_BUILD_FAST_CONTEXT_LIMIT=15
ENTITY_PROFILE_BUILD_PRIORITY_FIRST_PASS=true
ENTITY_DOSSIER_COMPILE_MAX=80
ASSEMBLY_CONDUCTOR_IDLE_SECONDS=30
ASSEMBLY_ENTITY_PROFILE_BUILD_CYCLE_BUDGET_SECONDS=600
ASSEMBLY_ENTITY_DOSSIER_COMPILE_CYCLE_BUDGET_SECONDS=600
SPINE_CONDUCTOR_IDLE_SECONDS=15

# Throughput
ENTITY_EXTRACTION_RUN_BUDGET_SECONDS=1800
SENTIMENT_ANALYSIS_RUN_BUDGET_SECONDS=1800
CLAIM_EXTRACTION_DRAIN_MAX_SECONDS=1800

# Entity profile catch-up sprint (run_backlog_gpu_sprint.py --phase entity_profile_build)
# ENTITY_PROFILE_BUILD_ANYTIME=true
# ENTITY_PROFILE_BUILD_DRAIN=true
# ENTITY_PROFILE_BUILD_PARALLEL=4
# BACKLOG_SPRINT_ACTIVE=true
# BACKLOG_SPRINT_GPU_HOST=http://192.168.93.99:11434

# Scheduling — PipelineController replan drives throughput
AUTOMATION_PER_PHASE_CONCURRENT_CAP=3
AUTOMATION_ADAPTIVE_BATCH_ENABLED=true

# Windows (don’t fight nightly)
# NIGHTLY_PIPELINE_EXCLUSIVE=1  # leave on; rely on nightly drain + daytime budgets

# Hygiene
# One line only:
# AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush,claims_to_facts,pattern_recognition
```

---

## 9. Docs cross-reference

| Doc | Topic |
|-----|-------|
| [PIPELINE_ORCHESTRATION_HARMONY.md](PIPELINE_ORCHESTRATION_HARMONY.md) | Retired harmony pointer + v10.1 scheduling map |
| [RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md](RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md) | DB pool + Ollama caps |
| [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) | Phase catalog |
| [configs/env.example](../configs/env.example) | Full env comment index (some defaults stale — trust this registry + code) |

---

## 10. Known ops issues (Widow, Jun 2026)

1. **Duplicate `AUTOMATION_DISABLED_SCHEDULES`** in `/opt/news-intelligence/.env` — merge to one line.
2. **Harmony/drain envs not in prod .env** — using code defaults (900s) after recent deploy.
3. **`claims_to_facts` disabled in schedules** — promotion only via nightly drain or manual `request_phase`.
