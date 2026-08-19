# Pipeline efficiency — remaining work

Tracked after the 2026-07-16 efficiency pass (quick wins + high-impact slices).

Canvas: `canvases/rss-pipeline-efficiency-review.canvas.tsx`

## Done

### Quick wins (earlier 2026-07-16)

| ID | Change | Notes |
|----|--------|-------|
| C1 | Conditional GET (ETag / Last-Modified) | Migration `266`; 304 skip |
| C2 | Batched URL dedup prefetch | `WHERE url = ANY(%s)` + early skip |
| U3 | Bulk UIE pass markers + queue finalize | `bulk_record` + batched queue complete/release |
| U2 | Extraction `num_ctx` default 8192 | Widow + PopOS UIE worker |
| P2 | Mention resolver pool + batch writes | `execute_values` |

### Next slice (same day)

| ID | Change | Notes |
|----|--------|-------|
| U1 | Entity store fast path by default | Skips relational LLM + Wikipedia unless `ENTITY_STORE_SLOW_ENRICH=true` |
| C4 | Inline RSS fulltext off by default | `RSS_INLINE_FULLTEXT_ENABLED` (default false); enrichment owns bodies |
| U4 | Parallel content enrichment | `CONTENT_ENRICHMENT_FETCH_PARALLEL=8`, per-host limit 2 |
| P1 | Throttled backlog invalidate | No per-round invalidate; end-of-drain throttle 60s |

### Final slice (same day)

| ID | Change | Notes |
|----|--------|-------|
| U5 | Queue-only enrichment drain | `shared/content_enrichment_drain.py` — claim → enrich → finalize; SQL fallback only when claim empty |
| C3 | Honor per-feed `fetch_interval_seconds` | Due-feed SELECT + empty-fetch interval bump |
| C5 | One commit per feed (deferred) | Removed per-article commits; `_insert_domain_article` returns id |
| P3 | Indexed event↔context junction | Migration `267` `event_chronicle_contexts`; anti-joins use btree |
| P4 | link_indexer one conn per domain | Optional `cur` on graph proposal upsert |
| P5 | Replan debounce + pass pending | `PIPELINE_REPLAN_DEBOUNCE_SECONDS=3`; reconcile reuses pending |

### Monitor / Ollama stability (2026-07-17)

| ID | Change | Notes |
|----|--------|-------|
| M1 | CE `runs_1h` alignment | Nightly CE no-op skips outer history; daytime always `batch_round`; nightly drain attributes enrich batches (`75c694f`) |
| M2 | EPB hang guards | Skip per-profile fallback on preempt/503/timeout; `wait_for` remaining drain budget mid-batch (`cb402ad`) |

## Intentionally deferred

- **`intelligence.spine_tail_queue`** (migration 254) — unused; spine SQL tail still runs direct drains. Drop or wire later; not required for U5.
- True `execute_values` multi-row article INSERT (C5 partial) — deferred commit already removes commit chatter; multi-row INSERT can follow if profiling shows INSERT cost dominates.

## Related constants (current defaults)

- `OLLAMA_EXTRACTION_NUM_CTX=8192`
- `OLLAMA_AUTOMATION_KEEP_ALIVE=2m`, `OLLAMA_UI_KEEP_ALIVE=2m`
- `ASSEMBLY_ENTITY_PROFILE_BUILD_CYCLE_BUDGET_SECONDS=900`
- `ENTITY_STORE_FAST_PATH=true` (opt out: `ENTITY_STORE_SLOW_ENRICH=true`)
- `RSS_INLINE_FULLTEXT_ENABLED=false`
- `CONTENT_ENRICHMENT_FETCH_PARALLEL=8`, `CONTENT_ENRICHMENT_PER_HOST_LIMIT=2`
- `PIPELINE_REPLAN_DEBOUNCE_SECONDS=3`
- Backlog invalidate: throttled 30–60s on high-frequency drains

Update this file when an item ships.
