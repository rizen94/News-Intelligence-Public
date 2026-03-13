# How the Dashboard Gets Its Data

The Intelligence Dashboard (3-column layout) reads from the **context-centric** layer and orchestrator state. Here’s what feeds each part and what you need to run so it stays populated.

---

## Dashboard sections and data sources

| Section | Data source | How it gets populated |
|--------|-------------|------------------------|
| **What’s New** (latest contexts) | `intelligence.contexts` (by domain, latest first) | Articles → context sync → contexts. See “Contexts” below. |
| **Active Investigations** (tracked events) | `intelligence.tracked_events` (filtered by `domain_keys`) | Event discovery (LLM) groups contexts into events. See “Tracked events” below. |
| **System Intelligence** (counts + collection) | `context_centric` status + orchestrator dashboard | Counts from DB; “Collection” times from `OrchestratorCoordinator` state (`last_collection_times`). |

---

## Pipeline order (what runs when)

1. **RSS collection** → new rows in `{domain}.articles`.
2. **Context sync** → for each new (or backfilled) article, create a row in `intelligence.contexts` and `article_to_context`.
3. **Entity extraction** (existing) → fills `{domain}.article_entities` and (after backfill) `{domain}.entity_canonical`.
4. **Entity profile sync** → copies `entity_canonical` into `intelligence.entity_profiles` (so Entity Browser has data).
5. **Event discovery** → LLM groups contexts into `tracked_events` + `event_chronicles`.
6. **Event coherence review** → prunes off-topic contexts from events.

RSS and context sync must run first; the rest can run on schedules or via API.

---

## What you need running

### 1. API server (with automation)

Start the API so the **AutomationManager** can run its scheduled tasks:

```bash
cd api
uvicorn main_v4:app --host 0.0.0.0 --port 8000
```

With `main_v4`, the app loads the automation manager and runs:

- **context_sync** (e.g. every 20 min): backfills `intelligence.contexts` from domain articles (`sync_domain_articles_to_contexts`).
- **event_tracking** (e.g. every 1 h): discovers events from contexts (`discover_events_from_contexts`).
- **entity_profile_sync** (e.g. every 6 h): syncs entities to the intelligence layer.
- **event_coherence_review** (e.g. every 2 h): cleans events.
- **data_cleanup** (e.g. daily): includes intelligence cleanup.

So: **keeping the API running** is the main way to keep the dashboard populated over time.

### 2. RSS collection (articles in)

The dashboard’s “What’s New” and events ultimately come from **articles**. Articles get in via:

- **Option A – Cron (recommended):**  
  Use the existing script so RSS runs on a schedule, e.g. twice daily:

  ```bash
  ./scripts/rss_collection_with_health_check.sh
  ```

  Ensure cron is set up (see `scripts/setup_rss_cron_with_health_check.sh`). Each run fetches feeds and, for each new article, the collector calls `ensure_context_for_article()` so new articles get a context immediately.

- **Option B – Orchestrator:**  
  The AutomationManager’s **rss_processing** task (e.g. every hour) can run RSS processing. That uses the in-process RSS pipeline; for “production-like” collection, the cron script is usually the main driver.

So: **RSS collection (cron or orchestrator)** fills articles; **context sync / ensure_context_for_article** turns them into contexts that the dashboard shows.

### 3. One-off / catch-up (optional)

If you already have articles but few or no contexts/entities/events:

- **Backfill contexts from existing articles**  
  Either wait for the next **context_sync** run, or call the logic that runs in that task (e.g. run the automation task or invoke `sync_domain_articles_to_contexts(domain_key, limit=500)` per domain from a script or admin endpoint if you add one).

- **Entity profiles (Entity Browser)**  
  In the UI: Discover → Entity browser → **Sync entities**.  
  That calls `POST /api/context_centric/sync_entity_profiles`, which runs `backfill_entity_canonical` then `sync_domain_entity_profiles` so `entity_canonical` and `entity_profiles` are filled. Do this after you have articles (and ideally entity extraction) so there are entities to sync.

- **Tracked events (Active Investigations)**  
  Either wait for the next **event_tracking** run, or trigger discovery once, e.g.:

  ```bash
  curl -X POST "http://localhost:8000/api/context_centric/discover_events?domain_key=politics&limit=100"
  ```

  (Exact path/params as in your `context_centric` routes.)

---

## Quick checklist for a populated dashboard

1. **API running** (`uvicorn main_v4:app ...`) so automation (context sync, event tracking, entity sync, etc.) runs.
2. **RSS collection** running on a schedule (cron + `rss_collection_with_health_check.sh`) so new articles (and thus new contexts) keep appearing.
3. **One-off:** If Entity Browser is empty, run **Sync entities** in the UI (or call sync_entity_profiles) after articles and entity extraction exist.
4. **One-off (optional):** If you want events immediately, trigger **discover_events** once; otherwise wait for the next event_tracking run.

After that, “What’s New” and “Active Investigations” will reflect new contexts and events as they’re created, and “System Intelligence” will show counts and collection times from the context-centric API and orchestrator state.
