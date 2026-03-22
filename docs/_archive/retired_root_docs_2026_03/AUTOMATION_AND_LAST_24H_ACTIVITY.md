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
- **Automation phases** — `automation_run_history` aggregates (runs per phase, last success); phases with schedule interval ≤ 24h and **no** successful run in the window (see `scripts/automation_run_analysis.py` for the same schedule table)
- **Pipeline traces** — `pipeline_traces` rows (Monitoring **Trigger pipeline** and any other writer that logs a trace)
- **Pipeline checkpoints** — stages and statuses, including **`orchestrator_rss_collection`** when OrchestratorCoordinator runs RSS
- **Orchestrator RSS** — count of `orchestrator_rss_collection` checkpoint rows (0 is normal if you use cron-only RSS)
- **System alerts** — last 24h
- **Orchestrator state** — `last_collection_times` from the coordinator (SQLite)
- **Cron RSS log** — last lines from `~/logs/news_intelligence/rss_collection.log` (or `logs/rss_collection.log`)

It also lists **potential gaps** (e.g. no new articles in a domain, no `pipeline_traces` rows, phases with no successful run in 24h, missing cron log file).

---

## What runs automatically (and where it’s recorded)

| What | How it runs | Where it’s recorded |
|------|-------------|----------------------|
| **RSS collection** | (1) **Cron** (e.g. 6am / 6pm) via `scripts/rss_collection_with_health_check.sh` if installed. (2) **OrchestratorCoordinator** (when API is up) — recommends RSS fetch, calls `collect_rss_feeds()`. (3) **Manual** “Trigger pipeline” from Monitoring UI. | **Cron:** log file under `~/logs/news_intelligence/` or project `logs/`. **Per-feed:** `rss_feeds.last_fetched_at` / `last_success`. **Coordinator RSS:** SQLite `orchestrator_state.db` (`last_collection_times`), plus **`pipeline_traces` / `pipeline_checkpoints`** with stage **`orchestrator_rss_collection`** (same mechanism as Trigger pipeline, different trace id). **Trigger pipeline:** `pipeline_traces` + `pipeline_checkpoints` (e.g. rss_collection → topic_clustering → ai_analysis). |
| **OrchestratorCoordinator** | Started with API in `api/main.py`. Loop: assess → plan (CollectionGovernor) → execute one task → learn → sleep (~60s). | **SQLite:** `data/orchestrator_state.db`. **PostgreSQL:** pipeline rows when RSS collection runs (see above). |
| **AutomationManager** | In-process with the API. Phases include `collection_cycle`, `context_sync`, `claim_extraction`, `claims_to_facts`, `topic_clustering`, `storyline_processing`, `health_check`, etc. | **PostgreSQL:** each completed phase is written to **`automation_run_history`** (`phase_name`, `started_at`, `finished_at`, `success`). **API:** GET `/api/system_monitoring/automation_status` merges in-memory last_run with DB. **Logs:** stdout / `logs/api_server.log` for detail. |
| **Pipeline (Monitoring “Trigger pipeline”)** | Only when **Trigger pipeline** is used (UI or API). | **PostgreSQL:** `pipeline_traces`, `pipeline_checkpoints` (stages such as rss_collection, topic_clustering, ai_analysis). |
| **Storyline work (scheduled)** | AutomationManager phases (e.g. `storyline_processing`, `storyline_automation`, `storyline_discovery`). | **Phase completion:** `automation_run_history`. **Not** the same rows as Trigger pipeline unless you also ran a manual pipeline that touches those stages. Domain tables (storylines, merges) reflect effects; there is no separate “merge audit” table in this doc. |
| **Topic clustering** | AutomationManager phase and/or Trigger pipeline stage. | **AutomationManager path:** `automation_run_history` (`topic_clustering`). **Trigger pipeline path:** `pipeline_checkpoints` with stage `topic_clustering`. |
| **health_check** | AutomationManager on an interval. | **`automation_run_history`** when the task completes successfully or fails (same persistence path as other phases). |
| **Health Monitor Orchestrator** | Started with API; polls configured feeds. | **PostgreSQL:** `system_alerts`. |

---

## What is still thin or optional

1. **Cron RSS in the database** — By default, cron is visible in the **log file** and indirectly via **`rss_feeds`** and new **articles**. For a durable “cron ran at” row without relying on logs, configure **`POST /api/system_monitoring/cron_heartbeat`** (header `X-Cron-Heartbeat-Key`, env **`CRON_HEARTBEAT_KEY`**) so the wrapper can record a phase such as **`cron_rss`** in **`automation_run_history`**.
2. **Trigger pipeline vs coordinator** — Full Monitoring pipeline runs and coordinator RSS runs both use **`pipeline_traces`**; distinguish them by **`trace_id`** prefix (e.g. `orch_rss_*` vs UI-triggered) and by checkpoint stage names.
3. **RSS “who fetched when”** — Per-feed **`last_fetched_at`** (and **`last_success`**) in **`rss_feeds`**; the report script uses this for “fetched in 24h” vs stale counts.

---

## Related scripts and endpoints

| Item | Purpose |
|------|---------|
| `scripts/last_24h_activity_report.py` | Report (invoked by `run_last_24h_report.sh`). |
| `scripts/automation_run_analysis.py` | Deeper schedule vs actuals per phase (`SCHEDULE_INTERVAL_SECONDS`). |
| `GET /api/system_monitoring/automation_status` | Last run / next due per phase (DB-backed where available). |
| `POST /api/system_monitoring/cron_heartbeat` | Optional cron heartbeat into **`automation_run_history`**. |

---

## Implementation notes (for code readers)

- **Automation persistence:** `api/shared/services/automation_run_history_writer.py` → **`persist_automation_run_history`**.
- **Pipeline logging:** `api/shared/services/pipeline_trace_writer.py` → **`log_pipeline_trace`** (used by Monitoring routes and **`OrchestratorCoordinator`** RSS).
