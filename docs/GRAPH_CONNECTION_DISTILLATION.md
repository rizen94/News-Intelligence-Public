# Graph connection distillation — inventory and merge queue

**Goal:** Treat the pipeline as **synthesis upward**: unify storylines, topics, and entities as signals arrive, prefer **auto-merge / auto-link** at **documented confidence tiers**, and avoid an ever-growing pile of unrelated rows. **Many-to-many** links and **multi-way clusters** are first-class: one proposal can reference several endpoints via JSONB.

**Queue table:** `intelligence.graph_connection_proposals` (migration `215_graph_connection_proposals.sql`).

**Applied links (M2M):** `intelligence.graph_connection_links` (migration `216_graph_connection_links.sql`) — pairwise rows for associates and hyperedge clusters.

**Services:**
- `api/services/graph_connection_queue_service.py` — upsert, fetch, links insert, `finalize_entity_merges_in_queue` after cleanup merges.
- `api/services/graph_connection_processor_service.py` — `process_graph_connection_proposals_batch` (merges + link materialization).
- **Automation phase** `graph_connection_distillation` — runs the processor on an interval (default 10 minutes, after `entity_organizer`).

---

## Confidence policy (defaults)

| Layer | Default | Env override | Notes |
|--------|---------|----------------|------|
| Storyline pairwise merge (existing) | **0.65** | `MERGE_SIMILARITY_THRESHOLD` in `storyline_consolidation_service` | Still performs DB merge in consolidation. |
| Queue “auto policy hint” column | **0.72** | `GRAPH_CONNECTION_AUTO_MERGE_MIN` | Stored as `min_confidence_for_auto`; future worker can auto-apply pending rows ≥ this without changing storyline merge yet. |
| Storyline parent / mega adjacency | **0.50** | `PARENT_SIMILARITY_THRESHOLD` | Drives mega clusters; also written as **hyperedge** proposals. |

**Many-to-many:** use `proposal_kind = 'associate'` for soft edges (topics, cross-links). Use `hyperedge` when `endpoints.storyline_ids` (or mixed types later) has **length ≥ 3** or represents a **cluster** rather than a single canonical winner.

---

## Inventory — object types and where connections are built today

| Object | Canonical / merge today | “High level” connections | Queue integration |
|--------|-------------------------|---------------------------|-------------------|
| **Storylines** | `merged_into_id`, mega `parent_storyline_id`, `storyline_consolidation_service` | Pairwise similarity (embedding + entity/title), mega BFS components | **Wired:** merge candidates and mega groups upsert proposals; successful merges → `auto_applied`. |
| **Entities** | `IntelligenceCleanupController` + `entity_canonical` merges in organizer cycle | `entity_relationships` from co-mentions (`relationship_extraction_service`) | **Wired:** after each same-name merge batch, `finalize_entity_merges_in_queue` writes **resolved** queue/audit rows. Pending **merge** proposals (high confidence) are applied by the processor (`GRAPH_CONNECTION_ENTITY_MERGE_MIN`, default **0.88**); lower confidence → **link only** in `graph_connection_links`. |
| **Topics** | Clustering in pipeline; manual merge API `topic_management.merge` | Near-duplicate / same-cluster topics | **Stub:** `record_topic_pair_association_proposal` — call from clustering or embedding pass with `proposal_kind=associate` first. |
| **Events / investigations** | `investigation_consolidation_service` supersets; `event_deduplication` automation | Keyword clusters → `tracked_event` superset | **Future:** enqueue `hyperedge` with `tracked_event_ids` when cluster size ≥ 2. |
| **Cross-domain** | `cross_domain_service` → `intelligence.cross_domain_correlations` | Shared entities across domains | **Future:** enqueue `associate` rows mirroring new correlation pairs for audit + replay. |

---

## Schedulers (where work runs)

1. **`ConsolidationScheduler`** (`api/main.py` + `consolidation_scheduler.py`) — rotates storylines / entities / investigations+events on `CONSOLIDATION_INTERVAL_SECONDS`.
2. **`AutomationManager`** — includes **`graph_connection_distillation`** (drains the proposal queue into merges and/or `graph_connection_links`). Also: `topic_clustering`, `event_deduplication`, `cross_domain_synthesis`, etc.
3. **Nightly sequential drain** — `graph_connection_distillation` is listed in `nightly_ingest_window_service` sequential phases so unified night runs can pick up backlog too.

---

## `endpoints` JSONB shape (convention)

```json
{
  "domain_key": "politics",
  "storyline_ids": [12, 34],
  "topic_ids": [],
  "entity_ids": [],
  "tracked_event_ids": []
}
```

Omit empty arrays over time if you prefer smaller rows; writers should stay consistent. **Cross-type** hyperedges may set several lists non-empty.

---

## Operational checklist

1. Apply migrations **215** and **216** on the DB used by the API.
2. Run storyline consolidation once; confirm rows appear in `intelligence.graph_connection_proposals` with `source = storyline_consolidation`.
3. Enable or tune **`graph_connection_distillation`** in `AutomationManager.schedules` (default on, `interval` 600s, `depends_on`: `entity_organizer`).
4. Optional env: **`GRAPH_CONNECTION_DISTILLATION_BATCH`** (default 12), **`GRAPH_CONNECTION_ENTITY_MERGE_MIN`** (default 0.88), **`GRAPH_CONNECTION_STORYLINE_LINK_ONLY_MAX`** (default 0.64 — between this and **0.65** merges become **links only**).
5. Wire **`record_topic_pair_association_proposal`** from topic near-duplicate detection when you have pairwise scores.

---

## Related code

- `api/services/storyline_consolidation_service.py` — merge + mega + queue hooks; `merge_storylines_by_ids` for the worker.
- `api/services/graph_connection_queue_service.py` — persistence API + link insert + entity finalize.
- `api/services/graph_connection_processor_service.py` — batch processor.
- `api/services/backlog_metrics.py` — `graph_connection_distillation` pending count (`SKIP_WHEN_EMPTY`).
- `api/services/entity_organizer_service.py` — organizer cycle entrypoint.
- `api/domains/content_analysis/routes/topic_management.py` — manual topic merge (complement to automated queue).
- `api/services/cross_domain_service.py` — cross-domain correlations.
