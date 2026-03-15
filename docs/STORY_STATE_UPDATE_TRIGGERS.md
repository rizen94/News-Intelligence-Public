# Automated Story State Update Triggers

Design for updating story states when new facts are added to the intelligence layer. Aligns with [RAG Enhancement Roadmap](RAG_ENHANCEMENT_ROADMAP.md) Phase 2 (story state tracking) and Phase 4 (watch patterns and alerts).

---

## 1. Overview

When a **versioned fact** is inserted (or superseded), we:

1. **Log** the change in `intelligence.fact_change_log`.
2. **Resolve** the fact’s entity profile → domain + canonical name.
3. **Find affected storylines** per domain via `story_entity_index` (entity name match).
4. **Enqueue** `(domain_key, storyline_id)` in `intelligence.story_update_queue`.
5. **Process** the queue (batch): refresh story state, optionally run significance analysis and alerts.

Storylines live in **domain schemas** (`politics.storylines`, `finance.storylines`, `science_tech.storylines`). Entity linkage is via **entity_profile_id** → `intelligence.entity_profiles` (domain_key, canonical_entity_id) → domain’s `entity_canonical.canonical_name` → `story_entity_index.entity_name` (per domain). The DB trigger only writes to `fact_change_log`; the rest runs in the application.

---

## 2. Event flow

```
INSERT/UPDATE intelligence.versioned_facts
    → Trigger: INSERT intelligence.fact_change_log (fact_id, entity_profile_id, change_type)
    → Optional: pg_notify('fact_change', payload)

Application (cron or listener):
    → SELECT * FROM fact_change_log WHERE processed = false
    → For each: entity_profile_id → (domain_key, canonical_name)
    → For each domain: SELECT storyline_id FROM {schema}.story_entity_index WHERE LOWER(entity_name) = LOWER(canonical_name)
    → INSERT story_update_queue (domain_key, storyline_id, trigger_type, trigger_id, priority)
    → UPDATE fact_change_log SET processed = true, processed_at = now()

Processor (cron or worker):
    → SELECT * FROM story_update_queue WHERE processed = false ORDER BY priority, created_at LIMIT N
    → Group by (domain_key, storyline_id), dedupe
    → For each: update_story_state(domain_key, storyline_id) — e.g. refresh timeline, maturity, alerts
    → UPDATE story_update_queue SET processed = true, processed_at = now()
```

---

## 3. Schema (intelligence schema)

### 3.1 fact_change_log

| Column | Type | Purpose |
|--------|------|--------|
| id | SERIAL | PK |
| fact_id | INTEGER | intelligence.versioned_facts.id |
| entity_profile_id | INTEGER | From versioned_facts |
| change_type | VARCHAR(50) | new_fact, fact_update, fact_superseded |
| changed_at | TIMESTAMPTZ | Default now() |
| processed | BOOLEAN | Default false |
| processed_at | TIMESTAMPTZ | When app finished |
| story_updates_triggered | INTEGER | Count of queue rows created |

### 3.2 story_update_queue

| Column | Type | Purpose |
|--------|------|--------|
| id | SERIAL | PK |
| domain_key | VARCHAR(50) | politics, finance, science-tech |
| storyline_id | INTEGER | ID in that domain’s storylines |
| trigger_type | VARCHAR(50) | new_fact, fact_update, etc. |
| trigger_id | VARCHAR(100) | fact_id or log id for trace |
| priority | VARCHAR(20) | high, medium, low (from fact confidence) |
| created_at | TIMESTAMPTZ | |
| processed | BOOLEAN | Default false |
| processed_at | TIMESTAMPTZ | |

No FK from `story_update_queue` to `storylines` (cross-schema). Application must validate (domain_key, storyline_id) when processing.

---

## 4. PostgreSQL trigger

- **Table:** `intelligence.versioned_facts`
- **When:** `AFTER INSERT` (and optionally `AFTER UPDATE` when superseded_by_id is set).
- **Action:** Insert one row into `intelligence.fact_change_log` with fact_id, entity_profile_id, change_type `'new_fact'` (or `'fact_update'` / `'fact_superseded'` on update).
- **No** direct insert into `story_update_queue` in the trigger (would require dynamic SQL over all domain schemas and entity resolution). Keeping the trigger minimal keeps it fast and avoids cross-schema logic in the DB.

Optional: trigger can call `pg_notify('fact_change', json_build_object('fact_id', NEW.id, 'entity_profile_id', NEW.entity_profile_id)::text)` so an app listener can process with low latency.

---

## 5. Application components

### 5.1 Fact change processor

- **Input:** Rows from `fact_change_log` where `processed = false`.
- **Steps:**
  1. Load `entity_profiles` (domain_key, canonical_entity_id) and domain’s `entity_canonical` (canonical_name, aliases) for that entity_profile_id.
  2. For each domain_key and canonical name (and main aliases), query `{schema}.story_entity_index` for `LOWER(entity_name) IN (LOWER(canonical_name), ...)` and collect distinct (domain_key, storyline_id).
  3. Insert into `story_update_queue` (domain_key, storyline_id, trigger_type, trigger_id, priority). Priority can come from fact confidence (e.g. high if confidence > 0.9).
  4. Update `fact_change_log` set processed = true, processed_at = now(), story_updates_triggered = count.

### 5.2 Story update processor

- **Input:** Batch of rows from `story_update_queue` where processed = false, ordered by priority and created_at.
- **Steps:**
  1. Dedupe by (domain_key, storyline_id); optionally merge multiple triggers for the same story.
  2. For each (domain_key, storyline_id), call **story state updater** (e.g. refresh timeline, recalc maturity, detect significant change).
  3. If **significance** exceeds threshold, optionally trigger **alerts** (watchlist, in-app, etc.).
  4. Mark queue rows as processed.

### 5.3 Story state updater

- **Input:** (domain_key, storyline_id).
- **Actions (examples):**
  - Recompute timeline or summary from recent articles/facts.
  - Update a `storyline_states` or `story_timeline` table if added (Phase 2).
  - Set `last_evolution_at` or similar on the storyline row.
- Can plug in **significance scoring** (e.g. key events: verdict, ruling, election, merger; role changes; temporal clustering) and set a flag or score for the alert layer.

### 5.4 Alert generation (Phase 4)

- **Input:** (domain_key, storyline_id, change_analysis).
- **Actions:** Respect user preferences (min significance, alert types, cooldown); create alert record or send notification.

---

## 6. Configuration

Suggested env / config (e.g. `config/trigger_settings.py` or existing config). The API endpoint `POST .../context_centric/run_story_state_triggers` accepts `fact_batch` and `queue_batch` as query params; cron or OrchestratorCoordinator can call it with `step=both`:

- `TRIGGER_BATCH_SIZE` — max fact_change_log rows per run (e.g. 50).
- `STORY_UPDATE_QUEUE_BATCH_SIZE` — max story_update_queue rows per processor run (e.g. 20).
- `SIGNIFICANCE_THRESHOLD` — minimum score to treat as “significant” (e.g. 0.3).
- `ALERT_SIGNIFICANCE_THRESHOLD` — minimum to trigger alert (e.g. 0.7).
- `STORY_CACHE_TTL` — seconds for story–entity cache (e.g. 3600).
- `ENABLE_FACT_BATCHING` — process fact_change_log in batches (default true).
- `ENABLE_PG_NOTIFY` — use pg_notify for near-real-time processing (default false until listener is in place).

---

## 7. Monitoring

- **fact_change_log:** Count by change_type, processed vs unprocessed, avg time to processed_at.
- **story_update_queue:** Count by priority, processed vs unprocessed, avg time to processed_at.
- **Stuck updates:** Rows in story_update_queue with processed = false and created_at &lt; now() - 1 hour (e.g. expose via admin view or dashboard).

Views similar to the user’s design:

- `story_update_metrics` — hourly counts and avg processing time.
- `stuck_updates` — unprocessed queue rows older than threshold with optional join to storyline title (per domain).

---

## 8. Performance

- **Batching:** Process fact_change_log and story_update_queue in limited batch sizes.
- **Caching:** Cache (entity_profile_id → domain_key, canonical_name) and/or (canonical_name, domain) → list of (storyline_id) with TTL to avoid repeated lookups.
- **Dedupe:** When enqueueing, avoid duplicate (domain_key, storyline_id) for the same trigger run; when processing, group queue rows by (domain_key, storyline_id).
- **Priority:** Use fact confidence and change_type to set priority so high-impact facts are processed first.

---

## 9. Implementation status

- **Migration 152:** Creates `fact_change_log`, `story_update_queue`, and trigger on `intelligence.versioned_facts`.
- **Service:** `story_state_trigger_service` (or similar) implements fact-change processing and story-update queue processing; can be invoked from cron or OrchestratorCoordinator.
- **State updater:** Initially can be a no-op or a call into existing storyline refresh logic; Phase 2 will add storyline_states / maturity and feed that here.
- **Alerts:** Phase 4; config and alert-generation stub can be added when watch patterns and user preferences exist.

---

## 10. References

- [RAG_ENHANCEMENT_ROADMAP.md](RAG_ENHANCEMENT_ROADMAP.md) — Phase 2 (story state), Phase 4 (alerts).
- [VECTOR_DATABASE_SCHEMA.md](VECTOR_DATABASE_SCHEMA.md) — versioned_facts, story_states.
- Migration 151 — `intelligence.versioned_facts`.
- Migration 135 — `story_entity_index` (per domain or public).
- Migration 122/125 — domain schemas and storylines.
