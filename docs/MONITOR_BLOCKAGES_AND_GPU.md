# Why Phases Don’t Run and GPU/Ollama Utilization

## Blockages vs slow processing

Phases can show as “not run in last 24h” for two main reasons:

1. **Blockage** – Something prevents the phase from being queued or running.
2. **Slow / never due** – Phase is queued rarely or runs so slowly that it doesn’t complete often.

---

## Common blockages

### 1. Yield-to-API (fixed)

**What it was:** Every API request (including Monitor polling every ~4.5s) was treated as “user active”. ML/Ollama tasks then **yielded** for 15 seconds so the GPU stayed idle whenever the Monitor (or any polling page) was open.

**What we did:** Polling endpoints (e.g. `/automation/status`, `/monitoring/overview`, `/process_run_summary`, `/health`) no longer update the “last API request” time. So having the Monitor open no longer blocks Ollama. Only non‑polling requests (e.g. triggering a phase, loading a heavy page) trigger the yield window.

**Where:** `api/shared/services/api_request_tracker.py` — `record_request(path=...)` skips recording for paths in `_POLLING_PATH_SUBSTRINGS`.

### 2. Backlog skip

Phases **event_tracking**, **claim_extraction**, **context_sync**, **entity_profile_build**, **investigation_report_refresh** are **skipped when backlog is 0** (so we don’t run empty cycles). If the backlog cache or DB says 0, they won’t be queued. If you expect work (e.g. unlinked contexts), check backlog counts on the Monitor or run the phase manually once to confirm.

### 3. Dependencies

Many phases depend on others (e.g. **ml_processing** depends on **article_processing**; **event_tracking** on **context_sync**). If the dependency hasn’t run within its “satisfied” window, the dependent phase won’t be queued. “Never run” bootstrap logic helps the first time; after that, intervals and dependency timing must both allow the phase to run.

### 4. Intervals and queue order

Each phase has an **interval**. It’s only queued when `last_run` is far enough in the past (and backlog/dependencies allow). With many phases and a single queue, if a few long-running or frequently scheduled phases (e.g. rss_processing, context_sync) run often, others can get fewer turns. Backlog-based priority helps (more backlog → queued first when due).

---

## Load balancing and prioritization

To share resources better between data collection, I/O, and GPU work:

### Queue order (what gets run first)

When the scheduler queues sequential tasks, it orders them by:

1. **Priority** (CRITICAL → HIGH → NORMAL → LOW) — so data collection (e.g. rss_processing CRITICAL) and high-value phases (e.g. event_tracking HIGH) are queued before optional/maintenance work (e.g. digest_generation, cache_cleanup LOW).
2. **Phase** (lower phase first) — keeps pipeline order so upstream work is available before downstream.
3. **Backlog** (more work first) — within the same priority/phase, phases with larger backlogs are queued first.

Workers drain a single FIFO queue; the order tasks are **added** ensures higher-priority and pipeline-earlier work is picked first.

### Ollama / GPU concurrency cap

At most **3** Ollama/LLM tasks run at the same time (`MAX_CONCURRENT_OLLAMA_TASKS` in `automation_manager`). That prevents the GPU from being overloaded when many ML phases are due and leaves worker slots for I/O- and DB-bound tasks (RSS, context_sync, claim_extraction, event_tracking, etc.). Ollama tasks acquire a semaphore before running and release it in `finally`, so the cap applies even on failure or retry.

### Tuning

- **Priorities** are set per phase in `AutomationManager.schedules` (e.g. CRITICAL for rss_processing, LOW for digest_generation, cache_cleanup, data_cleanup).
- **Ollama cap**: change `MAX_CONCURRENT_OLLAMA_TASKS` (default 3) in `api/services/automation_manager.py` if you have more GPU capacity or want to favor I/O over ML.
- **Yield-to-API** still applies: Ollama tasks defer when a non-polling API request is active (see above).

---

## GPU / Ollama utilization

- **Ollama** is used by: ml_processing, entity_extraction, sentiment_analysis, topic_clustering, rag_enhancement, claim_extraction, event_tracking, event_extraction, story_continuation, watchlist_alerts, quality_scoring, timeline_generation, basic_summary_generation, storyline_processing, article_processing, event_deduplication (and others that call the LLM).
- If those phases rarely **run** (because of yield, dependencies, or backlog skip), the GPU will sit idle.
- After the yield fix, leaving the Monitor on status pages should no longer block Ollama. If the GPU is still idle, check:
  - **Process run summary** – Are those LLM phases “run recently” or “not run”?
  - **Backlog** – For event_tracking / claim_extraction, is backlog > 0?
  - **Dependencies** – e.g. has **article_processing** run so **ml_processing** can run?

You can force a run from the Monitor with **Run phase now** (e.g. **context_sync** then **event_tracking**) to confirm the pipeline and GPU usage.

---

## Quick checks

| Symptom | Check |
|--------|--------|
| GPU rarely used | Process run summary: are LLM phases (ml_processing, event_tracking, …) running? After the fix, polling the Monitor alone shouldn’t block them. |
| Many “not run” phases | Dependencies (e.g. article_processing for ml_processing); backlog skip (event_tracking, claim_extraction); or intervals not yet due. |
| Only a few phases run | Look at phase order and intervals; use “Run phase now” for key phases to unblock downstream. |
