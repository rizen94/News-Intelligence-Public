# v6 Quality-First Upgrade — Targeted To-Do List

> **Purpose:** Actionable checklist ordered by practicality and impact. Completing Tier 1 first compounds progress for Tier 2–3.  
> **Reference:** [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) | [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md)

---

## Tier 1 — Foundation (do first)

### T1.1 Event tracking framework
- [ ] Add migration: `intelligence.tracked_events` (event_type, event_name, start_date, end_date, geographic_scope, key_participant_entity_ids, milestones, sub_event_ids).
- [ ] Add migration: `intelligence.event_chronicles` (event_id, update_date, developments, analysis, predictions, momentum_score).
- [ ] Create `api/domains/intelligence/routes/tracked_events.py` (or under system_monitoring): GET list, GET by id, POST create, PUT update; paths snake_case, prefix `/api/...`.
- [ ] Add minimal UI: list tracked events, create/edit one event (name, type, dates, scope).
- [ ] Document in DOMAIN_6 or intelligence hub doc.

### T1.2 Entity resolution enhancements
- [ ] Extend `entity_canonical` usage: ensure aliases and alternate names are populated from article_entities; add disambiguation step (same person, name variations) in entity extraction or a dedicated resolution job.
- [ ] Cross-domain entity linking: service that inserts/updates `intelligence.entity_relationships` from article_entities + entity_canonical across domains; call from pipeline or orchestrator.
- [ ] Add API or internal method: resolve_entity(domain, name, type) → canonical_entity_id or candidate list.
- [ ] Optional: UI to view/link entities across domains.

### T1.3 Entity dossier schema + basic compilation
- [ ] Add migration: `intelligence.entity_dossiers` (domain_key, entity_id, compilation_date, chronicle_data, relationships, positions, patterns, metadata).
- [ ] Add migration: `intelligence.entity_positions` (domain_key, entity_id, topic, position, confidence, evidence_refs, date_range).
- [ ] Implement DossierCompiler or extend existing service: given (domain_key, entity_id), build chronicle from articles/storylines mentioning that entity; write to entity_dossiers.chronicle_data and optionally entity_positions.
- [ ] API: GET dossier for entity (e.g. `GET /api/intelligence/entity_dossiers?domain_key=politics&entity_id=123`).
- [ ] Optional: trigger compilation from orchestrator or pipeline after T2.3.

---

## Tier 2 — Depth

### T2.1 Event chronicle builder
- [ ] Service: for each tracked_event, gather developments from storylines/chronological_events; compute momentum_score; write event_chronicles row.
- [ ] Schedule: run weekly or on_change (orchestrator or cron); config in quality_first_governance or orchestrator_governance.
- [ ] API: GET chronicles for event; POST to trigger update.

### T2.2 Dossier intelligence layer
- [ ] Position tracker: extract voting records, policy positions, public statements into entity_positions (evidence_refs → article_ids).
- [ ] Relationship web: populate entity_dossiers.relationships from intelligence.entity_relationships; optional UI.
- [ ] Pattern/controversy: store in entity_dossiers.patterns JSONB; feed from patterns or manual review.

### T2.3 Governance/orchestrator cycle alignment
- [ ] Add or extend config: `orchestrator_cycle` (duration_minutes, phases), `processing_priorities`, `entity_tracking`, `event_tracking`, `quality_thresholds` — all keys snake_case.
- [ ] Wire OrchestratorCoordinator (or ProcessingGovernor) to run assessment → prioritization → deep_processing → quality_review → synthesis; prioritization uses watchlist + active_events.
- [ ] Document cycle and config in CONTROLLER_ARCHITECTURE or ORCHESTRATOR_ROADMAP_TO_INITIATIVE.

---

## Tier 3 — Documents and narrative

### T3.1 Document acquisition pipeline
- [ ] Add migration: `intelligence.processed_documents` (and optionally document_intelligence) per V6_QUALITY_FIRST_UPGRADE_PLAN.
- [ ] Config: document_sources (source_priorities, document_types).
- [ ] Service: fetch/crawl metadata + URL from configured sources; insert into processed_documents.

### T3.2 Document processing engine
- [ ] PDF parsing (GPU if available); section extraction; key findings; entity/topic tagging.
- [ ] Populate processed_documents extracted_sections, key_findings, entities_mentioned, citations.
- [ ] Link documents to storylines/entities (document_intelligence or equivalent).

### T3.3 Narrative construction
- [ ] Thread detection: causal chains, timeline reconciliation; use narrative_threads + storylines.
- [ ] Synthesis engine: multi-source integration, conflict resolution, uncertainty quantification.
- [ ] Quality checks: fact verification, completeness scorer; optional bias detection.

---

## Style checklist (every task)

- [ ] File names: `snake_case`.
- [ ] Tables/columns: `snake_case`.
- [ ] Variables/functions: `snake_case`; classes: `PascalCase`.
- [ ] Config keys: `snake_case`.
- [ ] API paths: flat `/api/...`, segments `snake_case`.
- [ ] Reuse: extend existing entity_canonical, article_entities, intelligence.*, storylines, chronological_events before adding new systems.

---

*Update this file as items are completed; move completed items to an “Done” section if desired.*
