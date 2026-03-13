# v6 Quality-First Upgrade Plan (Adapted)

> **Source:** Governance Controller Development Plan — Quality-First Intelligence System (Untitled document 10).  
> **Adapted to:** [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) — snake_case (files, functions, variables, tables, columns, config keys), PascalCase (classes), flat `/api`, reuse-before-create.  
> **Purpose:** Prioritized, practical to-do list so early work compounds progress.  
> **Related:** [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md) — broader context-centric model (contexts, entity mapping, living profiles, claims, patterns); entity work here aligns with that plan.

---

## 1. Core philosophy (unchanged)

**"Deep understanding over quick reactions"** — Comprehensive analysis, historical context, and narrative coherence over speed. Investigative journalism, not breaking news.

---

## 2. Naming and style (adapted)

| Original / generic       | Our standard |
|--------------------------|--------------|
| camelCase variables      | `snake_case` |
| PascalCase tables/columns| `snake_case` (tables and columns) |
| Class names              | `PascalCase` (e.g. `EntityDossierService`) |
| Config keys              | `snake_case` (e.g. `entity_tracking`, `tracking_depth`) |
| API paths                | Flat `/api/...`, no version segment; path segments `snake_case` |
| File names               | `snake_case` (e.g. `entity_dossier_service.py`) |
| YAML keys                | `snake_case` (e.g. `governance_cycle` → `orchestrator_cycle`) |

**Reuse before create:** Extend existing `entity_canonical` / `article_entities` (per domain), `intelligence.entity_relationships`, `intelligence.narrative_threads`, `orchestration.investigations`, and storyline/chronological_events rather than duplicating.

---

## 3. Prioritized to-do list (practicality × impact)

Order chosen so **early items unblock later ones** and deliver visible value quickly.

### Tier 1 — Foundation (do first)

| # | Task | Rationale | Existing hooks |
|---|------|------------|----------------|
| **T1.1** | **Event tracking framework** — Add `tracked_events` and `event_chronicles` tables; event definition (type, name, dates, scope, key_participants, milestones); minimal UI to create/edit one tracked event. | Reuses storylines + chronological_events; delivers “2026 midterms” use case quickly; low new surface area. | `chronological_events`, storylines, domains |
| **T1.2** | **Entity resolution enhancements** — Disambiguation (same person, name variations); alias/alternate name tracking in `entity_canonical`; cross-domain entity linking using `intelligence.entity_relationships`. | Foundation for dossiers; we already have `entity_canonical.aliases` and article_entities; extend, don’t replace. | `entity_canonical`, `article_entities`, `intelligence.entity_relationships` |
| **T1.3** | **Entity dossier schema + basic compilation** — Add `entity_dossiers` (and optionally `entity_positions`) in `intelligence` schema; chronicle builder that aggregates article/storyline mentions for a canonical entity; one API to “get dossier” for an entity. | Builds on T1.2; one high-value output (dossier view) that improves as resolution improves. | `entity_canonical`, `article_entities`, articles, storylines |

### Tier 2 — Depth (next)

| # | Task | Rationale | Existing hooks |
|---|------|------------|----------------|
| **T2.1** | **Event chronicle builder** — For each tracked_event, maintain event_chronicles (developments, analysis, momentum_score); link to storylines/chronological_events; weekly or on_change updates. | Makes event tracking actually “live”; reuses existing narrative/event data. | tracked_events, storylines, chronological_events |
| **T2.2** | **Dossier intelligence layer** — Position tracker (voting records, policy positions, public statements as structured records); relationship web (associates, donors) using entity_relationships; pattern/controversy fields in dossier JSONB. | Turns dossiers into research-grade profiles; uses existing entity_relationships. | entity_dossiers, entity_positions, intelligence.entity_relationships |
| **T2.3** | **Governance/orchestrator cycle alignment** — 30–60 min cycle; phases: assessment → prioritization → deep_processing → quality_review → synthesis; config in snake_case (`orchestrator_governance.yaml` or extend existing); prioritization uses watchlist + active_events + resource availability. | Ties event + entity work into one loop; matches OrchestratorCoordinator / ORCHESTRATOR_ROADMAP. | OrchestratorCoordinator, ProcessingGovernor, watchlist |

### Tier 3 — Documents and narrative (later)

| # | Task | Rationale | Existing hooks |
|---|------|------------|----------------|
| **T3.1** | **Document acquisition pipeline** — Document sources config (government, think tanks, etc.); store metadata + URL in `processed_documents`; no heavy PDF parsing yet. | Lightweight “ingest” so we can attach documents to narratives later. | New table(s) in intelligence or public |
| **T3.2** | **Document processing engine** — PDF parsing (GPU where needed), section extraction, key findings, entity/topic tagging; fill `processed_documents` and link to storylines/entities. | High effort; do after T3.1 and when GPU pipeline is ready. | processed_documents, storylines, entity_canonical |
| **T3.3** | **Narrative construction** — Thread detection (causal chains, timeline reconciliation); synthesis engine (multi-source, conflict resolution); quality checks (fact verification, completeness). | Builds on entities, events, and documents; do after T2 and T3.1–T3.2. | narrative_threads, storylines, event_chronicles, entity_dossiers |

---

## 4. Schema additions (snake_case, aligned with existing)

### 4.1 Event tracking (T1.1, T2.1)

```sql
-- Optional: public or intelligence schema
CREATE TABLE IF NOT EXISTS intelligence.tracked_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,  -- election, legislation, investigation, etc.
    event_name VARCHAR(300) NOT NULL,
    start_date DATE,
    end_date DATE,
    geographic_scope VARCHAR(100),
    key_participant_entity_ids JSONB DEFAULT '[]',  -- [{domain, entity_id}, ...]
    milestones JSONB DEFAULT '[]',
    sub_event_ids INTEGER[],  -- self-ref or separate table if preferred
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intelligence.event_chronicles (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES intelligence.tracked_events(id) ON DELETE CASCADE,
    update_date DATE NOT NULL,
    developments JSONB DEFAULT '[]',
    analysis JSONB DEFAULT '{}',
    predictions JSONB DEFAULT '[]',
    momentum_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_event_chronicles_event ON intelligence.event_chronicles(event_id);
```

### 4.2 Entity dossiers (T1.3, T2.2)

```sql
-- intelligence schema (entity_id = entity_canonical id; domain_key identifies which domain’s entity_canonical)
CREATE TABLE IF NOT EXISTS intelligence.entity_dossiers (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,  -- references {domain_key}.entity_canonical(id)
    compilation_date DATE NOT NULL,
    chronicle_data JSONB DEFAULT '[]',
    relationships JSONB DEFAULT '[]',
    positions JSONB DEFAULT '[]',
    patterns JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain_key, entity_id)
);

CREATE TABLE IF NOT EXISTS intelligence.entity_positions (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    topic VARCHAR(255),
    position TEXT,
    confidence DECIMAL(3,2),
    evidence_refs JSONB DEFAULT '[]',
    date_range TSTZRANGE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_entity_positions_entity ON intelligence.entity_positions(domain_key, entity_id);
```

### 4.3 Entity relationships (extend existing)

`intelligence.entity_relationships` already has: source_domain, source_entity_id, target_domain, target_entity_id, relationship_type, confidence. Optionally add columns:

- `strength` DECIMAL(3,2)
- `evidence_refs` JSONB
- `temporal_data` JSONB

(Migration only; no new table.)

### 4.4 Document intelligence (T3.1–T3.2)

```sql
CREATE TABLE IF NOT EXISTS intelligence.processed_documents (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50),
    source_url TEXT,
    publication_date DATE,
    authors TEXT[],
    document_type VARCHAR(50),
    extracted_sections JSONB DEFAULT '[]',
    key_findings JSONB DEFAULT '[]',
    entities_mentioned JSONB DEFAULT '[]',
    citations JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intelligence.document_intelligence (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES intelligence.processed_documents(id) ON DELETE CASCADE,
    storyline_connections JSONB DEFAULT '[]',
    contradicts_document_ids INTEGER[] DEFAULT '{}',
    supports_document_ids INTEGER[] DEFAULT '{}',
    credibility_score DECIMAL(3,2),
    impact_assessment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. Config and governance loop (snake_case)

Use or extend `api/config/orchestrator_governance.yaml` (or a dedicated `api/config/quality_first_governance.yaml`):

```yaml
# quality_first_governance.yaml — all keys snake_case
orchestrator_cycle:
  duration_minutes: 45
  phases:
    - assessment
    - prioritization
    - deep_processing
    - quality_review
    - synthesis

processing_priorities:
  critical:
    - watched_entities
    - active_events
    - new_authoritative_documents
  high:
    - entity_relationship_updates
    - event_milestone_tracking
    - document_cross_referencing
  medium:
    - historical_pattern_analysis
    - narrative_gap_filling
    - archive_processing
  low:
    - speculative_connections
    - distant_historical_parallels
    - style_improvements

entity_tracking:
  politician_list: []        # optional; from watchlist or config
  organization_list: []
  tracking_depth: summary    # summary | comprehensive

event_tracking:
  active_events: []
  update_frequency: weekly   # daily | weekly | on_change

document_sources:
  source_priorities: []
  document_types: []        # reports, analysis, books

quality_thresholds:
  min_source_corroboration: 2
  required_evidence_depth: high
  narrative_completeness: 0.8
```

---

## 6. API surface (flat /api, snake_case)

| Area | Method | Path (pattern) |
|------|--------|----------------|
| Event tracking | GET/POST/PUT | `/api/system_monitoring/tracked_events`, `/api/system_monitoring/tracked_events/{event_id}` |
| Event chronicles | GET/POST | `/api/system_monitoring/tracked_events/{event_id}/chronicles` |
| Entity dossiers | GET | `/api/{domain}/entity_dossiers/{entity_id}` or `/api/intelligence/entity_dossiers?domain_key=&entity_id=` |
| Entity positions | GET | `/api/intelligence/entity_positions?domain_key=&entity_id=` |
| Document pipeline | POST/GET | `/api/intelligence/processed_documents`, `/api/intelligence/processed_documents/{id}` |

(Exact prefix can be `api/intelligence` or `api/system_monitoring` per your router layout; keep paths snake_case.)

---

## 7. Implementation order (targeted to-do)

**Phase 1 (get most done early)**  
1. **T1.1** — Event tracking framework (tables + CRUD + minimal UI).  
2. **T1.2** — Entity resolution enhancements (disambiguation, alias tracking, cross-domain linking).  
3. **T1.3** — Entity dossier schema + basic chronicle compilation + “get dossier” API.

**Phase 2**  
4. **T2.1** — Event chronicle builder (link to storylines/events; update on schedule).  
5. **T2.2** — Dossier intelligence (positions, relationship web, patterns in dossier).  
6. **T2.3** — Governance/orchestrator cycle alignment (config + loop phases).

**Phase 3**  
7. **T3.1** — Document acquisition (sources + metadata storage).  
8. **T3.2** — Document processing (PDF extraction, entity/topic tagging).  
9. **T3.3** — Narrative construction (thread detection, synthesis, quality checks).

---

## 8. Success metrics (unchanged intent)

- **Quantitative:** 95% entity resolution accuracy; 90% of tracked events with weekly updates; 100+ documents/week when pipeline active; &lt;5% factual errors in narratives.  
- **Qualitative:** Dossiers give a complete picture; event tracking captures major developments; document insights connect to narratives; summaries are publication-quality.

---

## 9. Design decisions (unchanged)

1. **Batch over stream** — Thoughtful batches, not reactive streams.  
2. **Depth over breadth** — Fully understand fewer things.  
3. **Evidence over speed** — Every claim traceable to source.  
4. **Context over isolation** — Everything connects to larger narratives.  
5. **Quality over quantity** — One good insight over 100 articles.

---

*This plan is the single v6 quality-first reference. Align all new code with [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md). Reuse existing entity, storyline, and intelligence schemas before adding new tables.*
