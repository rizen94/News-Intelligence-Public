# Persistent Editorial Content Strategy: Write Once, Refine Forever

**Purpose:** Define **living editorial documents** stored in the database that are created once and refined incrementally, instead of generating full narratives on demand. This reduces LLM cost, preserves narrative coherence, and lets documents compound in value over time.

**Related:** [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md), [NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md](NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md), [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md).

**Conventions:** snake_case for tables, columns, API paths. Storylines are per-domain (`{schema}.storylines`). Cross-cutting editorial tables live in `intelligence`; refinement log and dossiers reference existing orchestration/intelligence entities.

**Migration:** `api/database/migrations/158_persistent_editorial_documents.sql` adds the columns and tables below.

---

## 1. Living document architecture

```
Initial creation → Base document (stored) → Continuous refinement → Reader-ready
     (once)              (DB)                   (each trigger)        (always fresh)
```

**Core principle:** Every storyline, investigation, and major tracked event has a **canonical editorial document** in the database that is updated in place (section-level refinements) rather than regenerated.

| Benefit | How |
|--------|-----|
| **Cost efficiency** | Generate once; subsequent updates touch only 1–3 sections. |
| **Quality growth** | Each refinement adds information without discarding prior intelligence. |
| **Consistency** | Preserve voice, terminology, and narrative flow across updates. |
| **Speed** | Readers get pre-written content; no wait for generation. |
| **Audit trail** | Full version history and refinement log for learning and quality. |

---

## 2. Document types and structure

### 2.1 Storyline articles

**Storage:** Per-domain `storylines.editorial_document` (JSONB), plus version/status columns on `storylines`.

**Structure (sections):**

| Section | Purpose |
|---------|---------|
| **lede** | Essential story in 2–3 paragraphs. |
| **background** | How we got here. |
| **current_status** | Latest developments. |
| **key_players** | Entities and their roles. |
| **timeline** | Chronological narrative. |
| **analysis** | What it means. |
| **outlook** | What to watch for. |
| **sources** | Attribution and confidence. |

**Updates:** When new events/claims/contexts are added; refinement triggers update only the sections that need it (e.g. current_status + timeline).

**Existing hook:** Initial creation can use `NarrativeSynthesisService` / `DeepContentSynthesisService` output; refinement is a new path that merges into stored JSONB.

### 2.2 Investigation dossiers

**Storage:** `intelligence.investigation_dossiers` keyed by `investigation_id` (references `orchestration.investigations.id`).

**Structure (sections):**

| Section | Purpose |
|---------|---------|
| **executive_summary** | What we know / don’t know. |
| **hypothesis** | What we’re investigating. |
| **evidence_collection** | Organized findings. |
| **entity_profiles** | Deep dives on key players. |
| **pattern_analysis** | Connections and anomalies. |
| **open_questions** | Research directions. |
| **methodology** | How we’re investigating. |

**Updates:** As evidence and notes accumulate; section-level refinement only.

### 2.3 Event briefings

**Storage:** `intelligence.tracked_events.editorial_briefing` (TEXT or JSONB), plus version/status columns.

**Structure (sections):**

| Section | Purpose |
|---------|---------|
| **headline** | What happened. |
| **immediate_impact** | First-order effects. |
| **context** | Why this matters now. |
| **stakeholder_reactions** | Who’s saying what. |
| **market_policy_response** | Measurable changes. |
| **historical_parallels** | Similar past events. |
| **next_steps** | Expected developments. |

**Updates:** As the event moves through phases; link to `event_chronicles` for developments.

---

## 3. Refinement pipeline (incremental enhancement)

**Logic:**

```
Document exists?
├─ No → Generate complete document (one-time LLM call; store in DB)
└─ Yes → Refine existing document
         ├─ New information? → Update relevant sections only
         ├─ Conflicting info? → Add/update perspective / conflicting_reports section
         ├─ Time passed? → Update status / outlook
         └─ Quality feedback? → Revise specific claims or clarity
```

**Constraints:**

- **Max 2–3 sections per refinement** to keep updates coherent.
- **Preserve document voice** (terminology, style, paragraph shape).
- **Do not drop existing information**; add or revise in place.
- **Version every change** and log trigger + sections_updated.

---

## 4. Document state and metadata

**Lifecycle (document_status):**

| Status | Meaning |
|--------|---------|
| **draft** | First generation; not yet published. |
| **active** | Published; refinements applied. |
| **major_update** | Significant new information; optional human review. |
| **stable** | Minimal change expected; monitoring only. |
| **archived** | Story concluded; historical record. |

**Metadata (e.g. in JSONB or columns):**

```json
{
  "created_at": "ISO8601",
  "last_refined": "ISO8601",
  "refinement_count": 12,
  "sections_updated": { "current_status": "ISO8601", "timeline": "ISO8601" },
  "quality_score": 0.85,
  "completeness": { "lede": true, "background": true, "outlook": false },
  "feedback_incorporated": ["feedback_id_1", "feedback_id_2"]
}
```

---

## 5. Refinement triggers and rules

| Trigger | Refinement action (sections) |
|---------|-----------------------------|
| New event in storyline | Update **current_status**, **timeline** |
| New entity relationship | Update **key_players** |
| Market / policy reaction | Add to **analysis** or event **market_policy_response** |
| Time passage (e.g. 24h) | Update **outlook** if needed |
| Contradiction found | Add/update **conflicting_reports** or perspective section |
| User correction | Revise specific claim (targeted section) |
| Pattern detected | Enhance **analysis** |

Refinement service should: (1) determine which sections need updates from the trigger, (2) build a refinement prompt that includes existing document + new info + “preserve style,” (3) call LLM for only those sections, (4) merge result into stored document and bump version.

---

## 6. Storage schema design

**Storylines (per-domain):** Add columns to each domain’s `storylines` table (migration loops over `politics`, `finance`, `science_tech`):

```sql
-- Per-domain storylines (run in loop over domain schemas)
ALTER TABLE {schema}.storylines ADD COLUMN IF NOT EXISTS editorial_document JSONB DEFAULT '{}'::jsonb;
ALTER TABLE {schema}.storylines ADD COLUMN IF NOT EXISTS document_version INTEGER DEFAULT 0;
ALTER TABLE {schema}.storylines ADD COLUMN IF NOT EXISTS document_status TEXT DEFAULT 'draft';
ALTER TABLE {schema}.storylines ADD COLUMN IF NOT EXISTS last_refinement TIMESTAMPTZ;
ALTER TABLE {schema}.storylines ADD COLUMN IF NOT EXISTS refinement_triggers JSONB DEFAULT '[]'::jsonb;
```

**Investigation dossiers (intelligence schema):**

```sql
CREATE TABLE IF NOT EXISTS intelligence.investigation_dossiers (
    investigation_id INTEGER PRIMARY KEY REFERENCES orchestration.investigations(id) ON DELETE CASCADE,
    dossier_document JSONB NOT NULL DEFAULT '{}'::jsonb,
    document_version INTEGER DEFAULT 0,
    sections_updated JSONB DEFAULT '{}'::jsonb,
    quality_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_refined TIMESTAMPTZ
);
```

**Tracked events (intelligence schema):**

```sql
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS editorial_briefing TEXT;
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS editorial_briefing_json JSONB DEFAULT '{}'::jsonb;
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS briefing_version INTEGER DEFAULT 0;
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS briefing_status TEXT DEFAULT 'draft';
ALTER TABLE intelligence.tracked_events ADD COLUMN IF NOT EXISTS last_briefing_update TIMESTAMPTZ;
```

**Refinement log (intelligence schema):**

```sql
CREATE TABLE IF NOT EXISTS intelligence.document_refinements (
    refinement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type TEXT NOT NULL,   -- storyline, investigation, event
    domain_key TEXT,              -- for storylines
    document_id TEXT NOT NULL,    -- storyline_id, investigation_id, or event_id
    trigger_type TEXT NOT NULL,   -- new_event, entity_update, time_passage, user_feedback, etc.
    sections_updated TEXT[],
    refinement_prompt_snippet TEXT,
    before_version INTEGER,
    after_version INTEGER,
    quality_delta FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_document_refinements_doc ON intelligence.document_refinements(document_type, document_id);
CREATE INDEX IF NOT EXISTS idx_document_refinements_created ON intelligence.document_refinements(created_at DESC);
```

---

## 7. Refinement service design (conceptual)

```
DocumentRefinementService:

  async refine_storyline_document(domain_key, storyline_id, trigger):
    document = load_editorial_document(domain_key, storyline_id)  # from storylines.editorial_document
    if not document or document is empty:
      document = await generate_initial_document(domain_key, storyline_id)  # one-time full generation
      save_editorial_document(domain_key, storyline_id, document, version=1)
      return

    sections_to_update = analyze_update_needs(document, trigger)
    prompt = build_refinement_prompt(
      document=document,
      sections=sections_to_update,
      new_information=trigger.data,
      preserve_style=True
    )
    refined_sections = await llm.refine_sections(prompt)
    updated_document = merge_refinements(document, refined_sections)
    save_editorial_document(domain_key, storyline_id, updated_document, version++)
    log_refinement(document_type='storyline', document_id=storyline_id, trigger=trigger, sections=sections_to_update)
```

**Merge rules:** Replace only the requested sections; leave others unchanged. Preserve document-level metadata (e.g. quality_score, completeness) and update only last_refined and sections_updated.

---

## 8. Quality preservation

- **Style:** Keep terminology and voice consistent; reuse successful phrasing where possible.
- **Information:** Never remove existing content unless correcting an error (and log it).
- **Pacing:** Limit refinements per document per day; batch small updates; major rewrites require explicit trigger (e.g. user or “major_update” workflow).
- **Length:** Optional soft caps per section or total document to avoid drift.

---

## 9. Compound intelligence effect

Over time the same document gains depth without losing prior work:

| Time | Effect |
|------|--------|
| Week 1 | Base storyline article created. |
| Week 2 | Timeline and current_status enriched with new events. |
| Week 3 | Analysis deepened with pattern/context. |
| Month 2 | Multiple perspectives or conflicting_reports integrated. |
| Month 6 | Historical context and outlook refined; predictions validated. |
| Year 1 | Authoritative, long-lived document with full audit trail. |

---

## 10. API design for document access

**Get document (storyline example):**

```
GET /api/documents/storyline/{domain}/{id}
Response: {
  "document": { ... editorial_document sections ... },
  "metadata": {
    "version": 5,
    "document_status": "active",
    "quality_score": 0.82,
    "completeness": { "lede": true, "timeline": true, ... },
    "last_refined": "ISO8601",
    "refinement_count": 4
  },
  "available_formats": ["full", "brief", "mobile"],
  "refinement_available": true,
  "last_updated_sections": { "current_status": "ISO8601", "timeline": "ISO8601" }
}
```

**Request refinement:**

```
POST /api/documents/refine
Body: {
  "document_type": "storyline",
  "domain": "politics",
  "document_id": "42",
  "trigger": "new_events",
  "trigger_data": { "event_ids": [1, 2], "summary": "..." },
  "sections": ["current_status", "timeline"]   // optional; if omitted, service infers from trigger
}
```

**History:**

```
GET /api/documents/history/{document_type}/{domain?}/{id}
Response: {
  "versions": [
    { "version": 5, "timestamp": "ISO8601", "trigger_type": "new_events", "sections_changed": ["current_status", "timeline"] }
  ],
  "quality_trend": [ { "version": 4, "score": 0.78 }, { "version": 5, "score": 0.82 } ],
  "refinement_log": [ ... ]
}
```

Use the same pattern for `document_type`: `investigation` (document_id = investigation_id, no domain in path if global), `event` (document_id = event_id, optional domain or none).

---

## 11. Integration with editorial layer and report

- **Today’s Report:** Lead storylines can surface the **lede** (and optionally **outlook**) from `editorial_document` instead of calling narrative generation on each request; full document at `/api/documents/storyline/{domain}/{id}`.
- **Narrative arc / newsworthiness:** Editorial intelligence layer can set refinement priority (e.g. “developing” stories get current_status/outlook refined first).
- **Reader engagement:** If a document gets high engagement, refinement can prioritize it (e.g. next scheduled refinement includes analysis or key_players).
- **Existing synthesis:** First-time creation can call `DeepContentSynthesisService` or `NarrativeSynthesisService` and map their output into the canonical sectioned structure; subsequent updates go through `DocumentRefinementService` only.

This gives a single, persistent source of truth for “the story so far” and “what to watch,” with lower cost and higher consistency than full regeneration on every read.
