# Monitor reporting, logging, and metrics (inventory)

Single map of **where** the platform records “how well we are processing,” **what runs on a schedule** vs **manual/CLI**, and **how the Monitor UI** consumes it. Complements `AGENTS.md` (automation visibility) and `docs/DIAGNOSTICS_EVENT_COLLECTOR.md` (operator diagnostics).

---

## Monitor UI vs Grafana

| Surface | Owns | Does not own |
|---------|------|--------------|
| **In-app Monitor** (`/:domain/monitor`) | Live health (API/DB/web), automation running + FIFO/LIFO chip, **DB worker/UI pressure chips** (`resource_router.db_pressure`), current/recent activity, phase **pulse** (pending / fails / runs-to-clear), **Run phase now**, Open Grafana deep link | Multi-hour charts, GPU history, backlog ETAs, DB sessions |
| **Homelab Grafana** (NI Ops `uid=ni-ops`) | Queue depth / scheduling backlog history, intake SLA (when available), DB size & table growth, automation run rates, RSS feed/article counters (`ni_*`) | Phase triggers and live “what is running now” |

Deep link: build with `VITE_NEWS_INTEL_GRAFANA_URL` (documented as `NEWS_INTEL_GRAFANA_URL`), or set browser `localStorage.news_intel_grafana_url`. Dashboard JSON: `api/monitoring/grafana/` — apply steps in that folder’s README (PopOS Homelab).

SQL explorer and Work executed stay on **separate admin routes** — not folded into Grafana.

---

## Documentation (methodology)

| Doc | Role |
|-----|------|
| `AGENTS.md` | Automation visibility: `automation_run_history`, `/automation/status`, `/backlog_status`, pipeline vs polling. Monitor = live/action; Grafana = history/infra. |
| `docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md` | Pipeline order and handoffs (not a metrics store). |
| `docs/DIAGNOSTICS_EVENT_COLLECTOR.md` | Diagnostic events API and collection patterns. |
| `docs/AUTOMATION_MANAGER_SCHEDULING.md` | Scheduler caps, queue depth, concurrent phases. |
| `docs/MONITORING_SSH_SETUP.md` | Remote device metrics over SSH. |
| `docs/MONITOR_BLOCKAGES_AND_GPU.md` | GPU / blockage notes for Monitor operators (history → Grafana). |
| `api/monitoring/grafana/README.md` | Homelab import of NI Ops + RSS dashboards. |

---

## Database (durable reporting)

| Store | Written by | Used for |
|-------|------------|----------|
| **`public.automation_run_history`** | `persist_automation_run_history` on phase completion; `pending_db_flush` replay; optional **`POST /api/system_monitoring/cron_heartbeat`** | Last run, “runs in window,” nightly recent runs in `backlog_status`, **`GET /api/system_monitoring/process_run_summary`**, **`GET /api/system_monitoring/processing_progress`**. |
| **`public.db_pool_pressure_advisory`** | API (`pool_pressure_advisory.publish_*`) on headroom / status / waiter | Cross-host backpressure for PopOS workers; Monitor chips from live snapshot on `/automation/status`. |
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
| `GET /api/system_monitoring/prometheus` | Prometheus text exposition (`ni_*`) for Homelab Grafana. Cached ~60s. Optional `NI_PROMETHEUS_SCRAPE_TOKEN` via `X-NI-Scrape-Token`. |
| `GET /api/system_monitoring/automation/status` | Live queues, `pending_counts`, phase table, resource router (incl. `db_pressure`, **`api_yield`** coarse UI-yield proxy). |
| `GET /api/system_monitoring/backlog_status` | ETAs, steady_state, nightly_catchup, dimension throughputs (cached ~15s). **Not on default Monitor** — Admin / Grafana history. |
| `GET /api/system_monitoring/processing_progress` | **Processing pulse:** `routes/processing_progress.py`, mounted on `resource_dashboard` router. **phase_dashboard** fields: `pending_records` (unprocessed DB rows), `estimated_batch_per_run` (modeled rows per run), `batches_to_drain` (ceil divide = runs to clear queue, or `null`). Plus dimension throughputs, pass rates, 72h hourly buckets (cached **~90s** per worker). |
| `GET /api/system_monitoring/process_run_summary` | Phases run vs not in N hours, pipeline checkpoints, optional `activity.jsonl` **byte-bounded tail** (never full-file read — prod log can be multi‑GB). Middleware budget 90s. **Not on default Monitor.** |
| `GET /api/system_monitoring/pipeline_status` | Pipeline coordinator snapshot. |
| `GET /api/system_monitoring/database/connections` | `pg_stat_activity` style sessions. **Not on default Monitor.** |
| `POST /api/system_monitoring/circuit_breakers/reset` | Reset Ollama CB keys (`name` optional; default all of `ollama` / `ollama_gpu` / `ollama_cpu` / `ollama_pop_os`). Monitor **Actions → Reset Ollama CB** (and curl) after hard shed. |
| `GET /api/diagnostics_events/...` | Curated diagnostic events (see diagnostics doc). |

### Ollama backpressure terms (Monitor / AM)

| Term | Meaning |
|------|---------|
| **defer** | Schedule or worker leaves work pending and retries later (requeue). Preferred under CB open / overload. |
| **shed** | Hard pause of intake (`collection_cycle`, `storyline_discovery`, `proactive_detection`, `document_collection`) while any Ollama breaker is OPEN; must-run cadence also defers. Explicit Monitor phase trigger may still proceed. |
| **overload** | Timeout / 502–504 from Ollama — raise overloaded, **do not** trip the breaker; trickle drain continues. Host unreachable → `trip_open` hard shed. |
| **trickle** | Shrink LLM drain batches (profiles, appraisal, etc.) under backlog / CB pressure so work keeps moving without skip-and-burn. |

**Contract (single hub):** All generate/embed traffic goes through [`api/shared/services/llm_service.py`](../api/shared/services/llm_service.py). Keys: `OLLAMA_CB_KEYS` = `ollama`, `ollama_gpu`, `ollama_cpu`, `ollama_pop_os` in [`circuit_breaker_service.py`](../api/services/circuit_breaker_service.py). Recovery: `success_threshold=1` (one good half-open probe closes). Unload / `keep_alive:0` helpers are outside failure accounting.

**Health payload:** `GET /api/system_monitoring/health` → `circuit_breakers.ollama_keys`, `circuit_breakers.ollama_shedding`, and per-key `breakers` state. `services.ollama` is `circuit_open` when any Ollama key is open or half-open.

**Operator recovery (prefer reset over API restart):** use Monitor **Actions → Reset Ollama CB** when the status chip shows open keys, or:

```bash
# Inspect
curl -sS http://127.0.0.1:8000/api/system_monitoring/health \
  | jq '{status, ollama: .services.ollama, cb: .circuit_breakers}'

# After Ollama is reachable again — close hard shed without restarting uvicorn
curl -sS -X POST http://127.0.0.1:8000/api/system_monitoring/circuit_breakers/reset \
  -H 'Content-Type: application/json' -d '{}'

# Optional: one key only
curl -sS -X POST http://127.0.0.1:8000/api/system_monitoring/circuit_breakers/reset \
  -H 'Content-Type: application/json' -d '{"name":"ollama_gpu"}'
```

**Verify (from `api/`):** `python scripts/_debug_ollama_cb_starve.py` (CB contract); `python scripts/_check_no_direct_ollama_generate.py` (no stray `/api/generate` callers outside hub/unload); `python scripts/_check_prompt_paths_exist.py` (every live `PROMPT_PATH` / features.yaml prompt `.md` exists).

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
| `api/scripts/_debug_ollama_cb_starve.py` | CB contract smoke: probe after recovery, `success_threshold=1`, shedding sees `ollama_gpu`. |
| `api/scripts/_check_no_direct_ollama_generate.py` | Grep gate: production `/api/generate` / `/api/embeddings` only via hub (or unload helpers). |
| `api/scripts/_check_prompt_paths_exist.py` | Gate: live file-based LLM prompts (`PROMPT_PATH` + `features.yaml`) must exist on disk. |

**In-repo cron template:** `infrastructure/widow-db-adjacent.cron` — DB-adjacent jobs on Widow (RSS, `context_sync`, etc.), **not** the snapshot/report scripts above.

---

## What is “scheduled” for metrics?

- **No built-in periodic job** in the repo writes backlog snapshots to disk; that is **manual** (`./snapshot_backlog_status` or `scripts/snapshot_backlog_status.sh`) or external cron you add.
- **AutomationManager** (on the main API host) **continuously** runs phases and **appends** `automation_run_history` — that **is** the scheduled metrics backbone for phase frequency and duration.
- **Monitor SPA** polls overview (~15s) and processing pulse; queue depths ~every 60s. Historical trends are Homelab Grafana on `ni_*`, not SPA charts.

---

## Monitor UI (live / action)

Default Monitor is four blocks (not a second Grafana):

1. **Status** — API / DB / web, automation running, FIFO/LIFO chip, light corpus chips, pipeline status chip.
2. **Now** — current + short recent activity.
3. **Pulse** — phase table: pending, runs to clear, fail/run counts (stuck phases highlighted).
4. **Actions** — Run phase now + **Open Grafana** (deep link).

**Removed from default Monitor:** GPU 72h chart, trend arrows, hourly vanity bucket count, active-domains card noise, backlog ETAs / process-run summary / DB sessions (API still available for Admin/Grafana).

For a **true** week-long **time-series** of queues and SLA, use Homelab Grafana (`api/monitoring/grafana/ni-ops-dashboard.json`) scraping `/api/system_monitoring/prometheus`. Operator CLI snapshots (`.local/backlog_snapshots/`) remain available for burndown scripts.
