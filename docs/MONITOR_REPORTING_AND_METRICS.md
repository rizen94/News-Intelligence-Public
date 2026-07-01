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

**`processing_progress` phase `pending_records`:** `api/services/backlog_metrics.py` uses SQL aligned with each phase’s real selection rules (e.g. `event_tracking` = contexts in the discover window not referenced in chronicle `developments`, not `COUNT(contexts)−COUNT(chronicles)`; `claim_extraction` excludes contexts too short to extract; `entity_profile_build` excludes profiles with no `context_entity_mentions`; `entity_extraction` / `proactive_detection` match automation `WHERE` clauses). `claims_to_facts` defaults to **`promotable_hint`** (generic subjects excluded + at least one exact-resolution path: context mention, profile canonical/display, or `article_entities` name on the linked article); set **`CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE=batch_candidate`** for the larger pre-fuzzy SQL pool. `estimated_batch_per_run` uses the same batch heuristics as scheduling (including `topic_clustering` ≈ 20×active schemas and `storyline_automation` ≈ 5×pipeline domains per tick).

---

## API endpoints (Monitor-relevant)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/system_monitoring/monitoring/overview` | API/DB/webserver + in-memory activity feed. |
| `GET /api/system_monitoring/automation/status` | Live queues, `pending_counts`, phase table, resource router. |
| `GET /api/system_monitoring/backlog_status` | ETAs, steady_state, nightly_catchup, dimension throughputs (cached ~15s). |
| `GET /api/system_monitoring/processing_progress` | **Processing pulse:** `routes/processing_progress.py`, mounted on `resource_dashboard` router. **phase_dashboard** fields: `pending_records` (unprocessed DB rows), `estimated_batch_per_run` (modeled rows per run), `batches_to_drain` (ceil divide = runs to clear queue, or `null`). Plus dimension throughputs, pass rates, 72h hourly buckets (cached **~90s** per worker). |
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

---

## Context → claims backlog semantics

Monitor and automation must agree on what counts as **work to do** vs **terminal inventory**.

| Metric | Source | Meaning |
|--------|--------|---------|
| **`actionable_no_claims`** | `get_context_claim_backlog_stats()` / `backlog_metrics._count_claim_extraction_backlog()` | Contexts with no `extracted_claims` rows that **claim_extraction** would still select (min text length, no pass marker). Used for **`backlog_status.contexts.backlog`**, **`processing_progress`** dimension `contexts_claimed.backlog`, and phase `pending_records` for `claim_extraction`. |
| **`total_no_claims`** | Same helper | All contexts with zero claim rows, including pass-markered PDF sections and empty parses. **Not** queue depth — do not treat as operator to-do. |
| **`passed_no_claims_after_filters`**, **`text_too_short_no_claims`** | Breakdown fields | Subsets of terminal inventory for diagnostics. |

**Operator scripts:** `api/scripts/report_context_claim_pipeline_backlog.py` prints both actionable and total. **`scripts/backlog_burndown.sh`** steady-state gates use actionable counts via `backlog_status`.

**UI:** Monitor Processing pulse labels the dimension **Contexts → claims (actionable queue)**; ticker tooltips may show terminal inventory separately from queue depth.

---

## Unified intake extraction backlog semantics

Widow prod runs **unified intake** by default (`UNIFIED_INTAKE_EXTRACTION_ENABLED=true`, `LEGACY_INTAKE_EXTRACTION_ENABLED=false`). Legacy per-phase intake (`entity_extraction`, `event_extraction`, `sentiment_analysis`, `quality_scoring`) is **suppressed** in Monitor and scheduling.

| Mode | Monitor shows | Hidden (zeroed) |
|------|---------------|-----------------|
| **Unified (prod default)** | `unified_intake_extraction` **actionable** pending | Legacy intake phases → **0** |
| Legacy rollback | Legacy phase `pending_records` | `unified_intake_extraction` → **0** |

### Actionable vs inventory (legacy-aware)

When `UNIFIED_INTAKE_LEGACY_AWARE_BACKLOG=true` (default), unified pending is **not** "every article missing a unified pass marker."

| Metric | Source | Meaning |
|--------|--------|---------|
| **`actionable_unified_intake`** | `get_unified_intake_backlog_stats()` | Articles still needing unified LLM — **Monitor `pending_records`**, automation selection |
| **`legacy_backfill_eligible`** | Same | Legacy outputs present; marker backfill only (no GPU) |
| **`total_missing_unified_pass`** | Same | Raw inventory (missing unified pass marker) — **not** operator to-do |

**Legacy-complete** = stored `article_entities` + event work (pass marker, `timeline_processed`, or `chronological_events`) + sentiment/quality scores (columns or pass markers).

**Operator scripts:**

| Script | Purpose |
|--------|---------|
| `api/scripts/diagnose_unified_intake_backlog_detail.py` | Per-domain breakdown: actionable vs backfill vs inventory |
| `api/scripts/backfill_unified_intake_pass_from_legacy.py` | Bulk pass-marker backfill (no LLM) |

Masking: `apply_intake_mode_pending_mask()` in `api/shared/pipeline_resource_policy.py`, applied in `backlog_metrics._get_raw_pending_counts()`.

### Backlog metrics cache (pool pressure)

`backlog_metrics._refresh_cache()` uses a **single-flight lock** so concurrent Monitor polls + automation scheduler do not each run the full ~35-phase COUNT sweep on cache expiry.

`get_unified_intake_backlog_stats()` is cached separately (**default 300s**, `UNIFIED_INTAKE_BACKLOG_STATS_TTL_SECONDS`) because its cross-schema queries are heavier than per-phase counts.

Invalidate: `invalidate_backlog_metrics_cache()` (also clears unified stats cache). Unified runner invalidates after processing work.
