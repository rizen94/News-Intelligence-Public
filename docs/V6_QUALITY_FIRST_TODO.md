# v6 Quality-First Upgrade — Targeted To-Do List

> **Purpose:** Actionable checklist ordered by practicality and impact. Completing Tier 1 first compounds progress for Tier 2–3.  
> **Reference:** [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) | [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md)

---

## Tier 1 — Foundation (do first)

### T1.1 Event tracking framework ✅ Phase 1 done
- [x] Add migration: `intelligence.tracked_events` and `event_chronicles` — **Migration 144** (and 156 for domain_keys).
- [x] API: GET list, GET by id, **POST create**, **PUT update** in `api/domains/intelligence_hub/routes/context_centric.py` — paths `/api/tracked_events`, `/api/tracked_events/{event_id}`.
- [x] Minimal UI: Investigate page — list events, **Create event** button + dialog; Event detail — **Edit event** button + dialog (name, type, dates, scope, domain_keys).
- [x] Documented in DOMAIN_6 and below.

### T1.2 Entity resolution enhancements
- [ ] Extend `entity_canonical` usage: ensure aliases and alternate names are populated from article_entities; add disambiguation step (same person, name variations) in entity extraction or a dedicated resolution job.
- [ ] Cross-domain entity linking: service that inserts/updates `intelligence.entity_relationships` from article_entities + entity_canonical across domains; call from pipeline or orchestrator.
- [ ] Add API or internal method: resolve_entity(domain, name, type) → canonical_entity_id or candidate list.
- [ ] Optional: UI to view/link entities across domains.

### T1.3 Entity dossier schema + basic compilation ✅ Phase 1 done
- [x] Migrations: **Migration 144** — `intelligence.entity_dossiers`, `entity_positions`.
- [x] **DossierCompiler**: `api/services/dossier_compiler_service.py` — given (domain_key, entity_id), builds chronicle from article_entities + articles and storylines; upserts entity_dossiers.
- [x] API: **GET** `/api/entity_dossiers?domain_key=&entity_id=`; **POST** `/api/entity_dossiers/compile` with body `{ domain_key, entity_id }`.
- [ ] Optional: trigger compilation from orchestrator or pipeline after T2.3.

---

## Tier 2 — Depth ✅ Phase 2 done

### T2.1 Event chronicle builder ✅
- [x] Service: `api/services/event_chronicle_builder_service.py` — for each tracked_event, gather developments from storylines; compute momentum_score; write event_chronicles row.
- [x] Schedule: OrchestratorCoordinator runs chronicle updates when `event_tracking.update_interval_seconds` elapsed; config in `orchestrator_governance.yaml` (`event_tracking.enabled`, `update_interval_seconds`, `max_events_per_cycle`).
- [x] API: **POST** `/api/tracked_events/{event_id}/chronicles/update` to trigger update; chronicles also returned in GET event by id.

### T2.2 Dossier intelligence layer ✅
- [ ] Position tracker: extract voting records, policy positions into entity_positions (stub for later).
- [x] Relationship web: entity_dossiers.relationships populated from `intelligence.entity_relationships` (source/target domain + entity_id, relationship_type, confidence); storyline_refs kept in metadata.
- [ ] Pattern/controversy: entity_dossiers.patterns left as `{}` for now; can feed from pattern_discoveries later.

### T2.3 Governance/orchestrator cycle alignment ✅
- [x] Config: `orchestrator_governance.yaml` — `orchestrator.cycle_phases`, `event_tracking`, `entity_tracking`, `quality_thresholds` (snake_case).
- [x] OrchestratorCoordinator: when event_tracking enabled and interval due, runs `_run_scheduled_chronicle_updates` for up to max_events_per_cycle; state key `last_event_chronicle_update`.
- [ ] Document cycle in CONTROLLER_ARCHITECTURE or ORCHESTRATOR_ROADMAP (optional follow-up).

---

## Tier 3 — Documents and narrative ✅ Phase 3 done

### T3.1 Document acquisition pipeline ✅
- [x] Migration **160**: `intelligence.processed_documents`, `intelligence.document_intelligence` (V6_QUALITY_FIRST_UPGRADE_PLAN 4.4).
- [x] Config: `document_sources` in `orchestrator_governance.yaml` (source_priorities, document_types, ingest_urls).
- [x] Service: `api/services/document_acquisition_service.py` — `create_document()`, `ingest_from_config()` (metadata + URL from ingest_urls or API).
- [x] API: **GET** `/api/processed_documents`, **GET** `/api/processed_documents/{id}`, **POST** `/api/processed_documents`, **POST** `/api/processed_documents/ingest_from_config`.

### T3.2 Document processing engine ✅ (stub)
- [ ] PDF parsing (GPU): deferred; full pipeline later.
- [x] Stub: `api/services/document_processing_service.py` — `process_document()` can set extracted_sections, key_findings, entities_mentioned (placeholder); upserts document_intelligence with storyline_connections.
- [x] API: **POST** `/api/processed_documents/{document_id}/process` (body: storyline_connections, optional extracted_sections/key_findings/entities_mentioned).

### T3.3 Narrative construction ✅ (stub)
- [x] Thread detection: `api/services/narrative_thread_service.py` — `ensure_narrative_thread()`, `build_threads_for_domain()`; populate narrative_threads from storylines (summary, linked_article_ids).
- [x] Synthesis stub: `synthesize_threads(domain_key, thread_ids)` returns concatenated summary placeholder; full conflict resolution/uncertainty later.
- [ ] Quality checks: fact verification, completeness scorer (optional follow-up).
- [x] API: **GET** `/api/narrative_threads`, **POST** `/api/narrative_threads/build`, **POST** `/api/narrative_threads/synthesize`.

---

## Phase 4 — Polish, integration, and frontend ✅

- [x] **Migrations 155–160** applied via `api/scripts/run_migrations_155_to_160.py`.
- [x] **Frontend: Processed documents** — List page at `/:domain/investigate/documents`; API client in `contextCentric.ts`.
- [x] **Frontend: Narrative threads** — Phase 5 (see below).
- [ ] T1.2 entity resolution enhancements (disambiguation, cross-domain linking) when prioritized.

---

## Phase 5 — Orchestrator triggers and narrative UI ✅

- [x] **Dossier compile trigger:** When `entity_tracking.enabled` and `dossier_compile_interval_seconds` elapsed, OrchestratorCoordinator runs `_run_scheduled_dossier_compiles(max_dossiers_per_cycle)`; selects entity_profiles with no or stale dossier (7 days); state key `last_dossier_compile_run`. Config: `entity_tracking.dossier_compile_interval_seconds`, `max_dossiers_per_cycle`.
- [x] **Narrative threads UI:** Page at `/:domain/investigate/narrative-threads` — list threads, “Build for domain”, “Synthesize”; button on Investigate page.
- [x] **Documentation:** CONTROLLER_ARCHITECTURE.md §2.4.1 — orchestrator cycle (phases, event chronicle updates, dossier compilation), references to V6 TODO and DOMAIN_4.

---

## Style checklist (every task)

- [ ] File names: `snake_case`.
- [ ] Tables/columns: `snake_case`.
- [ ] Variables/functions: `snake_case`; classes: `PascalCase`.
- [ ] Config keys: `snake_case`.
- [ ] API paths: flat `/api/...`, segments `snake_case`.
- [ ] Reuse: extend existing entity_canonical, article_entities, intelligence.*, storylines, chronological_events before adding new systems.

---


---

## Architectural Audit — Completed 2026-03-06

Full code audit against intelligence-first principles. See [CODE_AUDIT_REPORT.md](CODE_AUDIT_REPORT.md) for details.

- [x] 34 violations identified (10 Critical, 12 High, 12 Medium) — all remediated.
- [x] Intelligence cascade wired: ml_data/content/entities flow through pipeline phases.
- [x] Editorial documents seeded from automation phases when empty.
- [x] Briefing generation uses editorial-first ordering (ledes → headlines → storylines → events → metrics).
- [x] LLM generate_briefing_lead method added for narrative-quality leads.
- [x] API endpoints return editorial_document/editorial_briefing fields.
- [x] RAG analysis writes back to editorial_document.
- [x] RSS collector captures full content:encoded body.
- [x] Storyline tracker uses article content + ml_data for topic analysis.
- [x] Entity extraction stores contextual excerpts.
- [x] Digest generation pulls editorial ledes into story_suggestions.
- [x] Article list endpoints return content excerpts (800 chars).
- [x] Analysis endpoints include narrative explanations alongside scores.

Remaining:
- [ ] Centralized content synthesis service (aggregate all intelligence phases into unified context).
- [ ] T1.2 entity resolution enhancements (disambiguation, cross-domain linking).

*Update this file as items are completed; move completed items to an “Done” section if desired.*
