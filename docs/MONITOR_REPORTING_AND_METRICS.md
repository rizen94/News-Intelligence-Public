# Monitor reporting, logging, and metrics (inventory)

Single map of **where** the platform records “how well we are processing,” **what runs on a schedule** vs **manual/CLI**, and **how the Monitor UI** consumes it. Complements `AGENTS.md` (automation visibility) and `docs/DIAGNOSTICS_EVENT_COLLECTOR.md` (operator diagnostics).

---

## Documentation (methodology)

| Doc | Role |
|-----|------|
| `AGENTS.md` | Automation visibility: `automation_run_history`, `/automation/status`, `/backlog_status`, pipeline vs polling. |
| `docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md` | Pipeline order and handoffs (not a metrics store). |
| `docs/DIAGNOSTICS_EVENT_COLLECTOR.md` | Diagnostic events API and collection patterns. |
| `docs/AUTOMATION_MANAGER_SCHEDULING.md` | Scheduler caps, queue depth, concurrent phases. |
| `docs/MONITORING_SSH_SETUP.md` | Remote device metrics over SSH. |
| `docs/MONITOR_BLOCKAGES_AND_GPU.md` | GPU / blockage notes for Monitor operators. |

---

## Database (durable reporting)

| Store | Written by | Used for |
|-------|------------|----------|
| **`public.automation_run_history`** | `persist_automation_run_history` on phase completion; `pending_db_flush` replay; optional **`POST /api/system_monitoring/cron_heartbeat`** | Last run, “runs in window,” nightly recent runs in `backlog_status`, **`GET /api/system_monitoring/process_run_summary`**, **`GET /api/system_monitoring/processing_progress`**. |
| **`pipeline_checkpoints` / `pipeline_traces`** | `pipeline_trace_writer` (e.g. orchestrator RSS, manual pipeline trigger) | `process_run_summary` checkpoint list; operator tracing. |
| **Domain + `intelligence.*` tables** | Pipeline phases | Backlog counts, throughput (articles enriched, contexts→claims, entity profiles, PDFs, storylines) in **`GET /api/system_monitoring/backlog_status`** and **`processing_progress`**. |
| **`orchestrator_state` (SQLite)** | Orchestrator | `orchestrator_decision_history`, `orchestrator_performance_metrics` — not the primary Postgres Monitor path. |

**Gap:** `automation_run_history` does **not** store rows-processed per run; throughput for “work accomplished” comes from **data plane SQL** (same as backlog_status), not from the phase row alone.

**`processing_progress` phase `pending_records`:** `api/services/backlog_metrics.py` uses SQL aligned with each phase’s real selection rules (e.g. `event_tracking` = contexts in the discover window not referenced in chronicle `developments`, not `COUNT(contexts)−COUNT(chronicles)`; `claim_extraction` excludes contexts too short to extract; `entity_profile_build` excludes profiles with no `context_entity_mentions`; `entity_extraction` / `proactive_detection` match automation `WHERE` clauses). `estimated_batch_per_run` uses the same batch heuristics as scheduling (including `topic_clustering` ≈ 20×active schemas and `storyline_automation` ≈ 5×pipeline domains per tick).

---

## API endpoints (Monitor-relevant)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/system_monitoring/monitoring/overview` | API/DB/webserver + in-memory activity feed. |
| `GET /api/system_monitoring/automation/status` | Live queues, `pending_counts`, phase table, resource router. |
| `GET /api/system_monitoring/backlog_status` | ETAs, steady_state, nightly_catchup, dimension throughputs (cached ~15s). |
| `GET /api/system_monitoring/processing_progress` | **Processing pulse:** `routes/processing_progress.py`, mounted on `resource_dashboard` router. **phase_dashboard** fields: `pending_records` (unprocessed DB rows), `estimated_batch_per_run` (modeled rows per run), `batches_to_drain` (ceil divide = runs to clear queue, or `null`). Plus dimension throughputs, pass rates, 72h hourly buckets (cached ~45s). |
| `GET /api/system_monitoring/process_run_summary` | Phases run vs not in N hours, pipeline checkpoints, optional `activity.jsonl` tail. |
| `GET /api/system_monitoring/pipeline_status` | Pipeline coordinator snapshot. |
| `GET /api/system_monitoring/database/connections` | `pg_stat_activity` style sessions. |
| `GET /api/diagnostics_events/...` | Curated diagnostic events (see diagnostics doc). |

---

## Scripts (not automatically scheduled in-repo)

These are **operator-run** unless you install cron/systemd yourself:

| Script | Purpose |
|--------|---------|
| `scripts/snapshot_backlog_status.sh` (repo root: `./snapshot_backlog_status`) | Saves JSON under `.local/backlog_snapshots/`, then prints a **single timeline table** for up to four snapshots (oldest→newest, Δ first→last). |
| `scripts/compare_backlog_snapshots.py` | Pair diff two files, or `timeline` mode: one table across 2+ snapshots (oldest→newest). |
| `scripts/backlog_burndown.sh` | `snapshot`, `timeline` (last four on disk), `diff` (last two or two paths). |
| `scripts/run_last_24h_report.sh` + `scripts/last_24h_activity_report.py` | Standalone DB report (venv-report); not invoked by the API. |
| `scripts/automation_run_analysis.py` | CLI analysis of `automation_run_history` vs schedule intervals. |

**In-repo cron template:** `infrastructure/widow-db-adjacent.cron` — DB-adjacent jobs on Widow (RSS, `context_sync`, etc.), **not** the snapshot/report scripts above.

---

## What is “scheduled” for metrics?

- **No built-in periodic job** in the repo writes backlog snapshots to disk; that is **manual** (`./snapshot_backlog_status` or `scripts/snapshot_backlog_status.sh`) or external cron you add.
- **AutomationManager** (on the main API host) **continuously** runs phases and **appends** `automation_run_history` — that **is** the scheduled metrics backbone for phase frequency and duration.
- **Monitor SPA** polls heavy endpoints on a **staggered** interval (~every 3rd tick for `backlog_status` / DB sessions / **processing_progress**).

---

## Monitor UI (after “Processing pulse”)

The Monitor page includes:

- Connection cards, current/recent **activity feed**.
- **Processing pulse (7-day window)** — ticker-style dimension chips + phase table + hourly bucket count (data from **`processing_progress`**).
- **Backlog status progression** — ETAs and steady state (`backlog_status`).
- Phase timeline, orchestrator decision log, triggers, etc.

For a **true** week-long **time-series DB** of backlogs (not just live SQL + history of runs), you would add a small **scheduled snapshot table** or keep using `.local/backlog_snapshots/` with external cron; the new API does not replace that.
