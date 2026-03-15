# RAG Enhancement Roadmap — Iterative Story Enhancement and Long-Term Tracking

This document captures a target architecture and phased plan to evolve the RAG system from **reactive query/on-demand enrichment** into a **proactive, iterative intelligence system** that continuously improves story understanding and alerts on significant developments.

**Related:** [RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md](RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md) for current implementation and rationale; [VECTOR_DATABASE_SCHEMA.md](VECTOR_DATABASE_SCHEMA.md) for versioned facts, entity relationships, and story-state vector collections (entity_profiles, versioned_facts, entity_relationships, story_states).

---

## 1. Current Strengths for These Goals

- **Storyline infrastructure** — Persistent storylines that can track topics over months/years
- **Entity extraction** — Basic entity identification (needs improvement)
- **External context** — Wikipedia and GDELT for entity/event enrichment
- **Domain separation** — Politics, finance, science-tech align with different story types

## 2. Key Gaps vs Vision

| Gap | Current | Target |
|-----|---------|--------|
| **Enhancement loop** | Mostly reactive (enrich on user query) | Proactive, continuous improvement of story understanding |
| **Entity resolution & profiling** | Extract entities but no persistent, evolving profiles | Entity profiles that accumulate facts, relationships, timeline; improve over time |
| **Historical state** | No “story evolution” | Track how understanding of a story has changed over time |
| **Watch & alert** | Discovery suggests articles; no story-type-specific “what to watch for” | Watch patterns (e.g. verdict, poll, hearing) and significance-triggered alerts |

---

## 3. Target Architecture

### 3.1 Core story and entity model

```python
# Conceptual — to be mapped to DB and services

class TrackedStory:
    id: str
    title: str                    # e.g. "The Donald Trump Presidency"
    type: StoryType               # PERSON_TENURE, ELECTION, ECONOMIC_EVENT, COURT_CASE, ...
    start_date: datetime
    end_date: Optional[datetime]

    primary_entities: List[EntityRef]
    secondary_entities: List[EntityRef]

    timeline_states: List[StoryState]   # How our understanding changed over time
    watch_patterns: List[WatchPattern] # What we're watching for
    maturity_score: float               # 0–1, how well we understand this story


class EntityProfile:
    id: str
    canonical_name: str
    aliases: List[str]
    entity_type: EntityType       # PERSON, ORGANIZATION, EVENT, PLACE

    facts: List[Fact]             # source, confidence, timestamp
    relationships: List[Relationship]
    timeline: List[Event]

    last_enriched: datetime
    enrichment_count: int
    confidence_score: float
```

### 3.2 Iterative enhancement pipeline

```python
class StoryEnhancementOrchestrator:
    """Continuously improves story and entity understanding"""

    def enhancement_loop(self):
        while True:
            stories = self.select_stories_for_enhancement()

            for story in stories:
                gaps = self.identify_knowledge_gaps(story)
                queries = self.generate_enhancement_queries(story, gaps)
                new_context = self.retrieve_from_sources(queries)
                facts = self.extract_facts(new_context)
                validated_facts = self.validate_against_existing(facts)
                self.update_profiles(story, validated_facts)

                if self.detect_significant_change(story):
                    self.trigger_alert(story)

            sleep(self.enhancement_interval)
```

### 3.3 Multi-stage (progressive) RAG

Instead of single-shot RAG, run **stages** so each story is enhanced step by step:

| Stage | Purpose |
|-------|--------|
| **entity_discovery** | NER + LLM to find entities; resolve to canonical; attach to story |
| **entity_enrichment** | For each under-enriched entity: Wikipedia, GDELT, domain context → synthesize profile |
| **relationship_mapping** | How entities relate (from text + LLM) |
| **timeline_construction** | When key events happened |
| **pattern_detection** | Recurring themes/patterns |
| **prediction_generation** | What might happen next (optional) |

Each stage can use different retrieval strategies and cache intermediate results.

### 3.4 Watch patterns (by story type)

Define what to watch for so new content can be matched and alerts raised:

- **Court case**: verdict, ruling, decision; entity actions (testify, appear); document types (filing, brief, motion); next hearing date
- **Election**: polls (for primary entities), events (debate, primary, convention), entity statements (announce, endorse)
- **Person tenure / economic event**: configurable keyword + entity-action patterns

Implementation: pattern types (keyword, entity-action, document, timeline) and a **WatchPatternEngine** that, given a story type and primary entities, creates concrete patterns and runs them against new content.

---

## 4. Phased Implementation Plan

### Phase 1: Enhanced entity system (Weeks 1–2)

1. Create **entity profile** tables with versioned facts (and, if needed, resolution table for canonical id).
2. Implement **entity resolution** — map name variations to canonical entities.
3. Add **LLM-based entity extraction** (and/or NER) to replace/augment regex in RAG base.
4. Build **entity enrichment pipeline** using existing Wikipedia/GDELT and domain knowledge.

**Phase 1 implementation (started):**
- **Migration 151** (`api/database/migrations/151_phase1_versioned_facts.sql`): `intelligence.versioned_facts` table (entity_profile_id, fact_type, fact_text, valid_from/valid_to, sources, superseded_by_id, extraction_method).
- **Entity resolution** (`api/services/entity_resolution_service.py`): `resolve_to_canonical(domain_key, entity_name, entity_type, create_if_missing=True)` → canonical_entity_id; used when storing article_entities.
- **Extraction wiring**: `ArticleEntityExtractionService` now resolves each extracted entity and sets `canonical_entity_id` on `article_entities`.
- **Enrichment pipeline** (`api/services/entity_enrichment_service.py`): `enrich_entity_profile(profile_id)` fetches Wikipedia summary, merges "Background (Wikipedia)" into `entity_profiles.sections`, inserts facts into `versioned_facts`; `run_enrichment_batch(limit)` for batch. API: `POST .../context_centric/run_entity_enrichment?limit=10`.

### Phase 2: Story state tracking (Weeks 3–4)

1. Add **story timeline / state** tables (e.g. storyline_states or story_timeline) to track understanding over time.
2. Implement **maturity scoring** — how complete is our understanding of this story?
3. **Knowledge gap detection** — what don’t we know yet? (feeds into enhancement queries.)
4. **Change detection** — when does a story’s state change enough to trigger an alert?

**Automated story state triggers (started):** When new facts are added to `intelligence.versioned_facts`, a DB trigger logs to `fact_change_log`; an application service resolves entity profiles to (domain, storyline_id) via `story_entity_index` and enqueues `story_update_queue`; a processor runs story state refresh (and later significance/alerts). See [STORY_STATE_UPDATE_TRIGGERS.md](STORY_STATE_UPDATE_TRIGGERS.md). Migration 152, `story_state_trigger_service`, API: `POST .../context_centric/run_story_state_triggers`.

**Phase 2 implementation (started):** Migration 153 adds `intelligence.storyline_states` (domain_key, storyline_id, version, state_summary, maturity_score, knowledge_gaps, significant_change, change_summary). `story_state_service` computes maturity (article count, entity index, recency), stub knowledge-gap detection, and change vs previous state; `story_state_trigger_service` calls it when processing the queue.

### Phase 3: Iterative enhancement (Weeks 5–6)

1. Build **enhancement orchestrator** that runs on a schedule (or from OrchestratorCoordinator).
2. Implement **staged RAG** with different strategies per stage (entity_discovery, entity_enrichment, etc.).
3. **Source priority** — which sources to use for which story types/entities.
4. **Enhancement scheduling** — by story importance, activity, and last-enhanced time.

**Phase 3 implementation (started):** **Enhancement orchestrator** (`api/services/enhancement_orchestrator_service.py`): `run_enhancement_cycle()` runs (1) story state triggers (fact_change_log → story_update_queue → storyline_states), (2) entity enrichment batch, (3) entity profile builder batch. **Scheduled tasks** in AutomationManager: `story_enhancement` (every 2h, full cycle), `entity_enrichment` (every 6h, enrichment only), `story_state_triggers` (every 30m, triggers only). API: `POST .../context_centric/run_enhancement_cycle`. Source priority and per-storyline enhancement scheduling remain configurable later (e.g. orchestrator_governance phases).

### Phase 4: Watch patterns and alerts (Weeks 7–8)

1. Define **watch pattern types** for story categories (court, election, tenure, etc.).
2. Implement **pattern matching** against new content (and, if needed, against enrichment output).
3. **Alert generation** with significance scoring.
4. **User notification** path for important updates (e.g. watchlist, email, or in-app).

**Phase 4 implementation (started):** **Migration 154** (`api/database/migrations/154_watch_patterns_phase4.sql`): `intelligence.watch_patterns` (domain_key, storyline_id, story_type, pattern_type, pattern_config) and `intelligence.pattern_matches` (domain_key, storyline_id, watch_pattern_id, content_ref_*, matched_text, significance_score, alert_created); `watchlist_alerts.alert_type` extended to include `pattern_match`. **Watch pattern service** (`api/services/watch_pattern_service.py`): default keyword sets by story_type (court_case, election, person_tenure, economic_event), `match_content(text, story_type)`, `run_pattern_matching(domain_key, storyline_id?, limit)` — resolves context→article→storyline(s), runs keyword matching, persists pattern_matches, creates watchlist_alerts when storyline is on watchlist and significance ≥ threshold. **Scheduled task**: `pattern_matching` (every 30m) in AutomationManager; **API**: `POST .../context_centric/run_pattern_matching` (optional `domain_key`, `limit`). Custom watch_patterns rows and entity-action/document patterns can be added later.

---

## 5. Concrete Changes to Current Codebase

1. **Data model**
   - Introduce **EntityProfile** (and related tables) and **WatchPattern** (and pattern match results).
   - Optionally use a **storyline_lookup_targets**-style table as a lightweight bridge until full entity profiles exist; roadmap is to evolve toward EntityProfile + WatchPattern as the source of truth.
   - For vector-backed entity/fact/relationship and story-state storage, see [VECTOR_DATABASE_SCHEMA.md](VECTOR_DATABASE_SCHEMA.md) (pgvector and/or ChromaDB, 768d, temporal versioning).

2. **StorylineAutomationService**
   - Extend to run **iterative enhancement stages**, not only discovery (e.g. call into entity_enrichment and timeline stages).
   - Maintain **story state history** (e.g. write to storyline_states when analysis or enhancement runs).
   - Track **entity profile maturity** (or “last enriched” / coverage) so the orchestrator knows what to enhance next.

3. **RAGService**
   - Support **multi-stage retrieval** (e.g. by stage: entity_discovery vs entity_enrichment vs timeline).
   - **Cache intermediate results** between stages (e.g. “what we’ve already looked up” and when).
   - Track **lookup history** (what was queried, when, which source) to avoid redundant pulls and to drive “what’s next.”

4. **OrchestratorCoordinator**
   - Add scheduled (or governor-driven) tasks, for example:
     - `story_enhancement` — run enhancement loop for selected storylines (e.g. every 2h).
     - `entity_enrichment` — run entity enrichment for under-enriched profiles (e.g. every 6h).
     - `pattern_matching` — run watch patterns against recent content (e.g. every 30m).

5. **Dashboard**
   - **Story maturity** view: story understanding score (0–100%), entity profile completeness, days since last significant update, and (if implemented) predicted next events/milestones.

---

## 6. Outcome

This roadmap turns the RAG system from a **reactive query and on-demand enrichment** tool into a **proactive intelligence layer** that:

- Continuously improves its understanding of tracked stories.
- Maintains evolving entity profiles and story states over time.
- Watches for story-type-specific signals and triggers alerts on significant developments.

Implementation can follow the phases above and align with [RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md](RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md) (e.g. domain-scoped retrieval, article embeddings, and lookup-target refresh) so that “what we look up” and “what we pull” are consistent with this architecture.
