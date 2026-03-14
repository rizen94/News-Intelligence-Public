# Automation and last-24h activity

How to see **what the News Intelligence program did** in the last 24 hours (what was collected, what ran) and how to spot **areas that were neglected** or not connected to automation.

---

## Quick: run the last-24h report

From the **News Intelligence project root** (not from `~`). On **externally-managed** Python (PEP 668, e.g. Pop!_OS / Debian), use the wrapper so you don't need system pip or a full project sync:

```bash
cd "/path/to/News Intelligence"
./scripts/run_last_24h_report.sh
```

The wrapper creates a minimal venv at `.venv-report` (once), installs `psycopg2-binary` there, and runs the report. `.env` is loaded from the project root. No `uv sync` or main project venv required.

The script prints:

- **Articles collected** in the last 24h per domain (politics, finance, science_tech)
- **RSS feeds** — how many were fetched in 24h vs not (stale)
- **Pipeline traces** — runs recorded when someone uses "Trigger pipeline" (Monitoring UI or API)
- **Pipeline checkpoints** — stages (rss_collection, topic_clustering, ai_analysis) and status
- **System alerts** — last 24h
- **Orchestrator state** — `last_collection_times` from the coordinator (SQLite)
- **Cron RSS log** — last lines from `~/logs/news_intelligence/rss_collection.log` (or `logs/rss_collection.log`)

It also lists **potential gaps** (e.g. no new articles in a domain, no pipeline_traces, no orchestrator last_collection_times, missing log file).

---

## What runs automatically (and where it’s recorded)

| What | How it runs | Where it’s recorded |
|------|-------------|----------------------|
| **RSS collection** | (1) **Cron** 6am / 6pm via `scripts/rss_collection_with_health_check.sh` (if installed). (2) **OrchestratorCoordinator** loop (when API is up) — recommends RSS fetch, calls `collect_rss_feeds()`. (3) **Manual** “Trigger pipeline” from Monitoring UI. | **Cron:** `~/logs/news_intelligence/rss_collection.log`. **Coordinator:** `data/orchestrator_state.db` → `last_collection_times.rss`. **DB:** `politics/finance/science_tech.rss_feeds.last_fetched_at` and `.articles.created_at`. **Trigger pipeline only:** `pipeline_traces` + `pipeline_checkpoints`. |
| **OrchestratorCoordinator** | Started with API in `main_v4.py`. Loop: assess state → plan (CollectionGovernor) → execute one task (e.g. RSS) → learn → sleep (~60s). | **SQLite:** `data/orchestrator_state.db` — `orchestrator_controller_state` (state_json: `last_collection_times`, `current_cycle`, etc.), `orchestrator_source_profiles`. |
| **AutomationManager** (in-process) | Started with API. Runs: health_check, consolidation, topic clustering (and can run RSS/processing when requested via coordinator). | **Not persisted.** Last run times and metrics are in-memory only. Check **API process logs** (stdout or `logs/api_server.log`) for activity. |
| **Pipeline (full run)** | Only when **“Trigger pipeline”** is used (Monitoring UI or API). Stages: rss_collection → topic_clustering → ai_analysis. | **PostgreSQL:** `pipeline_traces`, `pipeline_checkpoints`. |
| **Storyline consolidation** | AutomationManager runs it on a schedule (in-process). | **Not in pipeline_traces.** Service keeps `_last_run` in memory. DB is updated (storyline merges, etc.) but “last run” is not in DB. |
| **Topic clustering** | AutomationManager or “Trigger pipeline” (topic_clustering stage). | **Trigger pipeline only:** `pipeline_checkpoints` (stage = topic_clustering). AutomationManager runs are not written to pipeline tables. |
| **Health check** | AutomationManager every ~2 min; also GET `/api/system_monitoring/health`. | **Not persisted.** Health endpoint returns current status; no “last 24h history” of health checks. |
| **Health Monitor Orchestrator** | Started with API. Polls health feeds (config); creates system_alerts on failure. | **PostgreSQL:** `system_alerts` (alert_type, severity, title, created_at). |

---

## Areas that are not (or barely) recorded

1. **AutomationManager task runs** — health_check, consolidation, topic clustering, etc. **Last run** is only in memory. To know “did consolidation run in the last 24h?” you’d need to either (a) add writes to a DB table or `pipeline_automation_status` when each task runs, or (b) rely on API logs.
2. **Pipeline traces** — Only created when **“Trigger pipeline”** is used. Cron and OrchestratorCoordinator RSS runs do **not** write to `pipeline_traces` unless the code path is extended.
3. **Cron RSS** — Only in a log file. If the log is rotated or missing, there’s no DB record of cron runs.
4. **RSS “who fetched when”** — Per-feed `last_fetched_at` (and `last_success`) in `rss_feeds` is updated by the fetcher; the report script uses this to count “fetched in 24h” vs “stale”.

---

## Connecting automation to visibility (recommendations)

- **Persist AutomationManager last_run**  
  When a task (e.g. consolidation, topic_clustering, health_check) completes, update a table (e.g. `pipeline_automation_status` or a small `automation_run_log`) with task name, last_run timestamp, and optionally success/failure. Then the last-24h report (or a dashboard) can show “last consolidation run”, etc.

- **Record coordinator RSS runs in pipeline_traces**  
  When OrchestratorCoordinator runs RSS collection, call the same `_log_pipeline_trace` (or a small helper) so that RSS runs from the coordinator appear in `pipeline_traces` / `pipeline_checkpoints`. That way “what ran in the last 24h” is visible in one place.

- **Optional: cron run log to DB**  
  Have the cron wrapper script call a tiny API endpoint (or a one-off script) that writes “cron_rss_run at &lt;timestamp&gt;” to a table or `pipeline_automation_status`, so cron runs are visible even if the log file is gone.

After those are in place, the same `last_24h_activity_report.py` (or a small extension) can query the new data and list any automation that did **not** run in the last 24 hours.
