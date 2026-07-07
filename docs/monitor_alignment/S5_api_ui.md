# S5 — API / UI surface

## Scope

- `api/domains/system_monitoring/routes/system_monitoring.py`
- `api/domains/system_monitoring/routes/processing_progress.py` — `reporting_definitions`
- `web/src/pages/Monitor/MonitorPage.tsx`

## Happy-path pseudocode

```
Monitor poll every ~30s:
    overview = GET monitoring/overview      # activity current/recent
    pulse = GET processing_progress         # phase_dashboard
    merge activity.task_name with pulse.phase_name by string match
```

## Term table

| UI / API | Canonical | Notes |
|----------|-----------|-------|
| Activity `task_name` | `phase_key` | |
| Pulse `phase_name` | `phase_key` | |
| Column "Runs (1h)" | `phase_run` count | From SQL not activity |
| "queue_depth" | `queue_depth` | `pending_records` | Per-phase actionable depth — **do not sum across phases**. Subtitle shows `scheduling_backlog` when it differs. |
| "Runs to clear" | `estimated_phase_runs` | `batches_to_drain` |
| "First pass" | `first_pass_depth` | `pending_first_pass` |
| "Retry" | `retry_depth` | `pending_retry` |

## Confusion hotspots

- `pass_rate_24h` vs `pending_first_pass` — same screen, different domains
- Activity shows "round N" while pulse shows `runs_1h=0` when history not persisted
- `queue_stale=true` when pending > batch but runs_24h=0

## Rename targets (Phase 3)

- Add `monitor_schema_version`, additive aliases: `iteration_index`, `rows_processed`, `estimated_phase_runs`, `run_success_rate_24h`, `phase_key`
