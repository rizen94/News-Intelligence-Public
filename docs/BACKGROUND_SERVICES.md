# Background Services Catalog

Concise input/output contracts for major background workers. Polling remains primary; `shared.kernel.domain_events` is available for incremental event-driven hooks.

| Service | Trigger | Input | Output | Notes |
|---------|---------|-------|--------|-------|
| `AutomationManager` | 5s loop | DB queues, schedule manifest | Phase runs, backlog drains | SSOT for pipeline phases |
| `OrchestratorCoordinator` | 60s loop | RSS cadence, finance interest | Collection nudges | Does not own entity work |
| `ConsolidationScheduler` | `schedulers.yaml` rotation | Step name | Per-step stats dict | storylines/entities/investigations/events |
| `entity_resolution_service` | API/automation | domain_key, names/ids | Canonical IDs, merge stats | Batch via `run_resolution_batch` |
| `entity_profile_sync_service` | Cron/API | domain_key | Profiles created | Backfill + sync |
| `entity_position_tracker_service` | API/batch | entity_id | Positions list | LLM extraction optional |
| `TopicExtractionQueueWorker` | Per-domain queue | article_id | topic clusters | One worker per pipeline domain |
| `MLProcessingService` | Automation embed | article batches | embeddings | GPU/CPU lane routed |
| `HealthMonitorOrchestrator` | Timer | `/api/health` probes | Alerts | Background thread |

## Health

- API: `/api/health` (centralized probes)
- Workers: `shared.services.worker_health.list_worker_health()` (in-process heartbeats)

## Errors

Batch services should return `shared.services.service_result.service_ok()` / `service_err()` envelopes where practical.

## Entity operations

Prefer `services.entity_service_facade` from routes, scripts, and cross-domain callers instead of importing multiple entity modules.
