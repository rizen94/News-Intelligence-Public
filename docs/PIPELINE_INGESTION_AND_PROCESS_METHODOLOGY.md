# Pipeline ingestion logic and process methodology

**Purpose:** Single reference for **what each automation phase ingests, how it selects work, and what it writes** — for deeper analysis, tuning, and methodology review. This complements narrative flow docs ([DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md)) and scheduling order ([PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md)).

**Source of truth in code**

| Concern | Location |
|---------|----------|
| Task names, `depends_on`, phase numbers, default intervals | `api/services/automation_manager.py` → `self.schedules` |
| Per-task implementation | Same file → `async def _execute_<task_name>` (grep `_execute_`) |
| Pending / backlog counts (what “has work” means) | `api/services/backlog_metrics.py` → `_count_*` helpers, `BATCH_SIZE_PER_TASK` |
| Orchestrator budgets / collection interval overrides | `api/config/orchestrator_governance.yaml` |
| Domain silos RSS + iterators | `shared.domain_registry` → `url_schema_pairs()`, `get_schema_names_active()` |

---

## Scheduling model (how tasks actually run)

- **Workload-driven scheduling** (default path): phases with pending work (per `backlog_metrics`) are eligible every tick (subject to cooldown), not only on wall-clock intervals. Idle phases use their `interval` from `schedules`.
- **Collection throttle:** When downstream pending (enrichment + `context_sync` + `document_processing`) exceeds `COLLECTION_THROTTLE_PENDING_THRESHOLD`, `collection_cycle` can defer RSS so **collect → process → sync** can catch up.
- **Queue soft cap:** When `AUTOMATION_QUEUE_SOFT_CAP` is exceeded, new enqueues are skipped except phases in `AUTOMATION_QUEUE_PAUSE_ALLOW` (typically `collection_cycle`, `health_check`) so backlogs drain.
- **Widow / split hosts:** `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE` on the main host when RSS runs elsewhere; `content_enrichment` still drains `{domain}.articles` rows that need full text. See `AGENTS.md` and `docs/WIDOW_DB_ADJACENT_CRON.md`.

---

## `collection_cycle` (master ingest window)

Implemented in `_execute_collection_cycle`. Typical **ordered** sub-steps (exact branches depend on env and nightly window):

1. **RSS** — `_execute_rss_processing` → `collectors.rss_collector.collect_rss_feeds()` unless `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE`. Reads all active `{schema}.rss_feeds` (via `url_schema_pairs()`), inserts/updates `{schema}.articles` with deduplication, filtering (quality, clickbait, ads, etc.), and optional inline body fetch for short items.
2. **Content enrichment drain** — Loops `content_enrichment` batches until cap or empty (skipped in nightly window when `nightly_enrichment_context` owns the drain). Uses `article_content_enrichment_service` / trafilatura-style fetch for URLs with thin RSS body (`enrichment_status` pending/failed, attempts &lt; cap).
3. **Document collection / processing** — PDFs and `intelligence.processed_documents` pipeline as configured.
4. **Pending collection queue** — Any URL queue drained after RSS.

**Ingestion logic (articles):** RSS path is domain-scoped; article rows are **create or update by URL** within each schema; downstream phases assume **`content` length** drives ML and `context_sync` quality.

### Content readiness gates (shared rules)

Single source of truth: `api/shared/article_processing_gates.py`.

- **`ml_processing`, `quality_scoring`, `sentiment_analysis`:** Only articles with **`enrichment_status = 'enriched'`**, or **legacy** rows with `enrichment_status IS NULL` and **`LENGTH(content) >= 500`** (same bar as RSS “substantial body” / pre-tracking data). **Minimum** `LENGTH(content) > 100` is still part of the SQL fragment.
- **`context_sync` / `ensure_context_for_article`:** Create `intelligence.contexts` only when **`LENGTH(content) > 100`** and either **`LENGTH(content) >= 500`** or **`enrichment_status IN ('enriched', 'failed', 'inaccessible')`** (terminal or substantial body), so thin rows are not linked until enrichment catches up. After enrichment succeeds, batch enrichment calls **`sync_context_from_article_after_content_change`** (update existing context or create if missing).
- **`context_sync` scheduling:** `depends_on` includes **`content_enrichment`** as well as **`collection_cycle`** so a drain pass can settle before backfill (when `content_enrichment` is disabled via `AUTOMATION_DISABLED_SCHEDULES`, `depends_on` is stripped as today).
- **RSS ingest:** `rss_item_passes_ingest_gates` rejects empty titles, missing URLs, or extremely thin items before insert.

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

**Feed discovery:** `url_schema_pairs()` → for each `(domain_key, schema_name)` query `{schema}.rss_feeds WHERE is_active = true`.

**Per-item logic (conceptual):** fetch feed → parse entries → deduplicate (URL / content hash per project rules) → exclude low-quality / clickbait / ads where configured → insert or update `{schema}.articles` with `feed_name`, `published_at`, `content` (inline enrichment if body short), `enrichment_status`, `metadata` (e.g. source tier from governance).

**Failure / partial:** Empty fetch, HTTP errors, and excluded items are logged; activity may be logged via `log_rss_pull`.

---

## Methodology notes for improvement analysis

1. **Define “success” per phase** using the same predicates as `backlog_metrics` (e.g. metadata enrichment = `metadata.enrichment_done`; content enrichment = `enrichment_status` and attempts). Use **`api/scripts/report_metadata_enrichment_status.py`** for metadata coverage.
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
