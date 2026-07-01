# Pipeline tuning registry

Canonical map of **who reads what**, known **conflicts**, and **defunct** knobs after multiple dev cycles.

**Precedence (highest wins):** explicit env var → `orchestrator_governance.yaml` (harmony section only) → code default.

**Not authoritative:** `self.schedules[phase].interval` in AutomationManager when `USE_WORKLOAD_DRIVEN_ORDER=true` and phase has pending work (interval is fallback when idle only).

---

## 1. Three schedulers (single config: `pipeline_conductor`)

| Layer | Tick | What it schedules | Backlog-aware? |
|-------|------|-------------------|----------------|
| **AutomationManager** | `AUTOMATION_SCHEDULER_TICK_SECONDS` (5s) | All `self.schedules` phases + gap-fill | Yes — primary when `automation_primary: true` |
| **OrchestratorCoordinator** | `orchestrator.loop_interval_seconds` (60s) | RSS/finance collection + optional `request_phase` nudge | Only when `orchestrator_processing_nudge_enabled: true` (default **false**) |
| **NRI mention resolver** | systemd timer (5 min) | `resolve_drain` on CEM backlog | Documented in `pipeline_conductor.external_schedulers` |

**Conductor env:** `PIPELINE_CONDUCTOR_AUTOMATION_PRIMARY` (default true), `PIPELINE_CONDUCTOR_ORCHESTRATOR_NUDGE` (default false). See `api/services/pipeline_conductor_service.py`.

**Interference (mitigated):** With nudge disabled (default), ProcessingGovernor returns None and coordinator does not duplicate `request_phase`. ResourceGovernor `can_run("processing")` only checks **API calls/hour**, not LLM tokens.

---

## 2. AutomationManager — scheduling & caps

| Env | Default | Purpose | Conflicts / notes |
|-----|---------|---------|-------------------|
| `AUTOMATION_SCHEDULER_TICK_SECONDS` | 5 | Scheduler loop | × many phases = high DB load on backlog refresh |
| `AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS` | 10 | Min re-enqueue when pending | Overridden by **harmony** (fraction of measured duration) |
| `AUTOMATION_HARMONY_USE_MEASURED_DURATION` | true | Duration-based cooldown | + `adaptive_timing` in **idle/legacy** interval path only |
| `AUTOMATION_HARMONY_COOLDOWN_FRACTION` | 0.35 | cooldown ≈ avg_run × fraction | |
| `AUTOMATION_GAP_FILL_ENABLED` | true | Idle workers → backlog phases | Respects same caps as normal enqueue |
| `WORKLOAD_BALANCER_ENABLED` | **false** | Extra cooldown curve | **Off by default** — enable only if harmony too aggressive |
| `AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE` | 1 | Queued duplicates per phase | Good; prevents 5 min interval × tick spam |
| `AUTOMATION_PER_PHASE_CONCURRENT_CAP` | 2 | Same phase parallel runs | Long GPU drain occupies cap |
| `AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES` | — | e.g. `claim_extraction:1` | |
| `AUTOMATION_MAX_REQUEUE_PER_WINDOW` | 0 (unlimited) | Continuous re-queue after batch | yaml `analysis_pipeline.max_requeue_per_window` |
| `AUTOMATION_QUEUE_SOFT_CAP` | **0** (off) | Pause enqueue when deep queue | Prefer caps above |
| `COLLECTION_THROTTLE_PENDING_THRESHOLD` | 1200 | Block `collection_cycle` when downstream heavy | Sum of enrichment+context_sync+document_processing (+extras) |
| `COLLECTION_CYCLE_INTERVAL_SECONDS` | 7200 | yaml `collection_cycle.interval_seconds` | Ignored when workload-driven + pending |
| `AUTOMATION_DISABLED_SCHEDULES` | — | **Widow prod:** context_sync, entity_profile_sync, pending_db_flush, claims_to_facts, pattern_recognition | Cron offload; **duplicate key in .env** — fix to one line |
| `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE` | — | Widow: RSS elsewhere | |
| `PIPELINE_BACKFILL_MODE` | false | Pause RSS/docs during catch-up | Widow: false (good) |

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

**Monitor mismatch:** `backlog_metrics.BATCH_SIZE_PER_TASK` uses **single-round** estimates (e.g. entity 60 = 20×3). ETA in UI understates drain throughput — use `processing_progress` + run history, not batch table alone.

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
| `processing.phases.*.interval_seconds` | Yes | ProcessingGovernor when `orchestrator_processing_nudge_enabled: true` |
| `processing.batch_size`, `max_concurrent`, `context_window_days` | **Removed** | Were never wired — deleted from yaml |
| `pipeline_conductor` | Yes | `pipeline_conductor_service` — scheduler roles + external timers |
| `analysis_pipeline.step_budgets_seconds` | Partial | Step reporting; **gating disabled** when workload-driven |
| `pipeline_orchestration_harmony` | Yes (fallback) | `pipeline_batch_drain`, `pipeline_orchestration_harmony` if env unset |
| `resources.daily_llm_tokens` | Partial | Blocks orchestrator **analysis/synthesis** only |
| `entity_tracking.enabled` | Yes | Coordinator dossier compile (default false in yaml) |

---

## 6. Defunct or legacy (safe to ignore)

| Knob | Why |
|------|-----|
| `AUTOMATION_SCHEDULE` (cron string in env.example) | Not read by AutomationManager |
| `CELERY_*` | No Celery worker in NI API |
| `ML_BATCH_SIZE`, `ML_MODEL_PATH` | Legacy ML config; not automation path |
| `INTELLIGENCE_UPDATE_INTERVAL` | Not referenced in `api/` |
| `ENRICHMENT_BACKLOG_FIRST_*` | Hardcoded **false** in automation_manager |
| `articles.entities` jsonb | Unused; entities in `article_entities` |
| `processing_status` on articles | Never updated by extraction; use pass markers |
| `scripts/daily_batch_processor.py`, `optimized_ml_worker.py` | Manual/legacy; not systemd automation |
| `entity_tracking.enabled: false` + `entity_dossier_compile` in automation | Duplicate path — pick one |

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
# Throughput
ENTITY_EXTRACTION_RUN_BUDGET_SECONDS=1800
SENTIMENT_ANALYSIS_RUN_BUDGET_SECONDS=1800
CLAIM_EXTRACTION_DRAIN_MAX_SECONDS=1800

# Scheduling
AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS=30
WORKLOAD_BALANCER_ENABLED=true
AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES=claim_extraction:1,entity_extraction:1

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
| [PIPELINE_ORCHESTRATION_HARMONY.md](PIPELINE_ORCHESTRATION_HARMONY.md) | Duration harmony + gap-fill |
| [RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md](RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md) | DB pool + Ollama caps |
| [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) | Phase catalog |
| [configs/env.example](../configs/env.example) | Full env comment index (some defaults stale — trust this registry + code) |

---

## 10. Known ops issues (Widow, Jun 2026)

1. **Duplicate `AUTOMATION_DISABLED_SCHEDULES`** in `/opt/news-intelligence/.env` — merge to one line.
2. **Harmony/drain envs not in prod .env** — using code defaults (900s) after recent deploy.
3. **`claims_to_facts` disabled in schedules** — promotion only via nightly drain or manual `request_phase`.
