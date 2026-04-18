# Pipeline quality and idempotency — review checklist

**Goal:** Improve **output quality** and **efficiency** by preventing unnecessary rework at each step (lower latency, fewer redundant LLM/DB passes, stable artifacts).

**Scope:** All tasks in `AutomationManager.schedules` (`api/services/automation_manager.py`) plus **cross-cutting** ingest and metrics behavior. Methodology context: [PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md](PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md), order map: [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md).

**How to use this doc**

1. Complete **§0 Cross-cutting** once before deep-diving individual phases.
2. Work through **§1 Master checklist** in order (roughly collect → bridge → extract → ML → storylines → events → editorial → maintenance).
3. For each phase, open `**_execute_<name>`** in `api/services/automation_manager.py` (see §3) and the **service** it calls; compare **selection SQL / exit conditions** to `**backlog_metrics`** (`api/services/backlog_metrics.py`) if this phase has a pending count.
4. Record findings in the **Review log** table at the bottom (or your own doc).

**Legend — `SKIP_WHEN_EMPTY`**

- **Y** — Phase is in `SKIP_WHEN_EMPTY`: scheduler skips when **raw** `get_all_pending_counts()[phase] == 0` *before* interval fallback. A missing key behaves like permanent zero → **starvation**.
- **N** — Not in set: **interval ticks even at zero pending**; higher risk of empty cycles unless `_execute_*` exits cheaply.

**Structural guard (code):** `SKIP_WHEN_EMPTY ⊆ RAW_PENDING_COUNT_KEYS` is enforced at import in `api/services/backlog_metrics.py`, and a successful `_get_raw_pending_counts()` must return **exactly** `RAW_PENDING_COUNT_KEYS` — prevents the “in `SKIP` but no pending row” class of bugs from returning.

---

## §0 Cross-cutting (do these first)

Four themes cover the former 0.1–0.8 list; each points to **root cause** (single source / contract) rather than symptoms.


| #     | Theme                             | Root contract                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | What to verify / long-term                                                                                                                                           |
| ----- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | **One backlog truth**             | `SKIP_WHEN_EMPTY` phases **must** appear in `_get_raw_pending_counts()` with the **same eligibility** as `_execute_*` SQL (`backlog_metrics.py` + `automation_manager.py`).                                                                                                                                                                                                                                                                                                                                                                                                                     | Predicate drift → false backlog, starvation, or idle LLM ticks. Prefer **shared SQL fragments** (`article_processing_gates`, pass markers) over duplicated literals. |
| **B** | **Ingest & scheduling ownership** | **RSS domain list** (`RSS_INGEST_MIRROR_PIPELINE`, `RSS_INGEST_EXCLUDE_DOMAIN_KEYS`) matches **pipeline** silos; **one RSS writer** per DB when using `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE` + Widow. **Collection throttle** defers the **entire** `collection_cycle` (not RSS alone) when downstream sum > `COLLECTION_THROTTLE_PENDING_THRESHOLD`; standalone `content_enrichment` still drains. **Nightly:** `NIGHTLY_UNIFIED_PIPELINE_ENABLED` + `NIGHTLY_PIPELINE_*` — unified drain owns enrichment/context/GPU refinement; `NIGHTLY_PIPELINE_EXCLUSIVE` blocks duplicate schedulers. | Misconfig → duplicate articles or double-drains → full downstream rework.                                                                                            |
| **C** | **Row-level stability**           | `article_processing_gates`: ML + `context_sync` share `sql_*` helpers with backlog; optional `STRICT_ARTICLE_ENRICHMENT_GATES_SINCE`. `entity_extraction` uses its **own** SQL (not `sql_ml_ready`) — document or align if you want strict cutoff there too. `metadata.pipeline_skip` (`*_MAX_FAILURES`) for entity/sentiment/quality/event extraction — terminal skip stops poison-pill loops.                                                                                                                                                                                         | Rework / flip-flop / wasted LLM on rows that cannot succeed.                                                                                                         |
| **D** | **Observability & pressure**      | `automation_run_history` = run-level only (no row counts); `/processing_progress` merges history + `backlog_metrics` for `pending_records`, pass %, duration. **Graph distillation:** `graph_connection_distillation` + `intelligence.graph_connection_proposals` / `_links` ([GRAPH_CONNECTION_DISTILLATION.md](GRAPH_CONNECTION_DISTILLATION.md)). **Queue caps + DB gate** (`AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE`, `AUTOMATION_PER_PHASE_CONCURRENT_CAP`, `CLAIM_EXTRACTION_DRAIN`, `AUTOMATION_DB_POOL_*`) prevent stacked duplicate tasks.                                                                                                                                                                                                                           | “Success but no-op”: high pass % + low duration + flat pending. Oscillating pending: cache TTL + boundary rows + continuous re-queue.                                |


### §0.1 backlog_metrics vs `_execute_*` (predicate alignment)

**Rule:** For **every** phase in **`SKIP_WHEN_EMPTY`**, `get_all_pending_counts()[phase]` (raw pending from `_get_raw_pending_counts`) must reflect the same **“needs work”** predicate as the **batch selector** inside **`_execute_<phase>`** in `automation_manager.py`. **`_should_run_task`** skips `SKIP_WHEN_EMPTY` phases when **raw pending == 0** before interval fallback — so a **missing** pending key behaves like **permanent zero** → the phase **never schedules**.

**Sources:** `_get_raw_pending_counts()` → `_count_*` in `api/services/backlog_metrics.py`; executors `_execute_*` in `api/services/automation_manager.py`.

**Structural guards (already in code):** `SKIP_WHEN_EMPTY ⊆ RAW_PENDING_COUNT_KEYS` at import; after a successful `_get_raw_pending_counts`, returned keys must equal **`RAW_PENDING_COUNT_KEYS`** (catches key drift). Phases with counts but **not** in `SKIP_WHEN_EMPTY` (e.g. `document_processing`, `content_refinement_queue`) still use backlog for limits/UI but **interval** can tick at zero pending.

**Reference table:** Each row is a reminder of where alignment must hold; the **`SKIP_WHEN_EMPTY`** rows are the starvation-critical set.


| Phase (pending key)            | Backlog helper                                      | Execute selector (summary)                                                                 | Notes                                                                                                                                             |
| ------------------------------ | --------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `content_enrichment`           | `_count_content_enrichment_backlog`                 | `enrich_articles_batch`                                                                    | Status/attempts/URL align with count.                                                                                                             |
| `context_sync`                 | `_count_context_sync_backlog`                       | `sync_domain_articles_to_contexts(..., limit=100)`                                         | Uses `sql_context_sync_article_ready`; nightly defers to `nightly_enrichment_context`.                                                            |
| `event_tracking`               | `_count_event_tracking_backlog`                     | `discover_events_from_contexts` (service)                                                  | Window + min length + NOT EXISTS chronicle + optional **context pass marker**.                                                                    |
| `claim_extraction`             | `_count_claim_extraction_backlog`                   | `drain_claim_extraction_for_automation_task` / `run_claim_extraction_batch`                | Min text length env; optional **context pass marker**.                                                                                            |
| `entity_profile_build`         | `_count_entity_profile_build_backlog`               | `get_entity_profile_ids_to_build` path                                                     | Count requires context mentions; avoids empty builds.                                                                                             |
| `investigation_report_refresh` | `_count_investigation_report_backlog`               | `_execute_investigation_report_refresh`                                                    | Events without `event_reports`.                                                                                                                   |
| `document_processing`          | `_count_document_processing_backlog`                | `process_unprocessed_documents`                                                            | **Not** `SKIP_WHEN_EMPTY`; limit scales with backlog.                                                                                             |
| `content_refinement_queue`     | `_count_content_refinement_queue_pending`           | Queue worker                                                                               | **Not** `SKIP_WHEN_EMPTY`.                                                                                                                        |
| `metadata_enrichment`          | `_count_metadata_enrichment_pending`                | `run_metadata_enrichment_batch_for_domains`                                                | `LENGTH(content) > 50`, `enrichment_done`, optional **article pass marker**.                                                                      |
| `ml_processing`                | `_count_ml_processing_pending`                      | `ml_processed = false` + `sql_ml_ready_and_content_bounds`                                 | Execute LIMIT 50/schema vs count = all pending (OK).                                                                                              |
| `entity_extraction`            | `_count_entity_extraction_pending`                  | Same join + skip + length + enrichment gate + optional **article pass marker**             | Aligned with `_execute_entity_extraction`.                                                                                                        |
| `sentiment_analysis`           | `_count_sentiment_analysis_pending`                 | `sentiment_score IS NULL` + skip + `ml_ready` + pass marker                                | Execute records pass on success.                                                                                                                  |
| `quality_scoring`              | `_count_quality_scoring_pending`                    | `quality_score IS NULL` + skip + `ml_ready`                                                | **No** pass marker in count or execute — backlog = rows never scored.                                                                             |
| `storyline_processing`         | `_count_storyline_processing_pending`               | Storylines with articles + short `analysis_summary`/`master_summary`                       | Aligns with narrative backlog concept.                                                                                                            |
| `topic_clustering`             | `_count_topic_clustering_pending`                   | Pass-marker vs legacy confidence mode                                                      | Must match `topic_clustering` service / `_execute_topic_clustering`.                                                                              |
| `timeline_generation`          | `_count_timeline_generation_pending`                | Storylines missing short `timeline_summary`                                                | Matches `_execute_timeline_generation` WHERE clause.                                                                                              |
| `storyline_discovery`          | `_count_storyline_discovery_pending`                | Newest-N articles not on any storyline + pass marker                                       | Proxy cap matches discovery service limit.                                                                                                        |
| `proactive_detection`          | `_count_proactive_detection_pending`                | 72h articles without `storyline_articles`                                                  | **Differs from discovery** (window + no newest-N cap) — intentional different horizons.                                                           |
| `storyline_automation`         | `_count_storyline_automation_pending`               | Count = **all** `automation_enabled` storylines                                            | Execute rotates a small batch; pending is **pool depth**, not “unlinked articles”.                                                                |
| `rag_enhancement`              | `_count_rag_enhancement_pending`                    | `rag_enhanced_at` null or **> 1h** stale                                                   | Matches `_execute_rag_enhancement` **3600s** skip when recently enhanced.                                                                         |
| `event_extraction`             | `_count_event_extraction_pending`                   | `timeline_processed`, skips, content, status/enrichment gate + pass marker                 | Matches `_execute_event_extraction_v5` WHERE (LIMIT 30 vs full count).                                                                            |
| `claims_to_facts`              | `_count_claims_to_facts_pending`                    | `build_claims_to_facts_backlog_where_suffix`                                               | Count mode env (`CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE`).                                                                                            |
| `legislative_references`       | `_count_legislative_references_backlog`             | `run_legislative_reference_batch` domain list + scan table                                 | Uses `LEGISLATIVE_SCAN_DOMAIN_KEYS` + `SCAN_ARTICLE_DAYS`.                                                                                        |
| `entity_profile_sync`          | `_count_entity_profile_sync_pending`                | `sync_domain_entity_profiles`                                                              | Canonical without `old_entity_to_new` mapping.                                                                                                    |
| `entity_enrichment`            | `_count_entity_enrichment_pending`                  | **0/1** via `get_entity_profile_ids_to_enrich(limit=1)`                                    | Binary presence, not row count — Monitor “pending” is coarse.                                                                                     |
| `entity_dossier_compile`       | `_count_entity_dossier_compile_pending`             | `_execute_entity_dossier_compile`                                                          | Covered by `RAW_PENDING_COUNT_KEYS` / import invariant.                                                                                           |
| `story_enhancement`            | `_count_story_enhancement_pending`                  | `run_enhancement_cycle`: queues **+** enrich batch **+** profile build batch               | Count includes the same three backlog signals as the cycle (queues + `_count_entity_enrichment_pending` + `_count_entity_profile_build_backlog`). |
| `storyline_synthesis`          | `_count_storyline_synthesis_pending`                | 3+ articles and (`synthesized_content IS NULL` **or** article newer than `synthesized_at`) | Matches `_execute_storyline_synthesis` selector (fallback: NULL content only if `synthesized_at` path unavailable).                               |
| `nightly_enrichment_context`   | Sum of enrichment + context_sync + refinement queue | `_execute_nightly_enrichment_context`                                                      | Composite pending for throttle/nightly UI.                                                                                                        |
| `graph_connection_distillation` | `_count_graph_connection_distillation_pending`     | `process_graph_connection_proposals_batch` → merges + `graph_connection_links`            | Pending = rows in `intelligence.graph_connection_proposals` with `status = 'pending'`; align batch behavior with [GRAPH_CONNECTION_DISTILLATION.md](GRAPH_CONNECTION_DISTILLATION.md). |


**Phases with no row in `_get_raw_pending_counts`:** Everything else (`event_coherence_review`, `cross_domain_synthesis`, `editorial_`*, `digest_generation`, `event_deduplication`, …) relies on **interval-only** scheduling (`SKIP_WHEN_EMPTY` = N) or manual `request_phase` — not a pending/backlog mismatch, but Monitor will show **0** pending for them.

---

## §1 Master checklist (all automation phases)

Check each line when the **idempotency + quality** review for that process is done.

### Collection and infrastructure

- **§0 themes A–D** Cross-cutting
- **collection_cycle** — RSS, enrichment loop, document drain, pending URL queue; sub-steps `_execute_rss_processing`, `_execute_content_enrichment`, … inside cycle
- **nightly_enrichment_context** — Local night window orchestration vs standalone phases
- **document_processing** — PDF / `processed_documents` drain; **SKIP empty: N** (ticks on interval)
- **content_enrichment** — Trafilatura / URL fetch; idempotent promote `enrichment_status`
- **health_check** — Metrics only; **SKIP empty: N** — ensure cheap when healthy
- **pending_db_flush** — Spill replay when DB was down

### Bridge and profiles

- **context_sync** — Article → `intelligence.contexts`; no duplicate contexts per article; content gates
- **entity_profile_sync** — Canonical → `entity_profiles` drift
- **entity_profile_build** — Sections / relationships from contexts

### Intelligence extraction (context-centric)

- **claim_extraction** — Contexts → claims; cap / drain behavior; no duplicate claims for same signal
- **legislative_references** — Bill scan + Congress.gov; rate limits; skip when no API key / no candidates
- **claims_to_facts** — Promotion to `versioned_facts`; idempotent on same claim
- **claim_subject_gap_refresh** — Catalog rebuild; **SKIP empty: N** — full refresh vs delta?
- **extracted_claims_dedupe** — Same context + normalized triple; bounded batch; **SKIP empty: N**
- **event_tracking** — Contexts → tracked events / chronicles
- **event_coherence_review** — LLM fit check; **SKIP empty: N** — only rows needing review?
- **investigation_report_refresh** — Stale reports when events gain context
- **cross_domain_synthesis** — Cross-domain correlation; **SKIP empty: N** — avoid re-synthesizing unchanged pairs
- **pattern_recognition** — Network/temporal/behavioral; **SKIP empty: N**
- **entity_dossier_compile** — Dossiers stale/missing; “stale” definition clear?
- **entity_position_tracker** — Positions from articles; **SKIP empty: N**
- **metadata_enrichment** — `metadata.enrichment_done`; single-writer semantics
- **entity_organizer** — Merge/prune; **SKIP empty: N** — avoid merge thrash / repeated same merge
- **graph_connection_distillation** — Proposal queue → storyline/entity merges and M2M `graph_connection_links`; **SKIP empty: Y** — depends on `entity_organizer`; see [GRAPH_CONNECTION_DISTILLATION.md](GRAPH_CONNECTION_DISTILLATION.md)

### Per-article ML and topics (domain tables)

- **ml_processing** — `ml_processed`; summary regeneration only when needed
- **entity_extraction** — `article_entities`; strict domains; pipeline_skip integration
- **quality_scoring** — Only when gate passes; no flip-flop on identical content
- **sentiment_analysis** — Same as quality_scoring for stability
- **topic_clustering** — Assignments/clusters; avoid re-clustering unchanged article sets without version/hash

### Storylines and discovery

- **storyline_discovery** — New cluster → storyline; duplicate storyline guard
- **proactive_detection** — Emerging / unlinked promotions
- **fact_verification** — Recent claims; **SKIP empty: N** — verify only if not already verified / unchanged inputs
- **storyline_processing** — Summaries / narratives; **content version or updated_at** before LLM regen?
- **storyline_automation** — Match articles to automation storylines; idempotent links
- **storyline_enrichment** — Full-history pass (12h); **highest rework risk** — boundary for “already enriched”
- **rag_enhancement** — RAG chunks / enhanced fields; skip if chunk hash unchanged
- **story_enhancement** — Story enhancement queue; cap per run

### Events v5 and timeline

- **event_extraction** — v5 extraction; entity dependency
- **event_deduplication** — **SKIP empty: N** — cheap no-op when nothing to merge
- **story_continuation** — **SKIP empty: N**
- **timeline_generation** — `chronological_events`; depends on rag_enhancement per schedule

### RAG entity and refinement queue

- **entity_enrichment** — Wikipedia / external; skip already enriched; queue depth cap
- **content_refinement_queue** — DB queue + finisher; **SKIP empty: N** — must be fast when queue empty

### Editorial, digests, watchlist

- **editorial_document_generation** — **SKIP empty: N** — only if missing/stale editorial doc (hash / `updated_at` / source rev)
- **editorial_briefing_generation** — Tracked events narrative stack; same staleness rules
- **digest_generation** — **SKIP empty: N** — digest key per day/domain? avoid duplicate digests
- **storyline_synthesis** — Long-form synthesis; staleness / once-per-storyline-version
- **daily_briefing_synthesis** — Breaking briefing; idempotent per window
- **watchlist_alerts** — **SKIP empty: N** — alert dedup / same fingerprint
- **pattern_matching** — **SKIP empty: N** — pattern_matches idempotency

### Idle / maintenance

- **research_topic_refinement** — Finance; `idle_only`; **SKIP empty: N**
- **narrative_thread_build** — Cross-storyline arcs; **SKIP empty: N** — LLM cost
- **data_cleanup** — **SKIP empty: N** — destructive ops only on true orphans; bounded
- **cache_cleanup** — Expired keys only; **SKIP empty: N**

---

## §2 Per-phase review template (copy for each deep-dive)

Use one block per phase when reviewing in detail.

```
Phase name:
Primary implementation: automation_manager._execute_* → … (services / modules)

Scheduling:
  - depends_on:
  - Default interval (idle):
  - SKIP_WHEN_EMPTY: Y / N

Inputs (what rows / entities are selected?):
Outputs (what tables / JSON fields change?):

Idempotency / rework prevention:
  - [ ] Selection query matches backlog_metrics (if applicable)
  - [ ] “Already done” flag, hash, or version on source row prevents repeat LLM
  - [ ] Upserts / unique constraints prevent duplicate artifacts
  - [ ] Empty batch exits in O(1) or cheap query (especially if SKIP_WHEN_EMPTY = N)

Quality:
  - [ ] Output stable when re-run on unchanged input (or intentional refresh only when stale)
  - [ ] Failure path does not reset progress in a way that causes infinite retries

Efficiency notes:
  - Batch size vs env caps
  - LLM calls per row (minimize)

Reviewed by:     Date:
Outcome (keep / tune / code change follow-up):
```

---

## §3 Quick reference — `_execute_*` entry points


| Schedule key                    | Handler in `automation_manager.py`                             |
| ------------------------------- | -------------------------------------------------------------- |
| `collection_cycle`              | `_execute_collection_cycle` (includes RSS / enrichment / docs) |
| `nightly_enrichment_context`    | `_execute_nightly_enrichment_context`                          |
| `document_processing`           | `_execute_document_processing`                                 |
| `content_enrichment`            | `_execute_content_enrichment`                                  |
| `context_sync`                  | `_execute_context_sync`                                        |
| `entity_profile_sync`           | `_execute_entity_profile_sync`                                 |
| `claim_extraction`              | `_execute_claim_extraction`                                    |
| `legislative_references`        | `_execute_legislative_references`                              |
| `claims_to_facts`               | `_execute_claims_to_facts`                                     |
| `claim_subject_gap_refresh`     | `_execute_claim_subject_gap_refresh`                           |
| `extracted_claims_dedupe`       | `_execute_extracted_claims_dedupe`                             |
| `event_tracking`                | `_execute_event_tracking`                                      |
| `event_coherence_review`        | `_execute_event_coherence_review`                              |
| `investigation_report_refresh`  | `_execute_investigation_report_refresh`                        |
| `cross_domain_synthesis`        | `_execute_cross_domain_synthesis`                              |
| `entity_profile_build`          | `_execute_entity_profile_build`                                |
| `pattern_recognition`           | `_execute_pattern_recognition`                                 |
| `entity_dossier_compile`        | `_execute_entity_dossier_compile`                              |
| `entity_position_tracker`       | `_execute_entity_position_tracker`                             |
| `metadata_enrichment`           | `_execute_metadata_enrichment`                                 |
| `entity_organizer`              | `_execute_entity_organizer`                                    |
| `graph_connection_distillation` | `_execute_graph_connection_distillation`                       |
| `ml_processing`                 | `_execute_ml_processing`                                       |
| `topic_clustering`              | `_execute_topic_clustering`                                    |
| `entity_extraction`             | `_execute_entity_extraction`                                   |
| `quality_scoring`               | `_execute_quality_scoring`                                     |
| `sentiment_analysis`            | `_execute_sentiment_analysis`                                  |
| `storyline_discovery`           | `_execute_storyline_discovery`                                 |
| `proactive_detection`           | `_execute_proactive_detection`                                 |
| `fact_verification`             | `_execute_fact_verification`                                   |
| `storyline_processing`          | `_execute_storyline_processing`                                |
| `storyline_automation`          | `_execute_storyline_automation`                                |
| `storyline_enrichment`          | `_execute_storyline_enrichment`                                |
| `rag_enhancement`               | `_execute_rag_enhancement`                                     |
| `event_extraction`              | `_execute_event_extraction_v5`                                 |
| `event_deduplication`           | `_execute_event_deduplication_v5`                              |
| `story_continuation`            | `_execute_story_continuation_v5`                               |
| `timeline_generation`           | `_execute_timeline_generation`                                 |
| `entity_enrichment`             | `_execute_entity_enrichment`                                   |
| `story_enhancement`             | `_execute_story_enhancement`                                   |
| `content_refinement_queue`      | `_execute_content_refinement_queue`                            |
| `cache_cleanup`                 | `_execute_cache_cleanup`                                       |
| `editorial_document_generation` | `_execute_editorial_document_generation`                       |
| `editorial_briefing_generation` | `_execute_editorial_briefing_generation`                       |
| `digest_generation`             | `_execute_digest_generation`                                   |
| `storyline_synthesis`           | `_execute_storyline_synthesis`                                 |
| `daily_briefing_synthesis`      | `_execute_daily_briefing_synthesis`                            |
| `watchlist_alerts`              | `_execute_watchlist_alerts_v5`                                 |
| `pattern_matching`              | `_execute_pattern_matching`                                    |
| `research_topic_refinement`     | `_execute_research_topic_refinement`                           |
| `narrative_thread_build`        | `_execute_narrative_thread_build`                              |
| `data_cleanup`                  | `_execute_data_cleanup`                                        |
| `health_check`                  | `_execute_health_check`                                        |
| `pending_db_flush`              | `_execute_pending_db_flush`                                    |


RSS-only path: `_execute_rss_processing` (invoked from collection cycle).

---

## §4 `SKIP_WHEN_EMPTY` membership (from `backlog_metrics.py`)

**Y — in `SKIP_WHEN_EMPTY`:**  
`content_enrichment`, `context_sync`, `event_tracking`, `claim_extraction`, `entity_profile_build`, `investigation_report_refresh`, `pending_db_flush`, `nightly_enrichment_context`, `metadata_enrichment`, `ml_processing`, `entity_extraction`, `sentiment_analysis`, `quality_scoring`, `storyline_processing`, `topic_clustering`, `timeline_generation`, `storyline_discovery`, `proactive_detection`, `storyline_automation`, `rag_enhancement`, `event_extraction`, `claims_to_facts`, `legislative_references`, `entity_profile_sync`, `entity_enrichment`, `entity_dossier_compile`, `story_enhancement`, `storyline_synthesis`, `graph_connection_distillation`

**N — not in set (interval can fire at zero pending):**  
`collection_cycle`, `document_processing`, `claim_subject_gap_refresh`, `extracted_claims_dedupe`, `event_coherence_review`, `cross_domain_synthesis`, `pattern_recognition`, `entity_position_tracker`, `entity_organizer`, `fact_verification`, `storyline_enrichment`, `event_deduplication`, `story_continuation`, `content_refinement_queue`, `cache_cleanup`, `editorial_document_generation`, `editorial_briefing_generation`, `digest_generation`, `daily_briefing_synthesis`, `watchlist_alerts`, `pattern_matching`, `research_topic_refinement`, `narrative_thread_build`, `data_cleanup`, `health_check`

---

## §5 Suggested review order (highest impact on rework first)

Prioritize **LLM-heavy** and `**SKIP_WHEN_EMPTY: N`** phases, then **full-history / synthesis**, then **dedupe/catalog**, then **high-frequency ML**.

1. `editorial_briefing_generation`, `editorial_document_generation`, `narrative_thread_build`, `daily_briefing_synthesis`, `storyline_synthesis`
2. `storyline_enrichment`, `rag_enhancement`, `storyline_processing`, `content_refinement_queue`
3. `event_coherence_review`, `cross_domain_synthesis`, `fact_verification`
4. `claim_subject_gap_refresh`, `extracted_claims_dedupe`, `entity_organizer`, `graph_connection_distillation`, `pattern_recognition`
5. `event_deduplication`, `story_continuation`, `digest_generation`, `watchlist_alerts`, `pattern_matching`
6. `entity_extraction`, `claim_extraction`, `event_tracking`, `topic_clustering` (volume + strict gates)
7. Remaining phases and §0 cross-cutting

---

## §6 Review log (optional)


| Phase                  | Date | Reviewer | SKIP_Y/N | Outcome |
| ---------------------- | ---- | -------- | -------- | ------- |
| *(add rows as you go)* |      |          |          |         |


---

*Intervals and `depends_on` change over time; confirm `self.schedules` in `automation_manager.py` for your branch.*