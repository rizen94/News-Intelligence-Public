# Monitor terminology crosswalk

Synthesis of S1–S6 segment audits. Use as rename impact map and overlap reference.

## Overlap matrix

| Concept | S1 Execution | S2 Persistence | S3 Aggregation | S4 Health | S5 UI |
|---------|--------------|----------------|----------------|-----------|-------|
| Phase id | `task.name` | `phase_name` / `task_name` | `phase_name` | phase dict key | both |
| Iteration # | `loops_processed`, `batch_rounds` | metadata `loops_processed` | — | activity `loops_processed` | activity message |
| Rows cleared | `round_processed`, `articles_processed` | metadata keys | `_measured_count_from_payload` | `_processed_count_from_row` | — |
| Scheduler run | outer task | full row or batch row | `runs_1h` | history rows | Runs (1h) col |
| Queue depth | pending dict | — | `pending_records` | pending_history | Total queue |
| Item pass | pass marker SQL | — | `pending_first_pass` | — | First pass col |

## Blocked routes (fixed or to wire via SSOT)

| Route | Symptom | Fix |
|-------|---------|-----|
| Activity → no history | Pulse `runs_1h=0`, activity shows round | `emit_phase_run_event` + `allow_empty` for drain phases |
| History → no backlog refresh | Pending stale mid-drain | Invalidate on `rows_processed > 0` in emitter |
| In-memory `runs_last_60m` ≠ SQL | automation/status vs pulse mismatch | Use `is_measurable_run_history_row` for both |
| Conductor `drain_started` only | Zero measurable runs | PipelineController-only scheduling (retired conductor loops) |
| `pass_rate` vs `first_pass` | Operator confusion | Rename to `run_success_rate_24h` (Phase 3) |

## Canonical → alias map (Phase 3 targets)

| Canonical | Current aliases (accept during migration) |
|-----------|-------------------------------------------|
| `phase_key` | `task_name`, `phase_name` |
| `iteration_index` | `loops_processed`, `rounds`, `batch_rounds` |
| `rows_processed` | `round_processed`, `total_processed`, `articles_processed`, `processed`, `profiles_updated`, … |
| `run_history_status` | `metadata.status` |
| `estimated_phase_runs` | `batches_to_drain` |
| `queue_depth` | `pending_records` |
| `run_success_rate_24h` | `pass_rate_24h` |

## Rename impact (breaking if removed without alias)

| File | Field | Risk |
|------|-------|------|
| `MonitorPage.tsx` | `runs_1h`, `pending_records`, `batches_to_drain` | High — keep aliases |
| `processing_progress.py` | response shape | Medium — additive only in Phase 3 |
| `activity_feed_service.py` | `task_name` | Medium — add `phase_key` |
| External scripts reading pulse JSON | any | Low — version gate |

## SSOT module

All segments converge on `api/shared/monitor_run_vocabulary.py`:

- `PhaseRunEvent`, `normalize_phase_run_event`, `throughput_from_payload`
- `is_measurable_run_history_row`, `RUN_HISTORY_*_STATUSES`
- `emit_phase_run_event` (async) — single write contract
