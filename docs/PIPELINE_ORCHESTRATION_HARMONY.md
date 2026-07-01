# Pipeline orchestration harmony

How AutomationManager aligns **schedule intervals**, **run duration**, and **backlog**.

## Problem

Phases like `entity_extraction` had `interval: 300` (5 min) in `self.schedules` but measured runs of **1–4 hours**. That mismatch causes:

- Monitor showing “due every 5 min” while reality is a few runs per day
- A flat `WORKLOAD_MIN_COOLDOWN` (10s) that ignores GPU wall time
- One batch per invocation (`40` articles/domain) while intake adds hundreds per day
- `_has_pending_work` using legacy `articles.entities` instead of `article_entities`

## Model (three layers)

| Layer | Role |
|-------|------|
| **AutomationManager scheduler** | Workload-driven: every tick, rank phases by pending/backlog; respect concurrent caps, quiet/nightly windows, collection throttle |
| **Duration harmony** (`pipeline_orchestration_harmony.py`) | Cooldown ≈ fraction of measured avg duration; gap-fill idle workers with backlog phases |
| **OrchestratorCoordinator** | 60s loop: collection + optional `ProcessingGovernor` nudge → `request_phase` |

## Pipeline conductor

Three schedulers share one config section (`pipeline_conductor` in `orchestrator_governance.yaml`), implemented in `pipeline_conductor_service.py`:

| Scheduler | Role | Default |
|-----------|------|---------|
| **AutomationManager** | Primary — 5s tick, workload-driven phase drain, gap-fill | `automation_primary: true` |
| **OrchestratorCoordinator** | Collection (RSS/finance) every 60s; processing nudge only when enabled | `orchestrator_processing_nudge_enabled: false` |
| **NRI mention resolver** | External systemd timer on Widow (`/opt/nri`) | Listed in `external_schedulers` |

When nudge is **disabled** (production default), `ProcessingGovernor.recommend_next_processing` returns `None` immediately and the coordinator does not call `request_phase` for processing. Enable only for debugging or when AutomationManager is not running (`PIPELINE_CONDUCTOR_ORCHESTRATOR_NUDGE=true`).

Env overrides: `PIPELINE_CONDUCTOR_AUTOMATION_PRIMARY`, `PIPELINE_CONDUCTOR_ORCHESTRATOR_NUDGE`.

## Duration-aware cooldown

When `AUTOMATION_HARMONY_USE_MEASURED_DURATION=true` (default):

```
cooldown = max(WORKLOAD_MIN_COOLDOWN, measured_avg_duration × 0.35)
```

Large backlogs shorten cooldown so continuous re-queue after a run finishes stays responsive.

## Gap-fill

When `AUTOMATION_GAP_FILL_ENABLED=true` (default) and `running_workers < max_concurrent_tasks`:

1. List phases with pending work not at running+queued cap
2. Score by `pending / batch_size` (prefer idle phases)
3. Enqueue through normal `_should_run_task` gates

This lets CPU phases run while a long GPU `entity_extraction` drain occupies one worker.

## Time-budgeted batch drain

These phases loop batches until budget or backlog empty:

| Phase | Budget env | Batch env |
|-------|------------|-----------|
| `entity_extraction` | `ENTITY_EXTRACTION_RUN_BUDGET_SECONDS` (900) | `ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN` (40) |
| `ml_processing` | `ML_PROCESSING_RUN_BUDGET_SECONDS` (900) | `ML_PROCESSING_BATCH_LIMIT` (50/domain) |
| `sentiment_analysis` | `SENTIMENT_ANALYSIS_RUN_BUDGET_SECONDS` (900) | `SENTIMENT_ANALYSIS_BATCH_LIMIT` (100/domain) |
| `claim_extraction` | `CLAIM_EXTRACTION_DRAIN_MAX_SECONDS` (900) | batch limit via existing service |
| `claims_to_facts` | `CLAIMS_TO_FACTS_DRAIN_MAX_SECONDS` (900) | existing promote batch |

`claim_extraction` already had a drain loop; defaults now use a **900s cap** instead of unlimited.

## Investigation mention resolution (Widow)

**Retired:** `nri-mention-resolver.timer` (disabled June 2026 unification). Mention resolution runs as the **`mention_resolution`** automation phase in AutomationManager (`api/nri_core/resolver_runner.py` via `api/services/automation/executor.py`).

Tune via env vars consumed by the resolver runner (e.g. batch limits in `api/config/nri_resolution_config.py`). Restart `news-intelligence-api-public.service` after deploy.

## Env reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTOMATION_GAP_FILL_ENABLED` | true | Idle-worker backlog fill |
| `AUTOMATION_HARMONY_USE_MEASURED_DURATION` | true | Duration-based cooldown |
| `AUTOMATION_HARMONY_COOLDOWN_FRACTION` | 0.35 | Cooldown vs avg run time |
| `ENTITY_EXTRACTION_RUN_BUDGET_SECONDS` | 900 | Max wall time per entity_extraction task |
| `ML_PROCESSING_RUN_BUDGET_SECONDS` | 900 | Queue drain per ml_processing task |
| `ML_PROCESSING_BATCH_LIMIT` | 50 | Articles queued per domain per round |
| `SENTIMENT_ANALYSIS_RUN_BUDGET_SECONDS` | 900 | Max wall time per sentiment task |
| `SENTIMENT_ANALYSIS_BATCH_LIMIT` | 100 | Articles per domain per round |
| `CLAIM_EXTRACTION_DRAIN_MAX_SECONDS` | 900 | Cap per claim_extraction drain (default was unlimited) |
| `CLAIMS_TO_FACTS_DRAIN_MAX_SECONDS` | 900 | Cap per claims_to_facts drain |
| `NRI_MENTION_RESOLVE_BUDGET_SECONDS` | 240 | Per-tick mention drain budget (legacy timer; phase uses resolver config) |
| `NRI_MENTION_RESOLVE_BATCH_LIMIT` | 500 | CEM rows per batch (legacy timer) |
| `AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS` | 10 | Floor cooldown |
| `WORKLOAD_BALANCER_ENABLED` | false | Extra backlog-aware cooldown tuning |

## Tuning on Widow

After deploy, restart `news-intelligence-api-public.service`. Watch:

- `GET /api/system_monitoring/automation/status` — `pending_counts`, `active_tasks_by_phase`, `work_balancer`
- `public.automation_run_history` — run duration vs frequency for `entity_extraction`

For sustained catch-up, consider `ENTITY_EXTRACTION_RUN_BUDGET_SECONDS=1800` during daytime and enable `WORKLOAD_BALANCER_ENABLED=true`.

See [PIPELINE_TUNING_REGISTRY.md](PIPELINE_TUNING_REGISTRY.md) for the full knob map, defunct settings, and known conflicts.
