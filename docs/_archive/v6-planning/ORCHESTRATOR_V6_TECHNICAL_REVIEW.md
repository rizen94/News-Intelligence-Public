# Newsroom Orchestrator v6 — Technical Review

> **Purpose:** Identify mistakes, best-practice improvements, and missing links before implementation.

---

## 1. Summary

| Category | Count |
|----------|--------|
| **Mistakes / corrections** | 6 |
| **Best-practice improvements** | 8 |
| **Missing links** | 10 |

Addressing these before build will reduce rework and align the orchestrator with the existing codebase and constraints.

---

## 2. Mistakes and Corrections

### 2.1 Database: Entity IDs are per-domain

**Issue:** `orchestration.investigations.entity_ids` and `intelligence.entity_relationships.entity_a_id` / `entity_b_id` are plain `INTEGER[]` / `INTEGER`. Entities live in **per-domain** tables (`politics.entity_canonical`, `finance.entity_canonical`, etc.). An integer ID is only unique within a schema.

**Correction:** Either:
- Store **qualified** references: e.g. `entity_refs JSONB` like `[{"domain": "politics", "entity_id": 42}, ...]`, or
- Add `domain_key` to investigations and define that `entity_ids` in that row refer to that domain only; for cross-domain links use a separate table with `(domain_a, entity_id_a, domain_b, entity_id_b)`.

**Recommendation:** Add `domain_key` to `orchestration.investigations` and document that `entity_ids` are for that domain’s `entity_canonical` (or `article_entities`). For `intelligence.entity_relationships`, use `(source_domain, source_entity_id, target_domain, target_entity_id)` (or equivalent JSONB) instead of unqualified integers.

### 2.2 Database: Storyline and article IDs are per-domain

**Issue:** `intelligence.narrative_threads.storyline_id` and `intelligence.cross_domain_links.source_article_ids` are unqualified. Storylines and articles are in domain schemas (e.g. `politics.storylines`, `finance.articles`).

**Correction:**
- `narrative_threads`: add `domain_key` and document that `storyline_id` is in that domain’s `storylines` table.
- `cross_domain_links`: store article references as e.g. `links JSONB` like `[{"domain": "politics", "article_id": 1}, {"domain": "finance", "article_id": 2}]` instead of a single `source_article_ids INTEGER[]`.

### 2.3 Redis: Not yet used for pub/sub or queues

**Issue:** Redis is currently only used for **health checks** (ping in system_monitoring). The plan assumes Redis pub/sub and a priority queue. If Redis is down or not deployed, the new orchestrator would depend on it.

**Correction:**
- Treat Redis as **optional** for Phase 1: if Redis is unavailable, fall back to in-process queue + no pub/sub (single-node only).
- Document in plan and config: `REDIS_URL` optional; behavior when unset or connection fails.
- Use the same connection pattern as health check (e.g. `redis.Redis(host=..., port=..., decode_responses=True)`) and centralize URL in env (e.g. `REDIS_URL` from `config` or env).

### 2.4 Double execution when running parallel to AutomationManager

**Issue:** Migration path says “run new orchestrator parallel to existing AutomationManager.” If the Reporter module triggers RSS collection and AutomationManager still has `rss_processing` on a schedule, **RSS can run twice** (and duplicate work or race).

**Correction:**
- Define **ownership** per workflow: e.g. “Phase 1: Orchestrator owns only event emission; it does not run RSS. AutomationManager keeps running RSS; orchestrator subscribes to a hook or polls DB for new articles and emits ARTICLE_INGESTED.”
- Or: “Orchestrator runs RSS; disable RSS in AutomationManager schedules while orchestrator is enabled.”
- Document the chosen contract in the implementation plan and in code (comments / config flags).

### 2.5 AutomationManager uses its own DB connections

**Issue:** AutomationManager uses `psycopg2.connect(**self.db_config)` (no pool). The rest of the API uses `shared.database.connection.get_db_connection()` (pooled).

**Correction:** New orchestration code should use **shared pool**: `get_db_connection()` from `shared.database.connection`, and optionally `get_db_config()` for read-only config. This avoids connection exhaustion and matches the rest of the app. Do not replicate the “own connection per call” pattern for new code.

### 2.6 Shutdown order and lifecycle

**Issue:** Plan and skeleton do not specify how the new orchestrator is started/stopped. Main already starts AutomationManager, FinanceOrchestrator, TopicExtractionQueueWorker, StorylineConsolidation, RouteSupervisor and stops them in shutdown.

**Correction:** Add to implementation plan:
- **Start:** After AutomationManager (or as specified), start Newsroom Orchestrator in its own daemon thread (or same pattern as AutomationManager).
- **Stop:** In lifespan shutdown, set orchestrator stop flag and join its thread with a timeout (e.g. 5s), same as AutomationManager. Register the orchestrator on `app.state` (e.g. `app.state.newsroom_orchestrator`, `app.state.newsroom_orchestrator_thread`) so shutdown can find it.

---

## 3. Best-Practice Improvements

### 3.1 Config path and format

**Current:** YAML config is mentioned but path is not specified. Finance uses `config.paths` (e.g. `FINANCE_SCHEDULE_YAML`, `SOURCES_YAML` under `api/config/`).

**Improvement:** Add `NEWSROOM_YAML = CONFIG_DIR / "newsroom.yaml"` in `api/config/paths.py`. Load config in the orchestrator from this path; if the file is missing, log a warning and run with defaults (or disabled). Document in plan: “Config file: `api/config/newsroom.yaml` (optional).”

### 3.2 Async vs sync

**Current:** Plan says “use async throughout” and “asyncpg for DB”; existing code is sync (psycopg2, sync RSS collector).

**Improvement:** For Phase 1, **stay sync** for DB and RSS to match existing code and avoid introducing asyncpg and a second connection pattern. Use the shared `get_db_connection()`. If the orchestrator loop is in a thread (like AutomationManager), running sync code in that thread is acceptable. Add “Consider async/asyncpg in a later phase if we move to async-native workers” to the plan.

### 3.3 Event payload schema and idempotency

**Current:** Event payload schema is “event_type, payload, priority, timestamp, domain” but not formalized. No idempotency strategy.

**Improvement:**
- Define a small **event envelope** (e.g. Pydantic or dataclass): `event_id` (uuid), `event_type`, `payload`, `priority`, `timestamp`, `domain` (optional), `correlation_id` (optional).
- For events that trigger processing (e.g. ARTICLE_INGESTED): include a **deduplication key** (e.g. `(domain, article_id)` or `content_hash`). Processors should skip or ignore duplicates (e.g. “already processed”).
- Document in plan: “Event envelope schema” and “Idempotency: processors key off article_id/event_id to avoid double work.”

### 3.4 Failure handling and dead letter

**Current:** Plan mentions “retry with backoff,” “circuit breakers,” “dead letter queues,” but schema has no failed-events or dead-letter table.

**Improvement:** Add to implementation plan:
- **Retries:** Configurable max retries and backoff (e.g. exponential) for event handling and source fetches.
- **Dead letter:** Either a table (e.g. `orchestration.events_failed` with `event_id`, `error`, `failed_at`) or a Redis list key. After max retries, move event to dead letter and alert/log.
- **Circuit breaker:** For DataSource plugins (e.g. RSS), after N consecutive failures mark source as unhealthy and back off (e.g. skip next K fetch windows) before retrying.

### 3.5 Schema permissions and migration numbering

**Current:** New SQL creates `orchestration` and `intelligence` schemas but does not grant to `newsapp`. Migration file naming not specified.

**Improvement:**
- In migration SQL, add: `GRANT USAGE ON SCHEMA orchestration TO newsapp;` (and same for `intelligence`); `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA orchestration TO newsapp;` (and same for `intelligence`). Use `ALTER DEFAULT PRIVILEGES` if you add more tables later.
- Follow existing migration numbering: next file after `139_*` should be `140_orchestration_intelligence_schemas.sql` (or split into `140_orchestration_schema.sql` and `141_intelligence_schema.sql`).

### 3.6 Observability

**Current:** Plan mentions “metrics and dashboard” but no integration with existing monitoring.

**Improvement:** Add to plan:
- **Health:** Expose orchestrator status (e.g. “running” / “stopped”, last event time, queue depth) via existing system_monitoring or a small `/api/v4/system_monitoring/orchestrator` endpoint so the dashboard can show it.
- **Logging:** Use structured logging (same as rest of app) with a consistent logger name (e.g. `orchestration`) and log event types, domain, and duration for key operations.
- **Metrics (later):** Event processing latency, investigation completion rate, etc., can be added in a later phase; minimal first step is health + logs.

### 3.7 DataSource interface: sync for Phase 1

**Current:** Stub has `async def fetch_latest()`. Existing RSS collector is sync.

**Improvement:** Make the DataSource interface **sync** in Phase 1: `def fetch_latest(self) -> List[ArticlePayload]`. Implement `RSSDataSource` by wrapping the existing sync collector (or calling it in a thread if you need to avoid blocking the orchestrator loop). This avoids mixing sync RSS and async orchestrator and matches the rest of the stack. Async can be introduced later if needed.

### 3.8 Priority queue: Redis vs in-process

**Current:** Plan says “Redis pub/sub” and “priority queue” without specifying whether the queue is in Redis or in-process.

**Improvement:** Clarify in plan:
- **Phase 1:** Priority queue can be **in-process** (e.g. `asyncio.PriorityQueue` or `queue.PriorityQueue` in the orchestrator thread). This avoids Redis dependency for the queue and matches “Redis optional” above. Pub/sub can be “optional: if Redis available, publish events for other subscribers; else no-op.”
- **Later:** Move queue to Redis (e.g. sorted set or list) if you need multi-process or durable queue.

---

## 4. Missing Links

### 4.1 Who triggers what (contract)

**Missing:** Clear contract for “who triggers RSS / article processing / topic clustering” when both AutomationManager and the orchestrator run.

**Add to plan:** A short “Ownership matrix” table: e.g. “RSS: AutomationManager (orchestrator only emits events from DB poll)”; “Topic clustering: AutomationManager”; “Breaking-news alerts: Orchestrator.” Update as you migrate workflows.

### 4.2 How Reporter gets “new articles” to emit ARTICLE_INGESTED

**Missing:** Reporter is supposed to emit ARTICLE_INGESTED / BREAKING_NEWS. If we don’t run RSS inside the orchestrator (to avoid double run), we need a defined way to discover new articles (e.g. poll `articles` by `discovered_at` / `created_at` and emit for recent ones).

**Add to plan:** “Reporter Phase 1: Poll domain.articles for rows with discovered_at in last N minutes; emit ARTICLE_INGESTED per article. Optionally run breaking-news keyword check on title/summary and emit BREAKING_NEWS.” This keeps RSS ownership with AutomationManager while still feeding the event bus.

### 4.3 Integration point in main lifespan

**Missing:** Exact place and pattern to start/stop the orchestrator in `main.py`.

**Add to plan:** “In lifespan, after AutomationManager start: instantiate NewsroomOrchestrator with get_db_connection, config path, optional Redis URL; start in a daemon thread; store on app.state. On shutdown, stop orchestrator and join thread (timeout 5s).”

### 4.4 Dependency on redis package

**Missing:** Project may not list `redis` in requirements; health check imports it.

**Add to plan:** Ensure `redis` (e.g. `redis>=4.0`) is in `pyproject.toml` or `requirements.txt` if orchestration will use Redis. Document that it’s optional at runtime if we fall back when Redis is unavailable.

### 4.5 YAML dependency

**Missing:** Finance uses `yaml.safe_load`; stdlib does not include YAML.

**Add to plan:** If newsroom config is YAML, ensure `PyYAML` is in project dependencies (likely already there for finance). Document in plan.

### 4.6 Event persistence and retention

**Missing:** Whether every event is written to `orchestration.events` or only failures/samples; and retention (e.g. delete or archive after 7 days).

**Add to plan:** “Event persistence: Append to orchestration.events for audit/debug; optional TTL or retention job (e.g. delete rows older than 7 days) to avoid unbounded growth.”

### 4.7 Cross-domain entity identity

**Missing:** Cross-domain linking assumes we can match “same entity” across domains (e.g. “Company X” in politics and finance). There is no global entity ID; we have per-domain `entity_canonical`.

**Add to plan:** “Cross-domain entity matching: Phase 2 use name normalization (e.g. lowercased canonical name) to link; no global entity ID in Phase 2. If needed later, add a global entity registry or use entity_canonical.id + domain_key as composite key.”

### 4.8 Testing strategy

**Missing:** Plan mentions “mock event generators, scenario-based testing” but no concrete test locations or CI.

**Add to plan:** “Tests: unit tests for EventType and event envelope; unit tests for DataSource adapter (mock RSS); integration test that starts orchestrator with mock Redis and in-memory queue and processes one ARTICLE_INGESTED. Place under `tests/` or `api/tests/` to match existing structure.”

### 4.9 Feature flag or kill switch

**Missing:** How to disable the new orchestrator without code change (e.g. env or config).

**Add to plan:** “Feature flag: e.g. NEWSROOM_ORCHESTRATOR_ENABLED=false or newsroom.enabled: false in config disables starting the orchestrator. Default false in Phase 1 until validated.”

### 4.10 Finance orchestrator coexistence

**Missing:** FinanceOrchestrator already has its own scheduler and tasks. No mention of interaction with the new “Chief Editor” or data-processing orchestrator.

**Add to plan:** “Coexistence: Newsroom Orchestrator does not replace FinanceOrchestrator. Finance domain tasks (gold, EDGAR, etc.) remain in FinanceOrchestrator. Newsroom Orchestrator handles event-driven news pipeline (Reporter, Journalist, Editor). Cross-domain linking may consume finance events later; define interfaces when needed.”

---

## 5. Recommended Order of Fixes Before Build

1. **Contract and ownership** (Section 2.4, 4.1, 4.2): Define who runs RSS and how Reporter gets new articles; document in plan.
2. **Schema fixes** (2.1, 2.2, 3.5): Add domain-qualified entity/article/storyline references; add GRANTs and migration numbers.
3. **Redis optional + queue in-process** (2.3, 3.8): Document fallback and Phase 1 queue in-process.
4. **Lifecycle and main** (2.6, 4.3): Document start/stop in lifespan and app.state.
5. **Config path and feature flag** (3.1, 4.9): Add NEWSROOM_YAML and NEWSROOM_ORCHESTRATOR_ENABLED (or equivalent).
6. **DataSource sync and DB pool** (2.5, 3.2, 3.7): Use get_db_connection(); make DataSource sync in Phase 1.
7. **Event envelope and idempotency** (3.3): Define envelope and deduplication key in plan.
8. **Failure handling** (3.4): Add dead-letter and retry/backoff to plan.
9. **Observability and tests** (3.6, 4.8): Health endpoint, logging, minimal test strategy.

---

## 6. Conclusion

The overall architecture (roles, event-driven bus, plugin sources, migration path) is sound. The main risks are **double execution** if both systems run the same workflows, **unqualified IDs** in new schemas, and **missing lifecycle/contract** details. Applying the corrections and additions above will align the plan with the existing codebase and make Phase 1 implementation straightforward and maintainable.
