# S4 — Scheduling health (PipelineController)

## Scope

- `api/services/pipeline_controller.py` — `assess_phase_health`, `_update_stall_holds`, `pick_next_phases`
- Stall config: `stall_zero_progress_passes`, `stall_backlog_unchanged_replans`, `stall_hold_replans`

## Happy-path pseudocode

```
on_replan:
    pending = get_all_pending_counts()
    phase_health = assess_all_phase_health(pending, history, activity_feed)
    for phase where health in (stalled, failing):
        stall_holds[phase] = stall_hold_replans()  # log stall_yield
    desired = pick_next_phases(..., skip health=stalled)
    reconcile_and_enqueue(desired)
```

## Term table

| Local name | Canonical | Meaning |
|------------|-----------|---------|
| `PhaseHealth.status` | — | `moving`, `slow`, `stalled`, `failing`, `unknown` |
| `"drain in-flight"` detail | active drain | Activity feed has current row, no throughput yet |
| `"zero-progress passes"` | failed iterations | Recent history rows with rows_processed=0 |
| `stall_yield` (log) | scheduling yield | Phase temporarily removed from desired list |

## Progress signals (priority order)

1. Activity feed in-flight → `slow`
2. Activity `rows_processed` / `total_processed` → `moving`
3. Run history throughput → `moving`
4. Backlog decreased → `moving`
5. Flat backlog + zero history → `stalled`

## Dead ends

- Empty run history + flat backlog used to stall before in-flight check (fixed: activity first)
- Stalled phase dropped from queue while worker still running (re-enqueue blocked until hold expires)
