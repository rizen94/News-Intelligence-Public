# Context-Centric Upgrade Plan

**Version:** 1.0  
**Last updated:** 2026-03-21  
**Status:** Active (Phase 2 and 3 complete; Phase 4 frontend in progress — entity profiles, context browser, event dashboard, pipeline status added.)  
**Recovery:** See [Recovery & verification](#recovery--verification) below if the project was interrupted (e.g. crash) and you need to re-verify state.  
**Source:** Adapted from [CONTEXT_CENTRIC_TRANSITION_PLAN_ORIGINAL.md](_archive/CONTEXT_CENTRIC_TRANSITION_PLAN_ORIGINAL.md) to align with [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) and current project plans.

---

## Overview

This plan transitions the News Intelligence system to a **context-centric model**: content is stored and queried as **contexts** (universal content units) with **entity-centric mapping** and **living entity profiles**. The upgrade is designed to:

- **Prioritize context-centric design** — All new storage and pipelines treat “context” as the primary unit; articles become one source type feeding contexts.
- **Prioritize entity mapping** — Entity disambiguation, profiles, relationships, and old→new entity mapping are first-class; existing [ARTICLE_ENTITY_SCHEMA_DESIGN.md](ARTICLE_ENTITY_SCHEMA_DESIGN.md) and [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) entity work (e.g. `entity_canonical`, `article_entities`, event tracking) are extended, not replaced.

**Reuse before create:** Extend existing `article_entities`, `entity_canonical`, `intelligence.entity_relationships`, `chronological_events`, and v6 `tracked_events` / `entity_dossiers` rather than duplicating. See [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) and [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) for naming and schema conventions.

**Naming (aligned with project):** snake_case for tables, columns, files, config keys; PascalCase for classes; flat `/api/...` paths. Example tables: `contexts`, `entity_profiles`, `entity_relationships`, `extracted_claims`, `article_to_context`, `old_entity_to_new`.

---

## 1. Phase 1: Foundation layer (Week 1–2)

Build context infrastructure **without breaking** the current system. Entity mapping and bridging from current entities to enhanced profiles are core.

### 1.1 Database schema evolution

- Add **new tables alongside existing** (no migration of old data yet):
  - `contexts` — universal content storage (one row per “content unit”; articles, PDF sections, etc. can map in).
  - `entity_profiles` — living documents per canonical entity (extend or align with v6 `entity_dossiers`; see [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md)).
  - `entity_relationships` — graph connections (reuse/extend `intelligence.entity_relationships`).
  - `extracted_claims` — atomic facts (subject/predicate/object, confidence, source).
  - `pattern_discoveries` — detected patterns (behavioral, temporal, network, event).
- **Mapping tables (entity mapping focus):**
  - `article_to_context` — links existing `articles` to new `contexts` (one-to-one or one-to-many as needed).
  - `old_entity_to_new` — maps current entity identifiers (e.g. `article_entities.id`, `entity_canonical.id`) to enhanced `entity_profiles` so we never lose lineage.

**Schema location:** Prefer `intelligence` schema for new tables; per-domain tables stay in domain schemas per [ARTICLE_ENTITY_SCHEMA_DESIGN.md](ARTICLE_ENTITY_SCHEMA_DESIGN.md).

### 1.2 Context extraction pipeline

- **Parallel processing path:** ✅ Implemented
  - Current article processor unchanged (writes to `articles`, `article_entities`, etc.).
  - **Context processor** (`api/services/context_processor_service.py`):
    - `ensure_context_for_article(domain_key, article_id)` — creates `intelligence.contexts` + `article_to_context` for one article; called from RSS collector after each new article insert.
    - `sync_domain_articles_to_contexts(domain_key, limit)` — backfill: creates contexts for domain articles that don’t have one; called by AutomationManager `context_sync` task (every 20 min).
  - Both paths run; no removal of existing pipelines.
- **Universal extractors (plugin-style):**
  - Start with **enhanced article extractor** (builds on current entity extractor; adds confidence, context snippet).
  - Add **PDF extractor** for documents (sections → contexts).
  - Add **structured data extractor** (JSON, CSV) for future sources.
  - Use a small plugin interface so new source types can be added without rewriting the pipeline (see [DATA_INGESTION_PIPELINE_ASSESSMENT.md](DATA_INGESTION_PIPELINE_ASSESSMENT.md) for current ingestion ownership).

### 1.3 Entity evolution system (entity mapping priority)

- **Entity profile sync (implemented):** `entity_profile_sync_service.sync_domain_entity_profiles(domain_key)` ensures every `entity_canonical` has a row in `intelligence.entity_profiles` and `old_entity_to_new`; AutomationManager runs `entity_profile_sync` every 6h. Migration 145 adds `context_entity_mentions`; when a context is created from an article, `link_context_to_article_entities()` links it to entity_profiles via `article_entities.canonical_entity_id` → `old_entity_to_new` (from `ensure_context_for_article` and `sync_domain_articles_to_contexts`). Run migration: `api/scripts/run_migration_145.py`.
- **Enhanced entity recognition (future):**
  - Move from simple keyword matching to **contextual understanding** (reuse/extend existing entity extractor and `entity_canonical`).
  - **Entity disambiguation** — e.g. “John Smith” (politician) vs “John Smith” (CEO); store disambiguation signals and link to `entity_profiles`.
  - **Entity merger** — when two entities are determined to be the same, merge into one profile and update `old_entity_to_new` and relationship graph.
  - **Confidence scoring** on all entity identifications (store in `article_entities` and/or context-level entity mentions).
- **Entity profile builder:** Implemented — `entity_profile_builder_service.py`: builds Wikipedia-style sections and relationships_summary from contexts (via context_entity_mentions); AutomationManager `entity_profile_build` every 6h.
  - Generate Wikipedia-style sections from contexts (summaries, positions, relationships).
  - Track **entity evolution over time** (timeline of changes to the profile).
  - Build **relationship graphs** between entities (using `entity_relationships`).
  - “Living document” update system — profiles update as new contexts are processed; incremental updates preferred (see [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) for orchestrator-driven processing).

---

## 2. Phase 2: Intelligence layer (Week 3–4)

Add claim extraction, pattern recognition, and event tracking **without removing** current features. Entity-centric views and relationship data feed into these.

### 2.1 Claim extraction and tracking

- **Claim extractor:** ✅ Implemented — `api/services/claim_extraction_service.py`: `extract_claims_for_context(context_id)` fetches context text, calls LLM for subject/predicate/object triples, inserts into `intelligence.extracted_claims`. `run_claim_extraction_batch(limit)` processes contexts with no claims yet. AutomationManager runs `claim_extraction` task every 40 minutes (batch of 30 contexts).
- **Temporal awareness:** When the claim was true (valid_from / valid_to or equivalent) — columns exist; population is future.
- **Contradiction detection:** Compare claims across contexts; flag contradictions and corroborations (stored in DB or derived at query time) — future.

### 2.2 Pattern recognition engine

- **Pattern detectors:** Implemented — `api/services/pattern_recognition_service.py`: **network** (entity profiles co-mentioned in same context), **temporal** (context density by day), **behavioral** (entity + source_type frequency), **event** (tracked_events sharing participants). Results persisted to `intelligence.pattern_discoveries`. AutomationManager runs `pattern_recognition` every 2 hours (gated by `context_centric.yaml`). API: `GET /api/pattern_discoveries` (filters: pattern_type, domain_key).

### 2.3 Event tracking framework

- **Event tracking:** ✅ Implemented — `api/services/event_tracking_service.py`: from context content, LLM extracts event mentions (event_type, event_name, date, location, key_actors); **tracked_events** upserted (with `key_participant_entity_ids` = entity_profile ids resolved from actor names); **event_chronicles** entries added per context. `run_event_tracking_batch(limit)` processes recent contexts. AutomationManager runs `event_tracking` every 1 hour.
- **Participant tracking:** Participant names resolved to `entity_profiles` via `metadata->>'canonical_name'` in same domain.
- **Milestone / momentum:** Columns exist on `event_chronicles`; population is future. Reuse of `chronological_events` / storyline events can be added later.

---

## 3. Phase 3: Dual-mode operation (Week 5)

Run **both** current and context-centric systems in parallel. Entity mapping and data integrity are critical.

### 3.1 Data synchronization

- **Sync services:** Copy current articles into context system (create `contexts` rows and `article_to_context`); **map current entities to enhanced profiles** (`old_entity_to_new`). Implemented via context_sync and entity_profile_sync tasks.
- **Backwards compatibility layer:** Read-only context-centric APIs added under Intelligence Hub: `GET /api/entity_profiles`, `GET /api/entity_profiles/{id}`, `GET /api/contexts`, `GET /api/tracked_events`, `GET /api/tracked_events/{id}`, `GET /api/claims`. See `api/domains/intelligence_hub/routes/context_centric.py`. Article/entity APIs unchanged; dual-mode until Phase 5.
- **No data loss:** All migrations and syncs must be reversible or at least auditable; keep backups of original system.

### 3.2 Quality validation

- **Comparison tools:** Implemented — `GET /api/context_centric/quality` returns per-domain counts: articles, article_entities, entity_canonical, contexts, article_to_context_links, entity_profiles, context_entity_mentions; and **entity_coverage_pct** (entity_profiles / entity_canonical), **context_coverage_pct** (article_to_context / articles). Use to validate context system coverage vs old entity extraction.
- **Performance and correctness:** Status and quality endpoints support monitoring; full metrics (see Success metrics) can be added later.

### 3.3 Gradual migration

- **Feature flags:** Implemented — `api/config/context_centric.yaml` and `config/context_centric_config.py`. Task flags: `context_sync`, `entity_profile_sync`, `claim_extraction`, `event_tracking`, `entity_profile_build`, `pattern_recognition`. Set any to `false` to disable that task (fallback to old system for that part). AutomationManager checks flags before running each context-centric task.
- **Fallback:** Old system (article/entity APIs) remains available; no removal until Phase 5.
- **Subset of sources:** Optional `pipeline_fraction` in config (documented, not yet enforced) for future use.

---

## 4. Phase 4: Frontend evolution (Week 6–7)

Transform UX while keeping familiar workflows. **Entity-centric** and **context-centric** views are priorities.

### 4.1 Entity profile pages

- **Profile view:** ✅ Implemented — Wikipedia-style layout with sections, relationships summary, metadata; list page with domain filter at `/:domain/intelligence/entity-profiles`, detail at `/:domain/intelligence/entity-profiles/:id`. Frontend: `web/src/pages/Intelligence/EntityProfiles.tsx`, `EntityProfileDetail.tsx`; API client: `web/src/services/api/contextCentric.ts`.
- **Future:** Timeline of entity evolution; relationship network visualization; pattern and prediction display; source diversity indicators. Reuse or extend existing entity/storyline UI; see [DOMAIN_3_STORYLINE_MANAGEMENT.md](DOMAIN_3_STORYLINE_MANAGEMENT.md) and [STORYLINE_AUTOMATION_GUIDE.md](STORYLINE_AUTOMATION_GUIDE.md).

### 4.2 Entity management interface

- **Control panel:** ✅ Implemented — Entity importance (high/medium/low) stored in profile metadata; **merge** tool (source profile merged into target; same domain; `old_entity_to_new` and `context_entity_mentions` redirected; source marked merged for audit). Frontend: `EntityManagement.tsx` at `/:domain/intelligence/entity-management`; API: `PATCH /api/entity_profiles/{id}`, `POST /api/entity_profiles/{id}/merge` (body: `source_profile_id`). Entity type and alert_thresholds can be added to PATCH body and metadata; split is future.
- API: flat `/api/...` routes (snake_case path segments).

### 4.3 Context browser

- **Context list:** ✅ Implemented — list at `/:domain/intelligence/contexts` with domain and source_type filters; `ContextBrowser.tsx` uses `GET /api/contexts`. Article-based views unchanged (dual-mode).
- **Future:** Filter by date, entities mentioned; extraction confidence; claim extraction display; contradictions/corroborations; group related contexts.

### 4.4 Event dashboards

- **Event list and detail:** ✅ Implemented — list at `/:domain/intelligence/tracked-events` (optional event_type filter), detail with chronicles at `/:domain/intelligence/tracked-events/:id`; `TrackedEvents.tsx`, `TrackedEventDetail.tsx`. Pipeline status/quality at `/:domain/intelligence/context-centric-status` (`ContextCentricStatus.tsx`).
- **Future:** Event timeline with milestones; participant activity linked to entity profiles; pattern recognition results; prediction vs actual; historical parallels. Align with v6 event tracking and [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md).

### 4.5 Advanced search

- **Intelligence search:** ✅ Implemented — `GET /api/context_centric/search` with params: `q` (full-text on claims + contexts), `claim_subject`, `claim_predicate`, `entity_id` (profile ID), `pattern_type`, `valid_from`/`valid_to` (temporal), `domain_key`, `limit`, `offset`. Returns `claims`, `contexts`, `pattern_discoveries`. Frontend: `IntelligenceSearch.tsx` at `/:domain/intelligence/search` with form and result tabs.
- **Future:** By entity relationships (e.g. search by relationship type); richer temporal (“what did we know when”) UI.

---

## 5. Phase 5: Deprecation (Week 8)

Remove old pathways only after full migration and validation. **Archive, don’t delete** old tables initially.

### 5.1 Data migration completion

- Migrate all historical data to context model; convert article references to contexts; update entity references to enhanced profiles; **archive old tables** (rename or move to archive schema; do not drop until stable).

### 5.2 Code cleanup

- Remove article-only processors that have been replaced by context processor; remove redundant entity extraction code; deprecate outdated API endpoints; **update all documentation** (DOCS_INDEX, domain docs, API_REFERENCE).

### 5.3 Performance optimization

- Caching for entity profiles; optimize context search queries; materialized views for common patterns; **incremental profile updates** to avoid full recompute.

---

## 6. Critical success factors

- **Data integrity:** No information loss; audit trail of changes; backups; thorough validation of migrations.
- **User experience:** Familiar workflows kept; new features introduced gradually; clear docs and visible benefits.
- **System reliability:** Parallel systems until confident; monitoring; rollback procedures; edge-case testing.
- **Entity mapping:** Continuous care for `old_entity_to_new` and relationship consistency so that entity-centric features (profiles, search, UI) stay correct.

---

## 7. Risk mitigation

- **Technical:** Performance — monitor and optimize early; data loss — backups and validation; integration — testing and gradual rollout; complexity — focus on core value (context + entity mapping).
- **User:** Confusion — docs and gradual change; feature loss — parity before removal; learning curve — intuitive design and help.

---

## 8. Rollout strategy

| Week   | Mode        | Approach |
|--------|-------------|----------|
| 1–2    | Shadow      | New system processes data but does not affect production; compare results; tune algorithms. |
| 3–4    | Hybrid      | Some features use new system; opt-in to new interfaces; gather feedback. |
| 5–6    | Primary     | New system default; old system fallback; monitor. |
| 7–8    | Full migration | Complete transition; deprecate old code; optimize. |

---

## 9. Success metrics

- **Quality:** Entity recognition accuracy (target >95%); relationship detection improvement (e.g. 2× current); pattern detection rate; claim extraction precision.
- **Performance:** Processing time per context (<2s); profile generation (<5s); search response (<500ms); frontend load (<2s).
- **User:** Feature adoption; satisfaction; time to find information (target −50%); actionable insights.

---

## 10. Migration readiness (before relying on collection)

See **[CONTEXT_CENTRIC_MIGRATION_READINESS.md](CONTEXT_CENTRIC_MIGRATION_READINESS.md)** for: context-centric as primary path, what is incorporated vs dual-mode, and a pre-collection checklist. Entity extraction is incorporated (feeds entity_profiles and context_entity_mentions); entity_profile_sync runs a backfill of context_entity_mentions after each sync.

---

## 11. Recovery & verification

Use this checklist after an interruption (e.g. Cursor crash, partial edit) to confirm context-centric work is intact.

1. **Imports (no DB):** From project root with venv active:
   - `PYTHONPATH=api .venv/bin/python api/tests/test_context_centric_imports.py`
   - Expect: `PASS: context-centric imports` and `PASS: context-centric routes registered`.
2. **Migrations:** Ensure `intelligence` schema and context-centric tables exist. Run in order if needed:
   - `api/scripts/run_migration_140_141.py` (orchestration + intelligence schema)
   - `api/scripts/run_migration_142_143_144.py` (contexts, entity_profiles, claims, tracked_events, pattern_discoveries, etc.)
   - `api/scripts/run_migration_145.py` (context_entity_mentions)
   - `api/scripts/run_migration_146.py` (system_alerts columns for health monitor: alert_type, description, updated_at, is_active, alert_data)
3. **Config:** `api/config/context_centric.yaml` exists; task flags control AutomationManager (context_sync, entity_profile_sync, claim_extraction, event_tracking, entity_profile_build, pattern_recognition).
4. **API:** With API running, hit:
   - `GET /api/context_centric/status` — counts for contexts, entity_profiles, claims, tracked_events, etc.
   - `GET /api/context_centric/quality` — per-domain coverage (articles vs article_to_context, entity_canonical vs entity_profiles).
5. **Integration:** RSS collector calls `ensure_context_for_article(domain_key, article_id)` after new article insert; AutomationManager runs context_sync, entity_profile_sync, claim_extraction, event_tracking, entity_profile_build, pattern_recognition on schedule (see Phase 3.3).

If any step fails, fix that layer (imports → migrations → config → API → integration) before moving on.

---

## 12. References

| Document | Purpose |
|----------|---------|
| [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) | Naming, reuse-before-create, consolidation |
| [ARTICLE_ENTITY_SCHEMA_DESIGN.md](ARTICLE_ENTITY_SCHEMA_DESIGN.md) | Current entity and article schema |
| [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) | Event tracking, entity dossiers, v6 tiers |
| [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md) | Orchestrators and control flow |
| [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) | Single loop, initiative, user guidance |
| [DATA_INGESTION_PIPELINE_ASSESSMENT.md](DATA_INGESTION_PIPELINE_ASSESSMENT.md) | Who triggers collection and processing |
| [DOCS_INDEX.md](DOCS_INDEX.md) | Documentation index |
