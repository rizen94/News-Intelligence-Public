# Controller Architecture — High-Level Design Document

> **Status:** Proposal for review before development. Outlines three high-level controllers and all control functions across the News Intelligence project.

---

## 1. Executive Summary

The News Intelligence system currently has **multiple overlapping orchestration layers** that run in parallel without a single coordination point. This document proposes **three high-level controllers** working in parallel, with clear responsibilities and estimated pipelines:

| Controller | Scope | Primary Role |
|------------|-------|--------------|
| **Finance Controller** | Finance domain only | Gold, EDGAR, FRED refresh; analysis; scheduled ingest |
| **Data Processing Controller** | News/content pipelines | RSS, article processing, ML, topics, storylines, RAG |
| **Review & Cleanup Controller** | Maintenance & hygiene | Consolidation, deduplication, cleanup, log archive |

---

## 2. Current State: Orchestration Landscape

### 2.1 Existing Orchestrators and Schedulers

| Component | Location | Trigger | Scope |
|-----------|----------|---------|-------|
| **AutomationManager** | `api/services/automation_manager.py` | In-process, 10s poll | 20+ tasks (RSS, article, ML, topics, storyline, RAG, cleanup, etc.) |
| **FinanceOrchestrator** | `api/domains/finance/orchestrator.py` | In-process, 60s poll | Gold, EDGAR, analysis; config from `finance_schedule.yaml` |
| **StorylineConsolidationService** | `api/services/storyline_consolidation_service.py` | In-process, 30 min interval | Storyline merge, parent creation, article pooling |
| **TopicExtractionQueueWorker** | `api/domains/content_analysis/.../topic_extraction_queue_worker.py` | In-process, per-domain | Topic extraction for politics/finance/science-tech |
| **MLProcessingService** | `api/services/ml_processing_service.py` | In-process | Background ML article processing |

### 2.2 Cron Jobs (External Triggers)

| Script | Schedule | Action |
|--------|----------|--------|
| `scripts/rss_collection_with_health_check.sh` | 6 AM, 6 PM | RSS collection via `collect_rss_feeds()` |
| `scripts/log_archive_to_nas.py` | 6 AM, 6 PM | Archive local logs to NAS PostgreSQL |

### 2.3 API Pipeline Triggers

| Endpoint | Method | Action |
|----------|--------|--------|
| `POST /api/v4/system_monitoring/pipeline/run_all` | POST | RSS → Topic Clustering → AI Analysis (sequential) |
| `POST /api/v4/{domain}/rss_feeds/collect_now` | POST | Trigger RSS collection for domain |
| `POST /api/v4/fetch_articles` | POST | Fetch articles from configured feeds |
| `POST /storylines/consolidation/run` | POST | Run storyline consolidation |
| `POST /api/v4/{domain}/content_analysis/topics/queue/process` | POST | Process topic queue manually |

### 2.4 Overlap and Redundancy

- **RSS collection** runs from: AutomationManager (1h), cron (2x daily), pipeline route, news_aggregation `collect_now` / `fetch_articles`
- **Topic clustering** runs from: AutomationManager (20 min), pipeline route, topic queue worker, topic queue manual process
- **Data cleanup** runs from: AutomationManager (24h `data_cleanup`), `AutomatedCleanupSystem` (standalone script, not wired into startup)

---

## 3. Proposed Controller Architecture

### 3.1 Controller 1: Finance Controller

**Responsibility:** All finance-domain data refresh, ingest, and analysis. User requests preempt scheduled tasks.

| Behavior | Frequency | Config | Control Functions |
|----------|-----------|--------|-------------------|
| Gold price refresh | 24h | `finance_schedule.yaml` | `submit_task(refresh, topic=gold)` |
| EDGAR 10-K ingest | 168h (weekly) | `finance_schedule.yaml` | `submit_task(ingest, source=edgar)` |
| FRED fetch | On-demand | API params | `submit_task(refresh, topic=fred)` |
| Analysis (synthesis + verification) | On-demand / scheduled | API params | `submit_task(analysis, topic=...)` |

**Control functions:**
- `FinanceOrchestrator.submit_task(task_type, parameters, priority)`
- `FinanceOrchestrator.run_task(task_id)`
- `FinanceOrchestrator.start_scheduler()` / `stop_scheduler()`
- `FinanceOrchestrator.get_schedule_status()`
- API: `POST /{domain}/finance/gold/fetch`, `POST /{domain}/finance/edgar/ingest`, `POST /{domain}/finance/analyze`, `POST /{domain}/finance/fetch-fred`
- API: `GET /{domain}/finance/schedule`, `GET /{domain}/finance/tasks`, `GET /{domain}/finance/tasks/{id}`

**Estimated pipeline:**
```
[Schedule Loop 60s] → Check due → submit_task(low) → run_task
User API request → submit_task(high) → run_task (preempts)
```

---

### 3.2 Controller 2: Data Processing Controller

**Responsibility:** High-level data collection and processing — RSS, articles, ML, topics, storylines, RAG.

| Phase | Task | Interval | Depends On | Estimated Duration |
|-------|------|----------|------------|---------------------|
| 0 | health_check | 2 min | — | 10s |
| 1 | rss_processing | 1h | — | 2 min |
| 2 | article_processing | 20 min | — | 3 min |
| 3 | ml_processing | 20 min | article_processing | 4 min |
| 4 | entity_extraction, sentiment_analysis, quality_scoring | 20 min | article_processing | 2 min each (parallel) |
| 5 | topic_clustering | 20 min | article_processing | 3 min |
| 6 | basic_summary_generation | 10 min | storyline_processing | 2 min |
| 7 | storyline_processing | 30 min | ml, sentiment | 5 min |
| 8 | rag_enhancement | 30 min | basic_summary | 10 min |
| 9 | event_extraction, event_deduplication, story_continuation | 20 min | entity_extraction / event chain | 5 min each |
| 9 | timeline_generation | 30 min | rag_enhancement | 5 min |
| 10 | cache_cleanup | 1h | — | 1 min |
| 11 | digest_generation | 1h | timeline | 3 min |
| 12 | watchlist_alerts | 20 min | story_continuation | 1 min |

**Control functions:**
- `AutomationManager.start()` / `stop()`
- `AutomationManager.get_status()` / `get_metrics()`
- `collect_rss_feeds()` — direct from `api/collectors/rss_collector.py`
- `RSSService.processing.process_all_feeds()` — via `services/rss/`
- `TopicClusteringService.process_article()`
- `BackgroundMLProcessor.queue_article_for_processing()`
- Topic queue: `TopicExtractionQueueWorker.start()`, `process_queue_manually()`
- API: `POST /pipeline/run_all`, `POST /{domain}/rss_feeds/collect_now`, `POST /fetch_articles`
- API: `POST /{domain}/content_analysis/topics/queue/process`, `POST /articles/{id}/process_topics`

**Estimated pipeline (AutomationManager):**
```
[Scheduler 10s] → Phase order + deps → Queue tasks → [Workers x5] execute
Ollama tasks yield to API requests (should_yield_to_api)
```

---

### 3.3 Controller 3: Review & Cleanup Controller

**Responsibility:** Periodic review, consolidation, deduplication, and cleanup. Lower priority, runs when system is idle or on schedule.

| Behavior | Frequency | Location | Control Functions |
|----------|-----------|----------|-------------------|
| Storyline consolidation | 30 min | main_v4 lifespan | `StorylineConsolidationService.run_all_domains()` |
| Data cleanup (old articles) | 24h | AutomationManager | `_execute_data_cleanup` (30-day retention) |
| Cache cleanup | 1h | AutomationManager | `_execute_cache_cleanup` |
| Log archive to NAS | 2x daily | Cron | `scripts/log_archive_to_nas.py` |
| Automated cleanup (logs, temp, docker) | Daily/weekly/monthly | Standalone script | `AutomatedCleanupSystem.run_cleanup()` |
| Deduplication | On-demand | APIs | `POST /duplicates/auto_merge`, `POST /duplicates/prevent` |

**Control functions:**
- `StorylineConsolidationService.run_all_domains()` / `run_consolidation(domain)`
- `AutomatedCleanupSystem.run_cleanup(cleanup_type='auto')`
- `scripts/log_archive_to_nas.py` (cron-invoked)
- API: `POST /storylines/consolidation/run`, `POST /{domain}/storylines/consolidation/run`
- API: `POST /duplicates/auto_merge`, `POST /duplicates/prevent` (news + content dedup)

**Estimated pipeline:**
```
[Consolidation thread 30 min] → run_all_domains
[AutomationManager 24h] → data_cleanup (articles > 30 days)
[Cron 2x daily] → log_archive_to_nas.py
[Manual/script] → AutomatedCleanupSystem.run_cleanup()
```

---

## 4. Complete Control Functions Reference

### 4.1 Finance

| Function / Endpoint | Type | Description |
|--------------------|------|-------------|
| `FinanceOrchestrator.submit_task(...)` | Internal | Queue refresh/ingest/analysis |
| `FinanceOrchestrator.run_task(task_id)` | Internal | Execute queued task |
| `start_scheduler()` / `stop_scheduler()` | Internal | Start/stop schedule loop |
| `get_schedule_status()` | Internal | Next run, last run per task |
| `POST /{domain}/finance/gold/fetch` | API | Trigger gold refresh |
| `POST /{domain}/finance/edgar/ingest` | API | Trigger EDGAR ingest |
| `POST /{domain}/finance/analyze` | API | Run analysis |
| `POST /{domain}/finance/fetch-fred` | API | Trigger FRED fetch |
| `GET /{domain}/finance/schedule` | API | Schedule status |
| `GET /{domain}/finance/tasks` | API | List tasks |
| `GET /{domain}/finance/tasks/{id}` | API | Task result |

### 4.2 Data Processing (RSS, Articles, ML, Topics)

| Function / Endpoint | Type | Description |
|---------------------|------|-------------|
| `collect_rss_feeds()` | Python | Collect all RSS feeds (all domains) |
| `collect_rss_feed(feed_url, feed_name)` | Python | Collect single feed |
| `RSSService.processing.process_all_feeds()` | Python | RSS via service layer |
| `process_rss_feeds(feeds)` | Python | Process feeds (news_aggregation) |
| `AutomationManager.start()` / `stop()` | Python | Start/stop automation |
| `AutomationManager.get_status()` | Python | Status, metrics, queue |
| `POST /pipeline/run_all` | API | RSS → topic → AI (sequential) |
| `POST /{domain}/rss_feeds/collect_now` | API | Collect RSS for domain |
| `POST /fetch_articles` | API | Fetch from feeds |
| `TopicClusteringService.process_article(id)` | Python | Process one article |
| `TopicExtractionQueueWorker.start()` | Python | Queue worker per domain |
| `POST /{domain}/content_analysis/topics/queue/process` | API | Process queue |
| `POST /articles/{id}/process_topics` | API | Process article topics |
| `POST /batch/process` | API | Batch content analysis |

### 4.3 Review & Cleanup

| Function / Endpoint | Type | Description |
|---------------------|------|-------------|
| `StorylineConsolidationService.run_all_domains()` | Python | Full consolidation |
| `StorylineConsolidationService.run_consolidation(domain)` | Python | Per-domain |
| `POST /storylines/consolidation/run` | API | Run consolidation |
| `POST /{domain}/storylines/consolidation/run` | API | Per-domain |
| `AutomatedCleanupSystem.run_cleanup(type)` | Python | Logs, temp, docker, etc. |
| `scripts/log_archive_to_nas.py` | Script | Log archive (cron) |
| `POST /duplicates/auto_merge` | API | Auto-merge duplicates |
| `POST /duplicates/prevent` | API | Prevent future dupes |

### 4.4 Cron Scripts

| Script | Schedule | Invokes |
|--------|----------|---------|
| `scripts/rss_collection_with_health_check.sh` | 6 AM, 6 PM | `collect_rss_feeds()` via Python |
| `scripts/setup_log_archive_cron.sh` | 6 AM, 6 PM | `scripts/log_archive_to_nas.py` |

---

## 5. Estimated Pipelines of Activity

### 5.1 Finance Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ Finance Controller                                               │
├─────────────────────────────────────────────────────────────────┤
│ Schedule loop (60s)                                              │
│   └─ gold_refresh (24h) → submit_task → run_task                 │
│   └─ edgar_ingest (168h) → submit_task → run_task                │
│                                                                  │
│ User requests (preempt)                                          │
│   └─ gold/fetch, edgar/ingest, analyze, fetch-fred              │
│   └─ submit_task(high) → run_task                               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Processing Pipeline (AutomationManager)

```
┌─────────────────────────────────────────────────────────────────┐
│ Data Processing Controller (AutomationManager)                   │
├─────────────────────────────────────────────────────────────────┤
│ Scheduler (10s) → Phase order → Queue → Workers (5 concurrent)  │
│                                                                  │
│ Phase 0: health_check (2 min)                                    │
│ Phase 1: rss_processing (1h)                                     │
│ Phase 2: article_processing (20 min)                             │
│ Phase 3–4: ml_processing, entity, sentiment, quality (20 min)     │
│ Phase 5: topic_clustering (20 min)                              │
│ Phase 6–8: storyline → basic_summary → rag (10–30 min)          │
│ Phase 9: event_extraction → dedup → continuation → timeline     │
│ Phase 10–12: cache, digest, watchlist_alerts                    │
│ Phase 99: data_cleanup (24h)                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Review & Cleanup Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ Review & Cleanup Controller                                      │
├─────────────────────────────────────────────────────────────────┤
│ In-process:                                                      │
│   StorylineConsolidationService (30 min) → run_all_domains        │
│   AutomationManager.data_cleanup (24h) → delete old articles      │
│   AutomationManager.cache_cleanup (1h) → clear_expired_cache      │
│                                                                  │
│ Cron:                                                            │
│   log_archive_to_nas.py (6 AM, 6 PM)                             │
│                                                                  │
│ Manual / future:                                                 │
│   AutomatedCleanupSystem.run_cleanup() (daily/weekly/monthly)     │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Overlapping Entry Points (Current)

```
RSS collection:
  ├─ AutomationManager (1h)
  ├─ Cron (6 AM, 6 PM)
  ├─ POST /pipeline/run_all
  └─ POST /rss_feeds/collect_now, POST /fetch_articles

Topic clustering:
  ├─ AutomationManager (20 min)
  ├─ POST /pipeline/run_all (stage 2)
  ├─ TopicExtractionQueueWorker (continuous)
  └─ POST /topics/queue/process
```

---

## 6. Gaps and Recommendations

### 6.1 Gaps

- **watchlist_alerts** references `watchlist_alerts` table; migration 136 may not be applied.
- **AutomatedCleanupSystem** is not started from `main_v4`; it is a standalone script.
- **Multiple RSS paths** create redundancy and potential race conditions.
- **Pipeline route** uses a simplified topic extractor and keyword sentiment; AutomationManager uses full LLM pipeline.
- **No single controller** for coordination; each subsystem runs independently.

### 6.2 Recommendations for Development

1. **Keep Finance Controller** as-is; it is well-defined and isolated.
2. **Unify Data Processing** around AutomationManager; deprecate or gate pipeline route to avoid overlap.
3. **Consolidate RSS entry points** — choose one primary (e.g. cron + AutomationManager, or cron only) and make others optional/manual.
4. **Wire Review & Cleanup** — start AutomatedCleanupSystem on a schedule or via a dedicated controller thread.
5. **Add controller health endpoints** — each controller exposes status, last run, next run.
6. **Document handoffs** — e.g. when Finance Controller finishes ingest, Data Processing may need to know (if finance content flows into news pipeline).

---

## 7. Appendix: File Locations

| Component | File(s) |
|-----------|---------|
| AutomationManager | `api/services/automation_manager.py` |
| FinanceOrchestrator | `api/domains/finance/orchestrator.py` |
| Finance schedule config | `api/config/finance_schedule.yaml` |
| RSS collector | `api/collectors/rss_collector.py` |
| Pipeline orchestration | `api/domains/system_monitoring/routes/system_monitoring.py` (execute_pipeline_orchestration) |
| Storyline consolidation | `api/services/storyline_consolidation_service.py` |
| Topic queue worker | `api/domains/content_analysis/services/topic_extraction_queue_worker.py` |
| Automated cleanup | `api/scripts/automated_cleanup.py` |
| Log archive | `scripts/log_archive_to_nas.py` |
| RSS cron setup | `scripts/setup_rss_cron_with_health_check.sh` |
| Main startup | `api/main_v4.py` |

---

*Document generated for review before implementation. Last updated: 2025-02-21.*
