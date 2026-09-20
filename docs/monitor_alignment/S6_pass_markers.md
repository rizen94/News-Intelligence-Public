# S6 — Pipeline pass markers (separate domain)

## Scope

- `api/shared/pipeline_pass_marker.py`
- `api/services/phase_work_queue_metrics.py` — `first_pass`, `retry_pending`, `intake_first_pass`
- Article/context metadata pass columns

## Boundary rule

**Pipeline pass** = per-item completion marker (`last_pass_at`, unified intake pass, etc.).  
**Phase run** = scheduler invocation recorded in `automation_run_history`.

Never use "pass" for run success rate in new code — use `run_success_rate_*`.

## Happy-path pseudocode

```
on_article_phase_complete(article_id, phase_key):
    set_pass_marker(article_id, phase_key)
    # does NOT automatically write automation_run_history

on_drain_iteration_complete:
    emit_phase_run_event(...)  # S1/S2 — separate from pass marker
```

## Term table

| Field | Domain | Meaning |
|-------|--------|---------|
| `pending_first_pass` | pipeline_pass | Items never cleared for phase |
| `pending_retry` | pipeline_pass | Attempted, needs retry |
| `intake_first_pass` | pipeline_pass | First-pass in 72h intake window |
| `pass_rate_24h` | phase_run | Run success proportion — **misleading name** |

## Out of scope for rename

Pass marker schema and SQL remain unchanged in Phase 3; only Monitor copy and API aliases disambiguate.
