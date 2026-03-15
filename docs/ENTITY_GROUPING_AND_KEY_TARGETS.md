# Entity Grouping, Merging, and Key Targets — Current State

**Question:** Do we have a system that takes the full list of entities, connects/relates them, and reduces them to **key targets** or **recurring items**?

**Short answer:** We have **several building blocks** (resolution, duplicate merge, profile merge, pruning) but **no single system** that aggregates all entities into a ranked “key targets” or “recurring entities” list.

---

## What Exists Today

### 1. Entity resolution (per-domain canonicalization)

- **Where:** `api/services/entity_resolution_service.py`
- **What:** Maps `(domain, entity_name, entity_type)` → `canonical_entity_id` in that domain’s `entity_canonical`.
- **How:** Match by `canonical_name` (case-insensitive) or `aliases`; optionally create new canonical row.
- **Used by:** `ArticleEntityExtractionService` when storing article entities (each mention gets a `canonical_entity_id`).

So **within a domain**, name variations and aliases are already grouped into one canonical entity. There is **no cross-domain** canonical entity (no global “same person across politics/finance/science-tech”).

### 2. Duplicate entity merge (cleanup)

- **Where:** `api/services/intelligence_cleanup_controller.py` → `_merge_duplicate_entities()`
- **What:** Finds `entity_canonical` rows with the **same lowercase name + type**, keeps one, points all `article_entities` to it, deletes the rest.
- **When:** Run as part of the data_cleanup phase (automation_manager) or on demand.

This **reduces the raw list** by merging exact duplicates (same name, same type). It does **not** merge “Joe Biden” / “Biden” / “President Biden” into one unless resolution/aliases already did that.

### 3. Entity profile merge (manual/API)

- **Where:** `api/domains/intelligence_hub/routes/context_centric.py` → `POST /entity_profiles/{target_id}/merge`
- **What:** Merges a **source** entity profile into a **target** (same domain). Redirects `old_entity_to_new` and `context_entity_mentions` to the target.
- **Use case:** When you know two profiles are the same entity and want one combined profile.

This **connects and reduces** at the **profile** level by hand or script; it is not an automatic “group all and pick key targets” step.

### 4. Low-value prune and entity cap

- **Where:** Same `IntelligenceCleanupController`
- **What:**
  - **Low-value prune:** Removes entities that are old enough and have ≤ N mentions (policy: `entity_low_value_min_age_days`, `entity_low_value_max_mentions`).
  - **Entity cap:** If `entity_canonical` count exceeds `max_entity_profiles_per_domain`, removes **least-referenced** entities until under the cap.
- **Effect:** Shrinks the list by dropping rare/old or excess entities; the “remaining” set is not explicitly ranked as “key” or “recurring.”

### 5. Relationships (connecting, not reducing)

- **Where:** `api/services/relationship_extraction_service.py`, `intelligence.entity_relationships`
- **What:** Builds links between entity profiles (e.g. co-mentions in contexts → `entity_a_id`, `entity_b_id`).
- **Effect:** **Connects** entities; does not **group** or **rank** them into key targets.

### 6. Per-storyline “key” entities

- **Where:** `story_entity_index` (per domain), `storylines.key_entities` (JSONB), `storyline_automation_service`
- **What:** For each storyline, entities are tracked with `mention_count`; automation uses `story_entity_index` + `key_entities` for entity-based article search (ordered by `is_core_entity`, `mention_count`).
- **Effect:** “Recurring” or “key” entities exist **per storyline**, not as one global “key targets” list across all entities.

### 7. List APIs (no “key” or “recurring” ranking)

- **Entity profiles:** `GET .../entity_profiles` — lists profiles with optional `domain_key`, ordered by **updated_at**, not by mention count or importance.
- **Domain knowledge entities:** `GET /{domain}/rag/knowledge/entities` — lists entities from the **curated domain KB** (importance-sorted); this is **not** the same as all `entity_canonical` / article-derived entities.

So we have **no API** that returns “top N entities by mention count” or “recurring entities this week” across the whole system.

---

## Gaps Relative to “Key Targets / Recurring Items”

| Capability | Status |
|------------|--------|
| Group name variations into one canonical entity (per domain) | ✅ Resolution + aliases |
| Merge exact duplicates (same name + type) | ✅ Cleanup controller |
| Merge two known profiles into one | ✅ Merge API |
| Connect entities via relationships | ✅ Relationship extraction |
| Prune low-value / cap total entities | ✅ Cleanup controller |
| **Single list of “key” or “recurring” entities (ranked, e.g. by mentions)** | ❌ Not implemented |
| **Cross-domain entity grouping** (same entity across domains) | ❌ Not implemented (docs: Phase 2 could use normalized name) |
| **Semantic/fuzzy merge** (“Biden” / “President Biden” as one beyond aliases) | ❌ Only exact + alias match today |
| **Dashboard/report: “Key targets” or “Recurring this week”** | ❌ No such view or API |

---

## Possible Next Steps (if you want “key targets / recurring”)

1. **Key / recurring API (per domain or global)**  
   - Add an endpoint (e.g. under context_centric or a new “entity_analytics” module) that:
     - Reads from `entity_canonical` + `article_entities` (and optionally `entity_profiles`).
     - Aggregates by canonical entity: mention count, last_seen, article count.
     - Optionally filters by time window (e.g. last 7 days).
     - Returns a ranked list (e.g. top 50–100 “key” or “recurring” entities) with counts and recency.

2. **Reuse existing data**  
   - `article_entities` already has `canonical_entity_id`; joining to `entity_canonical` and counting gives “recurring” by mention volume.  
   - `story_entity_index` already has `mention_count` per (storyline, entity); could be aggregated across storylines for a domain to get “recurring in storylines.”

3. **Cross-domain grouping (later)**  
   - As in V6 docs: match across domains by normalized name (e.g. lowercased canonical name) or add a small global entity registry; then “key targets” could be defined across domains.

4. **UI**  
   - A “Key entities” or “Recurring entities” view could call the new API and show the reduced list (with links to entity profiles or storylines).

---

## Should a high-level orchestrator manage entities this way?

**Recommendation: keep the high-level orchestrator as the *scheduler*; put entity grouping / key-targets logic in a *dedicated organizer (service)*.**

### Why not a dedicated “entity orchestrator”

- **AutomationManager** already owns *when* to run entity-related work: `entity_profile_sync`, `entity_enrichment`, `story_enhancement` (enhancement cycle), `data_cleanup` (which runs `IntelligenceCleanupController`). Adding another “entity orchestrator” would duplicate scheduling and dependency logic, or you’d have to split “entity phases” between two orchestrators (confusing).
- Orchestrators in this codebase are **phase runners**: they decide order and dependencies and call **services** that implement the actual logic. Entity merge/prune/cap already follows that pattern: **IntelligenceCleanupController** (service) is invoked by AutomationManager during `data_cleanup`. The same pattern fits “key targets / recurring” well: a **service** computes the list; the **existing** orchestrator just needs to call it (e.g. in a phase or inside an existing phase).

### Why a dedicated organizer (service) is better

| Concern | Put in orchestrator? | Put in a separate organizer/service? |
|--------|-----------------------|---------------------------------------|
| **When** to refresh key entities (schedule) | ✅ Orchestrator already handles “when” via phases | — |
| **How** to compute key/recurring (rank, aggregate, filter) | ❌ Mixes scheduling with domain logic | ✅ Keeps logic testable and reusable |
| **API / UI** “key entities” on demand | ❌ Orchestrator isn’t the right entrypoint for reads | ✅ Same service can power API + scheduled refresh |
| **Reuse** by ProcessingGovernor (e.g. “only enrich key entities”) | ❌ Governor would depend on orchestrator internals | ✅ Governor can call a small “entity prioritization” service |

So:

- **Orchestrator (AutomationManager):** Add a phase (e.g. `key_entities_refresh`) that runs after `entity_profile_sync` or `data_cleanup` and **calls** the new service to recompute and optionally cache “key targets” / “recurring entities.” The orchestrator stays responsible only for *when* and *in what order* things run.
- **Dedicated organizer:** A small **service** (e.g. `EntityKeyTargetsService` or `EntityAnalyticsService`) that:
  - Aggregates entities by mention count, recency, optional importance;
  - Optionally writes to a cache table or JSON blob for fast API/UI reads;
  - Can be called from the new phase, from an API endpoint, or from ProcessingGovernor if you later want “prioritize key entities only.”

That way the “entity grouping / key targets” behavior lives in one place (the service), and the existing high-level orchestrator simply **invokes** it on a schedule, same as it does for cleanup and entity sync.

---

## Implemented: Entity organizer (pipeline + downtime loop)

- **Service:** `api/services/entity_organizer_service.py` — `run_cycle()` runs intelligence cleanup (merge/prune/cap) then relationship extraction (co-mentions → entity_relationships). `get_key_entities()` returns a ranked list by mention count for API/UI.
- **Pipeline:** AutomationManager phase `entity_organizer` runs after `entity_profile_sync` (every 10 min when dependencies are satisfied). Part of the data collection pipeline once entities are collected and identified.
- **Downtime loop:** When no data-load phase (`rss_processing`, `article_processing`, `entity_extraction`) has run in the last 5 minutes, a background loop keeps calling `run_cycle()` every 45s to clean up and generate relationship vectors between entities until the next data load.

---

## References

- Entity resolution: `api/services/entity_resolution_service.py`, `docs/RAG_ENHANCEMENT_ROADMAP.md`
- Cleanup (merge, prune, cap): `api/services/intelligence_cleanup_controller.py`, `docs/OPTIMIZATION_STRATEGIES_ASSESSMENT.md`
- Profile merge API: `api/domains/intelligence_hub/routes/context_centric.py` (`merge_entity_profiles`), `web/src/services/api/contextCentric.ts` (`mergeEntityProfiles`)
- Storyline key entities: `api/services/storyline_automation_service.py` (e.g. `_collect_entity_and_keyword_strings`), `story_entity_index` / `key_entities`
- Event key participants: `key_participant_entity_ids` on `tracked_events`; `api/services/event_tracking_service.py`, `cross_domain_service.py`
- Orchestration: `api/services/automation_manager.py` (phases, `data_cleanup`, `entity_profile_sync`), `api/services/enhancement_orchestrator_service.py`
