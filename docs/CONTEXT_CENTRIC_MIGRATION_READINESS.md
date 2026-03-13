# Context-Centric Migration Readiness

**Purpose:** Confirm the system is fully migrated to the context-centric model before relying on collection: either old code is disengaged or incorporated into the new model.  
**See also:** [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md).

---

## 1. Context-centric as primary path

- **Ingestion:** Every new article (RSS collector) creates a **context** and **article_to_context** via `ensure_context_for_article()` immediately after insert. No article-only path; context is the primary content unit.
- **Entity flow (incorporated):** Article-level entity extraction (topic queue worker → `ArticleEntityExtractionService`) still runs and writes to `article_entities` and `entity_canonical`. That is **incorporated**, not removed: it feeds `entity_profile_sync` → `entity_profiles` + `old_entity_to_new`. After each entity_profile_sync, **context_entity_mentions** is backfilled via `backfill_context_entity_mentions_for_domain()` so contexts are linked to entity profiles once entities exist.
- **Intelligence layer:** All downstream processing is context-centric: claim extraction, event tracking, entity profile build, and pattern recognition run on **contexts** and write to `intelligence.*` tables. AutomationManager tasks are gated by `context_centric.yaml` task flags.

---

## 2. What is incorporated (old code feeding context-centric)

| Component | Role | Status |
|-----------|------|--------|
| **Article entity extraction** | Populates `article_entities`, `entity_canonical` per article | Kept; feeds entity_profiles and context_entity_mentions |
| **Topic extraction queue** | Triggers entity extraction + topic extraction for queued articles | Kept; entity extraction is required for context_entity_mentions |
| **entity_profile_sync** | Maps entity_canonical → entity_profiles, old_entity_to_new | Context-centric; after sync runs backfill of context_entity_mentions |
| **context_sync** | Backfills contexts for articles without one | Context-centric |
| **Storyline / article APIs** | Article-based views and storylines | Dual-mode (Phase 3); remain until Phase 5 deprecation |

---

## 3. What is context-centric only (no legacy duplicate)

- **Context creation:** `ensure_context_for_article()` and `sync_domain_articles_to_contexts()`.
- **Context → entity links:** `link_context_to_article_entities()` (at context creation and in backfill after entity_profile_sync).
- **Claims, events, profiles, patterns:** `claim_extraction_service`, `event_tracking_service`, `entity_profile_builder_service`, `pattern_recognition_service` — all read/write intelligence schema from contexts.

---

## 4. What is not yet removed (intentional dual-mode)

- **Article/domain APIs:** Article list, detail, storylines, topic queues — still read from domain articles/topics. No removal until Phase 5.
- **AutomationManager “legacy” tasks:** e.g. `rss_processing`, `article_processing`, `ml_processing`, `entity_extraction`, `topic_clustering`, `storyline_processing`, etc. Some are still used (e.g. RSS, entity extraction via topic queue); others may be redundant with context-centric and are candidates for Phase 5 cleanup. See [ORCHESTRATOR_BEHAVIORS_AND_PLAN_GAP.md](ORCHESTRATOR_BEHAVIORS_AND_PLAN_GAP.md).

---

## 5. Pre-collection checklist

Before relying on collection as the main data source, verify:

1. **Migrations applied (in order):**
   - `api/scripts/run_migration_140_141.py`
   - `api/scripts/run_migration_142_143_144.py`
   - `api/scripts/run_migration_145.py`

2. **Config:** `api/config/context_centric.yaml` exists; all context-centric tasks enabled (or intentionally disabled for testing).

3. **Integration:**
   - RSS collector calls `ensure_context_for_article(domain_key, article_id)` after each new article insert.
   - Entity profile sync calls `backfill_context_entity_mentions_for_domain(domain_key)` after syncing so context_entity_mentions stays in sync with article_entities.

4. **Verification (no DB):**  
   `PYTHONPATH=api .venv/bin/python api/tests/test_context_centric_imports.py` → PASS.

5. **API (with API running):**
   - `GET /api/context_centric/status` — returns counts.
   - `GET /api/context_centric/quality` — per-domain coverage (context_coverage_pct, entity_coverage_pct).

---

## 6. Summary

- **Fully migrated** in the sense that (1) every new article gets a context at ingest, (2) entity extraction is incorporated as the feeder for entity_profiles and context_entity_mentions, (3) all intelligence features (claims, events, profiles, patterns) run on contexts only.
- **Fully disengaged** only for the intelligence pipeline (no duplicate context vs article pipeline for claims/events/profiles/patterns).
- **Old code retained by design:** article APIs, topic queue, entity extraction, and storyline logic stay until Phase 5; they either feed context-centric (entity extraction) or remain as dual-mode read paths.

Once the checklist above is satisfied, triggering collection (RSS, finance, etc.) is safe and will feed the context-centric model end-to-end.
