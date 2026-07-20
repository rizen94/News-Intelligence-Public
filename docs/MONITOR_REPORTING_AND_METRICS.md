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

**Gap (v10.1 fix):** Long drain tasks used to record only when the **outer scheduler task** finished. Monitor now also counts **`metadata.status=batch_round`** rows (one per completed batch with rows processed), including work done via `storyline_assembly_service` and `story_enhancement` → `entity_profile_build` attribution. Throughput counts still come from **data plane SQL** in `backlog_metrics`.

**Monitor run vocabulary SSOT (v10.1):** `api/shared/monitor_run_vocabulary.py` defines canonical terms (`phase_key`, `iteration_index`, `rows_processed`, `run_history_status`) and shared predicates (`throughput_from_payload`, `is_measurable_run_history_row`, `run_history_measurable_sql`). All batch/drain writers should use **`emit_phase_run_event()`** so the activity feed and `automation_run_history` stay aligned. Segment audit: `docs/monitor_alignment/`. API exposes additive aliases (`estimated_phase_runs`, `run_success_rate_24h`, `monitor_schema_version`) — see `processing_progress.reporting_definitions`.

**Queue depth vocabulary SSOT (2026-07):** `api/shared/pipeline_queue_vocabulary.py` and `api/shared/pipeline_queue_counts.py` define canonical terms (`queue_depth`, `scheduling_backlog`, `inventory_missing_pass`, `spine_queue_depth`, `in_memory_queue_depth`, `urgent_queue_depth`). Monitor run vocabulary remains in `api/shared/monitor_run_vocabulary.py` (`MONITOR_SCHEMA_VERSION` **1.1**). Dimension chip backlog delegates via `api/shared/monitor_dimension_metrics.py`. CI: `scripts/verify_pipeline_queue_alignment.py`.

**Phase E — heartbeat honesty & backlog snapshots (2026-07):** Conductor drains write `pipeline_phase_heartbeats.detail.status=running` at start and `complete`/`failed` at end (`conductor_run_history`). Monitor merges Widow + PopOS heartbeat `running` rows into Current activity (no stale “running” without a fresh heartbeat). Auto-silence persists in `public.phase_silence_state` via `phase_retry_silence_service` (config: `orchestrator_governance.yaml` → `phase_retry_policy`). Monitor backlog remains read-mostly from `automation_state.monitor_backlog_snapshot`; each refresh also appends `intelligence.monitor_backlog_snapshot_history` for p95/trend.

**`processing_progress` phase `queue_depth`:** Per-phase actionable depth from `pipeline_queue_counts.get_all_phase_queue_depths()` (cached via `backlog_metrics`, ~90s TTL). SQL aligns with each phase’s automation / PopOS drain selection rules:

- `claim_extraction` → `sql_claim_extraction_eligible` (gap-fill when fusion on)
- `topic_clustering` → `TopicClusteringService.count_pending_articles` (same predicates as `select_pending_article_ids`; default **first-pass-only**, not retry inflation)
- `storyline_assembly` → `count_assembly_actionable_pending` (unlinked only in domains that pass `domains_needing_assembly` threshold / `assembly_after_enrichment`)
- `entity_profile_build` → profiles with mentions, not raw context rows

Each row also exposes **`scheduling_backlog`** (`max(queue_depth − rows_per_run, 0)`). Legacy aliases: `pending_records`, `batches_to_drain` → `estimated_phase_runs`, `estimated_batch_per_run` → `rows_per_run`. Retry/first-pass breakdown for pass-marker phases remains on **`first_pass_depth` / `retry_depth`** (work-queue metrics), not inside `queue_depth`.

**Rows/run (measured vs config):** Each `phase_dashboard` row exposes **`rows_per_run`** (ETA divisor), **`measured_rows_per_run_24h`** (24h AVG from `automation_run_history` batch rows with throughput), **`configured_rows_per_run`** (`BATCH_SIZE_PER_TASK` / env), **`rows_per_run_source`** (`measured_24h*` | `config_default` | `no_row_batch_model`), and **`rows_per_run_sample_count`**. SQL aggregation: `monitor_run_vocabulary.query_measured_rows_per_run_by_phase`. Phases without a row-batch model (`collection_cycle`, ops/health) set `rows_per_run_source=no_row_batch_model` and hide ETA runs.

**Do not sum phase queues:** Each **queue_depth** cell is an independent per-phase depth (articles, contexts, storylines, or profiles — units differ). Adding rows across phases **double-counts correlated pipeline work**. Use **`actionable_unified_intake`** and **`actionable_no_claims`** for operator ETA — not **`inventory_missing_pass`**, **`total_missing_unified_pass`**, or **`spine_queue_depth`**.

---

## API endpoints (Monitor-relevant)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/system_monitoring/monitoring/overview` | API/DB/webserver + in-memory activity feed. |
| `GET /api/system_monitoring/automation/status` | Live queues: `queue_depths` (canonical), `scheduling_backlog`, `in_memory_queue_depth`; legacy `pending_counts`, `backlog_counts`, `combined_queue_depth`. |
| `GET /api/system_monitoring/backlog_status` | ETAs, steady_state, `intake_catchup_latency` (p50/p95 RSS→full-process hours vs `CATCHUP_SLA_HOURS` default 6), nightly_catchup; dimension throughputs use `monitor_dimension_metrics` for backlog (cached ~15s). |
| `GET /api/system_monitoring/processing_progress` | **Processing pulse:** `phase_dashboard` rows: `queue_depth` (+ `pending_records` alias), `scheduling_backlog`, `estimated_phase_runs` (+ `batches_to_drain` alias), `first_pass_depth` / `retry_depth` aliases, `scheduling_status`, `queue_stale`. Snapshot accepts `queue_depths` / `scheduling_backlog` keys. Cached **~90s** per worker. |
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
| **`scheduling_backlog`** | `get_all_backlog_counts()` | Excess beyond one batch tick: `max(queue_depth − estimated_batch_per_run, 0)` — scheduler priority, not ETA |
| **`actionable_unified_intake`** | `get_unified_intake_backlog_stats()` | Articles still needing unified LLM — **Monitor `queue_depth` / `pending_records`**, automation selection |
| **`legacy_backfill_eligible`** | Same | Legacy outputs present; marker backfill only (no GPU) |
| **`inventory_missing_pass`** / **`total_missing_unified_pass`** | Same | Raw inventory (missing unified pass marker) — **not** operator to-do |
| **`spine_queue_depth`** | `pipeline_queue_counts.get_spine_queue_depth()` | Spine work-queue table rows (`unified_intake_queue`) — **operational only**; must not be used for ETA or bulk catch-up floor |

### Intake → full-process catchup latency

SSOT: `api/shared/intake_catchup_latency.py` (CLI: `api/scripts/intake_catchup_latency.py`). Exposed on **`backlog_status.intake_catchup_latency`** and monitor backlog snapshots (`automation_state` key `intake_catchup_latency_samples`).

| Field | Meaning |
|-------|---------|
| **`p50_hours` / `p95_hours`** | Hours from `articles.created_at` to last of enrich terminal / UIE pass / context link / topic pass / storyline `added_at` for cohort articles that are **not** pending any of those stages |
| **`max_inflight_age_hours`** | Oldest still-pending article age in the intake window (how far the current batch is behind) |
| **`ok_under_sla`** | `p95_hours ≤ CATCHUP_SLA_HOURS` (default **6**) when `sample_n_completed ≥ CATCHUP_SLA_MIN_SAMPLES` |
| **Spine `spine_p95_latency_hours`** | Separate UIE-only metric (~4h SLA) — do not confuse with full-process catchup |

Assembly / entity_profile_build / dossier are **out of scope** for the 6h SLA.

### Queue depth vs spine queue vs inventory

**Operator rule:** trust **`queue_depth`** (alias `pending_records`) and **`actionable_unified_intake`** for "how much LLM work remains."

| Count | Use for ETA? | Notes |
|-------|--------------|-------|
| `queue_depth` / `actionable_unified_intake` | **Yes** | Eligibility SQL — same path as `unified_intake_extraction_runner` |
| `scheduling_backlog` | No | Scheduler excess beyond one tick — informational on `phase_dashboard` rows |
| `inventory_missing_pass` | No | Includes legacy-complete rows needing marker-only backfill |
| `spine_queue_depth` | **No** | Queue table can inflate (e.g. 9k vs ~3k actionable) when rows are stale or non-actionable |

SSOT modules: `api/shared/pipeline_queue_vocabulary.py`, `api/shared/pipeline_queue_counts.py`, `api/shared/monitor_dimension_metrics.py`. CI: `scripts/verify_pipeline_queue_alignment.py`.

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
