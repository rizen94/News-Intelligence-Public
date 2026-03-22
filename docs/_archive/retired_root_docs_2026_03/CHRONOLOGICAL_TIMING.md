# Chronological Timing (Data Ingestion Time, Not "Since Restart")

The system should be **chronologically aware**: metrics and summaries use **wall-clock time** and **persistent storage** (DB or file) so they reflect what actually happened, not "since the last API restart."

## Implemented (use new timing structure)

| Area | What | How |
|------|------|-----|
| **Process run summary** (`/process_run_summary`) | "Phases run in last 24h" / "not run recently" | Reads from `automation_run_history` (DB). Window is `finished_at >= now - hours`. |
| **Automation status** (`/automation/status`) | Per-phase "last run" on Monitor page | In-memory `last_run` is augmented from `automation_run_history` when missing (e.g. after restart). |
| **Automation runs** | When a phase completes (success or failure) | Each run is written to `automation_run_history` (phase_name, started_at, finished_at, success). |
| **Pipeline checkpoints** | "Pipeline checkpoints" in process run summary | Already time-based: `pipeline_checkpoints.timestamp >= cutoff`. |
| **Sources collected** | "Sources collected (last 30 min)" | Uses DB: `last_fetched_at` (RSS), orchestrator state, `pipeline_checkpoints`. |
| **Daily briefing** | "Last 3 days" of data | Uses `created_at >= start_date` and domain schema; not tied to restart. |
| **Orchestrator metrics / resource usage** | Recent metrics and API usage | Stored in SQLite with `recorded_at`; `get_resource_usage_sum(since)` is wall-clock. |

## Already time-based (no change needed)

- **Article / storyline queries**: "Last 24h" style filters use `created_at >= NOW() - INTERVAL '24 hours'` or equivalent.
- **Pipeline traces**: Queries use `start_time` / `end_time` and intervals.
- **Log storage / system alerts**: Time-windowed queries by `created_at`.
- **Resource governor** `api_calls_used_last_hour`: Uses `orchestrator_state.get_resource_usage_sum(..., since)`.

## Optional / future (still in-memory or restart-sensitive)

| Area | Current behavior | Possible improvement |
|------|------------------|------------------------|
| **AutomationManager metrics** | `tasks_completed`, `tasks_failed`, `system_uptime` in `get_status()` are in-memory; reset on restart. | Derive "tasks completed in last 24h" from `SELECT COUNT(*) FROM automation_run_history WHERE finished_at >= ...` if the UI needs it. |
| **Local monitoring (ML)** | `local_monitoring.get_system_metrics(hours)` / `get_ai_metrics(hours)` filter in-memory lists by timestamp; only data since process start. | Persist metrics to DB or file and query by time window if "last N hours" should survive restart. |
| **Storyline consolidation** | `_stats["last_run_at"]` is in-memory. | Persist last run to DB (e.g. `storylines.last_automation_run` or a small run_history table) if that dashboard must survive restart. |
| **Orchestrator coordinator** | `state["last_finance_interest_analysis"]` etc. in orchestrator state file. | Already file-backed; ensure state file path is persistent and not cleared on deploy. |

## Migration

Run migration **161** so `automation_run_history` exists:

```bash
PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_155_to_160.py
```

(See [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) and [DATABASE.md](DATABASE.md) for migration pointers.)
