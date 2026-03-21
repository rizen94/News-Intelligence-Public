# Data Ingestion Pipeline — Assessment

**Purpose:** Map what controls collections, how they are triggered, and identify any orphan processes that require manual triggering or are outside orchestrator control.

**Last updated:** 2026-03-06

---

## 1. Controllers (in-process, started with API)

These run automatically when the API starts (`main.py` lifespan).

| Controller | What it does | Trigger / interval |
|------------|--------------|--------------------|
| **AutomationManager** | 20+ tasks: RSS, article processing, ML, topic clustering, entity/sentiment/quality, storyline, RAG, events, timeline, digest, watchlist, cache cleanup, data cleanup, health check | Internal scheduler (~10s poll); each task has its own interval (e.g. RSS 1h, article 20m, ML 20m). |
| **OrchestratorCoordinator** | Decides *when* to run **RSS collection** and **finance gold refresh**. Calls `collect_rss_feeds()` and `FinanceOrchestrator.submit_task(refresh, topic=gold)`. | Loop every 60s (config: `orchestrator_governance.yaml`). Uses CollectionGovernor for timing. |
| **FinanceOrchestrator** | Gold/FRED/EDGAR refresh, analysis, ingest. Scheduler + queue worker. | Scheduler loop 60s; tasks from `finance_schedule.yaml`. Queue worker processes submitted tasks. |
| **StorylineConsolidationService** | Merge storylines, parent creation, article pooling across domains. | Background thread; interval from `CONSOLIDATION_INTERVAL_MINUTES` (e.g. 30 min). |
| **TopicExtractionQueueWorker** | Topic extraction for politics/finance/science-tech (per-domain queue). | One worker per domain; runs in background thread, processes queue continuously. |
| **MLProcessingService** | ML article processing. | Started with API; processes in background. |
| **NewsroomOrchestrator** (v6) | Event-driven newsroom flow (optional, feature-flagged). | Runs when `orchestration.config` has `enabled: true`. |

**RSS collection is triggered by:**

- **AutomationManager** — `rss_processing` task every 1 hour.
- **OrchestratorCoordinator** — when CollectionGovernor recommends RSS (min/max interval from config, typically every 5–120 min depending on state).
- **API** — `POST /api/system_monitoring/pipeline/trigger`, `POST /api/{domain}/rss_feeds/collect_now`, `POST /api/fetch_articles`.
- **Cron** — if installed: `rss_collection_with_health_check.sh` at 6 AM and 6 PM (see below).
- **Widow** — `newsplatform-secondary.service` runs `run_secondary_worker.py` (RSS every 10 min) on the secondary host.

So RSS is **not** under a single owner; AutomationManager, OrchestratorCoordinator, cron, and Widow can all run it.

---

## 2. External triggers (cron, systemd)

| Trigger | Schedule | What runs | Notes |
|---------|----------|-----------|--------|
| **Cron (Primary)** | Only if user ran `./scripts/setup_rss_cron_with_health_check.sh` | `rss_collection_with_health_check.sh` → checks API health → `collect_rss_feeds()` | 6 AM, 6 PM. Health URL in generated wrapper must be `http://localhost:8000/api/system_monitoring/health` (no `v4`). |
| **Cron (Primary)** | Only if user ran `./scripts/setup_morning_data_pipeline.sh` | `morning_data_pipeline.sh` → `api/scripts/run_rss_and_process_all.py` (RSS + queue articles + topic extraction) | Default env in script: `DB_HOST=localhost`, `DB_PORT=5433` (NAS tunnel). For Widow, set `DB_HOST=<WIDOW_HOST_IP>`, `DB_PORT=5432` or use `.env`. |
| **systemd (Widow)** | Continuous (service runs forever) | `newsplatform-secondary.service` → `scripts/run_secondary_worker.py` → `collect_rss_feeds()` every 10 min | Runs on **Widow** (<WIDOW_HOST_IP>). Not an orphan; documented in ARCHITECTURE_AND_OPERATIONS.md. |
| **Cron (Widow)** | 03:00 daily, 04:00 Sun | `db_backup.sh`, `db_backup_weekly.sh` | Backups only; not ingestion. |

**Orphan / optional:** The **morning data pipeline** and **RSS cron** are **optional**. If you never run `setup_rss_cron_with_health_check.sh` or `setup_morning_data_pipeline.sh`, no cron is installed. Then RSS on Primary is only from AutomationManager (1h), OrchestratorCoordinator (~5–120 min), and manual API calls.

---

## 3. API endpoints that trigger ingestion

| Endpoint | Method | Action |
|----------|--------|--------|
| `POST /api/system_monitoring/pipeline/trigger` | POST | Start full pipeline in background: RSS → topic clustering → AI analysis. |
| `POST /api/{domain}/rss_feeds/collect_now` | POST | Run `collect_rss_feeds()` (all domains) synchronously. |
| `POST /api/fetch_articles` | POST | Fetch articles from feeds (domain-scoped or all). |
| `POST /api/{domain}/content_analysis/topics/queue/process` | POST | Process topic queue for domain. |
| `POST /api/{domain}/finance/edgar/ingest` | POST | Trigger EDGAR 10-K ingest via FinanceOrchestrator. |
| Finance gold/FRED/analyze | POST | Various finance routes that call `FinanceOrchestrator.submit_task(...)`. |

---

## 4. Standalone scripts (not started by API)

These are **not** started from `main.py`. They only run if invoked manually or by cron/systemd.

| Script | Purpose | Orphan? | How to run |
|--------|---------|--------|------------|
| **scripts/run_secondary_worker.py** | RSS every 10 min (loop). | **No** — intended to run on **Widow** as `newsplatform-secondary.service`. | On Widow: `sudo systemctl start newsplatform-secondary`. |
| **scripts/rss_collection_with_health_check.sh** | Check API health, then run RSS. | **No** — used by cron if user installed it via `setup_rss_cron_with_health_check.sh`. | Via cron at 6 AM/6 PM, or manually. |
| **scripts/morning_data_pipeline.sh** | RSS + queue articles + topic extraction. | **Optional** — only runs if cron installed via `setup_morning_data_pipeline.sh`. | Via cron (e.g. 4–6 AM) or manually. |
| **api/scripts/run_rss_and_process_all.py** | Same as morning pipeline (RSS + queue + topic). | Same as above. | Invoked by `morning_data_pipeline.sh` or manually from `api/` with correct `DB_*`. |
| **api/scripts/utilities/manage_ingestion.py** | CLI: `run_rss_collection`, `run_enhanced_rss_collection`, etc. | **Yes** — manual/script only; no cron or API ties. | `python manage_ingestion.py` (from api dir). |
| **api/scripts/utilities/scheduler.py** | Loop: run_rss_collection, run_article_pruning on intervals. | **Yes** — not started by API or any standard cron. | Manual: run as standalone process if you want a separate scheduler. |
| **api/scripts/automated_collection.py** | RSS + optional ML trigger. | **Yes** — manual/script only. | `python automated_collection.py` (from api dir). |
| **api/scripts/daily_batch_processor.py** | Daily batch processing (log path, batch logic). | **Yes** — no `setup_daily_batch.sh` in repo; not wired to cron in this codebase. | Manual or add your own cron. |
| **api/scripts/automated_cleanup.py** (AutomatedCleanupSystem) | Logs, temp, docker cleanup. | **Yes** — documented as not started from main. | Manual or custom cron: `AutomatedCleanupSystem.run_cleanup(...)`. |
| **FeedScheduler** (`api/modules/data_collection/feed_scheduler.py`) | Feed scheduling logic. | **Yes** — not referenced from main or any started service. | Only if some code path instantiates it; currently unused in startup flow. |

---

## 5. Summary: who controls what

| Ingestion / collection type | Controlled by | Orphan / manual? |
|----------------------------|---------------|-------------------|
| **RSS collection** | AutomationManager (1h), OrchestratorCoordinator (adaptive), optional cron (2x/day), Widow worker (10 min), API trigger | No — multiple controllers; no single owner. |
| **Article processing** | AutomationManager (20 min) | No. |
| **ML processing** | AutomationManager (20 min), MLProcessingService | No. |
| **Topic clustering / extraction** | AutomationManager (20 min), TopicExtractionQueueWorker, API trigger, optional morning pipeline | No. |
| **Storyline consolidation** | StorylineConsolidationService (30 min from lifespan) | No. |
| **Finance (gold, EDGAR, FRED, analysis)** | FinanceOrchestrator (scheduler + queue), API triggers | No. |
| **Data cleanup** | AutomationManager `data_cleanup` (24h) | No. AutomatedCleanupSystem is separate and manual. |
| **AutomatedCleanupSystem** | Nothing in app startup | **Yes** — manual or custom cron. |
| **Morning pipeline** (RSS + entity + topic in one shot) | Optional cron only | **Optional** — manual or cron if user installed it. |
| **daily_batch_processor** | Nothing in repo | **Yes** — manual or add cron. |
| **manage_ingestion / scheduler.py / automated_collection** | Nothing | **Yes** — manual only. |
| **FeedScheduler** | Nothing | **Yes** — unused in startup. |

---

## 6. Recommendations

1. **Single source of truth for “when to collect” (optional):** If you want one place to decide when RSS runs, consider making OrchestratorCoordinator the only driver for RSS and disabling AutomationManager’s `rss_processing` (or gating it behind the coordinator). Then keep cron/Widow as backup or remove them.
2. **Fix cron health check URL:** In `scripts/setup_rss_cron_with_health_check.sh`, the generated wrapper uses `http://localhost:8000/api/v4/system_monitoring/health`. Change to `http://localhost:8000/api/system_monitoring/health` so the health check succeeds.
3. **Morning pipeline env:** If using Widow, ensure `morning_data_pipeline.sh` (or cron that runs it) has `DB_HOST=<WIDOW_HOST_IP>` and `DB_PORT=5432`, or that `.env` is sourced.
4. **Orphans to wire (if desired):**  
   - **AutomatedCleanupSystem** — add a scheduled task (e.g. daily) in AutomationManager or a small cron that runs `automated_cleanup.py`.  
   - **daily_batch_processor** — add `scripts/setup_daily_batch.sh` and cron, or a task in AutomationManager.  
   - **FeedScheduler** — remove or wire into a controller if you still need feed-level scheduling.
5. **Widow RSS worker:** Confirm it’s running: `ssh widow 'sudo systemctl status newsplatform-secondary'`. If the API and AutomationManager/OrchestratorCoordinator are on Primary, you have RSS from both Primary and Widow; that’s redundant but not wrong if you want extra collection points.

---

## 7. Quick reference: how to trigger collection manually

```bash
# From Primary (project root)
# 1. Full pipeline (RSS + topic clustering + AI analysis) in background
curl -X POST http://localhost:8000/api/system_monitoring/pipeline/trigger

# 2. RSS only (sync)
curl -X POST http://localhost:8000/api/politics/rss_feeds/collect_now

# 3. From command line (no API)
cd api && .venv/bin/python -c "from collectors.rss_collector import collect_rss_feeds; collect_rss_feeds()"

# 4. Morning pipeline (RSS + queue + topic extraction)
./scripts/morning_data_pipeline.sh   # set DB_* if not using .env
```

```bash
# On Widow
sudo systemctl start newsplatform-secondary   # RSS every 10 min
```
