# Diagnostics event collector

**Purpose:** One place to gather **actionable signals** for operators: failed automation runs, failed pipeline traces/checkpoints, **pending DB spill** (deferred `automation_run_history`), structured errors from **`logs/activity.jsonl`**, and heuristic **ERROR/CRITICAL/FATAL** lines from common log files.

**Code:** `api/services/diagnostics_event_collector_service.py`

**API (cached ~30s):**

- `GET /api/system_monitoring/diagnostics/events` — full normalized event list + counts  
- `GET /api/system_monitoring/diagnostics/summary` — counts only (smaller payload)

Query params include `since_hours` (default 24), `max_per_source`, and toggles for activity JSONL / plain log scan.

**CLI / cron:**

```bash
PYTHONPATH=api uv run python api/scripts/run_diagnostics_collect.py --json
PYTHONPATH=api uv run python api/scripts/run_diagnostics_collect.py --summary
```

**Install cron (every 4 hours, summary to `logs/diagnostics_cron.log`):**

```bash
./scripts/setup_diagnostics_cron.sh
```

Schedule: `0 */4 * * *` (at :00 past every 4th hour). Re-run the installer to update; it removes any previous `run_diagnostics_collect.py` line for this repo before adding the new one.

**Note:** Plain log scanning is **heuristic** (keyword match); use full log aggregation on the host for forensics. Activity JSONL depends on middleware calling `shared.logging.activity_logger` (e.g. `log_api_request`).

**Interpreting severity**

- **`automation_run_history`:** Rows with `success = false` are normal **phase-level** failures (bad data, LLM error, etc.). Diagnostics label most as **`high`**, not **`critical`**. **`critical`** is reserved for rows whose `error_message` looks like **connectivity/DB/pool** issues.
- **Large “critical” counts** in older builds were often **every** `success=false` mis-tagged as critical — compare with `PYTHONPATH=api uv run python api/scripts/analyze_automation_failures.py`.

**Related:** `docs/SECURITY_OPERATIONS.md` if exposing Monitor on untrusted networks — diagnostics can include error text and paths.
