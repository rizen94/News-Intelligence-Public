# S1 — Execution (drain / batch iteration)

## Scope

- `api/services/automation_manager.py` — task dispatch, `_execute_*`, `_record_phase_batch_loop`
- `api/shared/unified_intake_extraction_runner.py`
- `api/shared/pipeline_batch_drain.py` — `RunBudget`, `DrainStallTracker`
- Phase runners: claim extraction, entity profile builder, spine SQL tail, content enrichment

## Happy-path pseudocode

```
on_scheduler_enqueue(phase_key):
    worker starts task → activity_feed.add_current(phase_key, iteration_index=0)

on_drain_iteration_complete(phase_key, iteration_index, raw_stats):
    emit_phase_run_event(...)   # target SSOT (today: _record_phase_batch_loop)

on_outer_task_complete(phase_key):
    if not skip_automation_run_history: persist outer row
    invalidate_backlog_cache if phase in RAW_PENDING_COUNT_KEYS
    activity_feed.complete(phase_key)
```

## Term table

| Local name | Canonical | Emitted by |
|------------|-----------|------------|
| `task.name` | `phase_key` | AutomationManager |
| `loops_processed` (1st arg to batch cb) | `iteration_index` | Runners, conductors |
| `batch_rounds` / `rounds` | `iteration_index` (return dict) | unified intake, spine tail |
| `round_ok` / `round_processed` | `rows_processed` | unified intake runner |
| `processed_count` | `rows_cumulative` | unified intake runner |
| `updated` (entity profiles) | `rows_processed` | entity_profile_builder |
| `skip_automation_run_history` | — | Long drains: outer row skipped; batch rows only |

## Entry / exit

- **Entry:** PipelineController `reconcile_and_enqueue` → worker `_execute_task`
- **Exit:** Task complete/fail → run history (optional) → backlog invalidate → activity complete

## Dead ends / blocked routes

- Drain phases set `skip_automation_run_history=True` — outer task never counts toward `runs_1h`
- Unified wave callback skipped when `round_processed=0` (before SSOT fix: no DB row, activity still updated)
- `entity_profile_build` only emitted batch history when `updated > 0` (fixed: per-profile callback)
- Conductor path (`spine_conductor`) writes `drain_started` without matching `batch_round` rows since Jul 2026 cutover
