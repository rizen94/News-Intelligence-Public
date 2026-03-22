# Narrative bootstrap & DB outage handling

## Automatic domain storylines from emerging clusters

**`proactive_detection`** (per domain) finds recent articles **not** yet in any storyline, clusters them by keyword overlap, writes **`public.emerging_storylines`**, and — when the cluster is strong enough — **creates a real row in `{politics|finance|science_tech}.storylines`** with:

- Linked **`storyline_articles`** for still-unlinked articles  
- **`automation_enabled = true`**, **`automation_mode = suggest_only`** (suggestions queue + downstream enrichment)  
- **`story_entity_index`** seeding via **`StorylineAutomationService._merge_article_entities_to_storyline`** so **`story_continuation`** can match events later  
- **`public.emerging_storylines`** updated to **`status = confirmed`** and **`merged_into_storyline_id`**

### Thresholds (env)

| Variable | Default | Meaning |
|----------|---------|---------|
| `PROACTIVE_PROMOTE_MIN_ARTICLES` | `4` | Minimum unlinked articles in cluster to promote |
| `PROACTIVE_PROMOTE_MIN_CONFIDENCE` | `0.55` | With ≥ `PROACTIVE_PROMOTE_MIN_ARTICLES`, also require this confidence |
| (implicit) | — | Promotion also if cluster has **≥ 5** articles (confidence can be lower) |

Tune thresholds to trade off noise vs coverage across **finance** and **science-tech** (same logic as politics).

## DB outage: pause scheduling + local spill file

When **`AUTOMATION_PAUSE_WHEN_DB_DOWN`** is `true` (default), the scheduler uses **`probe_database_server_reachable()`** (a **short direct** `psycopg2.connect`, **not** the worker pool) with cache TTL **`DB_HEALTH_CACHE_SECONDS`** (default **8**). That way **pool exhaustion** (checkout timeout) does **not** pause automation — only real loss of connectivity to PostgreSQL does.

If **`automation_run_history`** INSERT fails (e.g. mid-outage), the run is appended to **`.local/db_pending_writes/pending.jsonl`** (override with **`DB_PENDING_WRITES_DIR`**).

Phase **`pending_db_flush`** (Monitoring, ~45s interval) replays those rows when the DB is back and clears the file. It is included in **`AUTOMATION_QUEUE_PAUSE_ALLOW`** so it can still be requested under queue soft-cap.

### Env summary

| Variable | Default | Meaning |
|----------|---------|---------|
| `AUTOMATION_PAUSE_WHEN_DB_DOWN` | `true` | Pause automation scheduling when DB health check fails |
| `DB_HEALTH_CACHE_SECONDS` | `8` | Cache positive/negative **server** probe |
| `DB_AUTOMATION_PROBE_CONNECT_TIMEOUT` | `4` | Seconds for direct TCP/auth probe (automation pause only) |
| `DB_PENDING_WRITES_DIR` | *(empty)* | Spill directory (default: repo `.local/db_pending_writes`) |

**Scope:** The spill file currently buffers **`automation_run_history`** only. Other writes (events, articles) still need the DB; extending the queue is possible by adding new `type` handlers in `shared.database.pending_db_writes.flush_pending_writes`.

## Related code

- `domains/storyline_management/services/proactive_detection_service.py` — cluster → emerging → promote  
- `services/automation_manager.py` — `_should_run_task` DB gate, `pending_db_flush`, `_persist_automation_run` enqueue  
- `shared/database/db_availability.py` — `is_automation_db_ready()`  
- `shared/database/pending_db_writes.py` — JSONL queue + flush  
