# S2 — Persistence (activity feed + run history)

## Scope

- `api/shared/services/phase_batch_run_history.py`
- `api/shared/services/automation_run_history_writer.py`
- `api/shared/services/conductor_run_history.py`
- `api/services/activity_feed_service.py`
- `api/shared/database/pending_db_writes.py`

## Happy-path pseudocode

```
emit_phase_run_event(event: PhaseRunEvent):
    activity_feed.update_current_progress(phase_key, iteration_index, rows_processed, message)
    if is_measurable_run_history_row(event):
        persist_automation_run_history(phase_key, started, finished, metadata=event.to_metadata())
    if event.rows_processed > 0:
        invalidate_backlog_metrics_cache()
        maybe_refresh_monitor_backlog_snapshot_after_drain()
```

## Term table

| Local name | Canonical | Store |
|------------|-----------|-------|
| `task_name` | `phase_key` | Activity feed JSON |
| `phase_name` | `phase_key` | `automation_run_history` column |
| `metadata.status` | `run_history_status` | JSONB |
| `loops_processed` in metadata | `iteration_index` | JSONB |
| `round_processed` etc. | `rows_processed` | JSONB |
| `scheduler_path` | — | `automation_manager` vs `spine_conductor` |

## Writers (multiple paths today)

| Path | Status values | Measurable? |
|------|---------------|-------------|
| `phase_batch_run_history` | `batch_round` | Yes (when work or allow_empty) |
| `conductor_run_history` | `phase_started`, `phase_finished`, `phase_failed` | phase_finished yes |
| `spine_pipeline_conductor` | `drain_started`, `drain_finished` | drain_finished if processed > 0 |
| `_persist_automation_run` (outer task) | none / error string | Duration-based |

## Dead ends

- `pending_db_writes` queue on worker pool failure — rows invisible until `pending_db_flush`
- Activity feed is in-memory only — lost on API restart; run history survives
- Four duplicate throughput key lists (`_MEASURED_KEYS`, `_MEASURED_BATCH_COUNT_KEYS`, `items_processed_from_stats`, `_processed_count_from_row`)
