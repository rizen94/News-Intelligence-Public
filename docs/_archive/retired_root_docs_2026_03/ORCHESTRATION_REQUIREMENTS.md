# Orchestration Requirements

Requirements for the automation pipeline to ensure content is preserved and intelligence accumulates through each phase.

See `../../DATA_FLOW_ARCHITECTURE.md` for the full cascade and `./CORE_ARCHITECTURE_PRINCIPLES.md` for the principles.

---

## Pipeline Overview

The automation pipeline runs in numbered phases (0–99) via `api/services/automation_manager.py`. Each phase processes data and passes results to downstream phases. The pipeline must enforce content preservation at every step.

---

## Phase Requirements

### Phase 1: Ingestion (rss_processing, context_sync, entity_profile_sync/build)

**rss_processing**
- MUST fetch full article text, not just RSS title + link
- MUST populate `articles.content` — if content is empty, log a warning
- Verification: after phase completes, `SELECT COUNT(*) FROM {schema}.articles WHERE content IS NULL AND created_at >= start_of_run` should be zero or near-zero

**context_sync**
- MUST copy article content into `intelligence.contexts`
- MUST link via `intelligence.article_to_context`
- Verification: `SELECT COUNT(*) FROM intelligence.contexts WHERE content IS NULL AND created_at >= start_of_run` should be zero

**entity_profile_sync / entity_profile_build**
- MUST build `sections` and `relationships_summary` from context content
- MUST NOT create profiles with empty `sections`
- Verification: `SELECT COUNT(*) FROM intelligence.entity_profiles WHERE sections = '[]' AND updated_at >= start_of_run` should decrease over time

### Phase 2: Intelligence Extraction (claim_extraction, event_tracking, event_coherence_review, pattern_recognition)

**claim_extraction**
- MUST extract from `contexts.content`, not metadata
- MUST reference source context_id for provenance
- Verification: `SELECT COUNT(*) FROM intelligence.extracted_claims WHERE created_at >= start_of_run` should be > 0 if new contexts exist

**event_tracking**
- MUST group contexts into events based on content similarity
- MUST create `event_chronicles` entries with `developments`, `analysis`, `predictions`
- Chronicles are append-only — MUST NOT delete existing chronicles
- Verification: new events or new chronicle entries for existing events

**event_coherence_review**
- MUST use LLM to verify context-event fit based on content
- MUST NOT assign contexts to events based on title matching alone

### Phase 3–4: ML Processing (ml_processing, entity_extraction, quality_scoring)

**ml_processing**
- MUST read `articles.content` and produce `ml_data` with: summary, key_points, sentiment, argument_analysis
- MUST MERGE with existing `ml_data`, not overwrite
- Verification: `SELECT COUNT(*) FROM {schema}.articles WHERE ml_data IS NOT NULL AND created_at >= start_of_run` should increase

**entity_extraction**
- MUST extract from article content, not just titles
- MUST populate `article_entities` and `articles.entities` (JSONB)
- Verification: entities extracted should include people, organizations, locations

**quality_scoring**
- MUST assess based on content quality (length, readability, sourcing), not just metadata
- MUST populate `articles.quality_score`

### Phase 5–6: Topic & Storyline Processing

**topic_clustering**
- MUST use content-derived features (from ml_data), not just titles
- MUST populate `topic_clusters` and link articles

**storyline_processing / storyline_automation**
- MUST work with article summaries and entities, not just counts
- Storyline discovery should find articles whose content is related, not just whose titles match

### Phase 7–9: Intelligence Synthesis (CRITICAL GAP)

These phases currently exist but do NOT populate editorial documents:

**MISSING: editorial_document generation**
- For each active storyline with linked articles:
  - Read article summaries (from `ml_data.ml_processing.summary`) and key entities
  - If `editorial_document` is empty or stale: generate via LLM
  - If `editorial_document` exists: refine with new article data
  - Increment `document_version`, set `document_status` to 'draft' or 'refined'
  - Update `last_refinement`

**MISSING: editorial_briefing generation**
- For each tracked event with chronicles:
  - Read event chronicles (developments, analysis, predictions)
  - If `editorial_briefing` is empty: generate via LLM
  - If it exists: refine with latest chronicle
  - Increment `briefing_version`, update `last_briefing_update`

These two phases are the critical link that transforms accumulated intelligence into user-facing editorial content.

### Phase 11: Digest Generation

**digest_generation**
- SHOULD draw from `editorial_document` and `editorial_briefing` when populated
- SHOULD NOT regenerate narratives from scratch if editorial documents exist
- Falls back to headlines + counts only when editorial fields are empty

### Phase 12: Watchlist Alerts

**watchlist_alerts**
- Alert content should include narrative context, not just "storyline updated"
- SHOULD include excerpt from `editorial_document.lede` or latest development

---

## Health Checks: Content Preservation Verification

Each pipeline run should produce a content health report. These checks verify that intelligence is accumulating, not being lost.

### After ingestion (phase 1)

```sql
-- Articles with content
SELECT
  COUNT(*) FILTER (WHERE content IS NOT NULL AND TRIM(content) != '') as with_content,
  COUNT(*) FILTER (WHERE content IS NULL OR TRIM(content) = '') as without_content
FROM {schema}.articles
WHERE created_at >= :run_start;

-- Contexts with content
SELECT COUNT(*) FILTER (WHERE content IS NOT NULL) as with_content,
       COUNT(*) FILTER (WHERE content IS NULL) as without_content
FROM intelligence.contexts
WHERE created_at >= :run_start;
```

### After ML processing (phases 3–4)

```sql
-- Articles with ML data populated
SELECT
  COUNT(*) FILTER (WHERE ml_data IS NOT NULL) as with_ml,
  COUNT(*) FILTER (WHERE ml_data IS NULL) as without_ml,
  COUNT(*) FILTER (WHERE summary IS NOT NULL) as with_summary,
  COUNT(*) FILTER (WHERE entities != '{}') as with_entities
FROM {schema}.articles
WHERE created_at >= :run_start;
```

### After intelligence extraction (phase 2)

```sql
-- Claims extracted
SELECT COUNT(*) FROM intelligence.extracted_claims WHERE created_at >= :run_start;

-- Events with chronicles
SELECT
  COUNT(DISTINCT te.id) as events_with_chronicles
FROM intelligence.tracked_events te
JOIN intelligence.event_chronicles ec ON ec.event_id = te.id
WHERE ec.created_at >= :run_start;
```

### After editorial generation (when implemented)

```sql
-- Storylines with editorial documents
SELECT
  COUNT(*) FILTER (WHERE editorial_document != '{}' AND editorial_document IS NOT NULL) as with_editorial,
  COUNT(*) FILTER (WHERE editorial_document = '{}' OR editorial_document IS NULL) as without_editorial
FROM {schema}.storylines
WHERE status = 'active';

-- Events with editorial briefings
SELECT
  COUNT(*) FILTER (WHERE editorial_briefing IS NOT NULL) as with_briefing,
  COUNT(*) FILTER (WHERE editorial_briefing IS NULL) as without_briefing
FROM intelligence.tracked_events;
```

---

## Pipeline Phase Checklist

Before adding a new pipeline phase or modifying an existing one:

- [ ] Does the phase read from content fields (not just metadata)?
- [ ] Does the phase WRITE enriched data (not just status flags)?
- [ ] Does the phase PRESERVE existing intelligence (merge, not overwrite)?
- [ ] Is there a health check query that verifies the phase's output?
- [ ] Does the phase fail gracefully if content is missing (log warning, skip, don't crash)?

---

## Common Mistakes

| Mistake | Why it's wrong | Correct approach |
|---------|---------------|-----------------|
| Pipeline phase updates `processing_status` but nothing else | Status flags are not intelligence | Phase must write enriched data to content fields |
| Overwriting `ml_data` with new run results | Loses prior intelligence | Merge: `existing_ml_data.update(new_results)` |
| Deleting event chronicles to "clean up" | Destroys accumulated narrative | Chronicles are append-only |
| Skipping articles with empty content | Hides the problem | Log warning, track content coverage metrics |
| Not verifying output after phase runs | No way to detect content loss | Run health check queries after each phase |
| Generating editorial from scratch on every run | Wastes LLM calls, loses refinement history | Check existing, refine if stale, generate only if empty |

---

## Priority: Closing the Editorial Gap

The highest-priority pipeline work is adding the two missing phases:

1. **`editorial_document_generation`** — Storyline editorial document generation/refinement
2. **`editorial_briefing_generation`** — Event editorial briefing generation/refinement

Until these exist, all user-facing outputs (briefings, reports, dashboards) are limited to headlines + counts + optional LLM lead. With them, the system transforms from "counts articles" to "understands events."

### Implementation sketch for editorial_document_generation

```python
async def run_editorial_document_generation(domain: str):
    """Generate or refine editorial_document for active storylines."""
    conn = get_db_connection()
    schema = get_schema_for_domain(conn, domain)
    
    # Find storylines needing editorial work
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT s.id, s.title, s.editorial_document, s.document_version,
               s.last_refinement, s.updated_at
        FROM {schema}.storylines s
        WHERE s.status = 'active'
          AND (s.editorial_document = '{{}}'
               OR s.editorial_document IS NULL
               OR s.updated_at > s.last_refinement)
        ORDER BY s.updated_at DESC
        LIMIT 10
    """)
    
    for storyline in cursor.fetchall():
        sid, title, existing_doc, version, last_refined, updated = storyline
        
        # Gather content for this storyline
        cursor.execute(f"""
            SELECT a.title, a.summary, a.sentiment_label
            FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE sa.storyline_id = %s AND a.summary IS NOT NULL
            ORDER BY a.published_at DESC LIMIT 8
        """, [sid])
        articles = cursor.fetchall()
        
        if not articles:
            continue
        
        # Build or refine
        if not existing_doc or existing_doc == {}:
            editorial = await generate_new_editorial(title, articles)
        else:
            editorial = await refine_editorial(existing_doc, articles, last_refined)
        
        # Save
        cursor.execute(f"""
            UPDATE {schema}.storylines
            SET editorial_document = %s,
                document_version = COALESCE(document_version, 0) + 1,
                document_status = 'refined',
                last_refinement = NOW()
            WHERE id = %s
        """, [json.dumps(editorial), sid])
    
    conn.commit()
```
