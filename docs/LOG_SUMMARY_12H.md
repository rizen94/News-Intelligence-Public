# Past 12 Hours: Activity Summary & Performance Review

**Generated:** From `logs/activity.jsonl`, `logs/activity.log`, `logs/app.log`, `logs/finance.log`, and `logs/pipeline_trace.log`.  
**Window:** Last 12 hours (UTC) from latest log timestamps (~2026-03-15 02:00–14:38 UTC).

---

## 1. Activity summary

### Volume (last 12h)

| Component    | Event count | Notes |
|-------------|-------------|--------|
| **rss**     | 11,683      | Feed fetch/pull across all domains |
| **api**     | 9,186       | HTTP requests to the API |
| **external**| 699         | External service calls |
| **orchestrator** | 229  | Queue decisions, scheduled runs, eval_gate |
| **llm**     | 8           | LLM synthesis/revision (Ollama llama3.1:8b) |

**Total:** ~21,800 activity events in the window.

### What was done

**API traffic (top paths):**

- **Orchestrator / monitoring:** `/api/orchestrator/dashboard` (1,053), `/api/orchestrator/status` (735), `/api/context_centric/status` (756), `/api/system_monitoring/*` (overview, automation/status, pipeline_status, sources_collected, process_run_summary) — consistent polling from the Monitor UI and/or dashboard.
- **Domain data:** Articles, storylines, topics, and rss_feeds for politics, finance, and science-tech (hundreds each) — dashboard or domain pages loading.
- **System:** `/api/system_monitoring/status` (368) — health/status checks.

**RSS:**

- **68 distinct feeds** had at least one pull in the window (e.g. Associated Press, Bloomberg, CNN Politics, Reuters, Financial Times, TechCrunch, Hacker News, Federal Reserve, SEC, etc.).
- Many pulls reported **0 fetched, 0 saved** (no new items); some feeds returned articles (e.g. 30 fetched, 10 fetched) with low save counts (dedupe/already seen).

**Orchestrator (processes triggered):**

- **Scheduled background refresh** — queued repeatedly (e.g. “Queued refresh: Scheduled background refresh”).
- **gold_refresh** — “Scheduled run: gold_refresh (interval met)” (finance gold/commodity data).
- **edgar_ingest** — “Scheduled run: edgar_ingest (interval met)” (SEC EDGAR ingest).
- **User requested analysis** — “Queued analysis: User requested analysis” (once in window).
- **eval_gate** — “eval_gate: accept — Verification passed” (finance task verification).

**Finance pipeline (from finance.log):**

- **gold_refresh:** Gold amalgamator fetched FRED and FreeGoldAPI (e.g. 422 + 1,769 observations); EVAL_PASSED; task completed (~503 ms).
- **edgar_ingest:** EDGAR 10-K ingest (e.g. GOLD, NEM, FCX filings); some CIK/index 404s (e.g. AEM, WPM); **vector store add failed** — “chromadb not installed”.
- One **EVAL_FAILED** (task fin-785d685af64f): “all_sources_failed” for a refresh phase; task finished as failed.
- **FinanceOrchestrator** start: scheduler and queue worker started; tasks submitted and completed (refresh, ingest).

**LLM (last 12h):**

- **8 events** — all **llama3.1:8b** “LLM synthesis” (and historically a few “LLM revision” on 2026-03-13).
- Latencies in window: **~6.5 s to ~24.4 s** per call (e.g. 6,564 ms, 8,479 ms, 9,407 ms, 11,206 ms, 12,028 ms, 21,138 ms, 24,440 ms).
- Indicates **Ollama (CPU or GPU)** used for synthesis; no GPU-specific logging in these entries.

**Pipeline trace:**

- Last trace in `pipeline_trace.log` is **2026-03-03** (RSS all_feeds, deduplication, completion ~58 s). No newer pipeline traces in the last 12h in that file.

---

## 2. GPU usage and performance review

**GPU is not currently tracked in the log pipeline.**

- **No `logs/resource_metrics.db`** — the resource metrics DB (used by `scripts/view_metrics.py` for stored metrics) does not exist, so no historical GPU series is being recorded.
- **Activity / app / finance logs** do not contain nvidia-smi or GPU utilization/memory fields; LLM events only record model name (e.g. llama3.1:8b) and latency.
- **scripts/monitor_system.py** can report GPU (memory used/total, utilization %, temperature) via **nvidia-smi** when run on-demand, but it is not writing to a log or DB in this project.

**Implications:**

- **LLM usage:** The 8 LLM calls in the last 12h use **Ollama** (llama3.1:8b). Whether that ran on GPU or CPU is not in the logs; typical Ollama setups use GPU when available.
- **Performance:** Synthesis latencies **6–24 s** are consistent with a local 8B model (CPU or GPU). No errors logged for those 8 calls.
- **Recommendation:** To get a **GPU performance review** in logs:
  1. Run **scripts/monitor_system.py** periodically (cron or from automation) and append output to a log file, or
  2. Integrate **nvidia-smi** (or existing system_monitor if it captures GPU) into the same pipeline that writes `resource_metrics.db` and ensure that DB and logger are created and run, or
  3. Add optional GPU fields to the LLM logger (e.g. device, gpu_memory_mb) when calling Ollama so each LLM event carries GPU context.

---

## 3. Processes triggered (summary)

| Trigger / process       | Source              | Notes |
|-------------------------|---------------------|------|
| **Scheduled background refresh** | Orchestrator       | Recurring; queued many times. |
| **gold_refresh**        | Orchestrator (interval) | Finance gold/commodity data (FRED, FreeGoldAPI). |
| **edgar_ingest**        | Orchestrator (interval) | SEC EDGAR 10-K ingest; some 404s; chromadb add failed. |
| **User requested analysis** | Orchestrator       | One “User requested analysis” in window. |
| **eval_gate accept**    | Finance             | Verification passed for a task. |
| **RSS feed pulls**      | API / collection    | 68 feeds pulled; many 0 new; some errors. |
| **OrchestratorCoordinator start/stop** | app.log        | Loop interval 60 s; multiple stop/start cycles (e.g. around 19:49–22:16 on 2026-03-14). |

No automation_manager “phase” runs (e.g. rss_processing, ml_processing) were seen in the activity log in the last 12h; the **process_run_summary** API reads from in-memory automation status and activity.jsonl, so actual phase runs would appear there if the automation manager had run phases in that window.

---

## 4. Errors and warnings (last 12h)

- **RSS:** **8,091** feed_pull **error** entries in the window. Many are “current transaction is aborted, commands ignored until end of transaction block” (database transaction state), affecting multiple feeds (e.g. NPR, BBC US Politics, Roll Call, RedState, NYT, WSJ, MSNBC, etc.).
- **Finance:** One **EVAL_FAILED** (all_sources_failed). **chromadb not installed** — vector store add failed. Some **EDGAR 404** (e.g. CIK 0000001832) and index fetch failures.

---

## 5. Recommendations

1. **RSS errors:** Investigate and fix the “current transaction is aborted” path (per-feed transaction handling or connection/transaction lifecycle) so feed pulls don’t leave the DB in a bad state.
2. **GPU:** Add persistent GPU metrics (e.g. run monitor_system or nvidia-smi into `resource_metrics.db` or a dedicated GPU log) and/or add GPU context to LLM log events so you can do a true “GPU usage and performance review” from logs.
3. **Finance:** Install/configure chromadb if vector store is required; address EDGAR 404s (e.g. CIK or URL changes).
4. **Process visibility:** Use **GET /api/system_monitoring/process_run_summary?hours=12** (and automation/status, pipeline_status) from the Monitor UI or API to see which phases ran in the last 12h and which did not; that complements this log-based summary.
