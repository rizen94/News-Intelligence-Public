# Pipeline scheduling (v10.1+)

> **Retired (July 2026):** The harmony / gap-fill / workload-balancer stack is removed.
> This doc is kept as a pointer for old env vars and Monitor fields.

## Current model

| Layer | Role |
|-------|------|
| **PipelineController** | SSOT for processing enqueue — replans on worker completion, lane pools, host balance |
| **AutomationManager** | Phase workers, drains, per-phase caps, DB pool pressure gate |
| **OrchestratorCoordinator** | RSS/finance collection when controller does not own collection; finance interest analysis via `ProcessingGovernor.trigger_finance_analysis` |

Processing phases are **not** driven by a 5s scheduler tick, harmony cooldowns, or orchestrator `request_phase` nudges.

## Where to look

| Concern | Location |
|---------|----------|
| Enqueue / replan | `api/services/pipeline_controller.py` |
| Run budgets (circuit breakers) | `pipeline_controller` section in `orchestrator_governance.yaml`, `api/shared/pipeline_batch_drain.py` |
| Phase policies (host, lane, resource class) | `api/shared/pipeline_resource_policy.py` |
| Backlog counts | `api/services/backlog_metrics.py` → `get_all_pending_counts()` |
| Nightly idle detection | `api/services/nightly_phase_idle.py` → `phase_has_pending_work()` |
| Monitor status | `GET /api/system_monitoring/automation/status` — `pipeline_controller`, `db_pools`, `pending_counts` |

## Defunct env vars (ignore)

| Variable | Was |
|----------|-----|
| `AUTOMATION_SCHEDULER_TICK_SECONDS` | Legacy scheduler loop |
| `AUTOMATION_GAP_FILL_ENABLED` | Idle-worker gap fill |
| `AUTOMATION_HARMONY_*` | Duration-based cooldown |
| `WORKLOAD_BALANCER_ENABLED` | `workload_balancer.py` (deleted) |
| `AUTOMATION_MAX_REQUEUE_PER_WINDOW` | Continuous self re-queue after batch |
| `PIPELINE_CONDUCTOR_ORCHESTRATOR_NUDGE` | Orchestrator processing nudge |

## Batch drain budgets (still valid)

Per-phase wall-clock caps use `{PHASE}_RUN_BUDGET_SECONDS` env or `pipeline_controller.*_run_budget_seconds` in YAML. See [PIPELINE_TUNING_REGISTRY.md](PIPELINE_TUNING_REGISTRY.md) §3.

## Mention resolution

Runs in-process as automation phase **`mention_resolution`** (`api/nri_core/resolver_runner.py`). External NRI systemd timer is documented under `pipeline_conductor.external_schedulers` for ops reference only.
