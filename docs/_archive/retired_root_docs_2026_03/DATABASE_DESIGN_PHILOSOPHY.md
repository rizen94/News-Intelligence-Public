# Database Design Philosophy

The database is not a metadata store. It's an intelligence repository. The JSONB editorial fields are the core product, not optional extras.

---

## Core Principle: Editorial Documents Are the Product

The database stores two kinds of data:

1. **Raw material** — article content, RSS feed metadata, processing status
2. **Intelligence product** — editorial documents, event briefings, entity profiles, claims

Category 2 is what users consume. Category 1 is what the pipeline processes. The pipeline exists to transform raw material into intelligence products.

---

## Schema Architecture

### Domain schemas (politics, finance, science_tech)

Each domain schema contains the domain's articles, storylines, and supporting tables.

**`{domain}.articles`** — Raw material + ML enrichment

| Column group | Key columns | Role |
|-------------|------------|------|
| Raw content | `content`, `title`, `excerpt`, `url` | Source material (Principle 1: Content is King) |
| ML enrichment | `ml_data` (JSONB), `summary`, `quality_score`, `sentiment_label` | Extracted intelligence (Principle 2: Intelligence Accumulates) |
| Structured extraction | `entities` (JSONB), `topics` (JSONB), `keywords` (JSONB), `categories` (JSONB) | Queryable intelligence |
| Processing metadata | `processing_status`, `processing_stage` | Pipeline tracking |
| Analysis | `analysis_results` (JSONB) | Accumulated analysis outputs |

**`{domain}.storylines`** — Intelligence product

| Column group | Key columns | Role |
|-------------|------------|------|
| Identity | `title`, `description`, `summary` | Basic identification |
| Editorial (PRIMARY) | `editorial_document` (JSONB), `document_version`, `document_status`, `last_refinement` | The narrative product |
| Intelligence | `key_entities` (JSONB), `timeline_events` (JSONB), `topic_clusters` (JSONB), `sentiment_trends` (JSONB) | Accumulated intelligence |
| Quality | `quality_score`, `completeness_score`, `coherence_score` | Quality metrics |
| Analysis | `analysis_results` (JSONB) | Analysis outputs |

### Intelligence schema

Cross-domain intelligence that connects articles, entities, events, and claims.

**`intelligence.tracked_events`** — Intelligence product

| Column group | Key columns | Role |
|-------------|------------|------|
| Identity | `event_name`, `event_type`, `start_date`, `end_date` | Basic identification |
| Editorial (PRIMARY) | `editorial_briefing` (TEXT), `editorial_briefing_json` (JSONB), `briefing_version`, `briefing_status` | The event briefing product |
| Structure | `key_participant_entity_ids` (JSONB), `milestones` (JSONB), `sub_event_ids` | Event structure |
| Scope | `domain_keys` (TEXT[]), `geographic_scope` | Cross-domain scope |

**`intelligence.event_chronicles`** — Accumulated event history

| Column | Type | Role |
|--------|------|------|
| `developments` | TEXT | What happened (narrative) |
| `analysis` | TEXT | Why it matters (narrative) |
| `predictions` | TEXT | What's next (narrative) |
| `momentum_score` | DECIMAL | Quantified momentum |

Chronicles accumulate over time. Each entry represents a point-in-time update. Never delete old chronicles.

**`intelligence.entity_profiles`** — Intelligence product

| Column group | Key columns | Role |
|-------------|------------|------|
| Identity | `domain_key`, `canonical_entity_id`, `compilation_date` | Identification |
| Content (PRIMARY) | `sections` (JSONB), `relationships_summary` (JSONB) | The entity dossier |
| Metadata | `metadata` (JSONB) | Supporting data |

**`intelligence.contexts`** — Canonical content units

| Column | Type | Role |
|--------|------|------|
| `content` | TEXT | Preserved article content |
| `raw_content` | TEXT | Original unprocessed content |
| `title` | TEXT | Content title |
| `domain_key` | VARCHAR | Source domain |

Contexts are the bridge between domain articles and intelligence extraction. They preserve content for downstream use by claim extraction, event tracking, and entity profiling.

**`intelligence.extracted_claims`** — Structured facts

Claims are subject-predicate-object triples extracted from contexts. They reference source contexts, preserving provenance.

---

## The editorial_document JSONB Structure

The `editorial_document` column on storylines is the primary narrative output. Its intended structure:

```json
{
  "lede": "One-sentence summary of the most important development",
  "developments": [
    "Development 1: what happened",
    "Development 2: what happened"
  ],
  "analysis": "Why these developments matter — context, implications, connections",
  "outlook": "What to watch for next — upcoming events, expected developments",
  "key_entities": ["Entity 1", "Entity 2"],
  "sources": ["Source 1", "Source 2"],
  "generated_at": "2026-03-06T14:30:00Z",
  "based_on_articles": [101, 102, 103]
}
```

This document is refined over time as new articles are added to the storyline. Each refinement increments `document_version` and updates `last_refinement`.

---

## The editorial_briefing_json JSONB Structure

The `editorial_briefing_json` column on tracked events stores the event briefing:

```json
{
  "headline": "Short headline summarizing the event",
  "summary": "2-3 sentence overview of the event and its significance",
  "chronology": [
    {"date": "2026-03-01", "development": "What happened"},
    {"date": "2026-03-04", "development": "What happened next"}
  ],
  "impact": "Assessment of the event's impact on relevant domains",
  "what_next": "What to watch for — upcoming dates, decisions, developments",
  "key_participants": ["Entity 1", "Entity 2"],
  "domain_relevance": {
    "finance": "Impact on markets...",
    "politics": "Policy implications..."
  }
}
```

The `editorial_briefing` TEXT column stores a plain-text version for simple display.

---

## The entity_profiles sections JSONB Structure

The `sections` column on entity profiles stores the entity dossier:

```json
[
  {
    "section_type": "overview",
    "content": "Who this entity is and why they matter..."
  },
  {
    "section_type": "recent_activity",
    "content": "Recent mentions and developments involving this entity..."
  },
  {
    "section_type": "connections",
    "content": "Key relationships and organizational affiliations..."
  }
]
```

The `relationships_summary` JSONB stores structured relationship data between entities.

---

## ml_data JSONB Structure (on articles)

The `ml_data` column stores ML pipeline outputs:

```json
{
  "content_analysis": {
    "cleaning_result": { ... },
    "metadata": { ... },
    "content_hash": "..."
  },
  "quality_score": {
    "overall_score": 0.75,
    "grade": "B",
    "dimensions": { ... }
  },
  "ml_processing": {
    "summary": { "success": true, "summary": "..." },
    "key_points": { "success": true, "key_points": [...] },
    "sentiment": { "success": true, "sentiment": {...} },
    "argument_analysis": { "success": true, "arguments": [...] },
    "processed_at": "2026-03-06T14:30:00Z"
  },
  "processed_at": "2026-03-06T14:30:00Z"
}
```

This data is the intermediate intelligence between raw article content and editorial documents. It must be preserved across pipeline runs.

---

## Design Rules

### 1. JSONB editorial fields are NOT optional

`editorial_document`, `editorial_briefing_json`, and `sections` are the reason the system exists. They must be:
- Populated by the automation pipeline
- Returned by API endpoints
- Displayed prominently in the UI
- Refined over time, not regenerated from scratch

### 2. Article content must be preserved in queryable form

The `content` column is never cleared after processing. The `summary` column and `ml_data.ml_processing.summary` provide processed versions, but the original is always accessible.

### 3. Intelligence accumulates in editorial documents

New articles added to a storyline should trigger refinement of its `editorial_document`, not regeneration. The `document_version` increments; `refinement_triggers` tracks what caused the update.

### 4. Chronicles are append-only

`intelligence.event_chronicles` entries are never deleted or overwritten. Each represents a point-in-time snapshot. The full chronicle history tells the event's story over time.

### 5. Cross-schema references use domain_key

Tables in the `intelligence` schema reference domain tables via `domain_key` (e.g., `"politics"`), not schema-qualified names. The application resolves `domain_key` → `schema_name` via the `domains` table.

---

## Common Mistakes

| Mistake | Why it's wrong | Correct approach |
|---------|---------------|-----------------|
| Treating `editorial_document` as optional metadata | It's the primary intelligence product | Populate it in the pipeline; return it in APIs |
| Storing intelligence only in `ml_data` | `ml_data` is intermediate; editorial documents are the product | Use `ml_data` as input to generate editorial documents |
| Querying `COUNT(*)` for user-facing content | Counts are metadata, not intelligence | Query editorial fields, summaries, and headlines |
| Overwriting `ml_data` on reprocessing | Loses accumulated intelligence | Merge new results with existing |
| Deleting event chronicles | Destroys historical narrative | Only append new chronicles |
| Storing narrative in plain text only | Loses structure for programmatic use | Use JSONB with structured fields + optional TEXT for display |
