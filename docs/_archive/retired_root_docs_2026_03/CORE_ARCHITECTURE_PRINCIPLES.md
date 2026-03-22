# Core Architecture Principles

These principles define what the News Intelligence System IS. Every feature, service, and endpoint must align with them. Violating these principles produces a system that counts articles instead of understanding events.

---

## Principle 1: Content is King

**Every article's actual text content must be preserved, extracted, and made queryable throughout the pipeline.**

Articles are not metadata objects. They are intelligence sources. The `content` column on `{domain}.articles` is the raw material from which all intelligence derives. If content is lost, ignored, or reduced to counts, the system has no intelligence to offer.

### What this means in practice

- The ML pipeline must extract structured intelligence from article content (summary, key points, entities, sentiment) into `ml_data` and `analysis_results`
- `intelligence.contexts` must preserve article content via `article_to_context` linking
- Queries that surface articles to users must include content or content derivatives (summary, key points), not just title + URL

### What violates this principle

```python
# WRONG: querying metadata only
cursor.execute("SELECT COUNT(*), AVG(quality_score) FROM politics.articles WHERE created_at >= %s", [start])

# RIGHT: querying content-derived intelligence
cursor.execute("""
    SELECT title, summary, sentiment_label, entities, quality_score
    FROM politics.articles
    WHERE created_at >= %s AND content IS NOT NULL
    ORDER BY quality_score DESC LIMIT 10
""", [start])
```

### Verification checklist

- [ ] Does every article ingested have its `content` column populated?
- [ ] Does the ML pipeline run on content (not just title)?
- [ ] Are `ml_data` fields (summary, key_points, sentiment, argument_analysis) populated after processing?
- [ ] Can a user reach the full content of any article through the UI?

---

## Principle 2: Intelligence Accumulates

**Each processing step must ADD intelligence, never lose it.**

The pipeline is an intelligence cascade. Each stage enriches the data:

```
article.content
  → ml_data (summary, key_points, sentiment, argument_analysis)
  → entities (people, orgs, locations extracted)
  → intelligence.contexts (canonical content units)
  → intelligence.extracted_claims (subject-predicate-object facts)
  → intelligence.tracked_events (grouped, with chronicles)
  → {domain}.storylines (editorial_document, timeline, narrative)
```

At every step, the original content and all prior enrichments must remain accessible. Intelligence only flows forward and accumulates.

### What this means in practice

- `ml_data` is populated by the ML pipeline and never overwritten with less data
- `intelligence.contexts` links back to source articles; content is preserved, not replaced
- `intelligence.extracted_claims` references source contexts; claims add to the evidence base
- `tracked_events` gain chronicles over time (developments, analysis, predictions); old chronicles are never deleted
- `storylines.editorial_document` is refined, not regenerated from scratch

### What violates this principle

```python
# WRONG: overwriting accumulated intelligence
article['ml_data'] = {"processed_at": now}  # loses summary, key_points, sentiment

# RIGHT: merging new intelligence with existing
existing_ml_data = article.get('ml_data') or {}
existing_ml_data.update({"new_field": new_value, "processed_at": now})
```

```python
# WRONG: deleting old chronicles when adding new ones
cursor.execute("DELETE FROM intelligence.event_chronicles WHERE event_id = %s", [event_id])

# RIGHT: adding a new chronicle entry
cursor.execute("INSERT INTO intelligence.event_chronicles (event_id, developments, analysis) VALUES (%s, %s, %s)",
               [event_id, new_developments, new_analysis])
```

### Verification checklist

- [ ] After each pipeline phase, does the data have MORE intelligence than before?
- [ ] Are prior enrichments preserved when new processing runs?
- [ ] Can you trace from any intelligence output back to its source article content?
- [ ] Do event chronicles accumulate over time?

---

## Principle 3: Narratives Over Metrics

**User-facing outputs must tell stories about what happened, not statistics about articles.**

Users come to understand events, not to review database statistics. Every API response, briefing, and UI view should answer "what happened and why it matters" before (or instead of) "how many articles were processed."

### What this means in practice

- Daily briefings lead with headlines and storyline developments, not article counts
- Storyline views show editorial narratives, not processing metadata
- Event views show chronological developments, not entity count summaries
- The UI hierarchy: narrative first, supporting metrics second

### What violates this principle

```
WRONG output:                           RIGHT output:
"23 articles processed"            →    "Fed signals rate pause as inflation cools"
"Average quality: 0.72"            →    "Three banks report exposure to commercial real estate"
"4 breaking stories"               →    "Tech regulation bill gains momentum in Senate"
"5 categories detected"            →    "Key developments: [actual headline text]"
```

```python
# WRONG: returning counts as primary content
return {"content": f"System processed {count} articles with {quality} avg quality"}

# RIGHT: returning narrative as primary content
return {"content": f"Key developments: {headlines[0]['title']}. Leading storylines: {storylines[0]['title']}",
        "supporting_data": {"article_count": count, "quality_score": quality}}
```

### Verification checklist

- [ ] Does the API response start with narrative content, not counts?
- [ ] Could a non-technical user understand the output without knowing database schema?
- [ ] Is "what happened" answered before "how much was processed"?
- [ ] Are article counts relegated to supporting data, not the lead?

---

## Principle 4: Editorial Documents are Primary

**The `editorial_document`, `editorial_briefing`, and `sections` fields are the PRIMARY outputs of the intelligence pipeline, not optional features.**

These JSONB fields are where accumulated intelligence becomes usable:

| Table | Field | Purpose |
|-------|-------|---------|
| `{domain}.storylines` | `editorial_document` | The narrative summary of the storyline: lede, developments, analysis, outlook |
| `intelligence.tracked_events` | `editorial_briefing` / `editorial_briefing_json` | The event briefing: what happened, chronology, impact |
| `intelligence.entity_profiles` | `sections`, `relationships_summary` | The entity dossier: who they are, what they've done, connections |

These fields exist in the schema (migration 158 for editorial documents/briefings, migration 143 for entity profiles). They are the culmination of the intelligence cascade.

### What this means in practice

- The automation pipeline must include phases that POPULATE these fields
- API endpoints for storylines, events, and entities must RETURN these fields
- The UI must DISPLAY editorial content prominently
- Briefings should DRAW FROM editorial documents, not regenerate narratives from scratch

### Current gap (as of v5.0)

- `editorial_document` columns exist on storylines but are **not selected by `get_domain_storyline`**
- `editorial_briefing` columns exist on tracked_events but are **not included in `_EVENT_COLS`**
- No automation phase currently writes to `editorial_document` or `editorial_briefing`
- These fields are empty in production — they must be populated

### What violates this principle

```python
# WRONG: ignoring editorial fields when they exist
cursor.execute("SELECT id, title, status FROM storylines WHERE id = %s", [sid])

# RIGHT: including editorial documents
cursor.execute("""
    SELECT id, title, status, editorial_document, document_version, document_status
    FROM storylines WHERE id = %s
""", [sid])
```

```python
# WRONG: generating narratives from scratch every time
narrative = llm.generate("Summarize these 10 articles...")

# RIGHT: refining the existing editorial document
existing = storyline['editorial_document']
narrative = llm.refine(existing_document=existing, new_articles=new_articles)
```

### Verification checklist

- [ ] Are `editorial_document`, `editorial_briefing`, and `sections` populated for active records?
- [ ] Do API endpoints return these fields?
- [ ] Does the UI display editorial content, not just metadata?
- [ ] Is there an automation phase that generates/refines editorial documents?

---

## Common Mistakes

| Mistake | Why it's wrong | What to do instead |
|---------|---------------|-------------------|
| Building features that query `COUNT(*)` on articles | Produces metrics, not intelligence | Query content, entities, storylines |
| Generating summaries from titles only | Title is not the article; content is | Use `content`, `ml_data.summary`, `ml_data.key_points` |
| Treating `editorial_document` as "nice to have" | It's the primary output of the intelligence cascade | Populate it in the pipeline, return it in APIs |
| Overwriting `ml_data` on reprocessing | Loses accumulated intelligence | Merge new results with existing |
| Returning processing stats as "briefings" | Users want to know what happened, not how many rows changed | Lead with narrative, append metrics as support |
| Ignoring `intelligence.contexts` | They're the canonical content units that feed claims, events, profiles | Link articles to contexts; extract from contexts |

---

## How These Principles Connect

```
Principle 1: Content is King
    ↓ content is preserved and extracted
Principle 2: Intelligence Accumulates
    ↓ each step adds intelligence to editorial documents
Principle 4: Editorial Documents are Primary
    ↓ editorial documents are the source of truth for...
Principle 3: Narratives Over Metrics
    ↓ user-facing outputs tell stories, not statistics
```

If any principle is violated, all downstream principles fail. Content loss means no intelligence accumulation. No accumulation means empty editorial documents. Empty editorial documents mean metrics-only outputs.
