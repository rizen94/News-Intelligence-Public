# S3 — Aggregation (Processing Pulse + backlog)

## Scope

- `api/domains/system_monitoring/routes/processing_progress.py`
- `api/services/backlog_metrics.py`
- `api/services/monitor_backlog_snapshot_service.py`
- `api/services/phase_work_queue_metrics.py`

## Happy-path pseudocode

```
GET processing_progress:
    rows = SQL COUNT automation_run_history WHERE is_measurable_run_history_row(...)
    pending = backlog_metrics.get_all_pending_counts()  # cached ~90s
    for phase in phases:
        runs_1h = rows[phase].r1h
        pending_records = pending[phase]
        batches_to_drain = ceil(pending_records / estimated_batch_per_run)
```

## Term table

| API field | Canonical | Source |
|-----------|-----------|--------|
| `phase_name` | `phase_key` | SQL GROUP BY |
| `runs_1h` / `runs_24h` | `phase_run` count | Measurable history rows |
| `pending_records` | `queue_depth` | backlog_metrics + work_queues max |
| `batches_to_drain` | `estimated_phase_runs` | ceil(pending / batch size) |
| `estimated_batch_per_run` | rows per phase_run | measured_24h or config |
| `pass_rate_24h` | `run_success_rate_24h` | success / completions (not pipeline pass) |
| `pending_first_pass` | `pipeline_pass` backlog | pass marker SQL — separate domain |

## Dead ends

- `_processing_progress_excluded_phases()` hides legacy/superseded phases from pulse table
- `runs_last_60m_by_phase` on AutomationManager status — in-memory, rules differ from SQL `runs_1h`
- Snapshot mode (`use_backlog_snapshot=true`) can stale pending vs live drain progress
- `_measured_count_from_payload` ignores wave-only rows (no row-count keys)
