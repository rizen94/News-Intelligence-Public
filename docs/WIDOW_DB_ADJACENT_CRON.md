# Widow: DB-adjacent cron (no full API on Widow)

**Goal:** Keep **AutomationManager only on the main GPU machine** (single scheduler). Run **RSS** and **light, SQL-heavy sync** next to PostgreSQL on **Widow** so the main host spends less time on collection and context bookkeeping.

**How processing flows:** `collect_rss_feeds` inserts rows into domain **`articles`** tables. Downstream work (enrichment, entity extraction, LLM, topic clustering) is still driven by **AutomationManager on the main PC**, which reads **database state** — there is no separate “RSS queue” into AutomationManager. Skipping RSS on the main host only removes duplicate fetching; new rows are still picked up by existing phases. The **`content_enrichment`** scheduled task (plus the enrichment loop inside **`collection_cycle`**) drains pending full-text fetches on a **5-minute** cadence so Widow-ingested articles are not stuck waiting only for **`collection_cycle`** (which can be throttled when downstream backlog is high).

---

## 1. Main GPU host (API + AutomationManager)

Add to project-root **`.env`** (or the environment of the process that runs uvicorn):

```bash
# RSS runs on Widow (systemd secondary and/or cron --rss); do not fetch feeds every collection_cycle here
AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true

# Phases run on Widow via api/scripts/run_widow_db_adjacent.py — disable here to avoid duplicate work
AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush
```

Restart the API after changing env. `AUTOMATION_DISABLED_SCHEDULES` turns off those schedules **and** removes them from other tasks’ `depends_on` so dependents (e.g. claim extraction) still run.

---

## 2. Widow: RSS

**Option A (default):** Keep **`newsplatform-secondary.service`** — RSS every 10 minutes, no API.

**Option B:** Stop the secondary service and run **`run_widow_db_adjacent.py --rss`** from cron instead. **Do not** run both on the same interval unless you want duplicate collection attempts (feeds should dedupe, but it wastes work).

---

## 3. Widow: context sync + entity profile sync + pending DB flush

Script: **`api/scripts/run_widow_db_adjacent.py`**

```bash
cd /opt/news-intelligence
mkdir -p logs
PYTHONPATH=api .venv/bin/python api/scripts/run_widow_db_adjacent.py \
  --context-sync --entity-profile-sync --pending-db-flush
```

Install cron from **`infrastructure/widow-db-adjacent.cron`** (edit user/path, then copy to `/etc/cron.d/`).

---

## 4. Do not run a full FastAPI stack on Widow

A second API duplicates **AutomationManager**, orchestrator loops, and ML — avoid it. If nginx on Widow serves the public demo, set **`PUBLIC_API_UPSTREAM`** to the **main host** `192.168.x.x:8000` and disable **`news-intelligence-api-public.service`**. See [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md).

---

## 5. Adding more Widow-only phases later

Pick schedules that are **mostly DB / CPU** and **do not** require local Ollama on Widow. Extend `run_widow_db_adjacent.py` and add their names to **`AUTOMATION_DISABLED_SCHEDULES`** on the main host. LLM-heavy phases (claim extraction, coherence review, etc.) should stay on the GPU host unless `OLLAMA_HOST` points to it.
