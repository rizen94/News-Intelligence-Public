# Contexts by domain (politics vs finance vs science-tech)

**Summary:** Politics and finance (and science-tech) use the **same** pipeline for collecting and storing contexts. The only difference is **which RSS feeds** are used. No domain-specific code path prevents finance from loading.

---

## How contexts are collected and stored

1. **RSS collection** (`api/collectors/rss_collector.py` — `collect_rss_feeds()`)
   - Reads active feeds from **each** domain schema:
     - `politics.rss_feeds` → `domain_key = 'politics'`
     - `finance.rss_feeds` → `domain_key = 'finance'`
     - `science_tech.rss_feeds` → `domain_key = 'science-tech'`
   - For each feed, fetches entries and inserts **articles** into that domain’s table:
     - Politics feeds → `politics.articles`
     - Finance feeds → `finance.articles`
     - Science-tech feeds → `science_tech.articles`
   - After each new article insert, calls `ensure_context_for_article(domain_key, article_id)`.

2. **Context creation** (`api/services/context_processor_service.py`)
   - `ensure_context_for_article(domain_key, article_id)`:
     - Reads the article from `{schema}.articles` (e.g. `finance.articles`).
     - Inserts one row into `intelligence.contexts` with that `domain_key`.
     - Links it in `intelligence.article_to_context`.
   - Same logic for every domain; no branch by domain.

3. **Backfill** (automation or API)
   - `sync_domain_articles_to_contexts(domain_key, limit)` finds articles in that domain that don’t yet have a context and creates contexts for them.
   - Automation runs this for **all three** domains (politics, finance, science-tech) in the `context_sync` task.

---

## Why finance might have no contexts

- **No finance articles**  
  If there are no rows in `finance.articles`, there is nothing to turn into contexts. That happens when:
  - **No (or no active) finance RSS feeds**  
    `finance.rss_feeds` is empty or every feed has `is_active = false`. The collector only processes feeds from `finance.rss_feeds` for the finance domain.
- **Articles exist but contexts not created yet**  
  Possible if:
  - Context pipeline was added after articles were ingested, or
  - `ensure_context_for_article` failed for those inserts (e.g. DB/connection issue).  
  Fix: run **Sync contexts** for the finance domain (Discover → “Sync contexts for this domain”) or call `POST /api/context_centric/sync_contexts?domain_key=finance`.

---

## What to do

1. **Check feed and article counts**
   - `GET /api/context_centric/quality` → `by_domain.finance`:
     - `rss_feeds_active`: number of active feeds in the finance domain.
     - `articles`: number of rows in `finance.articles`.
     - `contexts`: number of finance contexts in `intelligence.contexts`.
2. **If `rss_feeds_active` is 0**
   - Add finance RSS feeds (e.g. SEC, Federal Reserve, Treasury, FDIC):
     - **UI:** Monitor (or the domain’s RSS feed management) → add feeds for the **Finance** domain.
     - **API:** `POST /api/finance/rss_feeds` with `feed_name` and `feed_url`.
     - **Migration:** System monitoring route that applies migration 128 can insert official government/SEC feeds into `finance.rss_feeds`.
   - Then run RSS collection (e.g. Monitor → trigger collection, or automation will run it). New articles will go to `finance.articles` and get contexts via `ensure_context_for_article`.
3. **If `articles` > 0 but `contexts` is 0**
   - Run context sync for finance:
     - **UI:** Discover (Finance domain) → “Sync contexts for this domain”.
     - **API:** `POST /api/context_centric/sync_contexts?domain_key=finance&limit=500`.

---

## Restarting to reapply frontend/API fixes

- **Full stack (needs Docker for Redis):**  
  `./stop_system.sh` then `./start_system.sh`
- **API only:**  
  Stop any running uvicorn, then from `api/`:  
  `python3 -m uvicorn main_v4:app --host 0.0.0.0 --port 8000`  
  (or use your usual run script; ensure env e.g. `DB_*` is set.)

Frontend changes (e.g. context-centric base URL fix, Discover empty state) apply after a refresh or rebuild; no backend restart required for those.
