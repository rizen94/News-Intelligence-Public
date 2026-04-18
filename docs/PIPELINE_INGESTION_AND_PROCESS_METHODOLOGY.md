# Pipeline ingestion logic and process methodology

**Purpose:** Single reference for **what each automation phase ingests, how it selects work, and what it writes** — for deeper analysis, tuning, and methodology review. This complements narrative flow docs ([DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md)) and scheduling order ([PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md)).

**Source of truth in code**

| Concern | Location |
|---------|----------|
| Task names, `depends_on`, phase numbers, default intervals | `api/services/automation_manager.py` → `self.schedules` |
| Per-task implementation | Same file → `async def _execute_<task_name>` (grep `_execute_`) |
| Pending / backlog counts (what “has work” means) | `api/services/backlog_metrics.py` → `_count_*` helpers, `BATCH_SIZE_PER_TASK`, `SKIP_WHEN_EMPTY` |
| Orchestrator budgets / collection interval overrides | `api/config/orchestrator_governance.yaml` |
| Domain silos — **processing / backlog** | `shared.domain_registry` → `pipeline_url_schema_pairs()`, `get_pipeline_schema_names_active()`, `get_pipeline_active_domain_keys()` (`PIPELINE_INCLUDE` / `PIPELINE_EXCLUDE`) |
| Domain silos — **RSS** (default full registry) | `collect_rss_feeds` → `url_schema_pairs()` unless `RSS_INGEST_MIRROR_PIPELINE=true` (then pipeline pairs); minus `RSS_INGEST_EXCLUDE_DOMAIN_KEYS` |
| Shared article readiness (ML vs context) | `api/shared/article_processing_gates.py` |

---

## Scheduling model (how tasks actually run)

- **Workload-driven scheduling** (default path): phases with pending work (per `backlog_metrics`) are eligible every tick (subject to cooldown), not only on wall-clock intervals. Idle phases use their `interval` from `schedules`.
- **Collection throttle:** When downstream pending (enrichment + `context_sync` + `document_processing`, minus `COLLECTION_THROTTLE_EXCLUDE_PHASES`, plus optional `COLLECTION_THROTTLE_EXTRA_PHASES`) exceeds `COLLECTION_THROTTLE_PENDING_THRESHOLD`, workload-driven scheduling **does not enqueue `collection_cycle`** (the whole cycle, not RSS only). Standalone `content_enrichment` and nightly unified drain still run so rows can catch up.
- **Queue soft cap:** When `AUTOMATION_QUEUE_SOFT_CAP` is exceeded (default 100), new enqueues are skipped except phases in `AUTOMATION_QUEUE_PAUSE_ALLOW`. **`nightly_enrichment_context` is not allowlisted** (it would stack redundant drains). **`AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED`** caps running+queued nightly tasks (default 5).
- **Widow / split hosts:** `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE` on the main host when RSS runs elsewhere; `content_enrichment` still drains `{domain}.articles` rows that need full text. See `AGENTS.md` and `docs/WIDOW_DB_ADJACENT_CRON.md`.

---

## Quality-first phase contracts (success, skip, handoff)

This section states **what “good” means per layer**, **what we deliberately ignore**, and **how work flows forward** — aligned with code, not aspiration.

### Cross-cutting rules

| Mechanism | Role |
|-----------|------|
| **`SKIP_WHEN_EMPTY`** (`backlog_metrics.py`) | Phases in this set **do not enqueue** when pending count is 0 — avoids empty LLM/DB cycles. Omitted phases (e.g. `document_processing`, `content_refinement_queue`) still tick on interval so stuck work or “idle completion” is visible. |
| **Workload-driven scheduling** (`automation_manager`) | If a phase has pending work (`get_all_pending_counts`), it becomes eligible every tick (subject to cooldown + `depends_on`), not only on its idle interval. |
| **`depends_on`** | **Scheduling order only**: a task is not eligible until dependencies have run at least once in the manager’s history window; it does *not* mean “upstream must be empty.” Downstream backlog counts are the real “is there work?” signal. |
| **Collection throttle** | When the configured downstream pending sum exceeds `COLLECTION_THROTTLE_PENDING_THRESHOLD`, **`collection_cycle` is not scheduled** (entire cycle) so quality-sensitive steps can drain — **quality before volume**. Standalone enrichment and nightly drain still run. |
| **Pipeline domain scope** | Per-domain automation loops use **`get_pipeline_active_domain_keys()`** / **`pipeline_url_schema_pairs()`** so paused legacy silos are not enriched, synced, or story-processed. |
| **`BATCH_SIZE_PER_TASK`** | Defines “normal” batch per run; pending **above** this is treated as backlog (shorter effective interval in backlog mode). |
| **`BATCH_PHASES_CONTINUOUS` + `MAX_REQUEUE_PER_WINDOW`** | After `collection_cycle`, some phases may re-enqueue in the same analysis window up to a cap so one pass does not starve others. |
| **Nightly unified window** | When `in_nightly_pipeline_window_est()` is true, `content_enrichment` / `context_sync` standalone tasks defer to **`nightly_enrichment_context`** (single orchestrated drain). When `NIGHTLY_UNIFIED_PIPELINE_ENABLED=false`, the normal `collection_cycle` + interval phases own enrichment again. |

### Tier A — Ingestion (reject early)

| Step | Success / “counts as done” | Skipped or ignored (low quality / irrelevant) | Feeds next phase |
|------|----------------------------|-----------------------------------------------|------------------|
| **RSS** (`collect_rss_feeds`) | Items persisted or dedup-updated; activity count reflects touches. | Empty title/URL, ingest gates (`rss_item_passes_ingest_gates`), dedup, clickbait/ads/financial promo filters where configured, domains in **`RSS_INGEST_EXCLUDE_*`**, domains outside RSS list when **`RSS_INGEST_MIRROR_PIPELINE`**. | Rows in `{schema}.articles`; optional inline body fetch sets `enrichment_status` / length. |
| **Content enrichment** | Batch promotes `enrichment_status` toward terminal states (`enriched` / `failed` / `inaccessible`) where URL fetch applies. | Rows over attempt cap, no URL, or not selected by enrichment query; **skipped inside nightly window** except via nightly drain. | Longer `content` → ML gate + `context_sync` candidates. |
| **`collection_cycle` overall** | RSS (if not skipped) + bounded enrichment iterations + document drain + queue drain. | RSS skipped when `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE` or throttle; enrichment loop capped. | Downstream phases see new/updated articles and lower enrichment backlog. |

**Source credibility** (`orchestrator_governance.yaml` → `source_credibility`) scales **`quality_score`** and metadata at RSS ingest — upstream **quality signal** for later scoring and claims weighting.

### Tier B — Shared article readiness (single source of truth)

All of the following use **`api/shared/article_processing_gates.py`** so **backlog counts match `_execute_*` SQL**.

| Gate | Purpose | Rough rule |
|------|---------|------------|
| **ML / sentiment / quality** (`sql_ml_ready_and_content_bounds`) | Do not run expensive passes on stub text. | `LENGTH(content) > 100` and (`enrichment_status = 'enriched'` **or** legacy `NULL` + long body ≥ 500). **Strict mode** (`STRICT_ARTICLE_ENRICHMENT_GATES_SINCE`): requires **`enriched`** for new rows. |
| **Context sync** (`sql_context_sync_article_ready`) | Do not create `intelligence.contexts` for thin or not-yet-enriched bodies. | `LENGTH(content) > 100` and (long body **or** terminal enrichment status). Stricter under strict cutoff. |

### Tier C — Automation phases (success = “processed batch or correctly no-op”)

For each run, **success** means: *the phase consumed a bounded batch of eligible rows, or had zero eligible rows and exited quickly* (if in `SKIP_WHEN_EMPTY`, it was not scheduled when pending was 0).

| Phase group | What “has work” means (backlog) | Ignored / not selected | Typical handoff |
|-------------|----------------------------------|------------------------|-----------------|
| **`context_sync`** | Articles in pipeline silos passing **context SQL** not yet linked to contexts. | Short content, pending enrichment (under strict rules), wrong domain. | **`intelligence.contexts`**, `article_to_context` → claim/event/pattern phases. |
| **`entity_profile_sync`** | Canonical / profile drift per pipeline domain. | Inactive domains (not in pipeline). | Profiles for resolver, RAG, claims. |
| **`metadata_enrichment`** | Articles with content length &gt; 50 and metadata not marked done. | Below threshold; domain not in pipeline counts. | `quality_score`, categories, `metadata.enrichment_done`. |
| **`ml_processing`** | Same readiness as ML gate; `ml_processed` false. | Fails gate; missing columns handled gracefully. | Summaries / features for storylines and UI. |
| **`entity_extraction`** | Articles without `article_entities` rows, with sufficient content and enrichment timing rules (`automation_manager` SQL). | **Strict domains** (`ENTITY_EXTRACTION_RESOLVE_STRICT_DOMAIN_KEYS`): mentions that do not resolve to existing `entity_canonical` are skipped (no new canonical from extraction). | `article_entities` → context mentions / entity graph. |
| **`claim_extraction` / `claims_to_facts`** | Contexts without claims; high-confidence claims for promotion. | Low confidence, missing subjects; batch limits. | `versioned_facts` after resolution. |
| **`event_tracking` / v5 event stack** | Unlinked contexts or articles for event pipeline; schema from pipeline list. | Domains outside pipeline; rows failing extraction heuristics. | Tracked events → briefings, cross-domain, watchlist. |
| **Storyline family** (`discovery`, `proactive_detection`, `processing`, `automation`, `enrichment`, `rag_enhancement`) | Per-phase SQL/backlog (see `_count_*`); **only pipeline domains** in batch loops. | Inactive storylines, automation off, cooldowns, caps per domain. | Richer storylines → editorial, digest, refinement queue. |
| **`legislative_references`** | Unscanned articles in configured **legislative** domain keys; Congress.gov configured. | No bill mentions; API key missing; rate limits (`SLEEP_BETWEEN_*`). | `legislative_references` snapshots. |

### Operator validation

- **Config vs DB:** `PYTHONPATH=api uv run python api/scripts/validate_pipeline_rss_alignment.py` — pipeline vs RSS vs active feeds.
- **Metadata coverage:** `api/scripts/report_metadata_enrichment_status.py`.
- **Phase completions:** `public.automation_run_history`; Monitor backlog — compare pending to `BATCH_SIZE_PER_TASK` for “healthy throughput vs backlog.”

---

## `collection_cycle` (master ingest window)

Implemented in `_execute_collection_cycle`. Typical **ordered** sub-steps (exact branches depend on env and nightly window):

1. **RSS** — `_execute_rss_processing` → `collectors.rss_collector.collect_rss_feeds()` unless `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE`. Reads all active `{schema}.rss_feeds` (via `url_schema_pairs()`), inserts/updates `{schema}.articles` with deduplication, filtering (quality, clickbait, ads, etc.). **Body text:** `_extract_rss_entry_body` picks the **longest plaintext** among `entry.content` blocks (content:encoded) and summary/description so snippets do not win over full feed HTML when both exist. **Inline full-text fetch:** if visible text is shorter than **`RSS_FULLTEXT_FETCH_THRESHOLD_CHARS`** (default 900), trafilatura fetches the article URL at ingest (and on same-URL updates when content changes); set **`RSS_ALWAYS_FETCH_FULLTEXT=true`** to always fetch. Secondary helper **`collect_rss_feed`** uses the same extraction path as the main collector.
2. **Content enrichment drain** — Loops `content_enrichment` batches until cap or empty (skipped in nightly window when `nightly_enrichment_context` owns the drain). Uses `article_content_enrichment_service` / trafilatura-style fetch for URLs with thin RSS body (`enrichment_status` pending/failed, attempts &lt; cap).
3. **Document collection / processing** — PDFs and `intelligence.processed_documents` pipeline as configured.
4. **Pending collection queue** — Any URL queue drained after RSS.

**Ingestion logic (articles):** RSS path is domain-scoped; article rows are **create or update by URL** within each schema; downstream phases assume **`content` length** drives ML and `context_sync` quality.

### Content readiness gates (shared rules)

Single source of truth: `api/shared/article_processing_gates.py`.

- **Optional strict enrichment (new articles):** Set **`STRICT_ARTICLE_ENRICHMENT_GATES_SINCE`** to an ISO-8601 UTC instant (e.g. `2026-03-24T00:00:00+00:00`). Rows with **`created_at` ≥ that time** use stricter rules; older rows keep legacy behavior (no backfill required). When strict: **ML** requires **`enrichment_status = 'enriched'`** (no `NULL` + 500-char RSS shortcut). **Context backfill** requires **`LENGTH(content) > 100`** and a **terminal** enrichment status (`enriched` / `failed` / `inaccessible`), not `NULL` + long body alone. **RSS** inserts long feed-only bodies as **`pending`**; **`content_enrichment`** fast-path promotes them to **`enriched`** without a second fetch so the pipeline is not penalized.
- **`ml_processing`, `quality_scoring`, `sentiment_analysis`:** Only articles with **`enrichment_status = 'enriched'`**, or **legacy** rows with `enrichment_status IS NULL` and **`LENGTH(content) >= 500`** (same bar as RSS “substantial body” / pre-tracking data). **Minimum** `LENGTH(content) > 100` is still part of the SQL fragment.
- **`context_sync` / `ensure_context_for_article`:** Create `intelligence.contexts` only when **`LENGTH(content) > 100`** and either **`LENGTH(content) >= 500`** or **`enrichment_status IN ('enriched', 'failed', 'inaccessible')`** (terminal or substantial body), so thin rows are not linked until enrichment catches up. After enrichment succeeds, batch enrichment calls **`sync_context_from_article_after_content_change`** (update existing context or create if missing).
- **`context_sync` scheduling:** `depends_on` includes **`content_enrichment`** as well as **`collection_cycle`** so a drain pass can settle before backfill (when `content_enrichment` is disabled via `AUTOMATION_DISABLED_SCHEDULES`, `depends_on` is stripped as today).
- **RSS ingest:** `rss_item_passes_ingest_gates` rejects empty titles, missing URLs, or extremely thin items before insert. Full-body behavior: see **`RSS_FULLTEXT_FETCH_THRESHOLD_CHARS`**, **`RSS_ALWAYS_FETCH_FULLTEXT`** in `configs/env.example` and `_extract_rss_entry_body` / `_maybe_inline_fetch_article_body` in `api/collectors/rss_collector.py`.

---

## Phase reference: automation tasks

Below: **Task** = scheduler key in `schedules`. **Backlog key** = name in `backlog_metrics` / `get_all_pending_counts` when applicable. **“Selection logic”** is a short summary — see `_execute_*` and linked services for exact SQL.

### Phase 0 — Ingestion and drains

| Task | Default interval (idle) | depends_on | Primary implementation | Inputs / selection | Outputs / side effects |
|------|-------------------------|------------|-------------------------|--------------------|-------------------------|
| `collection_cycle` | `COLLECTION_CYCLE_INTERVAL_SECONDS` or governance (often ~2h) | — | `_execute_collection_cycle` | All active domain RSS feeds; optional skip RSS | New/updated rows in `{schema}.articles`; triggers enrichment loops |
| `content_enrichment` | 300s | — | `_execute_content_enrichment` | Articles with `enrichment_status` null/pending/failed, `enrichment_attempts` under cap, URL present | Full `content`, `enrichment_status` enriched/failed |
| `document_processing` | 600s | — | `_execute_document_processing` | `intelligence.processed_documents` (and related) backlog | Sections, entities, extraction fields |
| `nightly_enrichment_context` | 60s | — | `_execute_nightly_enrichment_context` | Within local **NIGHTLY_PIPELINE_*** window: coordinates RSS kickoff + enrichment + `context_sync` + refinement drain | Sequential drain of night batch |
| `health_check` | 120s | — | `_execute_health_check` | System / DB checks | Metrics only |
| `pending_db_flush` | 45s | — | `_execute_pending_db_flush` | Spill file when DB was down | Replays `automation_run_history` (or related) writes |

### Phase 1 — Bridge to intelligence schema

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `context_sync` | 900s | `collection_cycle`, `content_enrichment` | `_execute_context_sync` | Domain articles not yet linked, passing content readiness gate | `intelligence.contexts`, `intelligence.article_to_context` |
| `entity_profile_sync` | 21600s | — | `_execute_entity_profile_sync` | `entity_canonical` vs `entity_profiles` drift | Updates `intelligence.entity_profiles` |
| `entity_profile_build` | 900s | `context_sync`, `entity_profile_sync` | `_execute_entity_profile_build` | Contexts / profiles needing sections & relationships | Richer `entity_profiles` |

### Phase 2 — Intelligence extraction (context-centric)

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `claim_extraction` | 1800s | `context_sync` | `_execute_claim_extraction` | Batches of contexts without claims / backlog | `intelligence.extracted_claims` (and related) |
| `claims_to_facts` | 3600s | `claim_extraction` | `_execute_claims_to_facts` | High-confidence claims | `intelligence.versioned_facts` (subject resolution) |
| `event_tracking` | 900s | `context_sync` | `_execute_event_tracking` | Contexts → events backlog | `tracked_events`, chronicles |
| `event_coherence_review` | 7200s | `event_tracking` | `_execute_event_coherence_review` | Events needing LLM coherence pass | Updated event metadata |
| `investigation_report_refresh` | 7200s | `event_tracking` | `_execute_investigation_report_refresh` | Stale investigation reports | Refreshed reports |
| `cross_domain_synthesis` | 1800s | `event_tracking` | `_execute_cross_domain_synthesis` | Cross-domain event pairs | `cross_domain_correlations` / meta outputs |
| `pattern_recognition` | 7200s | `context_sync`, `entity_profile_sync` | `_execute_pattern_recognition` | Context + profile signals | Pattern tables / scores |
| `entity_dossier_compile` | 3600s | `entity_profile_sync` | `_execute_entity_dossier_compile` | Entities missing/stale dossiers | `entity_dossiers` |
| `entity_position_tracker` | 7200s | `entity_profile_sync` | `_execute_entity_position_tracker` | Article-derived stance signals | `entity_positions` |
| `metadata_enrichment` | 900s | `collection_cycle` | `_execute_metadata_enrichment` | `articles` with `LENGTH(content)&gt;50` and `metadata.enrichment_done` not set (per domain batch) | `quality_score`, `sentiment_score`, `categories`, `metadata.enrichment_done` |
| `entity_organizer` | 600s | `entity_profile_sync` | `_execute_entity_organizer` | Entity graph cleanup / relationships | Merged entities, relationships |

### Phase 3–5 — Per-article ML and topics (domain tables)

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `ml_processing` | 300s | `collection_cycle` | `_execute_ml_processing` | `ml_processed = false`, enriched or legacy long-body, `LENGTH(content) > 100` | `summary`, `ml_processing_metadata`, flags |
| `entity_extraction` | 300s | `collection_cycle` | `_execute_entity_extraction` | Articles pending entity phase | `{schema}.article_entities`, `articles.entities` JSONB |
| `quality_scoring` | 300s | `collection_cycle` | `_execute_quality_scoring` | Same content-readiness gate as ML | `quality_score` |
| `sentiment_analysis` | 300s | `collection_cycle` | `_execute_sentiment_analysis` | Same content-readiness gate as ML | Sentiment fields |
| `topic_clustering` | 300s | `collection_cycle` | `_execute_topic_clustering` | Articles for clustering / topic backlog | `topics`, assignments, clusters |

### Phase 6–8 — Storylines and RAG

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `storyline_discovery` | 14400s | `collection_cycle` | `_execute_storyline_discovery` | Embeddings + similarity clusters | New `storylines` candidates |
| `proactive_detection` | 7200s | `collection_cycle` | `_execute_proactive_detection` | Unlinked article clusters | New storylines / promotions |
| `fact_verification` | 14400s | `collection_cycle` | `_execute_fact_verification` | Recent claims | Verification flags |
| `storyline_processing` | 300s | `ml_processing`, `sentiment_analysis` | `_execute_storyline_processing` | Storylines needing summaries | Storyline narrative fields |
| `storyline_automation` | 300s | — | `_execute_storyline_automation` | Recent articles vs automation storylines | `storyline_articles` links |
| `storyline_enrichment` | 43200s | `storyline_automation` | `_execute_storyline_enrichment` | Full-history enrichment | Richer storyline fields |
| `rag_enhancement` | 300s | `storyline_processing` | `_execute_rag_enhancement` | Storylines in RAG queue | RAG chunks / enhanced retrieval fields |

### Phase 9 — Events v5, timeline, refinement

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `event_extraction` | 300s | `entity_extraction` | `_execute_event_extraction_v5` | Articles / entities for events | Domain + global event tables |
| `event_deduplication` | 600s | `event_extraction` | `_execute_event_deduplication_v5` | Duplicate event candidates | Deduplicated events |
| `story_continuation` | 600s | `event_deduplication` | `_execute_story_continuation_v5` | Events + storylines | Continuation links |
| `timeline_generation` | 300s | `rag_enhancement` | `_execute_timeline_generation` | Storylines / events for chronological_events | `chronological_events` |
| `entity_enrichment` | 1800s | `entity_profile_sync` | `_execute_entity_enrichment` | Profile IDs to enrich (e.g. Wikipedia) | `entity_profiles` external fields |
| `story_enhancement` | 300s | — | `_execute_story_enhancement` | Story update queues | Story enhancement records |
| `content_refinement_queue` | 120s | — | `_execute_content_refinement_queue` | `intelligence.content_refinement_queue` | Deep storyline narratives / finisher jobs |

### Phase 10–12 — Editorial, digests, watchlist

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `editorial_document_generation` | 1800s | `storyline_processing` | `_execute_editorial_document_generation` | Storylines missing editorial doc | `editorial_document` JSONB |
| `editorial_briefing_generation` | 1800s | `event_tracking` | `_execute_editorial_briefing_generation` | Tracked events | `editorial_briefing` on events |
| `storyline_synthesis` | 3600s | `storyline_processing` | `_execute_storyline_synthesis` | Storylines for long-form synthesis | Synthesis artifacts |
| `digest_generation` | 3600s | `editorial_document_generation` | `_execute_digest_generation` | Digest inputs | Digest records |
| `daily_briefing_synthesis` | 14400s | `storyline_synthesis` | `_execute_daily_briefing_synthesis` | Breaking / domain briefings | Briefing content |
| `narrative_thread_build` | 7200s | `storyline_processing`, `editorial_document_generation` | `_execute_narrative_thread_build` | Cross-storyline arcs | Narrative threads |
| `watchlist_alerts` | 1200s | `story_continuation` | `_execute_watchlist_alerts_v5` | Pattern / watch rules | Alerts |
| `pattern_matching` | 1800s | — | `_execute_pattern_matching` | Watch patterns vs new content | `pattern_matches` |

### Maintenance

| Task | Default interval | depends_on | Primary implementation | Inputs / selection | Outputs |
|------|------------------|------------|-------------------------|--------------------|---------|
| `cache_cleanup` | 3600s | — | `_execute_cache_cleanup` | Expired cache keys | Deleted cache rows |
| `data_cleanup` | 86400s | — | `_execute_data_cleanup` | Stale / orphaned rows policy | Cleanup |
| `research_topic_refinement` | 3600s | — (idle_only) | `_execute_research_topic_refinement` | Finance research topics when idle | Refined topic artifacts |

---

## RSS collector (ingestion detail)

**Entry:** `api/collectors/rss_collector.py` → `collect_rss_feeds()`.

**Feed discovery:** Default **`url_schema_pairs()`** minus **`RSS_INGEST_EXCLUDE_DOMAIN_KEYS`**. If **`RSS_INGEST_MIRROR_PIPELINE=true`**, use **`pipeline_url_schema_pairs()`** instead (same silos as processing), then apply RSS exclude. For each pair, query `{schema}.rss_feeds WHERE is_active = true`.

**Per-item logic (conceptual):** fetch feed → parse entries → deduplicate (URL / content hash per project rules) → exclude low-quality / clickbait / ads where configured → insert or update `{schema}.articles` with `feed_name`, `published_at`, `content` (inline enrichment if body short), `enrichment_status`, `metadata` (e.g. source tier from governance).

**Failure / partial:** Empty fetch, HTTP errors, and excluded items are logged; activity may be logged via `log_rss_pull`.

---

## Methodology notes for improvement analysis

1. **Define “success” per phase** using the [Quality-first phase contracts](#quality-first-phase-contracts-success-skip-handoff) section and the same predicates as `backlog_metrics` (pending counts must match `_execute_*` selection SQL). Use **`api/scripts/report_metadata_enrichment_status.py`** for metadata coverage.
2. **Batch sizes** in `BATCH_SIZE_PER_TASK` define “normal throughput” vs “backlog” — tuning analysis should compare pending counts to these floors.
3. **Dependencies** prevent upstream starvation (e.g. `claim_extraction` after `context_sync`); removing a dependency in code without shifting data flow can cause empty extracts.
4. **Cross-domain vs silo:** Domain tables hold raw + ML; **`intelligence.*`** holds cross-cutting claims/events/contexts — improvement work should state which layer is targeted.
5. **Observability:** `public.automation_run_history` (phase completions), `pipeline_traces` / `pipeline_checkpoints` (stage timing), Monitor UI backlog — use for before/after comparisons when changing methodology.

---

## Related documentation

- [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md) — when things run (big picture).
- [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) — intelligence cascade and failure modes.
- [AGENTS.md](../AGENTS.md) — terminology, domain registry, Widow split.
- [docs/CODEBASE_MAP.md](CODEBASE_MAP.md) — navigation.
- Operator report: `scripts/run_last_24h_report.sh` and `docs/AUTOMATION_AND_LAST_24H_ACTIVITY.md` (if present).

---

*Intervals and `depends_on` evolve; confirm `self.schedules` in `automation_manager.py` for your checkout.*
