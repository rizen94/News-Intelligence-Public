# Newsroom Orchestrator v6 — Development Plan (Build-Ready)

> **Goal:** Complement existing AutomationManager with event-driven, role-based orchestration.  
> **Status:** Incorporates technical review corrections and improvements. Ready for implementation.

---

## 1. Contract and Ownership

To avoid double execution when running parallel to AutomationManager, ownership is defined as follows.

### 1.1 Phase 1 ownership matrix

| Workflow | Owner | Orchestrator role |
|----------|--------|-------------------|
| **RSS collection** | AutomationManager | Does **not** run RSS. Polls DB for recently discovered articles and emits ARTICLE_INGESTED (and optionally BREAKING_NEWS). |
| **Article processing** | AutomationManager | No change. |
| **Topic clustering** | AutomationManager | No change. |
| **Entity extraction** | AutomationManager | No change. |
| **Breaking-news detection** | Orchestrator (Reporter) | After discovering new articles via poll, runs keyword/velocity check and emits BREAKING_NEWS. |
| **Event bus** | Orchestrator | Owns event emission, in-process priority queue, optional Redis pub/sub. |

### 1.2 How Reporter gets new articles (Phase 1)

- **Do not** run RSS inside the orchestrator in Phase 1. AutomationManager (and cron) continue to run RSS.
- **Reporter** runs a periodic poll (e.g. every 5–10 minutes): query each domain’s `articles` for rows where `discovered_at` (or `created_at`) is within the last N minutes (e.g. 15).
- For each new article: emit **ARTICLE_INGESTED** with deduplication key `(domain_key, article_id)`.
- Optionally: run breaking-news keyword check on title/summary; if match, emit **BREAKING_NEWS** with same key.
- **Idempotency:** Event handlers (and any persistence of “processed” state) must key off `(domain_key, article_id)` so the same article is not processed twice.

### 1.3 Coexistence with FinanceOrchestrator

- **Newsroom Orchestrator** does **not** replace **FinanceOrchestrator**. Finance domain tasks (gold, EDGAR, FRED, analysis) remain in FinanceOrchestrator.
- Newsroom Orchestrator handles the **event-driven news pipeline** (Reporter, Journalist, Editor). Cross-domain linking may consume finance-related events later; define interfaces when needed.

---

## 2. Feature flag and configuration

### 2.1 Feature flag

- **Env:** `NEWSROOM_ORCHESTRATOR_ENABLED` (default `false` for Phase 1 until validated).
- **Config:** Optional in `newsroom.yaml`: `newsroom.enabled: true/false`. Env overrides file.
- If disabled, `main.py` does **not** start the orchestrator (no thread, no subscription).

### 2.2 Config path

- **File:** `api/config/newsroom.yaml` (optional).
- **Path constant:** Add to `api/config/paths.py`: `NEWSROOM_YAML = CONFIG_DIR / "newsroom.yaml"`.
- If file is missing: log warning and run with defaults (e.g. Reporter poll interval 600s, orchestrator enabled only if env is true).

### 2.3 Configuration example

```yaml
# api/config/newsroom.yaml (optional)
newsroom:
  enabled: false   # override with NEWSROOM_ORCHESTRATOR_ENABLED env
  reporter:
    poll_interval_seconds: 600
    new_article_window_minutes: 15
    breaking_news_keywords: []
    priority_entities: []
  journalist:
    investigation_triggers:
      multiple_entity_mentions: 3
      pattern_confidence: 0.8
      user_watchlist_hit: true
    max_concurrent_investigations: 5
  editor:
    quality_threshold: 0.7
    narrative_update_frequency: 3600
  event_handling:
    max_retries: 3
    backoff_base_seconds: 2
    dead_letter_after_retries: true
  circuit_breaker:
    failure_threshold: 5
    recovery_minutes: 15
```

---

## 3. Event system

### 3.1 Event envelope (schema)

Use a single envelope for all events (Pydantic or dataclass):

- **event_id:** UUID (generated on emit).
- **event_type:** EventType enum value.
- **payload:** JSON-serializable dict (e.g. `domain_key`, `article_id`, `title`, `content_hash`, etc.).
- **priority:** Integer (1=critical, 2=high, 3=normal, 4=low).
- **timestamp:** ISO UTC.
- **domain:** Optional domain_key.
- **correlation_id:** Optional (for tracing a chain of events).
- **deduplication_key:** Optional string, e.g. `f"{domain_key}:{article_id}"` for ARTICLE_INGESTED. Processors use this to skip duplicates.

### 3.2 Idempotency

- For ARTICLE_INGESTED and BREAKING_NEWS: include `deduplication_key` = `{domain_key}:{article_id}`.
- Before processing, check (e.g. in DB or in-memory set) whether this key was already handled; if yes, skip and optionally ack.
- Persist “processed” keys in PostgreSQL (e.g. `orchestration.processed_events` with `deduplication_key` UNIQUE and TTL/retention) or in Redis with TTL.

### 3.3 Priority queue (Phase 1)

- **In-process:** Use a single in-process priority queue (e.g. `queue.PriorityQueue` or `heapq` in the orchestrator thread). No Redis required for the queue in Phase 1.
- **Redis:** Optional. If `REDIS_URL` is set and connection succeeds:
  - Use Redis **pub/sub** to publish events (for future multi-process or dashboard subscribers).
  - Do **not** use Redis for the main consumer queue in Phase 1; keep that in-process.
- If Redis is down or unset: run without pub/sub; log “Redis unavailable, pub/sub disabled.”

### 3.4 Event types (existing enum)

Keep and use `api/orchestration/events/types.py` EventType enum (ARTICLE_INGESTED, BREAKING_NEWS, PATTERN_DETECTED, INVESTIGATION_NEEDED, etc.).

---

## 4. Failure handling

### 4.1 Retries

- Config: `event_handling.max_retries` (default 3), `event_handling.backoff_base_seconds` (default 2).
- On handler failure: retry with exponential backoff (e.g. base^attempt seconds). After max retries, move to dead letter.

### 4.2 Dead letter

- **Table:** `orchestration.events_failed` (see schema below): `event_id`, `event_type`, `payload` (JSONB), `error` (TEXT), `failed_at`, `retry_count`.
- After max retries: insert into `events_failed`, log error, optionally emit alert. Do not re-queue.

### 4.3 Circuit breaker (DataSource)

- Per DataSource (e.g. per RSS feed or plugin instance): after N consecutive failures (config: `circuit_breaker.failure_threshold`, e.g. 5), mark source as **unhealthy**.
- While unhealthy: skip fetch for K minutes (config: `circuit_breaker.recovery_minutes`, e.g. 15). After that, one probe attempt; if success, mark healthy again.

---

## 5. Database schema (corrected)

### 5.1 Migration numbering

- Next migration after `139_*`: **140** for orchestration, **141** for intelligence (or one file `140_orchestration_intelligence_schemas.sql` with both). Use `api/database/migrations/` and existing naming.

### 5.2 Schema: orchestration

- **Permissions:** `GRANT USAGE ON SCHEMA orchestration TO newsapp;` and `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA orchestration TO newsapp;`. `ALTER DEFAULT PRIVILEGES IN SCHEMA orchestration GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO newsapp;`

- **investigations:** `entity_ids` are scoped to **domain_key** in the same row (i.e. IDs refer to that domain’s `entity_canonical` or `article_entities`). Document in migration comment.

- **events_failed:** New table for dead letter.

### 5.3 Schema: intelligence

- **entity_relationships:** Use **domain-qualified** entity refs: e.g. `source_domain`, `source_entity_id`, `target_domain`, `target_entity_id` (all in one row). So relationship is between (source_domain, source_entity_id) and (target_domain, target_entity_id).

- **narrative_threads:** Already have `domain_key`; document that `storyline_id` refers to `{domain_key}.storylines.id` (schema name = domain_key with hyphen replaced by underscore).

- **cross_domain_links:** Store article refs as **links JSONB**, e.g. `[{"domain": "politics", "article_id": 1}, {"domain": "finance", "article_id": 2}]`. Drop single `source_article_ids INTEGER[]` or keep for backward compat and add `links JSONB` as the canonical field.

### 5.4 Event retention

- **orchestration.events:** Append-only for audit. Add a **retention** job (Phase 2 or later): delete or archive rows older than e.g. 7 days to avoid unbounded growth. Document in plan.

---

## 6. DataSource interface and DB access

### 6.1 Sync interface (Phase 1)

- **DataSource** methods are **sync**: `def fetch_latest(self) -> List[ArticlePayload]`, `def validate_data(self, item: ArticlePayload) -> bool`, etc. No async in Phase 1 for plugins.
- **RSSDataSource:** Wraps or calls existing sync RSS collector (or polls DB as in 1.2); does not run the full RSS pipeline itself in Phase 1.

### 6.2 Database connections

- Use **shared pool only:** `get_db_connection()` (and optionally `get_db_config()`) from `shared.database.connection`. Do not create a separate connection pattern or use asyncpg in Phase 1.

---

## 7. Lifecycle and main integration

### 7.1 Startup (in lifespan, after AutomationManager)

1. Check feature flag: if `NEWSROOM_ORCHESTRATOR_ENABLED` is false (and config does not override), skip start and log “Newsroom orchestrator disabled.”
2. Load config from `config.paths.NEWSROOM_YAML` (if present).
3. Instantiate **NewsroomOrchestrator** with: `get_db_connection`, config dict, optional `REDIS_URL` from env.
4. Start orchestrator in a **daemon thread** (same pattern as AutomationManager: thread runs the orchestrator loop).
5. Store on **app.state:** `app.state.newsroom_orchestrator`, `app.state.newsroom_orchestrator_thread`.

### 7.2 Shutdown

1. If `app.state.newsroom_orchestrator` exists: set `orchestrator.is_running = False` (or equivalent stop flag).
2. If `app.state.newsroom_orchestrator_thread` exists: `thread.join(timeout=5)`.
3. If thread is still alive after 5s, log warning and continue shutdown.

---

## 8. Observability

### 8.1 Health endpoint

- Add **GET** (or include in existing) **`/api/v4/system_monitoring/orchestrator`** (or under existing system_monitoring router): returns `{ "enabled": true|false, "running": true|false, "last_event_at": ISO8601|null, "queue_depth": N }`. If orchestrator is disabled, return `enabled: false` and no thread.

### 8.2 Logging

- Use a consistent logger name, e.g. `logging.getLogger("orchestration")` or `logging.getLogger("news_intel.orchestration")`.
- Log event types, domain, and duration for key operations (emit, handle, fail). Use existing structured logging if the project has it.

---

## 9. Testing strategy

- **Unit:** Event envelope (serialize/deserialize, validation). EventType enum. DataSource adapter with mock (e.g. mock RSS returning fixed list).
- **Unit:** Idempotency: processor skips event when deduplication_key already seen.
- **Integration:** Start orchestrator with mock Redis (or no Redis), in-memory queue; enqueue one ARTICLE_INGESTED; assert one handler run and no duplicate when re-enqueued with same deduplication_key.
- **Location:** Under `tests/` or `api/tests/` to match existing structure. Add `tests/orchestration/` or `api/tests/orchestration/` if needed.

---

## 10. Dependencies

- **redis:** Ensure `redis` (e.g. `redis>=4.0`) is in `pyproject.toml` or `requirements.txt` if any Redis usage. Document that Redis is optional at runtime (orchestrator runs without it when unavailable).
- **PyYAML:** Already used by finance; ensure `PyYAML` is in project deps for `newsroom.yaml`.

---

## 11. Cross-domain entity matching (Phase 2)

- No global entity ID in Phase 2. Match across domains by **normalized name** (e.g. lowercased canonical name). Document: “Cross-domain entity linking uses name normalization; add global entity registry later if needed.”

---

## 12. Build order (implementation checklist)

Use this order when implementing.

### Phase 1a: Foundation (no new workflows yet)

1. **Config and flag**  
   - Add `NEWSROOM_YAML` to `config/paths.py`.  
   - Add `newsroom.yaml` example and read `NEWSROOM_ORCHESTRATOR_ENABLED` (env) and `newsroom.enabled` (file).

2. **Migrations 140 and 141**  
   - Create `orchestration` schema with: events, events_failed, investigations (with domain_key; entity_ids scoped to that domain), task_queue, source_plugins, processing_state, workflows.  
   - Create `intelligence` schema with: patterns, entity_relationships (domain-qualified), narrative_threads (domain_key + storyline_id), cross_domain_links (links JSONB), investigation_notes.  
   - GRANT USAGE and table privileges to newsapp; ALTER DEFAULT PRIVILEGES.

3. **Event envelope and types**  
   - Implement event envelope (dataclass or Pydantic) with event_id, event_type, payload, priority, timestamp, domain, correlation_id, deduplication_key.  
   - Keep EventType enum in `orchestration/events/types.py`.

4. **In-process priority queue**  
   - Implement in-process priority queue (e.g. in `orchestration/events/queue.py`).  
   - Optional: Redis pub/sub wrapper in `orchestration/events/redis_bus.py`; no-op if Redis unavailable.

5. **Base orchestrator**  
   - BaseOrchestrator: load config, hold queue, start/stop loop, use `get_db_connection()` for any DB.  
   - State persistence: PostgreSQL for processed_events (or similar) and durable state; in-memory for “recently processed” dedup if desired.

6. **Reporter: poll and emit**  
   - Reporter module: periodic poll of domain `articles` (discovered_at in last N minutes).  
   - Emit ARTICLE_INGESTED (and optionally BREAKING_NEWS) with deduplication_key.  
   - No RSS execution in orchestrator in Phase 1.

7. **Failure handling**  
   - Retry with backoff on handler failure; after max retries write to `orchestration.events_failed`.  
   - Circuit breaker for DataSource (per-feed or per-plugin): skip fetch for recovery window after N failures.

8. **Lifecycle in main**  
   - After AutomationManager start: if enabled, create NewsroomOrchestrator, start in daemon thread, store on app.state.  
   - On shutdown: set stop flag, join thread (timeout 5s).

9. **Health and logging**  
   - Expose orchestrator status at `/api/v4/system_monitoring/orchestrator` (or equivalent).  
   - Use logger name `orchestration` and log key operations.

10. **Tests**  
    - Unit: envelope, EventType, DataSource mock, idempotency.  
    - Integration: one ARTICLE_INGESTED through queue, no double process for same dedup key.

### Phase 1b: Optional refinements

- **RSSDataSource** (optional in Phase 1): Implement DataSource interface that wraps DB poll (or in future, a thin wrapper around existing collector) for consistency with plugin model. Reporter can call this adapter.
- **Processed-events table:** If using DB for idempotency, add `orchestration.processed_events` with `deduplication_key UNIQUE` and optional `processed_at`; retention job later.

### Phase 2 (after Phase 1 stable)

- Journalist module (pattern detection, investigation state machine).  
- Editor module (quality, narrative, publishing).  
- Cross-domain linking (name-normalized entity matching).  
- Optional: move queue to Redis for durability/multi-process.

### Phase 3 (later)

- Archivist, Chief Editor AI.

---

## 13. Directory structure (unchanged)

```
api/
  config/
    paths.py                    # add NEWSROOM_YAML
    newsroom.yaml               # optional
  orchestration/
    __init__.py
    base.py                     # BaseOrchestrator / NewsroomOrchestrator
    config.py                   # load newsroom.yaml, env
    events/
      __init__.py
      types.py                  # EventType enum
      envelope.py               # Event envelope (dataclass/Pydantic)
      queue.py                  # In-process priority queue
      redis_bus.py              # Optional Redis pub/sub
    roles/
      __init__.py
      reporter.py               # ReporterModule (poll DB, emit events)
    plugins/
      __init__.py
      base.py                   # DataSource (sync interface)
      rss_source.py             # Optional: RSSDataSource (DB poll or wrapper)
  database/
    migrations/
      140_orchestration_schema.sql
      141_intelligence_schema.sql
```

---

## 14. Reference: corrected schema (summary)

- **orchestration.events:** id, event_id (UUID), event_type, payload (JSONB), priority, created_at, processed_at.  
- **orchestration.events_failed:** id, event_id, event_type, payload (JSONB), error (TEXT), failed_at, retry_count.  
- **orchestration.investigations:** id, trigger_event_id, status, **domain_key**, entity_ids (interpreted as IDs in that domain’s entity_canonical/article_entities), pattern_confidence, notes, created_at, updated_at.  
- **intelligence.entity_relationships:** id, **source_domain**, **source_entity_id**, **target_domain**, **target_entity_id**, relationship_type, confidence, created_at.  
- **intelligence.narrative_threads:** id, **domain_key**, storyline_id (in that domain’s storylines), summary, linked_article_ids (or links JSONB), created_at.  
- **intelligence.cross_domain_links:** id, source_domain, target_domain, entity_name, link_type, **links JSONB** (e.g. [{"domain":"politics","article_id":1}, ...]), created_at.

All orchestration and intelligence tables: GRANT to newsapp; migrations 140 and 141.

---

This development plan is the single source of truth for building the v6 controller system. Implement in the order of Section 12 and refer to the technical review document for rationale.
